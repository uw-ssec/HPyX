# HPyX v1 Phase 2: Parallel Algorithms, Kernels, Execution Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Land the two-track parallel-computing surface — `hpyx.parallel.*` with 17 Python-callback algorithms (for audiences A and C), `hpyx.kernels.*` with 5 C++-native kernels over numpy arrays (for audience A), and `hpyx.execution` with policy objects (seq/par/par_unseq/unseq + task + chunk-size modifiers). Also deprecate `hpyx.multiprocessing` (now that `hpyx.parallel.for_loop` exists to replace it). End state: `hpyx.parallel.for_loop(par, 0, N, fn)` truly parallelizes Python callbacks on free-threaded 3.13t; `hpyx.kernels.dot(a, b)` beats single-threaded numpy on large arrays.

**Architecture:** Three new C++ translation units under `src/_core/` (`parallel.cpp`, `kernels.cpp`, `policy_dispatch.hpp`) plus shared `gil_macros.hpp`. Each Python-callback algorithm is ~15-20 lines of C++ using the `HPYX_CALLBACK_GIL` macro. Each kernel is ~20-30 lines using `HPYX_KERNEL_NOGIL`. Python side: `hpyx.parallel` + `hpyx.kernels` are thin dispatch shims over `_core`; `hpyx.execution` builds `PolicyToken` structs from Python policy objects.

**Tech Stack:** C++17, nanobind ≥2.7 with `nb::ndarray`, HPX parallel algorithms (`hpx::experimental::for_loop`, `hpx::transform`, `hpx::reduce`, `hpx::transform_reduce`, `hpx::sort`, etc.), numpy ≥1.26 for kernel reference tests, pytest, hypothesis (property-based tests).

**Depends on:** Plans 0 and 1 merged into `main` (runtime foundation + futures + executor).

**Reference documents:**
- Spec: `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md` §§ 3.3, 3.4, 3.5, 3.6, 4.3, 4.6, 4.7
- HPX knowledge: `docs/codebase-analysis/hpx/CODEBASE_KNOWLEDGE.md` §§ 4.3, 4.4, 5.1, 5.5

**Out of scope for this plan:**
- Benchmarks for parallel/kernels (Plan 3, but benchmarks shipped in Plan 4)
- Full `enable_tracing` (Plan 4)
- Docs and migration guide (Plan 5)
- Custom executors (`fork_join`, `limiting`, `annotating`) — v1.x

---

## File Structure

### Created files

| File | Responsibility |
|---|---|
| `src/_core/gil_macros.hpp` | `HPYX_KERNEL_NOGIL`, `HPYX_CALLBACK_GIL` macros. |
| `src/_core/policy_dispatch.hpp` | `PolicyToken` struct + `dispatch_policy<Fn>(token, fn)` translator. |
| `src/_core/parallel.cpp` | All 17 Python-callback parallel algorithms; `register_bindings(nb::module_&)`. |
| `src/_core/parallel.hpp` | Forward declarations + `register_bindings`. |
| `src/_core/kernels.cpp` | 5 C++-native kernels (dot, matmul, sum, max, min) × 4 dtypes. |
| `src/_core/kernels.hpp` | Forward decls + `register_bindings`. |
| `src/hpyx/execution.py` | Policy objects (`seq`, `par`, `par_unseq`, `unseq`, `task`) + chunk-size modifiers + `PolicyToken` marshalling. |
| `src/hpyx/parallel.py` | 17 algorithm wrappers; thin dispatch to `_core.parallel`. |
| `src/hpyx/kernels.py` | 5 kernel wrappers; dtype dispatch. |
| `tests/test_execution_policy.py` | Policy composition, chunk-size modifiers, `with_()` chaining. |
| `tests/test_parallel.py` | Tests for all 17 algorithms vs stdlib reference. |
| `tests/test_kernels.py` | Tests for 5 kernels × 4 dtypes vs numpy reference. |
| `tests/test_free_threaded.py` | Race-detection smoke + multi-thread submit via `HPXExecutor`. |

### Modified files

| File | Change |
|---|---|
| `src/_core/bind.cpp` | Register `_core.parallel` and `_core.kernels` submodules. Remove legacy top-level `dot1d` and `hpx_for_loop` bindings. |
| `src/hpyx/__init__.py` | Export `execution`, `parallel`, `kernels`. |
| `src/hpyx/multiprocessing/__init__.py` | Replace with deprecation shim re-exporting `hpyx.parallel.for_loop`. |

### Deleted files

- `src/_core/algorithms.cpp` (the v0.x file) — `dot1d` moves to `kernels.cpp::kernel_dot`, `hpx_for_loop` moves to `parallel.cpp::parallel_for_loop`.
- `src/_core/algorithms.hpp` — same reason.

---

## Execution Notes

- Base branch: `main` with Plans 0 and 1 merged.
- Environment: `pixi run -e test-py313t`.
- Rebuild after C++ changes.
- Commits: Conventional Commits. Stage one logical change per commit — many tasks below produce separate commits.

---

## Task 1: Create implementation branch

- [ ] **Step 1: Update main + branch**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/v1-phase-2-parallel-kernels-execution
pixi run test
```

Record baseline passing set. Expected: everything except `test_for_loop.py` passes (that's the file this plan fixes/rewrites).

---

## Task 2: Add `src/_core/gil_macros.hpp`

**Files:**
- Create: `src/_core/gil_macros.hpp`

- [ ] **Step 1: Write the header**

```cpp
#pragma once

#include <nanobind/nanobind.h>

// HPYX_KERNEL_NOGIL: release the GIL for the scope of a C++ kernel that
// operates on nb::ndarray views and never touches nb::object.
//
// Usage:
//     T kernel_foo(nb::ndarray<const T, nb::c_contig> a) {
//         HPYX_KERNEL_NOGIL;
//         // ... pure C++ work using a.data() ...
//         return result;
//     }
#define HPYX_KERNEL_NOGIL \
    ::nanobind::gil_scoped_release _hpyx_gil_release_

// HPYX_CALLBACK_GIL: acquire the GIL in a lambda that will execute on an
// HPX worker thread and needs to invoke a Python callable.
//
// Usage:
//     auto task = [pyfn](std::int64_t i) {
//         HPYX_CALLBACK_GIL;
//         pyfn(i);
//     };
#define HPYX_CALLBACK_GIL \
    ::nanobind::gil_scoped_acquire _hpyx_gil_acquire_
```

- [ ] **Step 2: Verify it compiles by a quick `#include` test**

No separate build target; these macros are included indirectly once used in Task 3+. No commit yet — commit together with `policy_dispatch.hpp` in Task 3.

---

## Task 3: Add `src/_core/policy_dispatch.hpp`

**Files:**
- Create: `src/_core/policy_dispatch.hpp`

- [ ] **Step 1: Write the header**

```cpp
#pragma once

#include <hpx/execution.hpp>
#include <cstddef>
#include <cstdint>

namespace hpyx::policy {

enum class Kind : std::uint8_t { seq, par, par_unseq, unseq };
enum class ChunkKind : std::uint8_t { none, static_, dynamic_, auto_, guided };

// Compact value type passed across the Python/C++ boundary.
// nanobind binds this as a simple struct.
struct PolicyToken {
    Kind kind;
    bool task;            // combine with policy for async return type
    ChunkKind chunk;
    std::size_t chunk_size;
};

// Translate a PolicyToken into a concrete HPX execution policy and invoke
// `fn` with it. Uses if-constexpr ladders so the compiler inlines one
// policy path per call site.
//
// The caller's `fn` must be a generic lambda taking an auto-policy:
//     dispatch_policy(token, [&](auto&& policy) { hpx::for_loop(policy, ...); });
template <typename Fn>
auto dispatch_policy(PolicyToken t, Fn&& fn) {
    namespace ex = hpx::execution;

    auto with_chunk = [&](auto&& pol) {
        switch (t.chunk) {
        case ChunkKind::none:
            return fn(pol);
        case ChunkKind::static_:
            return fn(pol.with(ex::static_chunk_size(t.chunk_size)));
        case ChunkKind::dynamic_:
            return fn(pol.with(ex::dynamic_chunk_size(t.chunk_size)));
        case ChunkKind::auto_:
            return fn(pol.with(ex::auto_chunk_size()));
        case ChunkKind::guided:
            return fn(pol.with(ex::guided_chunk_size()));
        }
        return fn(pol);
    };

    if (t.task) {
        switch (t.kind) {
        case Kind::seq:
            return with_chunk(ex::seq(ex::task));
        case Kind::par:
            return with_chunk(ex::par(ex::task));
        case Kind::par_unseq:
            return with_chunk(ex::par_unseq(ex::task));
        case Kind::unseq:
            return with_chunk(ex::unseq);  // no task variant
        }
    } else {
        switch (t.kind) {
        case Kind::seq:
            return with_chunk(ex::seq);
        case Kind::par:
            return with_chunk(ex::par);
        case Kind::par_unseq:
            return with_chunk(ex::par_unseq);
        case Kind::unseq:
            return with_chunk(ex::unseq);
        }
    }
    // Unreachable — but makes the compiler happy.
    return with_chunk(ex::seq);
}

}  // namespace hpyx::policy
```

