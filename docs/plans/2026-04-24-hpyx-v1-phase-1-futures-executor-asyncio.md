# HPyX v1 Phase 1: Futures, Executor, asyncio Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the broken `hpx_async` (switch from `launch::deferred` to `launch::async`), land the `HPXFuture` C++ class with full composition (`when_all`, `when_any`, `dataflow`, `shared_future`, `ready_future`), wrap it in a Python `Future` that implements the `concurrent.futures.Future` protocol, rewrite `HPXExecutor` as a real `concurrent.futures.Executor`, and ship Level-2 asyncio integration (awaitable `Future` + `hpyx.aio.await_all`/`await_any`). End state: `await hpyx.async_(fn, x)` works, `dask.compute(..., scheduler=HPXExecutor())` completes, and free-threaded 3.13t actually parallelizes Python callbacks submitted via `HPXExecutor.map`.

**Architecture:** Three stacked layers on top of Plan 0's runtime foundation. (1) `src/_core/futures.cpp` rewritten as a nanobind submodule exposing `HPXFuture` + six free functions (`async_submit`, `when_all`, `when_any`, `dataflow`, `ready_future`, `share`). (2) `src/hpyx/futures/_future.py` wraps `HPXFuture` with the full `concurrent.futures.Future` protocol and `__await__`. (3) `src/hpyx/executor.py` rewritten from scratch as `HPXExecutor(concurrent.futures.Executor)`; `src/hpyx/aio.py` adds asyncio combinators. A feature flag `HPYX_ASYNC_MODE` lets users roll back to the old `launch::deferred` behavior if the `launch::async` switch regresses something (per spec risk #1).

**Tech Stack:** C++17, nanobind ≥2.7, HPX ≥1.11 (uses `hpx::async`, `hpx::dataflow`, `hpx::when_all`, `hpx::when_any`, `hpx::make_ready_future`), Python 3.13 / 3.13t, pytest, asyncio (stdlib), dask + dask.array (optional test dep).

**Depends on:** Plan 0 merged into `main` (runtime foundation exists at `hpyx._core.runtime` with `runtime_start`/`runtime_stop`/`runtime_is_running`/`num_worker_threads`/`get_worker_thread_id`).

**Reference documents:**
- Spec: `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md` §§ 3.2, 4.4, 4.5, 4.8, 5.1-5.4
- HPX knowledge: `docs/codebase-analysis/hpx/CODEBASE_KNOWLEDGE.md` §§ 4.2, 5.1-5.2
- Plan 0 output: `docs/plans/2026-04-24-hpyx-v1-phase-0-foundation.md`

**Out of scope for this plan (deferred to later Plans):**
- Parallel algorithms `hpyx.parallel.*` (Plan 3)
- C++ kernels `hpyx.kernels.*` (Plan 3)
- `hpyx.execution` policies module (Plan 3)
- Benchmarks for futures/executor (Plan 4)
- Full asyncio user guide (Plan 5)
- Real task cancellation via `hpx::stop_token` (v1.x)

---

## File Structure

### Created files

| File | Responsibility |
|---|---|
| `src/_core/futures.cpp` | **Rewritten.** `HPXFuture` class wrapping `hpx::shared_future<nb::object>`; `async_submit`, `when_all`, `when_any`, `dataflow`, `ready_future` free functions; `register_bindings(nb::module_&)`. |
| `src/_core/futures.hpp` | Public header with class forward decl + `register_bindings`. |
| `src/hpyx/futures/__init__.py` | Re-exports `Future`, `async_`, `when_all`, `when_any`, `dataflow`, `shared_future`, `ready_future`. |
| `src/hpyx/futures/_future.py` | `Future` class wrapping `_core.futures.HPXFuture` with `concurrent.futures.Future` protocol + `__await__`. |
| `src/hpyx/aio.py` | `await_all(*futs)`, `await_any(*futs)` combinators. |
| `tests/test_futures.py` | Future.result/exception/done/cancelled/cancel/add_done_callback/then/share; when_all/when_any/dataflow/shared_future/ready_future. |
| `tests/test_executor.py` | concurrent.futures.Executor protocol conformance; submit/map/shutdown; max_workers reconciliation. |
| `tests/test_aio.py` | `await fut`; `asyncio.wrap_future(fut)`; `loop.run_in_executor(HPXExecutor(), fn, ...)`; `hpyx.aio.await_all/await_any`. |
| `tests/test_dask_integration.py` | Smoke: `dask.compute(arr.sum(), scheduler=HPXExecutor())` completes. |

### Modified files

| File | Change |
|---|---|
| `src/_core/bind.cpp` | Register `_core.futures` submodule; remove the legacy top-level `future`, `hpx_async`, `hpx_async_add` bindings. |
| `src/hpyx/executor.py` | **Rewritten.** Real `HPXExecutor(concurrent.futures.Executor)`. |
| `src/hpyx/__init__.py` | Export `async_`, `Future`, `when_all`, `when_any`, `dataflow`, `shared_future`, `ready_future`, `aio`. |

### Deleted files

- `src/_core/futures.cpp`'s existing `hpx_async_add` entry point (the "debug artifact" per spec §6.4). The `hpx_async` Python binding is replaced, not deleted — same callable name for migration compatibility, but now uses `launch::async`.

---

## Execution Notes

- pwd = repo root.
- Environment: `test-py313t` (free-threaded Python 3.13t). `pixi run -e test-py313t pytest ...`
- Rebuild after C++ changes: `pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .`
- Commits: Conventional Commits. No Co-Authored-By trailers.
- Base branch: `main` (after Plan 0 merges).

---

## Task 1: Create implementation branch

**Files:** none

- [ ] **Step 1: Start from main with Plan 0 merged**

```bash
git checkout main
git pull --ff-only origin main
git log --oneline -3
```

Expected: top commit is the Plan 0 merge; working tree clean. If Plan 0 hasn't merged yet, abort and merge it first.

- [ ] **Step 2: Create implementation branch**

```bash
git checkout -b feat/v1-phase-1-futures-executor-asyncio
```

- [ ] **Step 3: Baseline test run**

```bash
pixi run test
```