- [ ] **Step 2: Commit both `gil_macros.hpp` and `policy_dispatch.hpp`**

```bash
git add src/_core/gil_macros.hpp src/_core/policy_dispatch.hpp
git commit -m "feat(_core): add gil_macros.hpp and policy_dispatch.hpp"
```

---

## Task 4: Implement `src/hpyx/execution.py`

**Files:**
- Create: `src/hpyx/execution.py`
- Create: `tests/test_execution_policy.py`
- Modify: `src/hpyx/__init__.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_execution_policy.py`:

```python
"""Tests for hpyx.execution policy objects and chunk-size modifiers."""

import pytest

from hpyx import execution as ex


def test_singletons_exist():
    assert ex.seq.name == "seq"
    assert ex.par.name == "par"
    assert ex.par_unseq.name == "par_unseq"
    assert ex.unseq.name == "unseq"


def test_policy_call_with_task_tag_sets_task():
    par_task = ex.par(ex.task)
    assert par_task.task is True
    assert par_task.name == "par"


def test_policy_with_static_chunk_size():
    p = ex.par.with_(ex.static_chunk_size(1000))
    token = p._token()
    assert token.chunk_size == 1000
    # Chunk kind is "static" at the Python layer.
    assert p.chunk_name == "static"


def test_policy_with_dynamic_chunk_size():
    p = ex.par.with_(ex.dynamic_chunk_size(50))
    assert p._token().chunk_size == 50
    assert p.chunk_name == "dynamic"


def test_policy_with_auto_chunk_size():
    p = ex.par.with_(ex.auto_chunk_size())
    assert p.chunk_name == "auto"


def test_policy_with_guided_chunk_size():
    p = ex.par.with_(ex.guided_chunk_size())
    assert p.chunk_name == "guided"


def test_task_policy_with_chunk_size():
    p = ex.par(ex.task).with_(ex.static_chunk_size(100))
    assert p.task is True
    assert p.chunk_name == "static"
    assert p._token().chunk_size == 100


def test_policy_is_immutable():
    # Calling with_() returns a new policy; original is unchanged.
    p1 = ex.par
    p2 = p1.with_(ex.static_chunk_size(10))
    assert p1.chunk_name == "none"
    assert p2.chunk_name == "static"
    assert p1 is not p2


def test_policy_repr():
    assert "par" in repr(ex.par)
    assert "par_task" in repr(ex.par(ex.task)).replace(" ", "_").lower() or \
           "task" in repr(ex.par(ex.task))


def test_non_task_policy_raises_on_task_tag_reapply():
    # par(task)(task) is not meaningful.
    with pytest.raises(TypeError, match="already"):
        ex.par(ex.task)(ex.task)
```

Run: `pixi run -e test-py313t pytest tests/test_execution_policy.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implement `src/hpyx/execution.py`**

```python
"""hpyx.execution — HPX-style execution policies for parallel algorithms.

Usage
-----
    import hpyx
    from hpyx.execution import par, seq, task, static_chunk_size

    hpyx.parallel.for_loop(par, 0, 1_000_000, fn)
    hpyx.parallel.for_loop(par.with_(static_chunk_size(10_000)), ...)

    fut = hpyx.parallel.for_loop(par(task), 0, N, fn)  # returns Future
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# PolicyToken mirrors the C++ struct in policy_dispatch.hpp.
# nanobind marshals it as a small pod.
_KIND_SEQ = 0
_KIND_PAR = 1
_KIND_PAR_UNSEQ = 2
_KIND_UNSEQ = 3

_CHUNK_NONE = 0
_CHUNK_STATIC = 1
_CHUNK_DYNAMIC = 2
_CHUNK_AUTO = 3
_CHUNK_GUIDED = 4


@dataclass(frozen=True)
class _Token:
    """Wire-level token passed to C++. Matches PolicyToken in policy_dispatch.hpp."""
    kind: int
    task: bool
    chunk: int
    chunk_size: int


@dataclass(frozen=True)
class ChunkSize:
    """Opaque holder for a chunk-size strategy."""
    kind: int
    size: int = 0


def static_chunk_size(n: int) -> ChunkSize:
    """Fixed `n` elements per task."""
    if n <= 0:
        raise ValueError(f"static_chunk_size(n) requires n > 0, got {n}")
    return ChunkSize(kind=_CHUNK_STATIC, size=n)


def dynamic_chunk_size(n: int) -> ChunkSize:
    """Dynamic (load-balanced) chunks of `n` elements."""
    if n <= 0:
        raise ValueError(f"dynamic_chunk_size(n) requires n > 0, got {n}")
    return ChunkSize(kind=_CHUNK_DYNAMIC, size=n)


def auto_chunk_size() -> ChunkSize:
    """Let HPX pick chunk size automatically."""
    return ChunkSize(kind=_CHUNK_AUTO)


def guided_chunk_size() -> ChunkSize:
    """Guided (shrinking) chunks."""
    return ChunkSize(kind=_CHUNK_GUIDED)


class _TaskTag:
    """Singleton sentinel for the task modifier."""
    __slots__ = ()
    def __repr__(self) -> str:
        return "task"


task = _TaskTag()


class _Policy:
    """Base execution policy. Frozen at the object level — `with_()` returns copies."""

    __slots__ = ("name", "_kind", "task", "chunk_name", "_chunk_kind", "_chunk_size")

    def __init__(
        self,
        *,
        name: str,
        kind: int,
        task: bool = False,
        chunk_name: str = "none",
        chunk_kind: int = _CHUNK_NONE,
        chunk_size: int = 0,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "task", task)
        object.__setattr__(self, "chunk_name", chunk_name)
        object.__setattr__(self, "_chunk_kind", chunk_kind)
        object.__setattr__(self, "_chunk_size", chunk_size)

    def __setattr__(self, key, value):
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __call__(self, tag):
        if not isinstance(tag, _TaskTag):
            raise TypeError(f"Policy(...) only accepts `task`, got {tag!r}")
        if self.task:
            raise TypeError("Policy already has task tag applied")
        return _Policy(
            name=self.name,
            kind=self._kind,
            task=True,
            chunk_name=self.chunk_name,
            chunk_kind=self._chunk_kind,
            chunk_size=self._chunk_size,
        )

    def with_(self, chunk: ChunkSize) -> "_Policy":
        _chunk_names = {
            _CHUNK_NONE: "none",
            _CHUNK_STATIC: "static",
            _CHUNK_DYNAMIC: "dynamic",
            _CHUNK_AUTO: "auto",
            _CHUNK_GUIDED: "guided",
        }
        return _Policy(
            name=self.name,
            kind=self._kind,
            task=self.task,
            chunk_name=_chunk_names[chunk.kind],
            chunk_kind=chunk.kind,
            chunk_size=chunk.size,
        )

    def _token(self) -> _Token:
        return _Token(
            kind=self._kind,
            task=self.task,
            chunk=self._chunk_kind,
            chunk_size=self._chunk_size,
        )

    def __repr__(self) -> str:
        suffix = ""
        if self.task:
            suffix += "_task"
        if self.chunk_name != "none":
            suffix += f"[{self.chunk_name}]"
        return f"<Policy {self.name}{suffix}>"


# Module-level singletons
seq = _Policy(name="seq", kind=_KIND_SEQ)
par = _Policy(name="par", kind=_KIND_PAR)
par_unseq = _Policy(name="par_unseq", kind=_KIND_PAR_UNSEQ)
unseq = _Policy(name="unseq", kind=_KIND_UNSEQ)


__all__ = [
    "ChunkSize",
    "auto_chunk_size",
    "dynamic_chunk_size",
    "guided_chunk_size",
    "par",
    "par_unseq",
    "seq",
    "static_chunk_size",
    "task",
    "unseq",
]
```

- [ ] **Step 3: Update `src/hpyx/__init__.py`**

Add:

```python
from hpyx import execution
```

And include `"execution"` in `__all__`.

- [ ] **Step 4: Run tests**

```bash
pixi run -e test-py313t pytest tests/test_execution_policy.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/hpyx/execution.py src/hpyx/__init__.py tests/test_execution_policy.py
git commit -m "feat(execution): add policy objects seq/par/par_unseq/unseq + chunk-size modifiers"
```

---

## Task 5: Scaffold `src/_core/parallel.cpp` + first algorithm (`for_loop`)

**Files:**
- Create: `src/_core/parallel.hpp`
- Create: `src/_core/parallel.cpp`
- Create: `src/hpyx/parallel.py`
- Create: `tests/test_parallel.py`
- Modify: `src/_core/bind.cpp`
- Modify: `src/hpyx/__init__.py`

This task establishes the **pattern** every subsequent algorithm follows. Read it carefully — Tasks 6-10 will apply the same shape repeatedly.

- [ ] **Step 1: Write failing test**

Create `tests/test_parallel.py`:

```python
"""Tests for hpyx.parallel — Python-callback parallel algorithms."""

import threading

import pytest

import hpyx
from hpyx.execution import par, par_unseq, seq, static_chunk_size, task, unseq


# ---- for_loop ----

def test_for_loop_seq_calls_body_in_order():
    order = []
    hpyx.parallel.for_loop(seq, 0, 10, lambda i: order.append(i))
    assert order == list(range(10))


def test_for_loop_par_calls_body_for_each_index():
    results = set()
    lock = threading.Lock()

    def body(i):
        with lock:
            results.add(i)

    hpyx.parallel.for_loop(par, 0, 100, body)
    assert results == set(range(100))


def test_for_loop_par_with_chunk_size():
    count = 0
    lock = threading.Lock()

    def body(i):
        nonlocal count
        with lock:
            count += 1

    hpyx.parallel.for_loop(par.with_(static_chunk_size(10)), 0, 1000, body)
    assert count == 1000


def test_for_loop_task_returns_future():
    fut = hpyx.parallel.for_loop(par(task), 0, 10, lambda i: None)
    assert isinstance(fut, hpyx.Future)
    assert fut.result() is None  # for_loop returns void → Future[None]


def test_for_loop_propagates_exception():
    def body(i):
        if i == 5:
            raise ValueError(f"fail at {i}")

    with pytest.raises(ValueError):
        hpyx.parallel.for_loop(par, 0, 10, body)
```

Run: `pixi run -e test-py313t pytest tests/test_parallel.py::test_for_loop_seq_calls_body_in_order -v`
Expected: FAIL (`AttributeError: module 'hpyx' has no attribute 'parallel'`).

- [ ] **Step 2: Write `src/_core/parallel.hpp`**

```cpp
#pragma once

#include <nanobind/nanobind.h>

namespace hpyx::parallel {

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::parallel
```

- [ ] **Step 3: Write `src/_core/parallel.cpp` with `for_loop`**

```cpp
#include "parallel.hpp"
#include "gil_macros.hpp"
#include "policy_dispatch.hpp"
#include "futures.hpp"
#include "runtime.hpp"

#include <hpx/algorithm.hpp>
#include <hpx/async.hpp>
#include <hpx/parallel/algorithms/for_loop.hpp>
#include <hpx/parallel/algorithms/for_each.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <nanobind/trampoline.h>

#include <cstdint>
#include <stdexcept>
#include <variant>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::parallel {

namespace {

void ensure_runtime() {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
}

}  // namespace

// ---- for_loop ----

static void parallel_for_loop(
    hpyx::policy::PolicyToken tok,
    std::int64_t first,
    std::int64_t last,
    nb::callable body)
{
    ensure_runtime();

    auto pyfn = [body](std::int64_t i) {
        HPYX_CALLBACK_GIL;
        body(i);
    };

    // Release the GIL around the HPX call; the lambda reacquires per-iteration.
    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::experimental::for_loop(policy, first, last, pyfn);
    });
}

static hpyx::futures::HPXFuture parallel_for_loop_task(
    hpyx::policy::PolicyToken tok,
    std::int64_t first,
    std::int64_t last,
    nb::callable body)
{
    ensure_runtime();

    auto pyfn = [body](std::int64_t i) {
        HPYX_CALLBACK_GIL;
        body(i);
    };

    nb::gil_scoped_release release;
    // par(task) etc. cause algorithms to return hpx::future<void>; we wrap
    // that in an HPXFuture<nb::object> by then-chaining to produce None.
    auto void_fut = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::experimental::for_loop(policy, first, last, pyfn);
    });
    auto obj_fut = void_fut.then([](auto&& f) -> nb::object {
        f.get();
        nb::gil_scoped_acquire acquire;
        return nb::none();
    }).share();
    return hpyx::futures::HPXFuture(std::move(obj_fut));
}

void register_bindings(nb::module_& m) {
    // Bind PolicyToken as a plain struct.
    nb::class_<hpyx::policy::PolicyToken>(m, "PolicyToken")
        .def(nb::init<>())
        .def_rw("kind", &hpyx::policy::PolicyToken::kind)
        .def_rw("task", &hpyx::policy::PolicyToken::task)
        .def_rw("chunk", &hpyx::policy::PolicyToken::chunk)
        .def_rw("chunk_size", &hpyx::policy::PolicyToken::chunk_size);

    m.def("for_loop", &parallel_for_loop,
          "policy"_a, "first"_a, "last"_a, "body"_a);
    m.def("for_loop_task", &parallel_for_loop_task,
          "policy"_a, "first"_a, "last"_a, "body"_a);
}

}  // namespace hpyx::parallel
```

Note the cast of `Kind` / `ChunkKind` enums to `std::uint8_t` for `def_rw` — nanobind prefers plain integers. If compile errors occur, bind the fields as `int` by adjusting the struct fields or adding explicit casts.

- [ ] **Step 4: Register submodule in `bind.cpp`**

In `src/_core/bind.cpp`, add after the futures submodule registration:

```cpp
auto m_parallel = m.def_submodule("parallel");
hpyx::parallel::register_bindings(m_parallel);
```

Add `#include "parallel.hpp"` at the top.

Remove the legacy `m.def("hpx_for_loop", &algorithms::hpx_for_loop, ...)` binding — `parallel.for_loop` replaces it.

- [ ] **Step 5: Write `src/hpyx/parallel.py`**

```python
"""hpyx.parallel — Python-callback parallel algorithms over integer ranges
and iterables.