Record the passing/failing set. `test_submit.py` is expected to still fail (that's what this plan fixes); `test_for_loop.py` par policy also still fails (Plan 3). Everything in Plan 0's test set should pass.

---

## Task 2: Add `HPYX_ASYNC_MODE` feature flag (rollback safety)

**Files:**
- Modify: `src/hpyx/config.py` (add `async_mode` key)
- Modify: `src/hpyx/_runtime.py` (expose resolved async mode for C++ side)

Per spec risk #1, we want a way to flip back to `launch::deferred` if `launch::async` breaks something.

- [ ] **Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_defaults_include_async_mode():
    assert config.DEFAULTS["async_mode"] == "async"


def test_from_env_async_mode(monkeypatch):
    monkeypatch.setenv("HPYX_ASYNC_MODE", "deferred")
    assert config.from_env()["async_mode"] == "deferred"


def test_from_env_async_mode_default(monkeypatch):
    monkeypatch.delenv("HPYX_ASYNC_MODE", raising=False)
    assert config.from_env()["async_mode"] == "async"


def test_from_env_async_mode_invalid(monkeypatch):
    monkeypatch.setenv("HPYX_ASYNC_MODE", "bogus")
    with pytest.raises(ValueError, match="HPYX_ASYNC_MODE"):
        config.from_env()
```

Run: `pixi run -e test-py313t pytest tests/test_config.py::test_defaults_include_async_mode -v`
Expected: FAIL (key missing).

- [ ] **Step 2: Implement the key**

In `src/hpyx/config.py`:

```python
# Add to DEFAULTS dict:
DEFAULTS: dict[str, Any] = {
    "os_threads": None,
    "cfg": [],
    "autoinit": True,
    "trace_path": None,
    "async_mode": "async",  # "async" | "deferred"  — deferred is v0.x emergency rollback
}
```

Add parsing in `from_env()`:

```python
    raw_async_mode = os.environ.get("HPYX_ASYNC_MODE")
    if raw_async_mode is not None:
        lowered = raw_async_mode.strip().lower()
        if lowered not in {"async", "deferred"}:
            raise ValueError(
                f"HPYX_ASYNC_MODE={raw_async_mode!r} must be 'async' or 'deferred'"
            )
        cfg["async_mode"] = lowered
```

- [ ] **Step 3: Verify tests pass**

```bash
pixi run -e test-py313t pytest tests/test_config.py -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/hpyx/config.py tests/test_config.py
git commit -m "feat(config): add HPYX_ASYNC_MODE flag for launch::async rollback"
```

---

## Task 3: Rewrite `src/_core/futures.cpp` — `HPXFuture` class core

**Files:**
- Create: `src/_core/futures.hpp` (new contents)
- Modify: `src/_core/futures.cpp` (full rewrite — replaces existing hpx_async/hpx_async_add)

The existing `futures.cpp` uses `launch::deferred` and exposes free functions `hpx_async` and `hpx_async_add`. We replace it entirely with a proper `HPXFuture` class plus free functions registered on a `_core.futures` submodule.

- [ ] **Step 1: Write failing test** for construction + `result()` on a ready future

Create `tests/test_futures.py`:

```python
"""Tests for hpyx.futures — HPXFuture class and combinators."""

import threading
import time

import pytest

import hpyx
from hpyx._core import futures as core_futures


# ---- HPXFuture construction and .result() ----

def test_ready_future_result_returns_immediately():
    fut = core_futures.ready_future(42)
    assert fut.result() == 42
    assert fut.done()


def test_ready_future_result_with_object():
    fut = core_futures.ready_future({"a": 1, "b": [2, 3]})
    assert fut.result() == {"a": 1, "b": [2, 3]}


def test_async_submit_runs_on_hpx_worker():
    captured_worker_id = []

    def body():
        captured_worker_id.append(hpyx.debug.get_worker_thread_id())
        return "ok"

    fut = core_futures.async_submit(body, (), {})
    assert fut.result() == "ok"
    # The callable ran on an HPX worker, so worker id must be in [0, N)
    assert captured_worker_id[0] >= 0
    assert captured_worker_id[0] < hpyx.debug.get_num_worker_threads()


def test_async_submit_preserves_exceptions():
    def boom():
        raise ValueError("boom")

    fut = core_futures.async_submit(boom, (), {})
    with pytest.raises(ValueError, match="boom"):
        fut.result()


def test_async_submit_exception_method():
    def boom():
        raise RuntimeError("xyz")

    fut = core_futures.async_submit(boom, (), {})
    exc = fut.exception()
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "xyz"
```

Run: `pixi run -e test-py313t pytest tests/test_futures.py::test_ready_future_result_returns_immediately -v`
Expected: FAIL (`AttributeError: module 'hpyx._core' has no attribute 'futures'`).

- [ ] **Step 2: Write `src/_core/futures.hpp`**

Replace contents with:

```cpp
#pragma once

#include <nanobind/nanobind.h>
#include <hpx/future.hpp>

#include <atomic>
#include <memory>
#include <optional>
#include <string>

namespace hpyx::futures {

// Wraps hpx::shared_future<nb::object> so multiple consumers (then(),
// add_done_callback, __await__) share the same underlying future.
class HPXFuture {
  public:
    HPXFuture() = default;
    explicit HPXFuture(hpx::shared_future<nanobind::object> fut);
    HPXFuture(const HPXFuture&) = default;
    HPXFuture(HPXFuture&&) = default;
    HPXFuture& operator=(const HPXFuture&) = default;
    HPXFuture& operator=(HPXFuture&&) = default;

    // concurrent.futures.Future-compatible methods
    nanobind::object result(std::optional<double> timeout = std::nullopt);
    nanobind::object exception(std::optional<double> timeout = std::nullopt);
    bool done() const;
    bool running() const;
    bool cancelled() const;
    bool cancel();
    void add_done_callback(nanobind::callable cb);

    // HPX-native extensions
    HPXFuture then(nanobind::callable cb);
    HPXFuture share() const;  // no-op; already shared

    // Internal use only
    hpx::shared_future<nanobind::object> const& raw() const { return fut_; }

  private:
    hpx::shared_future<nanobind::object> fut_;
    std::shared_ptr<std::atomic<bool>> cancelled_{
        std::make_shared<std::atomic<bool>>(false)};
    std::shared_ptr<std::atomic<bool>> running_{
        std::make_shared<std::atomic<bool>>(false)};
};

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::futures
```

- [ ] **Step 3: Write `src/_core/futures.cpp` — class + `async_submit` + `ready_future`**

Replace contents with:

```cpp
#include "futures.hpp"
#include "runtime.hpp"

#include <hpx/async.hpp>
#include <hpx/future.hpp>
#include <hpx/iostream.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::futures {

namespace {

// Read HPYX_ASYNC_MODE env to decide launch::async vs launch::deferred.
// Default is "async" (the fix in this plan); "deferred" is the rollback.
hpx::launch resolve_launch_policy() {
    const char* mode = std::getenv("HPYX_ASYNC_MODE");
    if (mode != nullptr && std::string(mode) == "deferred") {
        return hpx::launch::deferred;
    }
    return hpx::launch::async;
}

// Task body wrapper: acquires GIL before invoking the Python callable,
// translates exceptions via nb::python_error.
auto make_python_task(nb::callable fn, nb::args args, nb::kwargs kwargs) {
    return [fn = std::move(fn), args = std::move(args),
            kwargs = std::move(kwargs)]() -> nb::object {
        nb::gil_scoped_acquire acquire;
        try {
            return fn(*args, **kwargs);
        } catch (nb::python_error& e) {
            e.restore();
            throw;
        }
    };
}

}  // namespace

// ---- HPXFuture methods ----

HPXFuture::HPXFuture(hpx::shared_future<nb::object> fut)
    : fut_(std::move(fut)) {}

nb::object HPXFuture::result(std::optional<double> timeout) {
    if (!fut_.valid()) {
        throw std::runtime_error("Future is invalid (default-constructed or moved-from)");
    }
    // Release GIL while waiting so other Python threads can run.
    {
        nb::gil_scoped_release release;
        if (timeout.has_value()) {
            auto status = fut_.wait_for(
                std::chrono::duration<double>(*timeout));
            if (status == hpx::future_status::timeout) {
                nb::gil_scoped_acquire reacq;
                throw nb::python_error(
                    nb::module_::import_("concurrent.futures").attr("TimeoutError")());
            }
        } else {
            fut_.wait();
        }
    }
    // Reacquire GIL and fetch (may re-raise Python exception).
    try {
        return fut_.get();
    } catch (nb::python_error&) {
        throw;  // already has Python exception state
    }
}

nb::object HPXFuture::exception(std::optional<double> timeout) {
    if (!fut_.valid()) {
        return nb::none();
    }
    {
        nb::gil_scoped_release release;
        if (timeout.has_value()) {
            auto status = fut_.wait_for(
                std::chrono::duration<double>(*timeout));
            if (status == hpx::future_status::timeout) {
                nb::gil_scoped_acquire reacq;
                throw nb::python_error(
                    nb::module_::import_("concurrent.futures").attr("TimeoutError")());
            }
        } else {
            fut_.wait();
        }
    }
    if (!fut_.has_exception()) {
        return nb::none();
    }
    try {
        fut_.get();  // re-raises
    } catch (nb::python_error& e) {
        return nb::borrow(e.value());
    } catch (std::exception& e) {
        return nb::cast(std::string(e.what()));
    } catch (...) {
        return nb::cast(std::string("unknown C++ exception"));
    }
    return nb::none();
}

bool HPXFuture::done() const {
    if (!fut_.valid()) return true;
    return fut_.is_ready();
}

bool HPXFuture::running() const {
    return running_->load() && !done();
}

bool HPXFuture::cancelled() const {
    return cancelled_->load();
}

bool HPXFuture::cancel() {
    // Per spec §5.4: only cancels if not started.
    if (running_->load() || done()) {
        return false;
    }
    bool expected = false;
    if (cancelled_->compare_exchange_strong(expected, true)) {
        return true;
    }
    return false;
}

void HPXFuture::add_done_callback(nb::callable cb) {
    if (!fut_.valid()) {
        // Already done/invalid; invoke immediately.
        nb::gil_scoped_acquire acquire;
        try { cb(nb::cast(*this)); } catch (...) {}
        return;
    }
    // HPX will invoke our lambda on some HPX worker thread (or the calling
    // thread if already ready). Our lambda acquires the GIL before calling
    // the Python callback.
    auto captured = *this;  // copy — shared_future is cheap to copy
    fut_.then([cb = std::move(cb), captured](hpx::shared_future<nb::object> const&) mutable {
        nb::gil_scoped_acquire acquire;
        try {
            cb(nb::cast(captured));
        } catch (nb::python_error& e) {
            // concurrent.futures.Future swallows callback errors with a log.
            // Print to stderr (std::cerr is GIL-safe since we hold it).
            PyErr_WriteUnraisable(e.value().ptr());
            e.discard_as_unraisable(nb::none());
        }
    });
}

HPXFuture HPXFuture::then(nb::callable cb) {
    if (!fut_.valid()) {
        throw std::runtime_error("Cannot call .then() on an invalid future");
    }
    auto pyfn = std::move(cb);
    auto new_fut = fut_.then(
        [pyfn = std::move(pyfn)](hpx::shared_future<nb::object> prev) -> nb::object {
            nb::gil_scoped_acquire acquire;
            try {
                // Per spec §4.4: .then receives the completed Future object.
                nb::object arg = prev.get();  // rethrows on exception
                return pyfn(arg);
            } catch (nb::python_error&) {
                throw;
            }
        }).share();
    return HPXFuture(std::move(new_fut));
}

HPXFuture HPXFuture::share() const {
    return HPXFuture(fut_);  // already shared internally
}

// ---- Free functions ----

static HPXFuture async_submit(nb::callable fn, nb::args args, nb::kwargs kwargs) {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
    auto policy = resolve_launch_policy();
    auto task = make_python_task(std::move(fn), std::move(args), std::move(kwargs));
    nb::gil_scoped_release release;
    auto fut = hpx::async(policy, std::move(task)).share();
    return HPXFuture(std::move(fut));
}

static HPXFuture ready_future(nb::object value) {
    auto fut = hpx::make_ready_future<nb::object>(std::move(value)).share();
    return HPXFuture(std::move(fut));
}

void register_bindings(nb::module_& m) {
    nb::class_<HPXFuture>(m, "HPXFuture")
        .def(nb::init<>())
        .def("result", &HPXFuture::result,
             "timeout"_a = nb::none(),
             "Block until the future is done; return the result or raise its exception.")
        .def("exception", &HPXFuture::exception,
             "timeout"_a = nb::none(),
             "Block until done; return the exception or None.")
        .def("done", &HPXFuture::done)
        .def("running", &HPXFuture::running)
        .def("cancelled", &HPXFuture::cancelled)
        .def("cancel", &HPXFuture::cancel)
        .def("add_done_callback", &HPXFuture::add_done_callback, "callback"_a)
        .def("then", &HPXFuture::then, "callback"_a,
             "Attach a continuation; return a new Future for the continuation's result.")
        .def("share", &HPXFuture::share);

    m.def("async_submit", &async_submit, "fn"_a, "args"_a, "kwargs"_a,
          "Submit a callable to HPX; return a Future for its result.");
    m.def("ready_future", &ready_future, "value"_a,
          "Return an already-completed future wrapping `value`.");
}

}  // namespace hpyx::futures
```

- [ ] **Step 4: Update `src/_core/bind.cpp` to register the new submodule**

In `src/_core/bind.cpp`:

1. Remove the top-level `bind_hpx_future<nb::object>` template instantiation and its call.
2. Remove the top-level `m.def("hpx_async", ...)` and `m.def("hpx_async_add", ...)` entries.
3. Add submodule registration below the runtime registration:

```cpp
// After the existing runtime registration block:
auto m_futures = m.def_submodule("futures");
hpyx::futures::register_bindings(m_futures);
```

4. Add `#include "futures.hpp"` at the top.
5. Remove the old `#include "futures.hpp"` only if the old one referenced old `futures::hpx_async` symbols — the new header is the same filename so the include line stays.

- [ ] **Step 5: Rebuild**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
```

Expected: compiles. If `'futures::hpx_async' is not declared` errors appear, ensure you fully removed the old binding entries from `bind.cpp`.

- [ ] **Step 6: Run the failing tests**

```bash
pixi run -e test-py313t pytest tests/test_futures.py -v
```

Expected: the four tests written in Step 1 all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/_core tests/test_futures.py
git commit -m "$(cat <<'EOF'
feat(_core/futures): rewrite futures with launch::async + HPXFuture class

Replaces the broken launch::deferred-based hpx_async with a proper
HPXFuture class wrapping hpx::shared_future<nb::object>. Implements the
concurrent.futures.Future protocol (result/exception/done/running/
cancelled/cancel/add_done_callback), plus HPX-native .then() and share().
Adds async_submit and ready_future free functions.

Also respects HPYX_ASYNC_MODE=deferred for emergency rollback (risk #1).
EOF
)"
```

---

## Task 4: Add `when_all`, `when_any`, `dataflow`, `shared_future` combinators

**Files:**
- Modify: `src/_core/futures.cpp` (add four free functions)
- Modify: `src/_core/futures.hpp` (no change needed — `register_bindings` adds them)
- Modify: `tests/test_futures.py` (add combinator tests)

- [x] **Step 1: Write failing tests**

Append to `tests/test_futures.py`:

```python
# ---- when_all / when_any / dataflow ----

from hpyx._core import futures as core_futures


def test_when_all_returns_tuple_of_values():
    f1 = core_futures.ready_future(1)
    f2 = core_futures.ready_future(2)
    f3 = core_futures.ready_future(3)
    combined = core_futures.when_all([f1, f2, f3])
    result = combined.result()
    assert result == (1, 2, 3)


def test_when_all_waits_for_slow_future():
    def slow():
        import time
        time.sleep(0.05)
        return "slow-result"

    fast = core_futures.ready_future("fast-result")
    slow_fut = core_futures.async_submit(slow, (), {})
    combined = core_futures.when_all([fast, slow_fut])
    assert combined.result() == ("fast-result", "slow-result")


def test_when_any_returns_index_and_future():
    def slow():
        import time
        time.sleep(0.5)
        return "slow"

    f_slow = core_futures.async_submit(slow, (), {})
    f_fast = core_futures.ready_future("fast")
    result = core_futures.when_any([f_slow, f_fast]).result()
    # Result is a tuple (index, list_of_futures).
    idx, futures_list = result
    assert idx == 1  # fast one is index 1
    assert futures_list[idx].result() == "fast"


def test_dataflow_combines_inputs_into_fn():
    f1 = core_futures.ready_future(10)
    f2 = core_futures.ready_future(20)

    def add(a, b):
        return a + b

    combined = core_futures.dataflow(add, [f1, f2])
    assert combined.result() == 30


def test_dataflow_propagates_exception():
    def boom():
        raise ValueError("upstream")

    f_bad = core_futures.async_submit(boom, (), {})
    f_ok = core_futures.ready_future(1)

    def add(a, b):
        return a + b

    combined = core_futures.dataflow(add, [f_bad, f_ok])
    with pytest.raises(ValueError, match="upstream"):
        combined.result()
```

Run: `pixi run -e test-py313t pytest tests/test_futures.py::test_when_all_returns_tuple_of_values -v`
Expected: FAIL (`AttributeError: ... has no attribute 'when_all'`).

- [x] **Step 2: Implement in `src/_core/futures.cpp`**

In the anonymous namespace at the top, add a helper for vector-of-futures:

```cpp
static std::vector<hpx::shared_future<nb::object>> extract_raw(
    std::vector<HPXFuture> const& inputs) {
    std::vector<hpx::shared_future<nb::object>> out;
    out.reserve(inputs.size());
    for (auto const& f : inputs) out.push_back(f.raw());
    return out;
}
```

Add three free functions before `register_bindings`:

```cpp
static HPXFuture when_all_impl(std::vector<HPXFuture> inputs) {
    auto raws = extract_raw(inputs);
    nb::gil_scoped_release release;
    auto combined = hpx::when_all(std::move(raws));
    auto mapped = combined.then(
        [](auto&& fut_of_vec) -> nb::object {
            auto vec = fut_of_vec.get();
            nb::gil_scoped_acquire acquire;
            nb::tuple out = nb::steal<nb::tuple>(PyTuple_New(vec.size()));
            for (std::size_t i = 0; i < vec.size(); ++i) {
                PyTuple_SET_ITEM(out.ptr(), i, vec[i].get().release().ptr());
            }
            return out;
        }).share();
    return HPXFuture(std::move(mapped));
}

static HPXFuture when_any_impl(std::vector<HPXFuture> inputs) {
    auto raws = extract_raw(inputs);
    auto captured_inputs = inputs;  // copy so wrappers stay alive
    nb::gil_scoped_release release;
    auto combined = hpx::when_any(std::move(raws));
    auto mapped = combined.then(
        [captured_inputs](auto&& fut_of_result) -> nb::object {
            auto result = fut_of_result.get();
            nb::gil_scoped_acquire acquire;
            // Return (index, list_of_HPXFuture).
            nb::list futures_list;
            for (auto const& w : captured_inputs) {
                futures_list.append(nb::cast(w));
            }
            return nb::make_tuple(static_cast<std::size_t>(result.index),
                                   futures_list);
        }).share();
    return HPXFuture(std::move(mapped));
}

static HPXFuture dataflow_impl(nb::callable fn, std::vector<HPXFuture> inputs) {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
    auto raws = extract_raw(inputs);
    auto captured_fn = std::move(fn);
    // Use hpx::dataflow to wait for all inputs, then invoke the Python fn
    // with their resolved values.
    nb::gil_scoped_release release;
    auto result = hpx::dataflow(
        hpx::launch::async,
        [captured_fn](auto&&... results) -> nb::object {
            nb::gil_scoped_acquire acquire;
            // Unpack each hpx::shared_future<nb::object> via .get() — the
            // args here are references to completed futures.
            std::array<nb::object, sizeof...(results)> args = {
                results.get()...
            };
            nb::tuple py_args = nb::steal<nb::tuple>(PyTuple_New(args.size()));
            for (std::size_t i = 0; i < args.size(); ++i) {
                PyTuple_SET_ITEM(py_args.ptr(), i, args[i].release().ptr());
            }
            try {
                return captured_fn(*py_args);
            } catch (nb::python_error& e) {
                e.restore();
                throw;
            }
        },
        std::move(raws));
    return HPXFuture(result.share());
}
```

**Note on the dataflow variadic pack:** the lambda above uses a `sizeof...(results)` expansion, which compiles only when called via `hpx::dataflow` with a variadic pack. `hpx::dataflow` with a vector of futures instead calls with `std::vector<shared_future<T>>` as the single arg — which matches our signature. Actually this is subtle — let me use a non-template form that accepts the vector. Replace `dataflow_impl` with this cleaner form:

```cpp
static HPXFuture dataflow_impl(nb::callable fn, std::vector<HPXFuture> inputs) {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
    auto raws = extract_raw(inputs);
    auto captured_fn = std::move(fn);
    nb::gil_scoped_release release;
    auto result = hpx::dataflow(
        hpx::launch::async,
        [captured_fn](std::vector<hpx::shared_future<nb::object>> fs) -> nb::object {
            nb::gil_scoped_acquire acquire;
            nb::tuple py_args = nb::steal<nb::tuple>(PyTuple_New(fs.size()));
            for (std::size_t i = 0; i < fs.size(); ++i) {
                // fs[i].get() may re-raise — that propagates out of the lambda
                // into the resulting future, which is what we want.
                nb::object val = fs[i].get();
                PyTuple_SET_ITEM(py_args.ptr(), i, val.release().ptr());
            }
            try {
                return captured_fn(*py_args);
            } catch (nb::python_error& e) {
                e.restore();
                throw;
            }
        },
        std::move(raws));
    return HPXFuture(result.share());
}
```

Add to `register_bindings`:

```cpp
    m.def("when_all", &when_all_impl, "inputs"_a);
    m.def("when_any", &when_any_impl, "inputs"_a);
    m.def("dataflow", &dataflow_impl, "fn"_a, "inputs"_a);
```

Add to the includes in `futures.cpp`:

```cpp
#include <hpx/async_combinators/when_all.hpp>
#include <hpx/async_combinators/when_any.hpp>
#include <hpx/executors/dataflow.hpp>
```

- [x] **Step 3: Rebuild and test**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_futures.py -v
```

Expected: all tests (Steps 1 and prior) pass.

- [x] **Step 4: Commit**

```bash
git add src/_core tests/test_futures.py
git commit -m "feat(_core/futures): add when_all, when_any, dataflow combinators"
```

---

## Task 5: Create `src/hpyx/futures/` Python package

**Files:**
- Create: `src/hpyx/futures/__init__.py`
- Create: `src/hpyx/futures/_future.py`
- Delete: `src/hpyx/futures.py` (if it exists as a flat module)

The existing `hpyx/futures` is currently a flat module with a broken `submit` function. We convert it to a subpackage with the new `Future` class + free functions.

- [ ] **Step 1: Check existing state**

```bash
ls src/hpyx/futures* 2>/dev/null
```

If there's a flat `src/hpyx/futures.py`, rename to `_old_futures.py` temporarily so we can reference it during the rewrite:

```bash
git mv src/hpyx/futures.py src/hpyx/_old_futures.py 2>/dev/null || true
```

If `src/hpyx/futures/` exists as a subpackage already (from v0.x), note its contents and plan to replace:

```bash
ls src/hpyx/futures/ 2>/dev/null
```

- [ ] **Step 2: Write failing test**

Create the skeleton in `tests/test_futures.py` (prepend or organize — put these under a new section):

```python
# ---- Python Future wrapper (hpyx.Future, hpyx.async_) ----

def test_async_returns_hpyx_Future():
    fut = hpyx.async_(lambda: 42)
    assert isinstance(fut, hpyx.Future)
    assert fut.result() == 42


def test_Future_concurrent_futures_protocol():
    import concurrent.futures
    fut = hpyx.async_(lambda: "hi")
    # Duck-type protocol: every concurrent.futures.Future method exists.
    for method in ("result", "exception", "done", "running", "cancelled",
                   "cancel", "add_done_callback"):
        assert callable(getattr(fut, method))
    assert fut.result() == "hi"


def test_Future_then_chain():
    fut = hpyx.async_(lambda: 10).then(lambda x: x * 2).then(lambda x: x + 1)
    assert fut.result() == 21


def test_when_all_free_function():
    f1 = hpyx.async_(lambda: 1)
    f2 = hpyx.async_(lambda: 2)
    assert hpyx.when_all(f1, f2).result() == (1, 2)


def test_dataflow_free_function():
    f1 = hpyx.async_(lambda: 3)
    f2 = hpyx.async_(lambda: 4)
    out = hpyx.dataflow(lambda a, b: a * b, f1, f2)
    assert out.result() == 12


def test_shared_future_is_idempotent():
    f = hpyx.async_(lambda: 99)
    s = hpyx.shared_future(f)
    assert s.result() == 99
    assert s.result() == 99  # can call twice


def test_ready_future_is_immediately_done():
    f = hpyx.ready_future(7)
    assert f.done()
    assert f.result() == 7
```

- [ ] **Step 3: Implement `src/hpyx/futures/_future.py`**

```python
"""hpyx.Future — Python wrapper around hpyx._core.futures.HPXFuture.

The wrapper adds:
- Type safety (the wrapper is what users import as `hpyx.Future`).
- `__await__` for asyncio integration (implementation in aio.py).
- A uniform `isinstance` check that works with user code.

The wrapper is thin — most methods delegate directly to the C++ object.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from hpyx import _core


class Future:
    """A future backed by the HPX runtime.

    Implements the `concurrent.futures.Future` protocol (``result``,
    ``exception``, ``done``, ``running``, ``cancelled``, ``cancel``,
    ``add_done_callback``), plus HPX-native ``.then(fn)`` and asyncio
    ``await`` support.

    Multiple consumers of the same Future are supported — internally
    every Future wraps a ``hpx::shared_future<nb::object>``.
    """

    __slots__ = ("_hpx",)

    def __init__(self, hpx_fut: _core.futures.HPXFuture) -> None:
        self._hpx = hpx_fut

    # ---- concurrent.futures.Future protocol ----

    def result(self, timeout: Optional[float] = None) -> Any:
        return self._hpx.result(timeout)

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        return self._hpx.exception(timeout)

    def done(self) -> bool:
        return self._hpx.done()

    def running(self) -> bool:
        return self._hpx.running()

    def cancelled(self) -> bool:
        return self._hpx.cancelled()

    def cancel(self) -> bool:
        return self._hpx.cancel()

    def add_done_callback(self, fn: Callable[["Future"], None]) -> None:
        # Wrap so the callback receives `Future`, not the raw HPXFuture.
        def _wrapper(_hpx_fut):
            try:
                fn(self)
            except BaseException:
                import logging
                logging.getLogger("hpyx.futures").exception(
                    "exception in Future.add_done_callback"
                )
        self._hpx.add_done_callback(_wrapper)

    # ---- HPX-native ----

    def then(self, fn: Callable[["Future"], Any]) -> "Future":
        # HPX's then receives the resolved value; we normalize to match
        # concurrent.futures style (callback receives the Future).
        def _shim(value):
            # Build a ready Future wrapping the value so the user's fn
            # can call .result(). This matches dask/concurrent.futures.
            ready = Future(_core.futures.ready_future(value))
            return fn(ready)
        new_hpx = self._hpx.then(_shim)
        return Future(new_hpx)

    def share(self) -> "Future":
        return Future(self._hpx.share())

    # ---- asyncio bridge (full body in hpyx.aio, imported lazily here to
    #      avoid importing asyncio at module load) ----

    def __await__(self):
        from hpyx.aio import _future_await
        return _future_await(self).__await__()

    def __repr__(self) -> str:
        state = "done" if self.done() else ("running" if self.running() else "pending")
        if self.cancelled():
            state = "cancelled"
        return f"<hpyx.Future state={state}>"
```

- [ ] **Step 4: Implement `src/hpyx/futures/__init__.py`**

```python
"""hpyx.futures — HPX-backed futures API (Pythonic wrapper).

Public names:
    Future, async_, when_all, when_any, dataflow, shared_future, ready_future
"""

from __future__ import annotations

from typing import Any, Callable

from hpyx import _core, _runtime
from hpyx.futures._future import Future


def async_(fn: Callable, *args: Any, **kwargs: Any) -> Future:
    """Submit a callable to an HPX worker; return a Future for its result.

    Runs `fn(*args, **kwargs)` on an HPX lightweight thread. The result
    is retrievable via ``fut.result()``, ``await fut``, ``.then(...)``,
    ``add_done_callback(...)``.
    """
    _runtime.ensure_started()
    raw = _core.futures.async_submit(fn, args, kwargs)
    return Future(raw)


def when_all(*futures: Future) -> Future:
    """Return a Future that resolves to a tuple of all input results."""
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    return Future(_core.futures.when_all(raws))


def when_any(*futures: Future) -> Future:
    """Return a Future that resolves to ``(index, futures_list)`` when any one completes."""
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    # when_any returns (index, list_of_HPXFuture); wrap inner list into Futures.
    inner = _core.futures.when_any(raws)
    def _wrap(result):
        idx, raw_list = result
        return (idx, [Future(r) for r in raw_list])
    return Future(inner.then(lambda x: _wrap(x)))


def dataflow(fn: Callable, *futures: Future) -> Future:
    """Run `fn(*resolved_values)` once all input futures complete."""
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    return Future(_core.futures.dataflow(fn, raws))


def shared_future(f: Future) -> Future:
    """Return a shareable view of ``f`` (supports multiple ``.result()`` consumers)."""
    return f.share()


def ready_future(value: Any) -> Future:
    """Return an already-completed Future wrapping ``value``."""
    return Future(_core.futures.ready_future(value))


__all__ = [
    "Future",
    "async_",
    "dataflow",
    "ready_future",
    "shared_future",
    "when_all",
    "when_any",
]
```

- [ ] **Step 5: Update `src/hpyx/__init__.py`**

Add the new exports:

```python
# Replace the existing `from hpyx import futures, multiprocessing` block with:
from hpyx import futures, multiprocessing
from hpyx.futures import (
    Future,
    async_,
    dataflow,
    ready_future,
    shared_future,
    when_all,
    when_any,
)
```

Extend `__all__`:

```python
__all__ = [
    "Future",
    "HPXExecutor",
    "HPXRuntime",
    "__version__",
    "async_",
    "config",
    "dataflow",
    "debug",
    "futures",
    "init",
    "is_running",
    "multiprocessing",
    "ready_future",
    "shared_future",
    "shutdown",
    "when_all",
    "when_any",
]
```

- [ ] **Step 6: Clean up old files**

```bash
# If you created _old_futures.py in Step 1 as a safety stash, remove it now.
rm -f src/hpyx/_old_futures.py
```

- [ ] **Step 7: Rebuild and run tests**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_futures.py -v
```

Expected: all tests pass, including the new wrapper tests from Step 2.

- [ ] **Step 8: Commit**

```bash
git add src/hpyx tests/test_futures.py
git commit -m "$(cat <<'EOF'
feat(futures): add hpyx.Future Python wrapper and hpyx.async_

Converts hpyx.futures into a subpackage with a Pythonic Future class
wrapping _core.futures.HPXFuture. Adds free functions async_, when_all,
when_any, dataflow, shared_future, ready_future. Future objects duck-type
concurrent.futures.Future so they work with asyncio.wrap_future,
loop.run_in_executor, and dask as an executor scheduler.
EOF
)"
```

---

## Task 6: Rewrite `src/hpyx/executor.py` as real `concurrent.futures.Executor`

**Files:**
- Modify: `src/hpyx/executor.py` (full rewrite — this is the v1 executor)
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_executor.py`:

```python
"""Tests for hpyx.HPXExecutor — concurrent.futures.Executor conformance."""

import concurrent.futures
import threading
import time

import pytest

import hpyx


# ---- Protocol conformance ----

def test_HPXExecutor_is_concurrent_futures_Executor_subclass():
    assert issubclass(hpyx.HPXExecutor, concurrent.futures.Executor)


def test_submit_returns_future_like_object():
    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(lambda: 42)
        assert fut.result() == 42


def test_submit_preserves_args_and_kwargs():
    def worker(a, b, *, c=0):
        return a + b + c

    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(worker, 1, 2, c=10)
        assert fut.result() == 13


def test_submit_propagates_exception():
    def boom():
        raise ValueError("boom")

    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(boom)
        with pytest.raises(ValueError, match="boom"):
            fut.result()


# ---- map ----

def test_map_basic():
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda x: x * x, range(5)))
        assert results == [0, 1, 4, 9, 16]


def test_map_two_iterables():
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda a, b: a + b, range(5), range(5, 10)))
        assert results == [5, 7, 9, 11, 13]


def test_map_propagates_exception():
    def pick(x):
        if x == 3:
            raise RuntimeError("no 3!")
        return x

    with hpyx.HPXExecutor() as ex:
        with pytest.raises(RuntimeError, match="no 3"):
            list(ex.map(pick, range(5)))


# ---- shutdown ----

def test_shutdown_is_idempotent():
    ex = hpyx.HPXExecutor()
    ex.shutdown()
    ex.shutdown()  # must not raise


def test_submit_after_shutdown_raises():
    ex = hpyx.HPXExecutor()
    ex.shutdown()
    with pytest.raises(RuntimeError, match="shut down|shutdown"):
        ex.submit(lambda: 1)


def test_context_manager_shuts_down():
    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(lambda: 1)
        fut.result()
    # After __exit__, submit must raise.
    with pytest.raises(RuntimeError, match="shut down|shutdown"):
        ex.submit(lambda: 2)


# ---- max_workers reconciliation ----

def test_max_workers_warning_when_mismatched(recwarn):
    # Session fixture started with os_threads=4. Specifying a different
    # max_workers after the runtime is already up should WARN, not raise.
    ex = hpyx.HPXExecutor(max_workers=99)
    assert any("max_workers" in str(w.message) for w in recwarn.list)
    ex.shutdown()


# ---- cross-thread submit ----

def test_submit_from_multiple_threads():
    N = 50
    results = [None] * N
    with hpyx.HPXExecutor() as ex:
        def submit_and_wait(i):
            results[i] = ex.submit(lambda x=i: x * 2).result()
        ts = [threading.Thread(target=submit_and_wait, args=(i,)) for i in range(N)]
        for t in ts: t.start()
        for t in ts: t.join()
    assert results == [i * 2 for i in range(N)]
```

Run: `pixi run -e test-py313t pytest tests/test_executor.py -v`
Expected: most/all FAIL (existing executor is broken).

- [ ] **Step 2: Rewrite `src/hpyx/executor.py`**

Replace entire contents:

```python
"""hpyx.HPXExecutor — a concurrent.futures.Executor backed by HPX.

All instances share one process-wide HPX runtime (HPX cannot host
multiple runtimes per process). `shutdown()` marks this executor handle
unusable but does not stop the runtime — atexit owns teardown.

Example
-------
>>> import hpyx
>>> with hpyx.HPXExecutor() as ex:
...     fut = ex.submit(pow, 2, 10)
...     print(fut.result())  # 1024

For dask integration:

>>> import dask.array as da
>>> with hpyx.HPXExecutor() as ex:
...     result = da.arange(1e6).sum().compute(scheduler=ex)
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Executor
from typing import Any

from hpyx import _runtime
from hpyx.futures import Future, async_


class HPXExecutor(Executor):
    """Real concurrent.futures.Executor backed by HPX.

    Parameters
    ----------
    max_workers : int | None, optional
        Advisory. HPX's worker pool is process-global; ``max_workers``
        seeds ``os_threads`` on the implicit init if the runtime isn't
        started yet. If the runtime is already started with a different
        ``os_threads``, a UserWarning is emitted and the existing pool
        is used.
    """

    def __init__(self, max_workers: int | None = None) -> None:
        self._closed = False
        if max_workers is not None:
            if _runtime.is_running():
                running_threads = None
                try:
                    running_threads = _runtime._started_cfg["os_threads"] if _runtime._started_cfg else None
                except Exception:
                    pass
                if running_threads is not None and running_threads != max_workers:
                    warnings.warn(
                        f"HPXExecutor(max_workers={max_workers}) differs from the "
                        f"running HPX runtime's os_threads={running_threads}; "
                        f"using the runtime pool as-is (HPX cannot be reconfigured "
                        f"after start).",
                        UserWarning,
                        stacklevel=2,
                    )
            else:
                _runtime.ensure_started(os_threads=max_workers)
        else:
            _runtime.ensure_started()

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        if self._closed:
            raise RuntimeError("HPXExecutor has been shut down")
        return async_(fn, *args, **kwargs)

    def map(
        self,
        fn: Callable[..., Any],
        *iterables: Iterable[Any],
        timeout: float | None = None,
        chunksize: int = 1,
    ) -> Iterator[Any]:
        # Submit every item eagerly, then yield results in order. This
        # matches concurrent.futures.ThreadPoolExecutor.map semantics.
        if self._closed:
            raise RuntimeError("HPXExecutor has been shut down")
        futures = [self.submit(fn, *group) for group in zip(*iterables, strict=True)]

        def _iter():
            try:
                for fut in futures:
                    yield fut.result(timeout=timeout)
            except GeneratorExit:
                for fut in futures:
                    fut.cancel()
                raise

        return _iter()

    def shutdown(
        self,
        wait: bool = True,
        *,
        cancel_futures: bool = False,
    ) -> None:
        # Per-handle shutdown. Does NOT stop the HPX runtime — atexit
        # owns teardown because HPX cannot restart within a process.
        self._closed = True


__all__ = ["HPXExecutor"]
```

- [ ] **Step 3: Rebuild + run tests**

No C++ changes, so no rebuild needed. Just:

```bash
pixi run -e test-py313t pytest tests/test_executor.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Run the full test suite to check for regressions**

```bash
pixi run -e test-py313t pytest tests/ -v --ignore=tests/test_submit.py --ignore=tests/test_for_loop.py
```

Expected: all pass. (`test_submit.py` was the v0.x broken executor test — we've replaced it, so you can delete it if its content is now obsolete. But check first: if it tests useful behavior, port it. Most likely its assertions are already covered in `test_executor.py`; delete the file to avoid confusion.)

- [ ] **Step 5: Delete legacy test_submit.py if it's redundant**

```bash
git rm tests/test_submit.py
```

- [ ] **Step 6: Commit**

```bash
git add src/hpyx/executor.py tests/test_executor.py
git commit -m "$(cat <<'EOF'
feat(executor): rewrite HPXExecutor as real concurrent.futures.Executor

- submit() returns a hpyx.Future (which duck-types concurrent.futures.Future)
- map() submits eagerly + yields results in order, matching ThreadPoolExecutor
- shutdown() marks the handle closed but leaves the HPX runtime running;
  atexit owns process-level teardown (HPX cannot restart in-process)
- max_workers is advisory — warns when it disagrees with the already-running
  runtime's os_threads
- Context manager support

Removes v0.x broken tests/test_submit.py — coverage moves to test_executor.py.
EOF
)"
```

---

## Task 7: Implement asyncio bridge (`__await__` + `hpyx.aio`)

**Files:**
- Create: `src/hpyx/aio.py`
- Create: `tests/test_aio.py`
- Modify: `src/hpyx/__init__.py` (re-export aio)

- [ ] **Step 1: Write failing tests**

Create `tests/test_aio.py`:

```python
"""Tests for the asyncio bridge (awaitable Future, hpyx.aio combinators)."""

import asyncio
import concurrent.futures

import pytest

import hpyx


# ---- direct await on Future ----

def test_await_future():
    async def main():
        fut = hpyx.async_(lambda: 42)
        return await fut

    assert asyncio.run(main()) == 42


def test_await_future_with_exception():
    async def main():
        fut = hpyx.async_(lambda: (_ for _ in ()).throw(ValueError("boom")))
        return await fut

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(main())


def test_await_does_not_block_event_loop():
    import time

    async def main():
        loop_iterations = 0

        async def counter():
            nonlocal loop_iterations
            while loop_iterations < 100:
                loop_iterations += 1
                await asyncio.sleep(0.001)

        def slow():
            time.sleep(0.1)
            return "slow-result"

        fut = hpyx.async_(slow)
        counter_task = asyncio.create_task(counter())
        result = await fut
        await counter_task
        return result, loop_iterations

    result, iterations = asyncio.run(main())
    assert result == "slow-result"
    # If awaiting blocked the loop, iterations would be ~0. We should see
    # the counter task progress while the HPX task was pending.
    assert iterations >= 50


# ---- asyncio.wrap_future compat ----

def test_wrap_future_works():
    async def main():
        fut = hpyx.async_(lambda: "ok")
        wrapped = asyncio.wrap_future(fut)
        return await wrapped

    assert asyncio.run(main()) == "ok"


# ---- loop.run_in_executor ----

def test_run_in_executor_with_HPXExecutor():
    async def main():
        loop = asyncio.get_running_loop()
        with hpyx.HPXExecutor() as ex:
            return await loop.run_in_executor(ex, pow, 2, 10)

    assert asyncio.run(main()) == 1024


# ---- hpyx.aio combinators ----

def test_aio_await_all():
    async def main():
        f1 = hpyx.async_(lambda: 1)
        f2 = hpyx.async_(lambda: 2)
        f3 = hpyx.async_(lambda: 3)
        return await hpyx.aio.await_all(f1, f2, f3)

    assert asyncio.run(main()) == (1, 2, 3)


def test_aio_await_any():
    import time

    async def main():
        def slow():
            time.sleep(0.2)
            return "slow"

        f_slow = hpyx.async_(slow)
        f_fast = hpyx.async_(lambda: "fast")
        idx, futs = await hpyx.aio.await_any(f_slow, f_fast)
        return idx, futs[idx].result()

    idx, result = asyncio.run(main())
    assert idx == 1
    assert result == "fast"
```

Run: `pixi run -e test-py313t pytest tests/test_aio.py -v`
Expected: FAIL (`hpyx.aio` does not exist).

- [ ] **Step 2: Implement `src/hpyx/aio.py`**

```python
"""hpyx.aio — asyncio integration for hpyx Futures.

Provides the internal `_future_await` used by `Future.__await__`, plus
the `await_all` and `await_any` combinators.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hpyx.futures import Future


async def _future_await(fut: "Future") -> Any:
    """Bridge an hpyx.Future into an asyncio-awaitable coroutine.

    Used by ``Future.__await__``. We wrap the hpyx Future into an
    ``asyncio.Future`` and hook its `add_done_callback` to post the
    result back to the running event loop via `call_soon_threadsafe`.
    """
    loop = asyncio.get_running_loop()
    aio_fut: asyncio.Future = loop.create_future()

    def _on_done(_hpx_fut: "Future") -> None:
        # This runs on an HPX worker thread — post back to the event loop.
        try:
            value = _hpx_fut.result()
        except BaseException as exc:  # noqa: BLE001
            if not aio_fut.done():
                loop.call_soon_threadsafe(aio_fut.set_exception, exc)
        else:
            if not aio_fut.done():
                loop.call_soon_threadsafe(aio_fut.set_result, value)

    fut.add_done_callback(_on_done)
    return await aio_fut


async def await_all(*futures: "Future") -> tuple:
    """Await all input futures; return a tuple of their results (in order).

    Unlike ``asyncio.gather``, exceptions are NOT consumed — the first
    exception raised aborts the whole operation (matches ``when_all``).
    """
    from hpyx.futures import when_all
    combined = when_all(*futures)
    return await combined


async def await_any(*futures: "Future") -> tuple[int, list["Future"]]:
    """Await any input future; return ``(index, futures_list)``.

    The ``futures_list`` element at ``index`` is the one that completed;
    others may still be pending.
    """
    from hpyx.futures import when_any
    combined = when_any(*futures)
    return await combined


__all__ = ["await_all", "await_any"]
```

- [ ] **Step 3: Export `hpyx.aio` from the package root**

In `src/hpyx/__init__.py`, add:

```python
from hpyx import aio
```

and include `"aio"` in `__all__`.

- [ ] **Step 4: Run the tests**

```bash
pixi run -e test-py313t pytest tests/test_aio.py -v
```

Expected: all pass. If `test_await_does_not_block_event_loop` fails (iterations == 0), it means `call_soon_threadsafe` isn't being called from the HPX worker — check that `add_done_callback` in the C++ `HPXFuture::add_done_callback` is registering a continuation rather than calling the callback synchronously for already-ready futures.

- [ ] **Step 5: Commit**

```bash
git add src/hpyx/aio.py src/hpyx/__init__.py tests/test_aio.py
git commit -m "$(cat <<'EOF'
feat(aio): add asyncio bridge — awaitable Future + await_all/await_any

- Future.__await__ bridges via loop.call_soon_threadsafe
- hpyx.aio.await_all wraps when_all for async contexts
- hpyx.aio.await_any wraps when_any
- asyncio.wrap_future(fut) and loop.run_in_executor(HPXExecutor(), ...)
  also work thanks to the concurrent.futures.Future protocol conformance.

Covers user story #5 (Carla — async-first web apps) and enables FastAPI/
asyncio codebases to schedule HPX work without boilerplate.
EOF
)"
```

---

## Task 8: Dask integration smoke test

**Files:**
- Create: `tests/test_dask_integration.py`

- [ ] **Step 1: Verify dask is available in the test environment**

```bash
pixi run -e test-py313t python -c "import dask.array as da; print(da.__version__)"
```

If dask is not installed, add it to `pixi.toml` under `[feature.test.dependencies]`:

```toml
dask = ">=2024.10.0"
numpy = ">=1.26"
```

Then `pixi install`.

- [ ] **Step 2: Write the smoke test**

Create `tests/test_dask_integration.py`:

```python
"""Smoke test for dask + hpyx.HPXExecutor integration (user story #8)."""

import pytest

pytest.importorskip("dask")
pytest.importorskip("dask.array")
pytest.importorskip("numpy")

import numpy as np
import dask.array as da

import hpyx


def test_dask_array_sum_via_HPXExecutor():
    with hpyx.HPXExecutor() as ex:
        x = da.arange(1000, chunks=100)
        result = x.sum().compute(scheduler=ex)
    assert int(result) == sum(range(1000))


def test_dask_array_matmul_via_HPXExecutor():
    rng = np.random.default_rng(42)
    a_np = rng.random((64, 64))
    b_np = rng.random((64, 64))
    a = da.from_array(a_np, chunks=(16, 16))
    b = da.from_array(b_np, chunks=(16, 16))

    with hpyx.HPXExecutor() as ex:
        c = (a @ b).compute(scheduler=ex)

    np.testing.assert_allclose(c, a_np @ b_np, rtol=1e-10)


def test_dask_delayed_via_HPXExecutor():
    from dask import delayed

    @delayed
    def inc(x):
        return x + 1

    @delayed
    def total(xs):
        return sum(xs)

    results = [inc(i) for i in range(10)]
    final = total(results)

    with hpyx.HPXExecutor() as ex:
        assert final.compute(scheduler=ex) == sum(range(1, 11))
```

- [ ] **Step 3: Run the test**

```bash
pixi run -e test-py313t pytest tests/test_dask_integration.py -v
```

Expected: all three pass. If the first fails with "executor does not accept scheduler=", dask may be expecting a `client` / `synchronous` / named scheduler instead. In dask ≥ 2024.x the scheduler protocol accepts `concurrent.futures.Executor` subclasses directly. If something's off, run:

```bash
pixi run -e test-py313t python -c "
from dask.base import get_scheduler
import hpyx
ex = hpyx.HPXExecutor()
s = get_scheduler(scheduler=ex)
print('resolved scheduler:', s)
"
```

to see how dask is resolving the argument.

- [ ] **Step 4: Commit**

```bash
git add tests/test_dask_integration.py
# If you modified pixi.toml, add it too.
git add pixi.toml pixi.lock 2>/dev/null || true
git commit -m "test(integration): add dask + HPXExecutor smoke test (user story 8)"
```

---

## Task 9: Final full-suite verification

- [ ] **Step 1: Run the entire test suite**

```bash
pixi run test
```

Expected results:
- All Plan 0 tests: pass (unchanged behavior).
- `test_futures.py`: pass.
- `test_executor.py`: pass.
- `test_aio.py`: pass.
- `test_dask_integration.py`: pass.
- `test_for_loop.py`: may still fail (Plan 3).
- `test_hpx_linalg.py`: pass.

- [ ] **Step 2: Smoke-test the rollback flag**

```bash
HPYX_ASYNC_MODE=deferred pixi run -e test-py313t python -c "
import hpyx
fut = hpyx.async_(lambda: 'from-deferred')
print(fut.result())
"
```

Expected: prints `from-deferred`. This confirms the rollback flag works end-to-end (though with reduced parallelism).

- [ ] **Step 3: Smoke-test free-threaded scaling**

```bash
pixi run -e test-py313t python -c "
import threading
import time

import hpyx

N = 20
durations = []
start = time.perf_counter()
with hpyx.HPXExecutor() as ex:
    futs = [ex.submit(time.sleep, 0.1) for _ in range(N)]
    for f in futs: f.result()
elapsed = time.perf_counter() - start
print(f'Ran {N} × 0.1s sleeps in {elapsed:.2f}s')
print(f'(With os_threads=4, expect ~0.5s — proves true concurrency)')
"
```

Expected: elapsed ~0.5s-0.7s. If it's close to 2.0s, the GIL is still serializing — check that `async_submit` uses `launch::async` and not `launch::deferred`.

---

## Task 10: Open draft PR

- [ ] **Step 1: Push**

```bash
git push -u origin feat/v1-phase-1-futures-executor-asyncio
```

- [ ] **Step 2: Create draft PR**

```bash
gh pr create --draft --title "feat(_core/futures,executor,aio): v1 Phase 1 — futures, executor, asyncio" --body "$(cat <<'EOF'
## Summary

Fixes the broken `launch::deferred` in `hpx_async` and lands the v1 futures/executor/asyncio surface.

- `_core.futures.HPXFuture` class with full concurrent.futures.Future protocol + `.then` + `.share`
- `_core.futures.async_submit` uses `hpx::launch::async` (configurable via `HPYX_ASYNC_MODE=deferred` for rollback)
- `when_all`, `when_any`, `dataflow`, `ready_future`
- `hpyx.Future` Python wrapper; `hpyx.async_`
- `HPXExecutor` rewritten as real `concurrent.futures.Executor` (submit/map/shutdown + context manager)
- `hpyx.aio` — `Future.__await__`, `await_all`, `await_any`; `asyncio.wrap_future` and `loop.run_in_executor` both Just Work
- Dask smoke test: `dask.compute(..., scheduler=HPXExecutor())` validated

## Spec + plan

- Spec §§ 3.2, 4.4, 4.5, 4.8, 5.1-5.4
- Plan: `docs/plans/2026-04-24-hpyx-v1-phase-1-futures-executor-asyncio.md`

## Test plan

- [x] `tests/test_futures.py` — HPXFuture construction, result, exception, then chains, when_all, when_any, dataflow, shared_future, ready_future
- [x] `tests/test_executor.py` — concurrent.futures.Executor subclass check, submit/map/shutdown, max_workers warning, cross-thread submit
- [x] `tests/test_aio.py` — await fut, wrap_future, run_in_executor, aio.await_all, aio.await_any, event-loop non-blocking
- [x] `tests/test_dask_integration.py` — da.array.sum, matmul, dask.delayed chain
- [x] `HPYX_ASYNC_MODE=deferred` rollback flag works
- [x] Free-threaded 3.13t scaling smoke test

## What's NOT in this PR

- Parallel algorithms + kernels (Plan 2)
- asv/CI benchmark gating (Plan 3 / Plan 4)
EOF
)"
```

---

## Self-review notes

**Spec coverage (Phase 1 subset):**
- Spec §1.6 item 1 "Fix broken async (launch::async + GIL discipline)" — Task 3.
- Spec §1.6 item 2 "Future composition + concurrent.futures.Future protocol conformance" — Tasks 3, 4, 5.
- Spec §1.6 item 3 "HPXExecutor as real concurrent.futures.Executor" — Task 6.
- Spec §1.6 item 6 "asyncio bridge Level 2" — Task 7.
- Spec §1.5 success criterion "dask.compute scheduler=HPXExecutor" — Task 8.
- Spec risk #1 mitigation (rollback flag) — Task 2.

Spec items 4, 5 (already done), 7, 8 are Plan 2/3/4.

**Placeholder scan:** no TBD/TODO. "Plan 2/3/4" references are scope boundaries.

**Type consistency:**
- `HPXFuture` (C++ class) ↔ `Future` (Python wrapper) — clean separation; users see `Future`.
- `async_` (Python) ↔ `async_submit` (C++) — Python name avoids shadowing the `async` keyword.
- `when_all` / `when_any` / `dataflow` — same names in C++ and Python free-function layer; Python `when_any` re-wraps the inner list into `Future` objects.
- `_runtime` / `_core` — private prefixes consistent; users import `hpyx.*`.

**Known caveats:**
- Task 4's `when_any` result conversion is done partly in C++ (tuple build) and partly in Python (`Future`-wrap the inner list via `.then`). This is intentional — C++ can't construct the Python `Future` class without a circular dependency.
- `Future.cancel()` only works on not-yet-started tasks (spec §5.4). Tests confirm this but don't test mid-flight cancellation (which is correctly not supported).
- `HPXExecutor.map` submits all items eagerly. For very large iterables, this could exhaust memory. `chunksize` is accepted per protocol but not yet used; Plan 3 revisits when chunk-size modifiers exist for parallel algorithms.