Every function takes a policy (from `hpyx.execution`) as the first
argument. When the policy carries the `task` tag, the function returns
an `hpyx.Future[T]` instead of the synchronous result.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Union

from hpyx import _core, _runtime
from hpyx.execution import _Policy
from hpyx.futures import Future


def _token_of(policy: _Policy) -> Any:
    """Convert a Python _Policy into a _core PolicyToken."""
    tok = _core.parallel.PolicyToken()
    t = policy._token()
    tok.kind = t.kind
    tok.task = t.task
    tok.chunk = t.chunk
    tok.chunk_size = t.chunk_size
    return tok


def for_loop(
    policy: _Policy,
    first: int,
    last: int,
    body: Callable[[int], None],
) -> Union[None, Future]:
    """Invoke `body(i)` for i in [first, last) under `policy`.

    If `policy` has the `task` tag, returns a Future[None]. Otherwise
    blocks until all iterations complete.
    """
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        raw = _core.parallel.for_loop_task(tok, first, last, body)
        return Future(raw)
    _core.parallel.for_loop(tok, first, last, body)
    return None


__all__ = ["for_loop"]
```

- [ ] **Step 6: Export `hpyx.parallel`**

In `src/hpyx/__init__.py`, add:

```python
from hpyx import parallel
```

and include `"parallel"` in `__all__`.

- [ ] **Step 7: Rebuild and run tests**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_parallel.py -v
```

Expected: all five `for_loop` tests pass. If `test_for_loop_par_with_chunk_size` fails because HPX's chunk_size API differs slightly, check the `.with()` call in `policy_dispatch.hpp` — newer HPX uses `.with_cs(...)` or drops the namespace.

- [ ] **Step 8: Commit**

```bash
git add src/_core/parallel.* src/_core/bind.cpp src/hpyx/parallel.py src/hpyx/__init__.py tests/test_parallel.py
git commit -m "feat(_core/parallel,hpyx.parallel): add for_loop with PolicyToken dispatch"
```

---

## Task 6: Add `for_each` (second algorithm in iteration family)

**Files:**
- Modify: `src/_core/parallel.cpp` (add two functions: `parallel_for_each` + `_task` variant)
- Modify: `src/hpyx/parallel.py` (add `for_each` wrapper)
- Modify: `tests/test_parallel.py` (add `for_each` tests)

This task follows the same pattern as Task 5. Subsequent algorithm tasks are shorter.

- [ ] **Step 1: Write failing tests** (append to `tests/test_parallel.py`):

```python
# ---- for_each ----

def test_for_each_seq_mutates_in_order():
    data = [0, 1, 2, 3, 4]
    result = []
    hpyx.parallel.for_each(seq, data, lambda x: result.append(x))
    assert result == [0, 1, 2, 3, 4]


def test_for_each_par_visits_every_element():
    data = list(range(50))
    result = set()
    lock = threading.Lock()

    def visit(x):
        with lock:
            result.add(x)

    hpyx.parallel.for_each(par, data, visit)
    assert result == set(range(50))


def test_for_each_task_returns_future():
    fut = hpyx.parallel.for_each(par(task), [1, 2, 3], lambda x: None)
    assert isinstance(fut, hpyx.Future)
    assert fut.result() is None
```

- [ ] **Step 2: Add `parallel_for_each` in `src/_core/parallel.cpp`**

Under `for_loop`, add:

```cpp
// ---- for_each ----

static void parallel_for_each(
    hpyx::policy::PolicyToken tok,
    nb::iterable iterable,
    nb::callable body)
{
    ensure_runtime();

    // Materialize the iterable into a vector<nb::object> so HPX algorithms
    // can use random-access iterators. This is fine for moderate sizes;
    // for huge generators, users should use hpyx.parallel.for_loop over
    // an index range.
    std::vector<nb::object> items;
    for (auto item : iterable) {
        items.push_back(nb::borrow(item));
    }

    auto pyfn = [body](nb::object& item) {
        HPYX_CALLBACK_GIL;
        body(item);
    };

    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::for_each(policy, items.begin(), items.end(), pyfn);
    });
}

static hpyx::futures::HPXFuture parallel_for_each_task(
    hpyx::policy::PolicyToken tok,
    nb::iterable iterable,
    nb::callable body)
{
    ensure_runtime();
    std::vector<nb::object> items;
    for (auto item : iterable) {
        items.push_back(nb::borrow(item));
    }
    auto pyfn = [body](nb::object& item) {
        HPYX_CALLBACK_GIL;
        body(item);
    };
    nb::gil_scoped_release release;
    auto void_fut = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::for_each(policy, items.begin(), items.end(), pyfn);
    });
    auto obj_fut = void_fut.then([items](auto&& f) -> nb::object {
        f.get();
        nb::gil_scoped_acquire acquire;
        return nb::none();
    }).share();
    return hpyx::futures::HPXFuture(std::move(obj_fut));
}
```

Update `register_bindings`:

```cpp
    m.def("for_each", &parallel_for_each,
          "policy"_a, "iterable"_a, "body"_a);
    m.def("for_each_task", &parallel_for_each_task,
          "policy"_a, "iterable"_a, "body"_a);
```

- [ ] **Step 3: Add `for_each` wrapper in `src/hpyx/parallel.py`**

```python
def for_each(
    policy: _Policy,
    iterable,
    fn: Callable[[Any], None],
) -> Union[None, Future]:
    """Apply `fn(x)` to every element in `iterable` under `policy`."""
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        raw = _core.parallel.for_each_task(tok, iterable, fn)
        return Future(raw)
    _core.parallel.for_each(tok, iterable, fn)
    return None
```

Add `"for_each"` to `__all__`.

- [ ] **Step 4: Rebuild + test**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_parallel.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/_core/parallel.cpp src/hpyx/parallel.py tests/test_parallel.py
git commit -m "feat(parallel): add for_each"
```

---

## Task 7: Transform/reduce family — `transform`, `reduce`, `transform_reduce`

**Files:** Same as Task 6 (add three more algorithms to `parallel.cpp` + `parallel.py` + tests).

- [ ] **Step 1: Write failing tests** (append to `tests/test_parallel.py`):

```python
# ---- transform ----

def test_transform_seq_copies_with_fn():
    src = list(range(10))
    dst = [None] * 10
    hpyx.parallel.transform(seq, src, dst, lambda x: x * 2)
    assert dst == [x * 2 for x in src]


def test_transform_par():
    src = list(range(100))
    dst = [None] * 100
    hpyx.parallel.transform(par, src, dst, lambda x: x + 1)
    assert dst == [x + 1 for x in src]


# ---- reduce ----

def test_reduce_default_is_sum():
    assert hpyx.parallel.reduce(par, range(100)) == sum(range(100))


def test_reduce_with_op():
    import operator
    assert hpyx.parallel.reduce(par, range(1, 6), init=1, op=operator.mul) == 120


def test_reduce_positional_init_rejected():
    # Per spec §4.6: init is keyword-only to avoid footguns.
    import operator
    with pytest.raises(TypeError):
        hpyx.parallel.reduce(par, [1, 2, 3], 0, operator.mul)


# ---- transform_reduce ----

def test_transform_reduce_sum_of_squares():
    import operator
    result = hpyx.parallel.transform_reduce(
        par, range(10),
        init=0, reduce_op=operator.add, transform_op=lambda x: x * x,
    )
    assert result == sum(x * x for x in range(10))


def test_transform_reduce_task_returns_future():
    import operator
    fut = hpyx.parallel.transform_reduce(
        par(task), range(10),
        init=0, reduce_op=operator.add, transform_op=lambda x: x,
    )
    assert isinstance(fut, hpyx.Future)
    assert fut.result() == sum(range(10))
```

- [ ] **Step 2: Implement in `src/_core/parallel.cpp`**

Following the same structure as `for_each`, add:

```cpp
// ---- transform ----

static void parallel_transform(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::list dst,          // mutable list to write into
    nb::callable fn)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto dst_size = nb::len(dst);
    if (dst_size < src.size()) {
        throw std::invalid_argument(
            "transform: dst is smaller than src");
    }

    auto pyfn = [fn](nb::object& x) -> nb::object {
        HPYX_CALLBACK_GIL;
        return fn(x);
    };

    std::vector<nb::object> out(src.size());
    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::transform(policy, src.begin(), src.end(), out.begin(), pyfn);
    });

    // Copy back into dst (requires GIL).
    nb::gil_scoped_acquire acquire;
    for (std::size_t i = 0; i < out.size(); ++i) {
        PyList_SET_ITEM(dst.ptr(), i, out[i].release().ptr());
    }
}

// ---- reduce ----

static nb::object parallel_reduce(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::object init,
    nb::callable op)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto reducer = [op](nb::object& a, nb::object& b) -> nb::object {
        HPYX_CALLBACK_GIL;
        return op(a, b);
    };

    nb::object result;
    {
        nb::gil_scoped_release release;
        auto raw_result = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
            return hpx::reduce(policy, src.begin(), src.end(),
                               init, reducer);
        });
        result = raw_result;  // raw_result is already nb::object
    }
    return result;
}

// ---- transform_reduce ----

static nb::object parallel_transform_reduce(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::object init,
    nb::callable reduce_op,
    nb::callable transform_op)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto red = [reduce_op](nb::object& a, nb::object& b) -> nb::object {
        HPYX_CALLBACK_GIL;
        return reduce_op(a, b);
    };
    auto tr = [transform_op](nb::object& x) -> nb::object {
        HPYX_CALLBACK_GIL;
        return transform_op(x);
    };

    nb::object result;
    {
        nb::gil_scoped_release release;
        auto raw = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
            return hpx::transform_reduce(
                policy, src.begin(), src.end(),
                init, red, tr);
        });
        result = raw;
    }
    return result;
}
```

Register:

```cpp
    m.def("transform", &parallel_transform,
          "policy"_a, "src"_a, "dst"_a, "fn"_a);
    m.def("reduce", &parallel_reduce,
          "policy"_a, "src"_a, "init"_a, "op"_a);
    m.def("transform_reduce", &parallel_transform_reduce,
          "policy"_a, "src"_a, "init"_a, "reduce_op"_a, "transform_op"_a);
```

For task variants, add `_task` functions that wrap the appropriate `hpx::future<T>`-returning call and convert to `HPXFuture`. Pattern is identical to `for_loop_task`/`for_each_task`.

- [ ] **Step 3: Add wrappers to `src/hpyx/parallel.py`**

```python
import operator


def _identity(x):
    return x


def transform(
    policy: _Policy,
    src,
    dst,
    fn: Callable[[Any], Any],
) -> Union[None, Future]:
    """Write `fn(x)` for each `x in src` into `dst[i]`."""
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        raw = _core.parallel.transform_task(tok, src, dst, fn)
        return Future(raw)
    _core.parallel.transform(tok, src, dst, fn)
    return None


def reduce(
    policy: _Policy,
    iterable,
    *,
    init=0,
    op: Callable[[Any, Any], Any] = operator.add,
) -> Union[Any, Future]:
    """Fold `op` over `iterable` starting from `init`."""
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        raw = _core.parallel.reduce_task(tok, iterable, init, op)
        return Future(raw)
    return _core.parallel.reduce(tok, iterable, init, op)


def transform_reduce(
    policy: _Policy,
    iterable,
    *,
    init=0,
    reduce_op: Callable[[Any, Any], Any] = operator.add,
    transform_op: Callable[[Any], Any] = _identity,
) -> Union[Any, Future]:
    """Apply `transform_op` to each element, then fold with `reduce_op`."""
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        raw = _core.parallel.transform_reduce_task(
            tok, iterable, init, reduce_op, transform_op)
        return Future(raw)
    return _core.parallel.transform_reduce(
        tok, iterable, init, reduce_op, transform_op)
```

Add to `__all__`: `"reduce"`, `"transform"`, `"transform_reduce"`.

- [ ] **Step 4: Rebuild + test + commit**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_parallel.py -v
git add -A
git commit -m "feat(parallel): add transform, reduce, transform_reduce"
```

---

## Task 8: Search family — `count`, `count_if`, `find`, `find_if`, `all_of`, `any_of`, `none_of`

Seven algorithms following the reduce-like pattern (return a scalar from a sequence). All wrap `nb::object`-based iterables.

- [ ] **Step 1: Tests (append to `tests/test_parallel.py`)**

```python
# ---- count family ----

def test_count():
    data = [1, 2, 3, 2, 1, 2]
    assert hpyx.parallel.count(par, data, 2) == 3


def test_count_if():
    assert hpyx.parallel.count_if(par, range(100), lambda x: x % 2 == 0) == 50


# ---- find family ----

def test_find_returns_index_or_minus_one():
    assert hpyx.parallel.find(par, [10, 20, 30, 40], 30) == 2
    assert hpyx.parallel.find(par, [10, 20, 30], 99) == -1


def test_find_if():
    assert hpyx.parallel.find_if(par, [1, 2, 3, 4], lambda x: x > 2) == 2
    assert hpyx.parallel.find_if(par, [1, 2], lambda x: x > 99) == -1


# ---- logical all/any/none ----

def test_all_of():
    assert hpyx.parallel.all_of(par, range(10), lambda x: x >= 0) is True
    assert hpyx.parallel.all_of(par, range(10), lambda x: x >= 5) is False


def test_any_of():
    assert hpyx.parallel.any_of(par, range(10), lambda x: x == 5) is True
    assert hpyx.parallel.any_of(par, range(10), lambda x: x > 99) is False


def test_none_of():
    assert hpyx.parallel.none_of(par, range(10), lambda x: x > 99) is True
    assert hpyx.parallel.none_of(par, range(10), lambda x: x == 5) is False
```

- [ ] **Step 2: C++ implementations**

Each follows the same shape as `reduce`: materialize iterable into `std::vector<nb::object>`, release GIL, dispatch policy, call `hpx::count` / `hpx::count_if` / etc., return the scalar.

Add to `src/_core/parallel.cpp`:

```cpp
// ---- count / count_if ----

static std::int64_t parallel_count(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::object value)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    // Custom equality — use Python rich-compare so user-defined __eq__ works.
    // This requires GIL per comparison, so mark carefully.
    auto eq = [value](nb::object const& a, nb::object const& b) -> bool {
        HPYX_CALLBACK_GIL;
        return a.equal(b);
    };
    // We implement count as count_if because hpx::count wants an equality
    // predicate we can't cleanly pass as a value.
    auto pred = [value](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL;
        return x.equal(value);
    };

    nb::gil_scoped_release release;
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return static_cast<std::int64_t>(
            hpx::count_if(policy, src.begin(), src.end(), pred));
    });
}

static std::int64_t parallel_count_if(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::callable pred)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto cxx_pred = [pred](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL;
        return nb::cast<bool>(pred(x));
    };

    nb::gil_scoped_release release;
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return static_cast<std::int64_t>(
            hpx::count_if(policy, src.begin(), src.end(), cxx_pred));
    });
}

// ---- find / find_if ----

static std::int64_t parallel_find(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::object value)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto pred = [value](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL;
        return x.equal(value);
    };

    nb::gil_scoped_release release;
    auto it = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::find_if(policy, src.begin(), src.end(), pred);
    });
    if (it == src.end()) return -1;
    return static_cast<std::int64_t>(it - src.begin());
}

static std::int64_t parallel_find_if(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::callable pred)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));

    auto cxx_pred = [pred](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL;
        return nb::cast<bool>(pred(x));
    };

    nb::gil_scoped_release release;
    auto it = hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::find_if(policy, src.begin(), src.end(), cxx_pred);
    });
    if (it == src.end()) return -1;
    return static_cast<std::int64_t>(it - src.begin());
}

// ---- all_of / any_of / none_of ----

static bool parallel_all_of(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::callable pred)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));
    auto cxx_pred = [pred](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL; return nb::cast<bool>(pred(x));
    };
    nb::gil_scoped_release release;
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::all_of(policy, src.begin(), src.end(), cxx_pred);
    });
}

static bool parallel_any_of(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::callable pred)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));
    auto cxx_pred = [pred](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL; return nb::cast<bool>(pred(x));
    };
    nb::gil_scoped_release release;
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::any_of(policy, src.begin(), src.end(), cxx_pred);
    });
}

static bool parallel_none_of(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it,
    nb::callable pred)
{
    ensure_runtime();
    std::vector<nb::object> src;
    for (auto item : src_it) src.push_back(nb::borrow(item));
    auto cxx_pred = [pred](nb::object const& x) -> bool {
        HPYX_CALLBACK_GIL; return nb::cast<bool>(pred(x));
    };
    nb::gil_scoped_release release;
    return hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        return hpx::none_of(policy, src.begin(), src.end(), cxx_pred);
    });
}
```

Register all seven in `register_bindings`:

```cpp
    m.def("count",     &parallel_count,     "policy"_a, "src"_a, "value"_a);
    m.def("count_if",  &parallel_count_if,  "policy"_a, "src"_a, "pred"_a);
    m.def("find",      &parallel_find,      "policy"_a, "src"_a, "value"_a);
    m.def("find_if",   &parallel_find_if,   "policy"_a, "src"_a, "pred"_a);
    m.def("all_of",    &parallel_all_of,    "policy"_a, "src"_a, "pred"_a);
    m.def("any_of",    &parallel_any_of,    "policy"_a, "src"_a, "pred"_a);
    m.def("none_of",   &parallel_none_of,   "policy"_a, "src"_a, "pred"_a);
```

Include: `<hpx/parallel/algorithms/count.hpp>`, `<hpx/parallel/algorithms/find.hpp>`, `<hpx/parallel/algorithms/all_any_none.hpp>`.

- [ ] **Step 3: Python wrappers**

Add to `src/hpyx/parallel.py`:

```python
def count(policy, iterable, value) -> Union[int, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.count_task(tok, iterable, value))
    return int(_core.parallel.count(tok, iterable, value))


def count_if(policy, iterable, pred) -> Union[int, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.count_if_task(tok, iterable, pred))
    return int(_core.parallel.count_if(tok, iterable, pred))


def find(policy, iterable, value) -> Union[int, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.find_task(tok, iterable, value))
    return int(_core.parallel.find(tok, iterable, value))


def find_if(policy, iterable, pred) -> Union[int, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.find_if_task(tok, iterable, pred))
    return int(_core.parallel.find_if(tok, iterable, pred))


def all_of(policy, iterable, pred) -> Union[bool, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.all_of_task(tok, iterable, pred))
    return bool(_core.parallel.all_of(tok, iterable, pred))


def any_of(policy, iterable, pred) -> Union[bool, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.any_of_task(tok, iterable, pred))
    return bool(_core.parallel.any_of(tok, iterable, pred))


def none_of(policy, iterable, pred) -> Union[bool, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.none_of_task(tok, iterable, pred))
    return bool(_core.parallel.none_of(tok, iterable, pred))
```

Extend `__all__`.

Note on `_task` variants: for this family, the synchronous versions already don't take long enough to benefit much from `task`. Still, implement the `_task` C++ variant for each (per the pattern in Task 5 step 3). Tests should cover at least one task-variant per family, but not all seven — add `test_any_of_task_returns_future` as a representative.

- [ ] **Step 4: Rebuild + test + commit**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_parallel.py -v
git add -A
git commit -m "feat(parallel): add count, count_if, find, find_if, all_of, any_of, none_of"
```

---

## Task 9: Sort family — `sort`, `stable_sort`

- [ ] **Step 1: Tests**

```python
# ---- sort ----

def test_sort_par_ascending():
    data = [3, 1, 4, 1, 5, 9, 2, 6]
    hpyx.parallel.sort(par, data)
    assert data == sorted([3, 1, 4, 1, 5, 9, 2, 6])


def test_sort_par_descending():
    data = list(range(10))
    hpyx.parallel.sort(par, data, reverse=True)
    assert data == sorted(range(10), reverse=True)


def test_sort_with_key():
    data = ["banana", "apple", "cherry"]
    hpyx.parallel.sort(par, data, key=len)
    assert data == ["apple", "banana", "cherry"]


def test_stable_sort_preserves_order_for_equal_keys():
    # Tuples (key, original_index); sort by key should preserve order.
    data = [(1, "a"), (2, "b"), (1, "c"), (2, "d"), (1, "e")]
    hpyx.parallel.stable_sort(par, data, key=lambda t: t[0])
    # Items with key 1 come in original relative order: a, c, e.
    ones = [t for t in data if t[0] == 1]
    assert ones == [(1, "a"), (1, "c"), (1, "e")]
```

- [ ] **Step 2: C++**

```cpp
// ---- sort / stable_sort ----

static void parallel_sort(
    hpyx::policy::PolicyToken tok,
    nb::list data,
    nb::object key,     // None or callable
    bool reverse)
{
    ensure_runtime();

    std::size_t n = nb::len(data);
    std::vector<nb::object> vec;
    vec.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        vec.push_back(nb::borrow(data[i]));
    }

    bool have_key = !key.is_none();
    nb::callable key_fn;
    if (have_key) key_fn = nb::cast<nb::callable>(key);

    auto cmp = [have_key, key_fn, reverse](
        nb::object const& a, nb::object const& b) -> bool {
        HPYX_CALLBACK_GIL;
        nb::object ka = have_key ? nb::object(key_fn(a)) : a;
        nb::object kb = have_key ? nb::object(key_fn(b)) : b;
        bool lt = nb::cast<bool>(ka.less(kb));
        return reverse ? !lt && !nb::cast<bool>(ka.equal(kb)) : lt;
    };

    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::sort(policy, vec.begin(), vec.end(), cmp);
    });

    // Write sorted vec back into `data`.
    nb::gil_scoped_acquire acquire;
    for (std::size_t i = 0; i < n; ++i) {
        PyList_SET_ITEM(data.ptr(), i, vec[i].release().ptr());
    }
}

static void parallel_stable_sort(
    hpyx::policy::PolicyToken tok,
    nb::list data,
    nb::object key,
    bool reverse)
{
    // Same as sort but calls hpx::stable_sort.
    ensure_runtime();
    std::size_t n = nb::len(data);
    std::vector<nb::object> vec;
    vec.reserve(n);
    for (std::size_t i = 0; i < n; ++i) vec.push_back(nb::borrow(data[i]));

    bool have_key = !key.is_none();
    nb::callable key_fn;
    if (have_key) key_fn = nb::cast<nb::callable>(key);
    auto cmp = [have_key, key_fn, reverse](
        nb::object const& a, nb::object const& b) -> bool {
        HPYX_CALLBACK_GIL;
        nb::object ka = have_key ? nb::object(key_fn(a)) : a;
        nb::object kb = have_key ? nb::object(key_fn(b)) : b;
        bool lt = nb::cast<bool>(ka.less(kb));
        return reverse ? !lt && !nb::cast<bool>(ka.equal(kb)) : lt;
    };
    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::stable_sort(policy, vec.begin(), vec.end(), cmp);
    });
    nb::gil_scoped_acquire acquire;
    for (std::size_t i = 0; i < n; ++i) {
        PyList_SET_ITEM(data.ptr(), i, vec[i].release().ptr());
    }
}
```

Register `sort` and `stable_sort`. Include: `<hpx/parallel/algorithms/sort.hpp>`, `<hpx/parallel/algorithms/stable_sort.hpp>`.

- [ ] **Step 3: Python**

```python
def sort(policy, data, *, key=None, reverse=False) -> Union[None, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.sort_task(tok, data, key, reverse))
    _core.parallel.sort(tok, data, key, reverse)
    return None


def stable_sort(policy, data, *, key=None, reverse=False) -> Union[None, Future]:
    _runtime.ensure_started()
    tok = _token_of(policy)
    if policy.task:
        return Future(_core.parallel.stable_sort_task(tok, data, key, reverse))
    _core.parallel.stable_sort(tok, data, key, reverse)
    return None
```

Extend `__all__`. Add `sort_task` / `stable_sort_task` C++ variants.

- [ ] **Step 4: Rebuild + test + commit**

```bash
git add -A
git commit -m "feat(parallel): add sort and stable_sort"
```

---

## Task 10: Fill / copy / iota — `fill`, `fill_n`, `copy`, `copy_if`, `iota`

Five mechanical algorithms — see `hpx/parallel/algorithms/fill.hpp`, `copy.hpp`, `iota.hpp`. Follow the same pattern as Tasks 5-9.

Tests (append to `tests/test_parallel.py`):

```python
# ---- fill / fill_n / copy / copy_if / iota ----

def test_fill():
    data = [None] * 10
    hpyx.parallel.fill(par, data, "X")
    assert data == ["X"] * 10


def test_fill_n():
    data = [None] * 10
    hpyx.parallel.fill_n(par, data, 5, "Y")
    assert data[:5] == ["Y"] * 5
    assert data[5:] == [None] * 5


def test_copy():
    src = list(range(10))
    dst = [None] * 10
    hpyx.parallel.copy(par, src, dst)
    assert dst == src


def test_copy_if():
    src = list(range(10))
    dst = [None] * 10
    n = hpyx.parallel.copy_if(par, src, dst, lambda x: x % 2 == 0)
    assert dst[:n] == [0, 2, 4, 6, 8]


def test_iota():
    data = [None] * 5
    hpyx.parallel.iota(par, data, start=10)
    assert data == [10, 11, 12, 13, 14]
```

C++ pattern for `fill`:

```cpp
static void parallel_fill(
    hpyx::policy::PolicyToken tok,
    nb::list data,
    nb::object value)
{
    ensure_runtime();
    std::size_t n = nb::len(data);
    std::vector<nb::object> vec(n, value);

    nb::gil_scoped_release release;
    hpyx::policy::dispatch_policy(tok, [&](auto&& policy) {
        hpx::fill(policy, vec.begin(), vec.end(), value);
    });

    nb::gil_scoped_acquire acquire;
    for (std::size_t i = 0; i < n; ++i) {
        PyList_SET_ITEM(data.ptr(), i, vec[i].release().ptr());
    }
}
```

Similar shapes for the other four; see `src/_core/parallel.cpp` after merging.

Python wrappers:

```python
def fill(policy, data, value) -> Union[None, Future]: ...
def fill_n(policy, data, n, value) -> Union[None, Future]: ...
def copy(policy, src, dst) -> Union[None, Future]: ...
def copy_if(policy, src, dst, pred) -> Union[int, Future]: ...
def iota(policy, data, start=0) -> Union[None, Future]: ...
```

Commit as `feat(parallel): add fill, fill_n, copy, copy_if, iota`.

---

## Task 11: Scan family — `inclusive_scan`, `exclusive_scan`

Two algorithms. Tests + C++ + Python wrappers following the pattern.

Tests:

```python
# ---- scans ----

def test_inclusive_scan():
    import operator
    src = [1, 2, 3, 4, 5]
    dst = [None] * 5
    hpyx.parallel.inclusive_scan(par, src, dst, op=operator.add)
    assert dst == [1, 3, 6, 10, 15]


def test_exclusive_scan():
    import operator
    src = [1, 2, 3, 4, 5]
    dst = [None] * 5
    hpyx.parallel.exclusive_scan(par, src, dst, init=0, op=operator.add)
    assert dst == [0, 1, 3, 6, 10]
```

C++ signatures:

```cpp
static void parallel_inclusive_scan(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it, nb::list dst,
    nb::callable op, nb::object init);

static void parallel_exclusive_scan(
    hpyx::policy::PolicyToken tok,
    nb::iterable src_it, nb::list dst,
    nb::object init, nb::callable op);
```

Python wrappers with keyword-only args (per spec §4.6):

```python
def inclusive_scan(policy, src, dst, *, op=operator.add, init=None) -> ...:
    ...

def exclusive_scan(policy, src, dst, *, init=0, op=operator.add) -> ...:
    ...
```

Include: `<hpx/parallel/algorithms/inclusive_scan.hpp>`, `<hpx/parallel/algorithms/exclusive_scan.hpp>`.

Commit as `feat(parallel): add inclusive_scan, exclusive_scan`.

---

## Task 12: Create `src/_core/kernels.cpp` with `kernel_dot`

**Files:**
- Create: `src/_core/kernels.hpp`
- Create: `src/_core/kernels.cpp` (absorbs the old `dot1d` from `algorithms.cpp`)
- Create: `src/hpyx/kernels.py`
- Create: `tests/test_kernels.py`
- Modify: `src/_core/bind.cpp` (add submodule + remove old `dot1d`)
- Delete: `src/_core/algorithms.cpp`, `src/_core/algorithms.hpp`
- Modify: `src/hpyx/__init__.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_kernels.py`:

```python
"""Tests for hpyx.kernels — C++-native kernels over numpy arrays."""

import numpy as np
import pytest

import hpyx


# ---- dot ----

@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.int64])
def test_dot_matches_numpy(dtype):
    rng = np.random.default_rng(0)
    n = 10_000
    a = rng.random(n).astype(dtype) if np.issubdtype(dtype, np.floating) \
        else rng.integers(0, 100, size=n, dtype=dtype)
    b = rng.random(n).astype(dtype) if np.issubdtype(dtype, np.floating) \
        else rng.integers(0, 100, size=n, dtype=dtype)
    hp = hpyx.kernels.dot(a, b)
    ref = np.dot(a, b)
    np.testing.assert_allclose(hp, ref, rtol=1e-6)


def test_dot_size_mismatch_raises():
    a = np.ones(10, dtype=np.float64)
    b = np.ones(11, dtype=np.float64)
    with pytest.raises(ValueError, match="size"):
        hpyx.kernels.dot(a, b)


def test_dot_unsupported_dtype_raises():
    a = np.ones(10, dtype=np.float16)
    b = np.ones(10, dtype=np.float16)
    with pytest.raises(TypeError, match="dtype"):
        hpyx.kernels.dot(a, b)


def test_dot_non_contiguous_raises():
    a = np.arange(100, dtype=np.float64)[::2]  # non-contig
    b = np.arange(100, dtype=np.float64)[::2]
    with pytest.raises(TypeError, match="contiguous"):
        hpyx.kernels.dot(a, b)
```

- [ ] **Step 2: Write `src/_core/kernels.hpp`**

```cpp
#pragma once
#include <nanobind/nanobind.h>

namespace hpyx::kernels {

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::kernels
```

- [ ] **Step 3: Write `src/_core/kernels.cpp`**

```cpp
#include "kernels.hpp"
#include "gil_macros.hpp"
#include "runtime.hpp"

#include <hpx/algorithm.hpp>
#include <hpx/execution.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>

#include <cstdint>
#include <functional>
#include <stdexcept>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::kernels {

namespace {

void ensure_runtime() {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
}

}  // namespace

// ---- dot ----

template <typename T>
static double kernel_dot(
    nb::ndarray<const T, nb::c_contig> a,
    nb::ndarray<const T, nb::c_contig> b)
{
    ensure_runtime();
    if (a.size() != b.size()) {
        throw std::invalid_argument(
            "kernels.dot: input size mismatch (a=" + std::to_string(a.size())
            + ", b=" + std::to_string(b.size()) + ")");
    }
    const T* ap = a.data();
    const T* bp = b.data();
    std::size_t n = a.size();

    HPYX_KERNEL_NOGIL;
    return static_cast<double>(
        hpx::transform_reduce(
            hpx::execution::par,
            ap, ap + n, bp,
            T{0},
            std::plus<T>{},
            std::multiplies<T>{}));
}

void register_bindings(nb::module_& m) {
    m.def("dot", &kernel_dot<float>,    "a"_a, "b"_a);
    m.def("dot", &kernel_dot<double>,   "a"_a, "b"_a);
    m.def("dot", &kernel_dot<int32_t>,  "a"_a, "b"_a);
    m.def("dot", &kernel_dot<int64_t>,  "a"_a, "b"_a);
    // Later kernels (matmul, sum, max, min) added here.
}

}  // namespace hpyx::kernels
```

- [ ] **Step 4: Update `bind.cpp`**

Add after the parallel submodule:

```cpp
auto m_kernels = m.def_submodule("kernels");
hpyx::kernels::register_bindings(m_kernels);
```

Add `#include "kernels.hpp"`. Remove `algorithms.hpp` include. Remove the top-level `m.def("dot1d", ...)` entry (the test file `test_hpx_linalg.py` tests `hpyx.kernels.dot` now — update that test too if needed).

- [ ] **Step 5: Delete legacy algorithms.* files**

```bash
git rm src/_core/algorithms.cpp src/_core/algorithms.hpp
```

Update `CMakeLists.txt` to remove the reference:

```cmake
nanobind_add_module(
    _core
    FREE_THREADED
    src/_core/bind.cpp
    src/_core/runtime.cpp
    src/_core/futures.cpp
    src/_core/parallel.cpp
    src/_core/kernels.cpp
    # algorithms.cpp removed
)
```

- [ ] **Step 6: Write `src/hpyx/kernels.py`**

```python
"""hpyx.kernels — C++-native kernels over numpy arrays.

All kernels accept float32, float64, int32, int64 and release the GIL
for the full duration (no Python callbacks in these hot paths).
"""

from __future__ import annotations

import numpy as np

from hpyx import _core, _runtime

_SUPPORTED_DTYPES = {np.float32, np.float64, np.int32, np.int64}


def _check(arr: np.ndarray, name: str) -> None:
    if arr.dtype.type not in _SUPPORTED_DTYPES:
        raise TypeError(
            f"hpyx.kernels.{name}: dtype {arr.dtype} not supported "
            f"(supported: float32, float64, int32, int64). "
            f"Try hpyx.parallel.transform_reduce or numpy."
        )
    if not arr.flags["C_CONTIGUOUS"]:
        raise TypeError(
            f"hpyx.kernels.{name}: input must be C-contiguous. "
            f"Use np.ascontiguousarray(arr) first."
        )


def dot(a: np.ndarray, b: np.ndarray):
    """Parallel dot product over two 1-D arrays."""
    _runtime.ensure_started()
    _check(a, "dot")
    _check(b, "dot")
    return _core.kernels.dot(a, b)


__all__ = ["dot"]
```

- [ ] **Step 7: Update `src/hpyx/__init__.py`**

Add `from hpyx import kernels`; include `"kernels"` in `__all__`.

- [ ] **Step 8: Rebuild + test + commit**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_kernels.py -v
git add -A
git commit -m "feat(kernels): add hpyx.kernels.dot over numpy arrays (absorbs legacy dot1d)"
```

---

## Task 13: Remaining kernels — `matmul`, `sum`, `max`, `min`

Four additional templated kernels in `src/_core/kernels.cpp`. Each follows the same pattern as `dot`.

Tests (append to `tests/test_kernels.py`):

```python
# ---- matmul ----

@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_matmul_matches_numpy(dtype):
    rng = np.random.default_rng(1)
    A = rng.random((64, 128)).astype(dtype)
    B = rng.random((128, 32)).astype(dtype)
    C = hpyx.kernels.matmul(A, B)
    np.testing.assert_allclose(C, A @ B, rtol=1e-5 if dtype == np.float32 else 1e-10)


def test_matmul_shape_mismatch():
    A = np.ones((3, 4))
    B = np.ones((5, 6))
    with pytest.raises(ValueError, match="shape"):
        hpyx.kernels.matmul(A, B)


# ---- sum ----

@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.int64])
def test_sum_matches_numpy(dtype):
    a = np.arange(1000, dtype=dtype)
    assert hpyx.kernels.sum(a) == np.sum(a).item()


# ---- max / min ----

@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.int64])
def test_max_matches_numpy(dtype):
    rng = np.random.default_rng(2)
    a = (rng.random(10_000) * 1000).astype(dtype)
    assert hpyx.kernels.max(a) == np.max(a).item()


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32, np.int64])
def test_min_matches_numpy(dtype):
    rng = np.random.default_rng(3)
    a = (rng.random(10_000) * 1000).astype(dtype)
    assert hpyx.kernels.min(a) == np.min(a).item()
```

C++ implementations:

```cpp
// ---- matmul ----
template <typename T>
static nb::ndarray<T, nb::c_contig> kernel_matmul(
    nb::ndarray<const T, nb::c_contig> A,
    nb::ndarray<const T, nb::c_contig> B)
{
    ensure_runtime();
    if (A.ndim() != 2 || B.ndim() != 2) {
        throw std::invalid_argument("matmul: inputs must be 2-D");
    }
    auto rowsA = A.shape(0);
    auto colsA = A.shape(1);
    auto rowsB = B.shape(0);
    auto colsB = B.shape(1);
    if (colsA != rowsB) {
        throw std::invalid_argument(
            "matmul: shape mismatch (A.shape[1]=" + std::to_string(colsA)
            + ", B.shape[0]=" + std::to_string(rowsB) + ")");
    }

    // Allocate output on Python heap via nb::ndarray.
    size_t shape[2] = {static_cast<size_t>(rowsA), static_cast<size_t>(colsB)};
    T* out_raw = new T[rowsA * colsB];
    nb::capsule owner(out_raw, [](void* p) noexcept { delete[] static_cast<T*>(p); });
    nb::ndarray<T, nb::c_contig> C(out_raw, 2, shape, owner);

    const T* Ap = A.data();
    const T* Bp = B.data();
    T* Cp = out_raw;

    HPYX_KERNEL_NOGIL;
    hpx::experimental::for_loop(
        hpx::execution::par,
        std::size_t(0), std::size_t(rowsA),
        [&](std::size_t i) {
            const T* row = Ap + i * colsA;
            T* out_row = Cp + i * colsB;
            for (std::size_t j = 0; j < (size_t)colsB; ++j) {
                T s{0};
                for (std::size_t k = 0; k < (size_t)colsA; ++k) {
                    s += row[k] * Bp[k * colsB + j];
                }
                out_row[j] = s;
            }
        });
    return C;
}

// ---- sum ----
template <typename T>
static T kernel_sum(nb::ndarray<const T, nb::c_contig> a) {
    ensure_runtime();
    const T* p = a.data();
    std::size_t n = a.size();
    HPYX_KERNEL_NOGIL;
    return hpx::reduce(hpx::execution::par, p, p + n, T{0}, std::plus<T>{});
}

// ---- max ----
template <typename T>
static T kernel_max(nb::ndarray<const T, nb::c_contig> a) {
    ensure_runtime();
    if (a.size() == 0) throw std::invalid_argument("max: empty array");
    const T* p = a.data();
    std::size_t n = a.size();
    HPYX_KERNEL_NOGIL;
    auto it = hpx::max_element(hpx::execution::par, p, p + n);
    return *it;
}

// ---- min ----
template <typename T>
static T kernel_min(nb::ndarray<const T, nb::c_contig> a) {
    ensure_runtime();
    if (a.size() == 0) throw std::invalid_argument("min: empty array");
    const T* p = a.data();
    std::size_t n = a.size();
    HPYX_KERNEL_NOGIL;
    auto it = hpx::min_element(hpx::execution::par, p, p + n);
    return *it;
}
```

Register all four × 4 dtypes. Python wrappers in `src/hpyx/kernels.py`:

```python
def matmul(A, B):
    _runtime.ensure_started()
    _check(A, "matmul"); _check(B, "matmul")
    return _core.kernels.matmul(A, B)

def sum(a):
    _runtime.ensure_started()
    _check(a, "sum")
    return _core.kernels.sum(a)

def max(a):
    _runtime.ensure_started()
    _check(a, "max")
    return _core.kernels.max(a)

def min(a):
    _runtime.ensure_started()
    _check(a, "min")
    return _core.kernels.min(a)
```

Extend `__all__`.

Rebuild + test + commit:

```bash
git add -A
git commit -m "feat(kernels): add matmul, sum, max, min over numpy arrays"
```

---

## Task 14: Deprecate `hpyx.multiprocessing`

**Files:**
- Modify/rewrite: `src/hpyx/multiprocessing/__init__.py`

Now that `hpyx.parallel.for_loop` exists, `hpyx.multiprocessing.for_loop` becomes a deprecation shim.

- [ ] **Step 1: Look at the existing file**

```bash
cat src/hpyx/multiprocessing/__init__.py 2>/dev/null || ls src/hpyx/multiprocessing/
```

- [ ] **Step 2: Replace with shim**

```python
"""hpyx.multiprocessing — DEPRECATED.

This module is retained for backward compatibility with v0.x code.
Use `hpyx.parallel.for_loop` in new code.

Will be removed in v1.1.
"""

from __future__ import annotations

import warnings

from hpyx import parallel as _parallel
from hpyx.execution import par as _par, seq as _seq


def for_loop(function, iterable, policy="seq"):
    """DEPRECATED shim. Use hpyx.parallel.for_loop instead.

    The new API takes a policy object (hpyx.execution.par) and explicit
    first/last integer bounds or an iterable and a body function.
    """
    warnings.warn(
        "hpyx.multiprocessing.for_loop is deprecated — use "
        "hpyx.parallel.for_loop(hpyx.execution.par, 0, len(iterable), body). "
        "This shim will be removed in v1.1.",
        DeprecationWarning,
        stacklevel=2,
    )
    pol = _par if policy == "par" else _seq

    # Old semantics: iterable[i] = function(iterable[i]) for each i.
    mutable = list(iterable)

    def _body(i):
        mutable[i] = function(mutable[i])

    _parallel.for_loop(pol, 0, len(mutable), _body)

    # Write back into the original iterable if it supports __setitem__.
    try:
        for i, v in enumerate(mutable):
            iterable[i] = v
    except TypeError:
        pass  # not mutable — user's fault
    return mutable


__all__ = ["for_loop"]
```

- [ ] **Step 3: Add a deprecation test**

Add to `tests/test_parallel.py`:

```python
# ---- deprecation ----

def test_multiprocessing_for_loop_emits_deprecation_warning():
    import hpyx.multiprocessing as mp
    with pytest.warns(DeprecationWarning, match="deprecated"):
        mp.for_loop(lambda x: x + 1, [1, 2, 3], policy="par")
```

- [ ] **Step 4: Test + commit**

```bash
pixi run -e test-py313t pytest tests/test_parallel.py::test_multiprocessing_for_loop_emits_deprecation_warning -v
git add src/hpyx/multiprocessing tests/test_parallel.py
git commit -m "refactor(multiprocessing): convert to deprecation shim over hpyx.parallel.for_loop"
```

---

## Task 15: Free-threaded race-detection smoke test

**Files:**
- Create: `tests/test_free_threaded.py`

- [ ] **Step 1: Write tests**

```python
"""Smoke tests for free-threaded Python 3.13t: verify no races in the
shared runtime + cross-thread submit behavior."""

import sysconfig
import threading

import pytest

import hpyx
from hpyx.execution import par


# Most of these tests apply on both GIL-mode and 3.13t — they exercise
# cross-thread invariants that must hold in both builds.


def test_concurrent_submit_from_many_threads():
    N = 200
    results = [None] * N
    errors = []

    with hpyx.HPXExecutor() as ex:
        def submitter(i):
            try:
                fut = ex.submit(lambda x=i: x * 2)
                results[i] = fut.result()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submitter, args=(i,))
                   for i in range(N)]
        for t in threads: t.start()
        for t in threads: t.join()

    assert errors == []
    assert results == [i * 2 for i in range(N)]


def test_concurrent_add_done_callback():
    fut = hpyx.async_(lambda: "value")
    call_count = [0]
    lock = threading.Lock()

    def cb(f):
        with lock:
            call_count[0] += 1

    # Register many callbacks from multiple threads.
    def register():
        for _ in range(10):
            fut.add_done_callback(cb)

    threads = [threading.Thread(target=register) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()

    fut.result()  # block until done
    # Wait briefly for callbacks to drain.
    import time
    time.sleep(0.2)
    assert call_count[0] == 100


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="True parallelism of Python callbacks requires 3.13t"
)
def test_parallel_for_loop_python_body_scales_on_3_13t():
    """Under 3.13t, parallel.for_loop with a Python body should give
    real speedup vs seq. We just verify correctness at large N plus
    presence of concurrent execution."""
    import time

    workers_seen = set()
    lock = threading.Lock()

    def body(i):
        with lock:
            workers_seen.add(hpyx.debug.get_worker_thread_id())
        # Small spin to encourage scheduler interleaving.
        for _ in range(1000): pass

    hpyx.parallel.for_loop(par, 0, 100_000, body)
    # With os_threads=4 and 100k iterations, we must have touched more
    # than one worker.
    assert len(workers_seen) >= 2
```

- [ ] **Step 2: Run + commit**

```bash
pixi run -e test-py313t pytest tests/test_free_threaded.py -v
git add tests/test_free_threaded.py
git commit -m "test(free-threaded): smoke test for concurrent submit + nogil parallelism"
```

---

## Task 16: Final full-suite verification + PR

- [ ] **Step 1: Run entire suite**

```bash
pixi run test
```

Expected: every test passes. Record any remaining xfail/skip.

- [ ] **Step 2: Push + PR**

```bash
git push -u origin feat/v1-phase-2-parallel-kernels-execution
gh pr create --draft --title "feat(parallel,kernels,execution): v1 Phase 2" --body "$(cat <<'EOF'
## Summary

- 17 Python-callback parallel algorithms in `hpyx.parallel`
- 5 C++-native kernels in `hpyx.kernels` (dot, matmul, sum, max, min × 4 dtypes)
- `hpyx.execution` policy objects with chunk-size modifiers and task tag
- `PolicyToken` dispatch machinery (`src/_core/policy_dispatch.hpp`)
- `HPYX_KERNEL_NOGIL` / `HPYX_CALLBACK_GIL` macros
- Deprecation shim for `hpyx.multiprocessing`
- Free-threaded race-detection test

## Spec

§§ 3.3, 3.4, 3.5, 3.6, 4.3, 4.6, 4.7

## Test plan

- [x] `tests/test_execution_policy.py` — policy composition
- [x] `tests/test_parallel.py` — all 17 algorithms + task variants + deprecation shim
- [x] `tests/test_kernels.py` — 5 kernels × 4 dtypes vs numpy reference
- [x] `tests/test_free_threaded.py` — nogil parallelism smoke

## What's NOT in this PR

- Benchmarks (Plan 4)
- Docs (Plan 5)
- CI matrix updates (Plan 5)
EOF
)"
```

---

## Self-review notes

**Spec coverage (Phase 2):**
- Spec §1.6 item 4 (17 algorithms + 5 kernels + chunk-size) — Tasks 5-13.
- Spec §4.6 footgun — Task 7 (keyword-only `init`/`op`).
- Spec §6.4 multiprocessing deprecation — Task 14.

**Placeholder scan:** None. "Apply same pattern" references have concrete C++ snippets in the preceding task.

**Type consistency:**
- `_Policy` Python class ↔ `PolicyToken` C++ struct — `_Policy._token()` serializes.
- `hpyx.parallel.*` return types: `None` for void algorithms, scalar for reductions, `int` for find (-1 sentinel), `Future` when policy has `task`.
- `hpyx.kernels.*` dtype list consistent with `_SUPPORTED_DTYPES` set.

**Known caveats:**
- `hpx::count` is implemented via `hpx::count_if` + equality predicate (avoids needing specialized bindings per dtype).
- `matmul` uses a triply-nested loop — naive O(n^3). Fine for correctness; real BLAS integration is v1.x.
- The `_task` variant must be implemented for every algorithm; where the sync version is cheap (count, find), the task variant is still provided for API uniformity but rarely needed in practice.
