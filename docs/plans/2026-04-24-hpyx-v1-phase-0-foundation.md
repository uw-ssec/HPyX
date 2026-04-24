# HPyX v1 Phase 0: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `src/*.cpp` into `src/_core/`, rewrite runtime lifecycle with clean API, establish CMake profile preset, and land the Python `hpyx._runtime` / `hpyx.runtime` / `hpyx.config` / `hpyx.debug` foundation with session-scoped tests. End state: `hpyx.init()`, `hpyx.shutdown()`, `hpyx.is_running()`, `hpyx.HPXRuntime()` context manager, `hpyx.debug.get_num_worker_threads()`, `hpyx.debug.get_worker_thread_id()`, and env-var config all work end-to-end on both GIL-mode 3.13 and free-threaded 3.13t.

**Architecture:** Two-PR worth of work in sequence. First we move existing `src/*.cpp` into `src/_core/` with no behavior change (pure mechanical refactor, tests pass unchanged). Then we rewrite `runtime.cpp` with a cleaner API (`runtime_start`/`runtime_stop`/`runtime_is_running`/`num_worker_threads`/`get_worker_thread_id`) and land the Python lifecycle wrappers that implement implicit auto-init plus `atexit`-owned shutdown. The existing `futures.cpp`, `algorithms.cpp` and broken `HPXExecutor` stay untouched — Plan 2 handles those.

**Tech Stack:** C++17, nanobind ≥2.7, HPX ≥1.11 (conda-forge) or vendor 2.0, scikit-build-core, CMake ≥3.15, Python 3.13 / 3.13t (free-threaded), pixi for environment management, pytest.

**Reference documents:**
- Spec: `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md`
- HPX knowledge: `docs/codebase-analysis/hpx/CODEBASE_KNOWLEDGE.md`

**Out of scope for this plan (deferred to Plan 2+):**
- `futures.cpp` rewrite (launch::async fix, `HPXFuture` class, combinators)
- `HPXExecutor` rewrite
- Parallel algorithms (`parallel.cpp`, `hpyx.parallel`)
- C++ kernels (`kernels.cpp`, `hpyx.kernels`)
- asyncio bridge (`hpyx.aio`)
- Benchmark infrastructure (`benchmarks/conftest.py`, `scripts/run_bench_local.sh`)
- Docs (`adding-a-binding.md`, migration guide, user guides)
- Deprecation of `hpyx.multiprocessing` (defer until `hpyx.parallel.for_loop` exists in Plan 3)
- Full `enable_tracing` JSONL output (ships a stub in Plan 1; real implementation in Plan 4)

---

## File Structure

### Created files

| File | Responsibility |
|---|---|
| `src/_core/bind.cpp` | Top-level `NB_MODULE(_core, m)`; registers four submodules (`runtime`, `futures`, `parallel`, `kernels`) via `register_bindings(nb::module_&)` pattern. In Phase 0 only `runtime` is populated; the other three just exist as stubs or continue to host the legacy bindings. |
| `src/_core/runtime.cpp` | Rewritten runtime lifecycle. Exposes `runtime_start`, `runtime_stop`, `runtime_is_running`, `num_worker_threads`, `get_worker_thread_id`, `hpx_version_string`. Internally keeps the existing `global_runtime_manager` pattern. |
| `src/_core/runtime.hpp` | Public headers for `register_bindings(nb::module_&)` + the free functions. |
| `src/_core/futures.cpp` | Moved verbatim from `src/futures.cpp` in PR 1; Plan 2 rewrites it. In Phase 0 we only relocate. |
| `src/_core/futures.hpp` | Moved verbatim. |
| `src/_core/algorithms.cpp` | Moved verbatim from `src/algorithms.cpp`; Plan 3 replaces with `parallel.cpp` + `kernels.cpp`. |
| `src/_core/algorithms.hpp` | Moved verbatim. |
| `src/hpyx/_runtime.py` | `ensure_started()`, lock-guarded singleton state, `atexit.register(runtime_stop)`, reads config from env at first call. Called implicitly by all public APIs. |
| `src/hpyx/config.py` | `from_env()` dict builder, `DEFAULTS` mapping. Honors `HPYX_OS_THREADS`, `HPYX_CFG`, `HPYX_AUTOINIT`. |
| `src/hpyx/debug.py` | `get_num_worker_threads()`, `get_worker_thread_id()` (thin re-exports from `_core.runtime`). Stubs for `enable_tracing`/`disable_tracing` that raise `NotImplementedError("tracing ships in v1.x")` — keeps the public import surface stable. |
| `CMakePresets.json` | `default` preset + `profile` preset (`RelWithDebInfo`, `-fno-omit-frame-pointer`, IPO off). |
| `tests/conftest.py` | Session-scoped `hpx_runtime` fixture (`autouse=True`) that calls `hpyx.init(os_threads=4)` once and lets `atexit` own shutdown. `@pytest.mark.skip_after_shutdown` marker registered. |
| `tests/test_runtime.py` | Covers init idempotency, conflicting-args error, `is_running`, `HPXRuntime` context manager, post-shutdown error, env var precedence. |
| `tests/test_config.py` | Covers `from_env()` parsing of the three env vars, defaults, precedence. |
| `tests/test_debug.py` | Covers `get_num_worker_threads`, `get_worker_thread_id` from HPX and non-HPX threads, `enable_tracing` stub raises. |

### Modified files

| File | Change |
|---|---|
| `CMakeLists.txt` | Update the `nanobind_add_module` source list from flat `src/*.cpp` to `src/_core/*.cpp`. |
| `src/hpyx/__init__.py` | Update exports: add `init`, `shutdown`, `is_running`, `config`, `debug` alongside existing `HPXRuntime`, `HPXExecutor`, `futures`, `multiprocessing`. |
| `src/hpyx/runtime.py` | Refactor `HPXRuntime` context manager to a thin wrapper on `_runtime.ensure_started()` + idempotent shutdown. Preserves existing `HPXRuntime()` user API. |

### Deleted files

None in Phase 0. The existing `src/bind.cpp`, `src/init_hpx.cpp`, `src/init_hpx.hpp`, `src/algorithms.*`, `src/futures.*` are **moved** (`git mv`) into `src/_core/`, not deleted.

---

## Execution Notes

- All commands assume pwd is the repo root (`/Users/lsetiawan/Repos/SSEC/HPyX`).
- `pixi run test` runs the full test suite in the `test-py313t` environment (free-threaded Python 3.13t).
- Single-test runs: `pixi run -e test-py313t pytest tests/test_runtime.py::test_init_idempotent -v`.
- After any C++ change, rebuild before running tests: `pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .` (or use editable-rebuild autobuild if configured).
- All commits use the **Conventional Commits** style (repo convention, see recent `git log`): `docs(spec): ...`, `refactor(_core): ...`, `feat(runtime): ...`, `test(runtime): ...`, etc. **Do not add Co-Authored-By trailers** per user's `/commit` skill preference.
- Current branch is `docs/v1-design-specs`. **Task 1 starts by creating a fresh implementation branch** off `main`.

---

## Task 1: Create implementation branch

**Files:** none

- [ ] **Step 1: Switch back to main and verify clean state**

```bash
git checkout main
git status
```

Expected: "working tree clean" (the spec commit lives on `docs/v1-design-specs`).

- [ ] **Step 2: Create implementation branch**

```bash
git checkout -b feat/v1-phase-0-foundation
```

Expected: "Switched to a new branch 'feat/v1-phase-0-foundation'".

- [ ] **Step 3: Sanity-check current build**

```bash
pixi run test
```

Expected: existing tests pass (`test_for_loop.py`, `test_hpx_linalg.py`, `test_submit.py`). If `test_submit.py` fails — that's known (HPXExecutor broken); record which tests fail so we can tell later whether we regressed them. Note: all test failures here are pre-existing bugs that Plan 2 will fix.

---

## Task 2: Refactor `src/*.cpp` → `src/_core/` (no behavior change)

**Files:**
- Create dir: `src/_core/`
- Move: `src/bind.cpp` → `src/_core/bind.cpp`
- Move: `src/init_hpx.cpp` → `src/_core/runtime.cpp` (rename during move)
- Move: `src/init_hpx.hpp` → `src/_core/runtime.hpp` (rename during move)
- Move: `src/algorithms.cpp` → `src/_core/algorithms.cpp`
- Move: `src/algorithms.hpp` → `src/_core/algorithms.hpp`
- Move: `src/futures.cpp` → `src/_core/futures.cpp`
- Move: `src/futures.hpp` → `src/_core/futures.hpp`
- Modify: `src/_core/bind.cpp` (update `#include` paths)
- Modify: `src/_core/runtime.cpp` (no logic change; only header rename follow-up)
- Modify: `CMakeLists.txt` (path updates)

- [ ] **Step 1: Create the `_core` directory and git-move files**

```bash
mkdir -p src/_core
git mv src/bind.cpp src/_core/bind.cpp
git mv src/init_hpx.cpp src/_core/runtime.cpp
git mv src/init_hpx.hpp src/_core/runtime.hpp
git mv src/algorithms.cpp src/_core/algorithms.cpp
git mv src/algorithms.hpp src/_core/algorithms.hpp
git mv src/futures.cpp src/_core/futures.cpp
git mv src/futures.hpp src/_core/futures.hpp
```

Expected: `ls src/_core/` shows all seven files; `ls src/` shows only `hpyx/`.

- [ ] **Step 2: Update `#include` in `src/_core/bind.cpp`**

Open `src/_core/bind.cpp`. Find the includes and replace:

```cpp
// Before:
#include "init_hpx.hpp"
#include "algorithms.hpp"
#include "futures.hpp"

// After:
#include "runtime.hpp"
#include "algorithms.hpp"   // unchanged
#include "futures.hpp"      // unchanged
```

Only `init_hpx.hpp` changes to `runtime.hpp` (file was renamed). The other two stay because they're in the same `src/_core/` dir and the basename didn't change.

- [ ] **Step 3: Rename internal include guards / paths in `src/_core/runtime.hpp`**

Open `src/_core/runtime.hpp`. If it uses `INIT_HPX_HPP` guards, rename to `HPYX_CORE_RUNTIME_HPP`. If it uses `#pragma once`, no change needed.

Check the file:

```bash
cat src/_core/runtime.hpp
```

If you see `#ifndef INIT_HPX_HPP` or similar, replace with `#ifndef HPYX_CORE_RUNTIME_HPP` (and matching `#define` / `#endif`). If it's `#pragma once`, leave it.

- [ ] **Step 4: Update `CMakeLists.txt` source list**

Open `CMakeLists.txt` and find the `nanobind_add_module` call. Replace:

```cmake
# Before:
nanobind_add_module(
  _core
  FREE_THREADED
  src/bind.cpp
  src/init_hpx.cpp
  src/algorithms.cpp
  src/futures.cpp
)

# After:
nanobind_add_module(
  _core
  FREE_THREADED
  src/_core/bind.cpp
  src/_core/runtime.cpp
  src/_core/algorithms.cpp
  src/_core/futures.cpp
)
```

- [ ] **Step 5: Rebuild**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
```

Expected: compiles without errors. If you see "No such file or directory" referencing `src/init_hpx.cpp`, you missed the CMakeLists update.

- [ ] **Step 6: Run existing tests — verify behavior unchanged**

```bash
pixi run test
```

Expected: same pass/fail set as Task 1 Step 3. Any NEW failure means the refactor broke something; investigate before continuing.

- [ ] **Step 7: Commit the pure refactor**

```bash
git add -A src/ CMakeLists.txt
git status
```

Verify only `src/**` and `CMakeLists.txt` are staged. Then:

```bash
git commit -m "$(cat <<'EOF'
refactor(_core): move flat src/*.cpp into src/_core/ package

No behavior change — pure file relocation. init_hpx.cpp renamed to
runtime.cpp for clarity. This lays the foundation for the v1 runtime
rewrite (futures, parallel, kernels submodules land in later PRs).
EOF
)"
```

---

## Task 3: Add `CMakePresets.json` with `default` and `profile` presets

**Files:**
- Create: `CMakePresets.json`

- [ ] **Step 1: Verify no existing presets file**

```bash
ls CMakePresets.json 2>/dev/null || echo "does not exist — good"
```

Expected: "does not exist — good".

- [ ] **Step 2: Write `CMakePresets.json`**

Create `CMakePresets.json` at the repo root:

```json
{
  "version": 3,
  "cmakeMinimumRequired": { "major": 3, "minor": 21, "patch": 0 },
  "configurePresets": [
    {
      "name": "default",
      "displayName": "Default Release build",
      "description": "Release-optimized build via scikit-build-core's default CMake config",
      "binaryDir": "${sourceDir}/build/default",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Release"
      }
    },
    {
      "name": "profile",
      "displayName": "Profile (RelWithDebInfo + frame pointers)",
      "description": "Release-level optimization with debug info + frame pointers so py-spy/perf/memray can resolve C++ frames.",
      "inherits": "default",
      "binaryDir": "${sourceDir}/build/profile",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "RelWithDebInfo",
        "CMAKE_CXX_FLAGS_RELWITHDEBINFO": "-O2 -g -fno-omit-frame-pointer",
        "CMAKE_INTERPROCEDURAL_OPTIMIZATION": "OFF",
        "CMAKE_CXX_VISIBILITY_PRESET": "default"
      }
    }
  ]
}
```

- [ ] **Step 3: Verify CMake can parse the presets**

```bash
cmake --list-presets 2>&1 | tee /tmp/cmake-presets.out
```

Expected output:

```
Available configure presets:

  "default" - Default Release build
  "profile" - Profile (RelWithDebInfo + frame pointers)
```

If CMake errors with "json schema" complaint, check for trailing commas or typos in the JSON.

- [ ] **Step 4: Commit**

```bash
git add CMakePresets.json
git commit -m "$(cat <<'EOF'
build(cmake): add default and profile presets

The profile preset enables py-spy --native, perf, and memray --native
to resolve C++ frames for benchmarking and profiling workflows. Used
by scripts/run_bench_local.sh (lands in Plan 4).
EOF
)"
```

---

## Task 4: Rewrite `src/_core/runtime.cpp` with the new API

**Files:**
- Modify: `src/_core/runtime.hpp` (new public signatures)
- Modify: `src/_core/runtime.cpp` (new free functions + `register_bindings`)
- Modify: `src/_core/bind.cpp` (defer submodule creation to runtime's `register_bindings`)

The goal is to replace the old `init_hpx_runtime` / `stop_hpx_runtime` surface with:

```cpp
bool runtime_start(std::vector<std::string> const& cfg);
void runtime_stop();
bool runtime_is_running();
std::size_t num_worker_threads();
std::int64_t get_worker_thread_id();
std::string hpx_version_string();
```

Keep the existing `global_runtime_manager` internal class and its suspended-runtime condition-variable pattern — that code works. We're just adding query functions, renaming the entry points, and moving binding registration out of `bind.cpp`.

- [ ] **Step 1: Write the failing test first** (TDD pattern — we'll run it *after* adding config/runtime Python modules in later tasks, but codify it now)

Create a placeholder note in your scratch — we'll flesh out `tests/test_runtime.py` in Task 11. The shape of the test for THIS task:

```python
# Will be added as test_runtime.py::test_runtime_start_returns_true_first_time
def test_runtime_start_returns_true_first_time():
    assert hpyx._core.runtime.runtime_start([]) is True
    assert hpyx._core.runtime.runtime_is_running() is True
```

We'll write and run this in Task 11. For now, implement the C++ side so the test can exist.

- [ ] **Step 2: Update `src/_core/runtime.hpp`**

Replace contents of `src/_core/runtime.hpp` with:

```cpp
#pragma once

#include <nanobind/nanobind.h>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace hpyx::runtime {

// Thread-safe, idempotent. Returns true if this call started the runtime,
// false if it was already running. Throws std::runtime_error if the runtime
// was previously started and then stopped (HPX cannot restart in-process).
bool runtime_start(std::vector<std::string> const& cfg);

// Blocks until HPX drains. Idempotent — safe to call after a prior stop
// (no-op in that case). Does NOT re-enable starting.
void runtime_stop();

bool runtime_is_running();

std::size_t num_worker_threads();
std::int64_t get_worker_thread_id();  // -1 if called from a non-HPX OS thread
std::string hpx_version_string();

// Called by _core's NB_MODULE macro to register all bindings in this file
// on the `runtime` submodule.
void register_bindings(nanobind::module_& m);

}  // namespace hpyx::runtime
```

- [ ] **Step 3: Update `src/_core/runtime.cpp`**

Replace contents with:

```cpp
#include "runtime.hpp"

#include <hpx/hpx.hpp>
#include <hpx/hpx_start.hpp>
#include <hpx/version.hpp>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>

namespace nb = nanobind;

namespace hpyx::runtime {

namespace {

// Preserved from the original init_hpx.cpp — this is HPX's suspended-runtime
// pattern. Keep the guts verbatim; only rename the free functions.
struct global_runtime_manager {
    global_runtime_manager(std::vector<std::string> const& config)
        : running_(false), rts_(nullptr), cfg(config) {
        hpx::init_params params;
        params.cfg = cfg;

        hpx::function<int(int, char**)> start_function =
            hpx::bind_front(&global_runtime_manager::hpx_main, this);

        if (!hpx::start(start_function, 0, nullptr, params)) {
            std::abort();
        }

        std::unique_lock<std::mutex> lk(startup_mtx_);
        while (!running_) startup_cond_.wait(lk);
    }

    ~global_runtime_manager() {
        {
            std::lock_guard<hpx::spinlock> lk(mtx_);
            rts_ = nullptr;
        }
        cond_.notify_one();
        hpx::stop();
    }

    int hpx_main(int /*argc*/, char** /*argv*/) {
        rts_ = hpx::get_runtime_ptr();
        {
            std::lock_guard<std::mutex> lk(startup_mtx_);
            running_ = true;
        }
        startup_cond_.notify_one();
        {
            std::unique_lock<hpx::spinlock> lk(mtx_);
            if (rts_ != nullptr) cond_.wait(lk);
        }
        return hpx::finalize();
    }

  private:
    hpx::spinlock mtx_;
    hpx::condition_variable_any cond_;
    std::mutex startup_mtx_;
    std::condition_variable startup_cond_;
    bool running_;
    hpx::runtime* rts_;
    std::vector<std::string> const cfg;
};

// Process-wide singleton + a "was-stopped" flag because HPX can't restart.
std::mutex g_state_mtx;
global_runtime_manager* g_mgr = nullptr;
std::atomic<bool> g_stopped{false};

}  // namespace

bool runtime_start(std::vector<std::string> const& cfg) {
    if (g_stopped.load()) {
        throw std::runtime_error(
            "HPyX runtime has been stopped and cannot restart within this process");
    }
    std::lock_guard<std::mutex> lk(g_state_mtx);
    if (g_mgr != nullptr) return false;

    // Construction must not hold the GIL — hpx::start + startup CV wait can
    // be long-running, and callbacks into Python (unlikely here) would deadlock.
    nb::gil_scoped_release release;
    g_mgr = new global_runtime_manager(cfg);
    return true;
}

void runtime_stop() {
    global_runtime_manager* to_delete = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_state_mtx);
        to_delete = g_mgr;
        g_mgr = nullptr;
    }
    if (to_delete != nullptr) {
        g_stopped.store(true);
        nb::gil_scoped_release release;
        delete to_delete;
    }
}

bool runtime_is_running() {
    std::lock_guard<std::mutex> lk(g_state_mtx);
    return g_mgr != nullptr;
}

std::size_t num_worker_threads() {
    if (!runtime_is_running()) return 0;
    return hpx::get_num_worker_threads();
}

std::int64_t get_worker_thread_id() {
    if (!runtime_is_running()) return -1;
    auto id = hpx::get_worker_thread_num();
    if (id == std::size_t(-1)) return -1;
    return static_cast<std::int64_t>(id);
}

std::string hpx_version_string() {
    return hpx::complete_version();
}

void register_bindings(nb::module_& m) {
    m.def("runtime_start", &runtime_start, "cfg"_a,
          "Start the HPX runtime. Idempotent; returns True if this call started it.");
    m.def("runtime_stop", &runtime_stop,
          "Stop the HPX runtime. Irreversible within this process.");
    m.def("runtime_is_running", &runtime_is_running);
    m.def("num_worker_threads", &num_worker_threads);
    m.def("get_worker_thread_id", &get_worker_thread_id);
    m.def("hpx_version_string", &hpx_version_string);
}

}  // namespace hpyx::runtime
```

Note the key changes from the original:
- Wrapped in `namespace hpyx::runtime`.
- `g_stopped` flag prevents restart and raises a clear error.
- `runtime_start` is idempotent with a return value.
- GIL released during construction (previously it was **acquired** — that's a bug for free-threaded builds because construction can block for the HPX startup CV).
- New query functions: `runtime_is_running`, `num_worker_threads`, `get_worker_thread_id`, `hpx_version_string`.
- `register_bindings` owns the submodule's `.def` calls.

- [ ] **Step 4: Update `src/_core/bind.cpp` to defer to `register_bindings`**

Open `src/_core/bind.cpp`. The file currently registers many things directly. For Phase 0, we keep the legacy `futures` and `algorithms` bindings intact (Plan 2/3 replace them), but we **move runtime registrations into a `runtime` submodule via `register_bindings`.** Replace the top-level `init_hpx_runtime` / `stop_hpx_runtime` / `get_num_worker_threads` / `hpx_complete_version` entries with:

Find and DELETE these four lines from the existing `bind.cpp`:

```cpp
m.def("init_hpx_runtime", &init_hpx_runtime);
m.def("stop_hpx_runtime", &stop_hpx_runtime);
m.def("get_num_worker_threads", []() { return hpx::get_num_worker_threads(); });
m.def("hpx_complete_version", []() { return hpx::complete_version(); });
```

Add the runtime submodule registration at the top of `NB_MODULE(_core, m)`:

```cpp
auto m_runtime = m.def_submodule("runtime");
hpyx::runtime::register_bindings(m_runtime);
```

Also remove the `#include "init_hpx.hpp"` line (replaced earlier by `#include "runtime.hpp"` — verify the include at the top of `bind.cpp` reads `#include "runtime.hpp"`).

The remaining `hpx_async` / `dot1d` / `hpx_for_loop` bindings at the top level stay exactly as they were — Plans 2 and 3 move them into their respective submodules.

- [ ] **Step 5: Rebuild**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
```

Expected: compiles. Any `'init_hpx_runtime' is not a member of 'hpyx::runtime'` errors mean you didn't fully delete the old-name entries from `bind.cpp`.

- [ ] **Step 6: Smoke-test the new API from Python**

```bash
pixi run -e test-py313t python -c "
import hpyx._core as c
print('is_running before:', c.runtime.runtime_is_running())
print('started:', c.runtime.runtime_start([]))
print('is_running after:', c.runtime.runtime_is_running())
print('workers:', c.runtime.num_worker_threads())
print('version:', c.runtime.hpx_version_string()[:40])
c.runtime.runtime_stop()
print('is_running final:', c.runtime.runtime_is_running())
"
```

Expected output (exact worker count depends on host):

```
is_running before: False
started: True
is_running after: True
workers: 8
version: HPX V1.11.0 ...
is_running final: False
```

- [ ] **Step 7: Verify restart error**

```bash
pixi run -e test-py313t python -c "
import hpyx._core as c
c.runtime.runtime_start([])
c.runtime.runtime_stop()
try:
    c.runtime.runtime_start([])
except RuntimeError as e:
    print('OK, restart raised:', e)
else:
    print('BAD: restart did not raise')
"
```

Expected: `OK, restart raised: HPyX runtime has been stopped and cannot restart within this process`.

- [ ] **Step 8: Verify existing (non-broken) tests still pass**

```bash
pixi run -e test-py313t pytest tests/test_hpx_linalg.py -v
```

Expected: same result as before the rewrite. (`test_for_loop.py` and `test_submit.py` may have pre-existing failures.)

**Important:** if `test_hpx_linalg.py` previously used `hpyx.HPXRuntime` context manager, it still passes because the legacy `HPXRuntime` Python code still calls the old `_core.init_hpx_runtime` / `_core.stop_hpx_runtime`. We have a problem: we deleted those from `bind.cpp`. Before committing, we need to update `src/hpyx/runtime.py` to use the new `_core.runtime.runtime_start` / `_core.runtime.runtime_stop`. That's Task 7 below — but Tasks 5-7 need to land *before* we run the test suite cleanly.

**Defer commit to after Task 7.** Keep all Task 4-7 changes in the working tree, then commit together as one logical change.

---

## Task 5: Create `src/hpyx/config.py`

**Files:**
- Create: `src/hpyx/config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
import pytest
from hpyx import config


def test_defaults_present():
    assert config.DEFAULTS == {
        "os_threads": None,
        "cfg": [],
        "autoinit": True,
        "trace_path": None,
    }


def test_from_env_empty(monkeypatch):
    for k in ("HPYX_OS_THREADS", "HPYX_CFG", "HPYX_AUTOINIT", "HPYX_TRACE_PATH"):
        monkeypatch.delenv(k, raising=False)
    assert config.from_env() == config.DEFAULTS


def test_from_env_os_threads(monkeypatch):
    monkeypatch.setenv("HPYX_OS_THREADS", "4")
    assert config.from_env()["os_threads"] == 4


def test_from_env_os_threads_invalid_raises(monkeypatch):
    monkeypatch.setenv("HPYX_OS_THREADS", "not-a-number")
    with pytest.raises(ValueError, match="HPYX_OS_THREADS"):
        config.from_env()


def test_from_env_cfg_semicolon_split(monkeypatch):
    monkeypatch.setenv(
        "HPYX_CFG",
        "hpx.stacks.small_size=0x20000;hpx.os_threads!=2",
    )
    assert config.from_env()["cfg"] == [
        "hpx.stacks.small_size=0x20000",
        "hpx.os_threads!=2",
    ]


def test_from_env_cfg_empty_entries_stripped(monkeypatch):
    monkeypatch.setenv("HPYX_CFG", "a=1;;b=2;")
    assert config.from_env()["cfg"] == ["a=1", "b=2"]


@pytest.mark.parametrize("value,expected", [
    ("0", False), ("false", False), ("FALSE", False), ("no", False),
    ("1", True), ("true", True), ("TRUE", True), ("yes", True),
])
def test_from_env_autoinit(monkeypatch, value, expected):
    monkeypatch.setenv("HPYX_AUTOINIT", value)
    assert config.from_env()["autoinit"] is expected


def test_from_env_trace_path(monkeypatch):
    monkeypatch.setenv("HPYX_TRACE_PATH", "/tmp/hpyx.jsonl")
    assert config.from_env()["trace_path"] == "/tmp/hpyx.jsonl"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pixi run -e test-py313t pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'hpyx.config'` or `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/hpyx/config.py`:

```python
"""Configuration for the HPyX runtime.

Precedence: explicit hpyx.init() kwargs > environment variables > DEFAULTS.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    "os_threads": None,
    "cfg": [],
    "autoinit": True,
    "trace_path": None,
}

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str, *, var_name: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{var_name}={value!r} is not a recognized boolean "
        f"(use one of: 0, 1, true, false, yes, no, on, off)"
    )


def from_env() -> dict[str, Any]:
    """Build a config dict from HPYX_* environment variables.

    Returns a fresh copy of DEFAULTS with any present env vars layered on top.
    Unset env vars leave the default value unchanged.
    """
    cfg = dict(DEFAULTS)
    cfg["cfg"] = list(DEFAULTS["cfg"])  # defensive — don't share the default list

    raw_threads = os.environ.get("HPYX_OS_THREADS")
    if raw_threads is not None:
        try:
            cfg["os_threads"] = int(raw_threads)
        except ValueError as exc:
            raise ValueError(
                f"HPYX_OS_THREADS={raw_threads!r} must be an integer"
            ) from exc

    raw_cfg = os.environ.get("HPYX_CFG")
    if raw_cfg is not None:
        cfg["cfg"] = [entry for entry in raw_cfg.split(";") if entry]

    raw_autoinit = os.environ.get("HPYX_AUTOINIT")
    if raw_autoinit is not None:
        cfg["autoinit"] = _parse_bool(raw_autoinit, var_name="HPYX_AUTOINIT")

    raw_trace = os.environ.get("HPYX_TRACE_PATH")
    if raw_trace is not None:
        cfg["trace_path"] = raw_trace

    return cfg
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pixi run -e test-py313t pytest tests/test_config.py -v
```

Expected: all tests in `test_config.py` pass.

- [ ] **Step 5: Commit** (deferred — commit after Task 7 is done)

---

## Task 6: Create `src/hpyx/_runtime.py`

**Files:**
- Create: `src/hpyx/_runtime.py`

- [ ] **Step 1: Write the failing tests** (fleshed out further in Task 11)

For now, write tests that only exercise `ensure_started` + idempotency. Full test file lands in Task 11. Add this as a placeholder in `tests/test_runtime.py` (will be fleshed out in Task 11):

```python
# tests/test_runtime.py (initial skeleton — Task 11 expands it)
from hpyx import _runtime, is_running


def test_ensure_started_is_idempotent():
    _runtime.ensure_started()
    assert is_running()
    _runtime.ensure_started()  # no-op; must not raise
    assert is_running()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pixi run -e test-py313t pytest tests/test_runtime.py::test_ensure_started_is_idempotent -v
```

Expected: `ImportError: cannot import name '_runtime'` or `ImportError: cannot import name 'is_running'` (since Task 9 hasn't updated `__init__.py` yet).

- [ ] **Step 3: Write minimal implementation**

Create `src/hpyx/_runtime.py`:

```python
"""Internal runtime lifecycle for HPyX.

`ensure_started()` is called by every public API that needs the runtime.
It is idempotent, thread-safe, and respects HPYX_AUTOINIT=0 (in which case
it raises instead of auto-starting).

Shutdown is registered with `atexit` on first start; users should not call
`_core.runtime.runtime_stop()` directly.
"""

from __future__ import annotations

import atexit
import os
import threading
from typing import Any

from hpyx import config as _config
from hpyx import _core

_lock = threading.Lock()
_started = False
_started_cfg: dict[str, Any] | None = None
_atexit_registered = False


def _build_cfg_strings(
    *, os_threads: int | None, cfg: list[str]
) -> list[str]:
    """Translate Python kwargs into HPX-style "key!=value" strings."""
    result: list[str] = []
    if os_threads is not None:
        result.append(f"hpx.os_threads!={int(os_threads)}")
    # HPyX-standard defaults (align with docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md §3.1)
    result.append("hpx.run_hpx_main!=1")
    result.append("hpx.commandline.allow_unknown!=1")
    result.append("hpx.commandline.aliasing!=0")
    result.append("hpx.diagnostics_on_terminate!=0")
    result.append("hpx.parcel.tcp.enable!=0")
    # User-provided overrides come last so they take precedence.
    result.extend(cfg)
    return result


def _normalized_cfg(
    *, os_threads: int | None = None, cfg: list[str] | None = None
) -> dict[str, Any]:
    """Merge kwargs → env vars → DEFAULTS into a canonical config dict."""
    env = _config.from_env()
    if os_threads is None:
        os_threads = env["os_threads"]
    if cfg is None:
        cfg = env["cfg"]
    return {
        "os_threads": os_threads,
        "cfg": list(cfg),
        "autoinit": env["autoinit"],
        "trace_path": env["trace_path"],
    }


def ensure_started(
    *, os_threads: int | None = None, cfg: list[str] | None = None
) -> None:
    """Start the HPX runtime if not already started. Idempotent.

    If the runtime is already started with a *different* (os_threads, cfg),
    raises RuntimeError — HPX cannot be reconfigured after start.

    Respects HPYX_AUTOINIT=0 only when called with all defaults; explicit
    kwargs always start the runtime.
    """
    global _started, _started_cfg, _atexit_registered
    normalized = _normalized_cfg(os_threads=os_threads, cfg=cfg)

    with _lock:
        if _started:
            if _started_cfg is not None and (
                _started_cfg["os_threads"] != normalized["os_threads"]
                or _started_cfg["cfg"] != normalized["cfg"]
            ):
                raise RuntimeError(
                    "HPyX runtime already started with different config: "
                    f"existing={_started_cfg!r}, requested={normalized!r}"
                )
            return

        explicit = os_threads is not None or cfg is not None
        if not explicit and not normalized["autoinit"]:
            raise RuntimeError(
                "HPyX auto-init is disabled (HPYX_AUTOINIT=0) and no "
                "explicit hpyx.init(...) call was made"
            )

        cfg_strings = _build_cfg_strings(
            os_threads=normalized["os_threads"], cfg=normalized["cfg"]
        )
        _core.runtime.runtime_start(cfg_strings)
        _started = True
        _started_cfg = normalized

        if not _atexit_registered:
            atexit.register(_atexit_shutdown)
            _atexit_registered = True


def _atexit_shutdown() -> None:
    """Called at process exit. Tolerant of double-shutdown."""
    global _started
    if _started:
        try:
            _core.runtime.runtime_stop()
        except Exception:  # noqa: BLE001 — atexit must never raise
            pass
        _started = False


def shutdown() -> None:
    """Explicit shutdown. Irreversible within the process."""
    global _started
    with _lock:
        if _started:
            _core.runtime.runtime_stop()
            _started = False


def is_running() -> bool:
    return _core.runtime.runtime_is_running()
```

- [ ] **Step 4: Run the test to verify it passes** — defer until Task 9 updates `__init__.py` (because the test imports from `hpyx`).

---

## Task 7: Refactor `src/hpyx/runtime.py`

**Files:**
- Modify: `src/hpyx/runtime.py`

The existing `src/hpyx/runtime.py` implements `HPXRuntime` by directly calling old `_core.init_hpx_runtime` / `_core.stop_hpx_runtime`. Since Task 4 removed those symbols, this file is currently broken. Rewrite to use `_runtime.ensure_started` + `_runtime.shutdown`.

- [ ] **Step 1: Read the existing file**

```bash
cat src/hpyx/runtime.py
```

Note any behavior you want to preserve (the user-facing `HPXRuntime` API, any kwargs it accepts).

- [ ] **Step 2: Write the failing test**

Add to `tests/test_runtime.py`:

```python
from hpyx import HPXRuntime, is_running


def test_HPXRuntime_context_manager():
    # The session fixture has already started the runtime; HPXRuntime
    # should be a no-op enter/exit.
    assert is_running()
    with HPXRuntime() as rt:
        assert rt is not None
        assert is_running()
    # Exit does NOT shut down — atexit owns shutdown.
    assert is_running()


def test_HPXRuntime_nested_is_idempotent():
    with HPXRuntime():
        with HPXRuntime():
            assert is_running()
        assert is_running()
    assert is_running()
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
pixi run -e test-py313t pytest tests/test_runtime.py::test_HPXRuntime_context_manager -v
```

Expected: `AttributeError: module 'hpyx._core' has no attribute 'init_hpx_runtime'`.

- [ ] **Step 4: Write the new implementation**

Replace `src/hpyx/runtime.py` contents entirely:

```python
"""HPXRuntime context manager — optional convenience wrapper.

Using this is no longer required in v1 — HPyX auto-initializes on first
use. This context manager remains for users who want explicit lifecycle
scoping in scripts and tests, and for backward compatibility with v0.x
code.

Exit does NOT shut down the runtime (HPX can't restart within a process).
Shutdown is owned by `atexit`; call `hpyx.shutdown()` explicitly if you
need to force an early stop.
"""

from __future__ import annotations

from hpyx import _runtime


class HPXRuntime:
    """Context manager that ensures the HPX runtime is running.

    Parameters
    ----------
    os_threads : int | None
        Number of HPX worker OS threads. Defaults to HPYX_OS_THREADS env
        var or os.cpu_count().
    cfg : list[str] | None
        Extra HPX config strings (e.g., ["hpx.stacks.small_size=0x20000"]).
    """

    def __init__(
        self,
        *,
        os_threads: int | None = None,
        cfg: list[str] | None = None,
    ) -> None:
        self._os_threads = os_threads
        self._cfg = cfg

    def __enter__(self) -> "HPXRuntime":
        _runtime.ensure_started(os_threads=self._os_threads, cfg=self._cfg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # No-op — atexit owns shutdown. HPX cannot restart, so exiting
        # the context does NOT tear down the runtime.
        return None
```

- [ ] **Step 5: Run the tests — deferred until Task 9 updates `__init__.py`**

---

## Task 8: Create `src/hpyx/debug.py`

**Files:**
- Create: `src/hpyx/debug.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_debug.py`:

```python
import threading

import pytest

from hpyx import HPXExecutor, debug


def test_get_num_worker_threads_positive():
    # Session fixture started runtime with os_threads=4.
    assert debug.get_num_worker_threads() == 4


def test_get_worker_thread_id_from_python_thread_is_minus_one():
    # Calling from the main Python thread (not an HPX worker) returns -1.
    assert debug.get_worker_thread_id() == -1


def test_get_worker_thread_id_from_hpx_thread_is_valid():
    # Smoke: from inside an HPX-scheduled callable (via HPXExecutor once it
    # works in Plan 2), the worker id is 0..num_worker_threads-1.
    # Plan 1 marks this test xfail until Plan 2 lands a working executor.
    pytest.xfail("HPXExecutor is rewritten in Plan 2")


def test_enable_tracing_is_stubbed():
    with pytest.raises(NotImplementedError, match="v1.x"):
        debug.enable_tracing("/tmp/hpyx.jsonl")


def test_disable_tracing_is_stubbed():
    with pytest.raises(NotImplementedError, match="v1.x"):
        debug.disable_tracing()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pixi run -e test-py313t pytest tests/test_debug.py -v
```

Expected: `ImportError: cannot import name 'debug' from 'hpyx'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/hpyx/debug.py`:

```python
"""Diagnostics and tracing hooks.

Phase-0 scope: query-only (worker thread count + current thread id).
`enable_tracing` / `disable_tracing` are stubbed and raise — full
JSONL-output implementation ships in Plan 4.
"""

from __future__ import annotations

from hpyx import _core, _runtime


def get_num_worker_threads() -> int:
    """Return the number of HPX worker OS threads in the default pool."""
    _runtime.ensure_started()
    return int(_core.runtime.num_worker_threads())


def get_worker_thread_id() -> int:
    """Return the caller's HPX worker thread id, or -1 if not on an HPX thread."""
    _runtime.ensure_started()
    return int(_core.runtime.get_worker_thread_id())


def enable_tracing(path: str | None = None) -> None:
    """Start capturing per-task events as JSONL. Ships in v1.x."""
    raise NotImplementedError("hpyx.debug.enable_tracing ships in v1.x (Plan 4)")


def disable_tracing() -> None:
    """Stop capturing per-task events. Ships in v1.x."""
    raise NotImplementedError("hpyx.debug.disable_tracing ships in v1.x (Plan 4)")
```

- [ ] **Step 4: Run the tests — deferred until Task 9 updates `__init__.py`**

---

## Task 9: Update `src/hpyx/__init__.py`

**Files:**
- Modify: `src/hpyx/__init__.py`

- [ ] **Step 1: Read the existing file**

```bash
cat src/hpyx/__init__.py
```

Current content exports `HPXExecutor`, `HPXRuntime`, `futures`, `multiprocessing`.

- [ ] **Step 2: Write the new `__init__.py`**

Replace contents with:

```python
"""HPyX: Pythonic bindings for the HPX C++ parallel runtime.

HPyX v1 provides:

- ``HPXExecutor`` — a real ``concurrent.futures.Executor`` backed by HPX.
- ``async_`` / ``Future`` / ``when_all`` / ``when_any`` / ``dataflow`` — HPX futures composition.
- ``hpyx.parallel`` — 17 parallel algorithms with Python callbacks.
- ``hpyx.kernels`` — 5 C++-native kernels over numpy arrays.
- ``hpyx.aio`` — asyncio integration (awaitable ``Future``).

On first use, HPyX auto-initializes the HPX runtime with sensible defaults.
Call ``hpyx.init(os_threads=N, cfg=[...])`` before any other HPyX API to
customize. See ``docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md``
for the full design.
"""

from __future__ import annotations

try:
    from hpyx._version import version as __version__
except ImportError:
    __version__ = "0.0.0"

from hpyx import _runtime, config, debug
from hpyx._runtime import is_running, shutdown

# Legacy surfaces — these continue to import cleanly; Plan 2 reshapes
# hpyx.futures and hpyx.executor, Plan 3 adds hpyx.parallel / hpyx.kernels.
from hpyx.executor import HPXExecutor
from hpyx.runtime import HPXRuntime
from hpyx import futures, multiprocessing


def init(
    *,
    os_threads: int | None = None,
    cfg: list[str] | None = None,
) -> None:
    """Explicitly start the HPX runtime. Idempotent within a process.

    Raises RuntimeError if the runtime is already started with conflicting
    config, or if the runtime was previously stopped (HPX cannot restart).

    Parameters
    ----------
    os_threads : int | None
        Number of HPX worker OS threads. Defaults to HPYX_OS_THREADS env
        var if set, otherwise ``os.cpu_count()``.
    cfg : list[str] | None
        Extra HPX config strings, e.g. ``["hpx.stacks.small_size=0x20000"]``.
    """
    _runtime.ensure_started(os_threads=os_threads, cfg=cfg)


__all__ = [
    "HPXExecutor",
    "HPXRuntime",
    "__version__",
    "config",
    "debug",
    "futures",
    "init",
    "is_running",
    "multiprocessing",
    "shutdown",
]
```

- [ ] **Step 3: Run every test written so far**

```bash
pixi run -e test-py313t pytest tests/test_config.py tests/test_runtime.py tests/test_debug.py -v
```

Expected: all Task 5/6/7/8 tests pass. If not, triage:
- `ImportError` → check circular imports between `_runtime.py`, `config.py`, and `__init__.py`. `_runtime.py` imports from `hpyx.config` — that's fine because `config.py` has no imports from `hpyx`. `__init__.py` imports `_runtime`, `config`, `debug`, `executor`, `runtime`, `futures`, `multiprocessing` — order matters.
- `AttributeError: module 'hpyx._core' has no attribute 'runtime'` → the C++ rebuild failed silently; re-run `pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .`.

- [ ] **Step 4: Minimal patch to `src/hpyx/executor.py`** so instantiation doesn't crash (`__init__` and `shutdown` call the deleted `_core.init_hpx_runtime`/`_core.stop_hpx_runtime`). Do NOT rewrite the full executor — Plan 2 handles that. Goal: the class imports and constructs; `submit` stays broken (xfail/skip in pre-existing `test_submit.py`).

The existing file has exactly two lines to patch: `hpyx._core.init_hpx_runtime(cfg)` at the end of `__init__` (around line 92), and `hpyx._core.stop_hpx_runtime()` at the end of `shutdown` (around line 147).

In `src/hpyx/executor.py`, replace the body of `__init__` starting from the `cfg = [...]` assignment:

```python
# Before (around line 83):
        cfg = [
            f"hpx.run_hpx_main!={int(run_hpx_main)}",
            f"hpx.commandline.allow_unknown!={int(allow_unknown)}",
            f"hpx.commandline.aliasing!={int(aliasing)}",
            f"hpx.os_threads!={os_threads}",
            f"hpx.diagnostics_on_terminate!={int(diagnostics_on_terminate)}",
            f"hpx.parcel.tcp.enable!={int(tcp_enable)}",
        ]

        hpyx._core.init_hpx_runtime(cfg)
```

```python
# After:
        # Plan 2 rewrites HPXExecutor as a real concurrent.futures.Executor.
        # For Phase 0 we only fix instantiation so the import path doesn't
        # crash. The HPX-style kwargs (run_hpx_main, allow_unknown, etc.)
        # are now baked into _runtime._build_cfg_strings defaults; only
        # os_threads still threads through.
        from hpyx import _runtime
        _runtime.ensure_started(os_threads=os_threads)
```

And replace the body of `shutdown`:

```python
# Before (around line 147):
        hpyx._core.stop_hpx_runtime()
```

```python
# After:
        # Plan 2 implements real per-handle shutdown semantics.
        # atexit owns process-level teardown; nothing to do here in Phase 0.
        return None
```

Then verify import + construction:

```bash
pixi run -e test-py313t python -c "
from hpyx import HPXExecutor, is_running
ex = HPXExecutor(os_threads=4)
print('executor constructed, runtime running:', is_running())
ex.shutdown()
print('shutdown no-op, runtime still running:', is_running())
"
```

Expected: `executor constructed, runtime running: True` and `shutdown no-op, runtime still running: True`.

Note: `HPXExecutor.submit` still references the unbound `hpyx._core.hpx_async_set_result` — that's the real broken bit Plan 2 fixes. Any pre-existing test that calls `executor.submit(...)` continues to fail exactly as before.

- [ ] **Step 5: Re-run the full v1 foundation test set**

```bash
pixi run -e test-py313t pytest tests/test_config.py tests/test_runtime.py tests/test_debug.py -v
```

Expected: all pass.

---

## Task 10: Create `tests/conftest.py`

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the conftest**

Create `tests/conftest.py`:

```python
"""Pytest configuration for HPyX tests.

The session-scoped HPX runtime fixture starts HPX once at session start
with a deterministic thread count so tests are reproducible. Individual
tests may not shut down the runtime (HPX can't restart in-process); use
``@pytest.mark.skip_after_shutdown`` if a test would need a post-shutdown
runtime.
"""

from __future__ import annotations

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "skip_after_shutdown: skip this test if the HPX runtime has been stopped",
    )


@pytest.fixture(scope="session", autouse=True)
def hpx_runtime():
    """Start the HPX runtime once per pytest session.

    Uses a deterministic os_threads=4 so tests asserting on worker count
    are portable across developer machines and CI.
    """
    import hpyx
    hpyx.init(os_threads=4)
    yield
    # atexit owns shutdown — don't call hpyx.shutdown() here.
```

- [ ] **Step 2: Run all tests written so far with the fixture active**

```bash
pixi run -e test-py313t pytest tests/test_config.py tests/test_runtime.py tests/test_debug.py -v
```

Expected: all pass. Notice that `test_get_num_worker_threads_positive` now passes because the session fixture set `os_threads=4`.

---

## Task 11: Flesh out `tests/test_runtime.py`

**Files:**
- Modify: `tests/test_runtime.py` (expand beyond the skeleton from Task 6 Step 1)

- [ ] **Step 1: Replace the skeleton with the full test set**

Replace `tests/test_runtime.py` with:

```python
"""Tests for hpyx runtime lifecycle."""

import pytest

import hpyx
from hpyx import HPXRuntime, _runtime, is_running


# ---- ensure_started idempotency ----

def test_ensure_started_is_idempotent():
    # Session fixture already started the runtime. Further calls are no-ops.
    _runtime.ensure_started()
    assert is_running()
    _runtime.ensure_started()
    assert is_running()


def test_init_idempotent_with_same_args():
    hpyx.init(os_threads=4)
    hpyx.init(os_threads=4)  # no-op, must not raise
    assert is_running()


def test_init_raises_on_conflicting_threads():
    # Session fixture used os_threads=4.
    with pytest.raises(RuntimeError, match="different config"):
        hpyx.init(os_threads=2)


def test_init_raises_on_conflicting_cfg():
    with pytest.raises(RuntimeError, match="different config"):
        hpyx.init(cfg=["hpx.stacks.small_size=0x40000"])


# ---- is_running query ----

def test_is_running_true_during_session():
    assert is_running()


# ---- HPXRuntime context manager ----

def test_HPXRuntime_context_manager():
    assert is_running()
    with HPXRuntime() as rt:
        assert rt is not None
        assert is_running()
    # Exit does NOT shut down — atexit owns shutdown.
    assert is_running()


def test_HPXRuntime_nested_is_idempotent():
    with HPXRuntime():
        with HPXRuntime():
            assert is_running()
        assert is_running()
    assert is_running()


# ---- env var precedence ----

def test_ensure_started_honors_explicit_over_env(monkeypatch):
    # Runtime already started; this just verifies that kwargs validated against
    # the running config win over env (no restart happens, but an explicit
    # matching kwarg should be accepted).
    monkeypatch.setenv("HPYX_OS_THREADS", "16")
    _runtime.ensure_started(os_threads=4)  # matches session, no-op
    assert is_running()
    with pytest.raises(RuntimeError, match="different config"):
        _runtime.ensure_started(os_threads=16)


# ---- "cannot restart" constraint ----
# These are skip_after_shutdown because running them would leave the runtime
# stopped and break subsequent tests. Include them so the behavior is
# documented and testable with `pytest -m skip_after_shutdown` in a
# dedicated process.

@pytest.mark.skip_after_shutdown
def test_shutdown_makes_further_init_raise():
    hpyx.shutdown()
    assert not is_running()
    with pytest.raises(RuntimeError, match="cannot restart"):
        hpyx.init()


@pytest.mark.skip_after_shutdown
def test_shutdown_is_idempotent():
    hpyx.shutdown()
    hpyx.shutdown()  # no-op; must not raise
    assert not is_running()
```

- [ ] **Step 2: Configure pytest to skip `skip_after_shutdown` tests by default**

Add to `tests/conftest.py` (extend the file created in Task 10):

```python
def pytest_collection_modifyitems(config, items):
    """Skip tests marked skip_after_shutdown unless run in isolation.

    These tests leave the runtime stopped; running them in-session would
    break subsequent tests. Use `pytest -m skip_after_shutdown -p no:cacheprovider`
    in a separate process to execute them.
    """
    if config.getoption("-m") == "skip_after_shutdown":
        return  # user explicitly requested them; don't skip
    skip = pytest.mark.skip(reason="Leaves runtime stopped; run in isolation")
    for item in items:
        if "skip_after_shutdown" in item.keywords:
            item.add_marker(skip)
```

- [ ] **Step 3: Run the runtime tests**

```bash
pixi run -e test-py313t pytest tests/test_runtime.py -v
```

Expected output: all non-`skip_after_shutdown` tests pass; the two skip-after-shutdown tests are SKIPPED with the "run in isolation" reason.

- [ ] **Step 4: Run the isolation tests separately to prove they work**

```bash
pixi run -e test-py313t pytest tests/test_runtime.py -m skip_after_shutdown -v
```

Expected: both skip-after-shutdown tests PASS.

---

## Task 12: Final full-suite test run before commit

- [ ] **Step 1: Run every test in `tests/`**

```bash
pixi run -e test-py313t pytest tests/ -v
```

Expected:
- All Plan-1 tests (`test_config.py`, `test_runtime.py`, `test_debug.py`) pass.
- `test_hpx_linalg.py` passes (it uses `HPXRuntime` which now delegates to `_runtime.ensure_started`).
- `test_for_loop.py` and `test_submit.py` MAY fail — these exercise the broken `hpx_for_loop` par path and broken `HPXExecutor.submit` respectively. Plans 2 and 3 fix these. Record the baseline failure set.

- [ ] **Step 2: Verify free-threaded 3.13t build**

The default `test-py313t` environment already uses free-threaded 3.13t. Confirm:

```bash
pixi run -e test-py313t python -c "
import sysconfig
print('GIL disabled:', sysconfig.get_config_var('Py_GIL_DISABLED'))
"
```

Expected: `GIL disabled: 1`.

- [ ] **Step 3: Smoke-test concurrent init from multiple threads**

```bash
pixi run -e test-py313t python -c "
import threading
import hpyx

results = [False] * 8
def worker(i):
    hpyx.init(os_threads=4)  # all threads call init concurrently
    results[i] = hpyx.is_running()

ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
for t in ts: t.start()
for t in ts: t.join()
print('all threads saw is_running:', all(results))
"
```

Expected: `all threads saw is_running: True`.

---

## Task 13: Commit Phase 0

- [ ] **Step 1: Verify staged changes**

```bash
git status
git diff --stat HEAD
```

Expected staged/modified files:
- `src/_core/*` (moved + modified runtime files; other files just moved)
- `CMakeLists.txt`
- `CMakePresets.json`
- `src/hpyx/__init__.py`
- `src/hpyx/_runtime.py` (new)
- `src/hpyx/config.py` (new)
- `src/hpyx/debug.py` (new)
- `src/hpyx/runtime.py` (modified)
- `src/hpyx/executor.py` (minor patch — delete-migration of `init_hpx_runtime` call)
- `tests/conftest.py` (new)
- `tests/test_config.py` (new)
- `tests/test_runtime.py` (new)
- `tests/test_debug.py` (new)

Verify nothing unrelated is staged — no `.DS_Store`, no `__pycache__`, no `.env*`, no `blah`, no debug scripts in repo root.

- [ ] **Step 2: Stage only what this plan produced**

```bash
git add src/_core CMakeLists.txt CMakePresets.json src/hpyx tests/
```

- [ ] **Step 3: Create the commit**

```bash
git commit -m "$(cat <<'EOF'
feat(_core): add v1 runtime foundation and src/_core/ refactor

Phase 0 of the v1 Pythonic HPX binding design:

- Refactors src/*.cpp into src/_core/ (no behavior change in the move)
- Rewrites runtime.cpp with a clean API: runtime_start, runtime_stop,
  runtime_is_running, num_worker_threads, get_worker_thread_id,
  hpx_version_string — all registered on the _core.runtime submodule.
- Releases the GIL around hpx::start construction (previously acquired,
  which could deadlock free-threaded builds).
- Adds hpyx._runtime with ensure_started + atexit-owned shutdown.
- Adds hpyx.config with HPYX_OS_THREADS / HPYX_CFG / HPYX_AUTOINIT /
  HPYX_TRACE_PATH env var parsing.
- Adds hpyx.debug with get_num_worker_threads / get_worker_thread_id;
  tracing hooks are stubbed (ship in v1.x per plan).
- Refactors hpyx.runtime.HPXRuntime to a thin wrapper on ensure_started;
  exit no longer tears down (HPX cannot restart).
- Exposes hpyx.init / hpyx.shutdown / hpyx.is_running at the package root.
- Adds CMakePresets.json with default + profile presets (RelWithDebInfo
  + -fno-omit-frame-pointer) for downstream py-spy/perf/memray use.
- Adds session-scoped HPX fixture in tests/conftest.py plus
  skip_after_shutdown marker.
- Covers the above with tests/test_runtime.py, tests/test_config.py,
  tests/test_debug.py.

Pre-existing failures in test_for_loop.py (par policy) and
test_submit.py (broken HPXExecutor) remain — Plans 2 and 3 fix those.

See docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md for the
full design and docs/plans/2026-04-24-hpyx-v1-phase-0-foundation.md for
this plan.
EOF
)"
```

- [ ] **Step 4: Verify the commit**

```bash
git log --oneline -3
git status
```

Expected: the new commit appears at HEAD on branch `feat/v1-phase-0-foundation`; working tree clean.

---

## Task 14: Push the branch and open a draft PR (optional)

- [ ] **Step 1: Push**

```bash
git push -u origin feat/v1-phase-0-foundation
```

- [ ] **Step 2: Open a draft PR referencing the spec + plan**

```bash
gh pr create --draft --title "feat(_core): v1 Phase 0 — runtime foundation" --body "$(cat <<'EOF'
## Summary

- Refactor `src/*.cpp` into `src/_core/`
- Rewrite runtime with clean API (`runtime_start` / `runtime_stop` / `runtime_is_running` / `num_worker_threads` / `get_worker_thread_id` / `hpx_version_string`)
- Fix GIL-around-hpx::start bug
- Land `hpyx._runtime`, `hpyx.config`, `hpyx.debug` + `hpyx.init` / `hpyx.shutdown` / `hpyx.is_running`
- Add `CMakePresets.json` with `default` + `profile` presets
- Session-scoped pytest fixture + `skip_after_shutdown` marker

## Spec + plan

- Spec: `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md`
- Plan: `docs/plans/2026-04-24-hpyx-v1-phase-0-foundation.md`

## Test plan

- [x] `pytest tests/test_config.py` passes
- [x] `pytest tests/test_runtime.py` passes (non-isolation)
- [x] `pytest tests/test_runtime.py -m skip_after_shutdown` passes (isolation)
- [x] `pytest tests/test_debug.py` passes
- [x] `pytest tests/test_hpx_linalg.py` still passes (legacy behavior preserved via refactored HPXRuntime)
- [x] Free-threaded 3.13t: `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`
- [x] `cmake --list-presets` shows `default` and `profile`
- [ ] (Deferred to Plan 2) `test_submit.py` — HPXExecutor rewrite
- [ ] (Deferred to Plan 3) `test_for_loop.py` par policy

## What's NOT in this PR

Plans 2-5 will land:
- futures.cpp rewrite + HPXExecutor (Plan 2)
- parallel/kernels algorithms + execution policies (Plan 3)
- asyncio bridge + benchmark infra (Plan 4)
- Docs + CI matrix (Plan 5)
EOF
)"
```

---

## Forthcoming plans (high-level scope for the remaining v1 phases)

These are not part of this plan — each gets its own TDD-detail document once Plan 1 merges. Summaries here so reviewers see the arc.

### Plan 2: Futures + Executor + asyncio bridge (spec §§3.2, 4.4, 4.5, 4.8)

**Goal:** land true `hpx::launch::async` futures composition, `concurrent.futures.Executor`-compatible `HPXExecutor`, and the asyncio Level-2 bridge (`__await__` on `Future`, `hpyx.aio` combinators).

**Major tasks:**
1. Rewrite `src/_core/futures.cpp` — `HPXFuture` class wrapping `hpx::shared_future<nb::object>`, `async_submit`, `when_all`, `when_any`, `dataflow`, `ready_future`. Register on `_core.futures` submodule.
2. Implement `src/hpyx/futures/_future.py` — `Future` class with full `concurrent.futures.Future` protocol (`result`, `exception`, `done`, `cancelled`, `running`, `cancel`, `add_done_callback`) plus `.then` and `__await__`.
3. Implement `src/hpyx/futures/__init__.py` free functions: `async_`, `when_all`, `when_any`, `dataflow`, `shared_future`, `ready_future`.
4. Rewrite `src/hpyx/executor.py` — `HPXExecutor(concurrent.futures.Executor)` with `submit` / `map` / `shutdown` / context manager.
5. Implement `src/hpyx/aio.py` — `__await__` bridging via `loop.call_soon_threadsafe`, plus `await_all` / `await_any`.
6. Tests: `test_futures.py`, `test_executor.py`, `test_aio.py`, `test_dask_integration.py` (smoke `dask.compute(..., scheduler=HPXExecutor())`).
7. Risk #1 mitigation: feature flag `HPYX_ASYNC_MODE=deferred|async` with `async` default; `deferred` available for emergency rollback.

### Plan 3: Parallel algorithms + kernels + execution policies (spec §§3.3, 3.4, 4.3, 4.6, 4.7)

**Goal:** 17 Python-callback parallel algorithms plus 5 C++-native kernels over numpy arrays, with chunk-size-aware execution policies. Deprecation shim for `hpyx.multiprocessing` lands here (since `hpyx.parallel.for_loop` now exists to replace it).

**Major tasks:**
1. Land `src/_core/policy_dispatch.hpp` + `src/_core/gil_macros.hpp`.
2. Implement `src/hpyx/execution.py` — `seq`/`par`/`par_unseq`/`unseq`/`task` + chunk-size modifiers + `PolicyToken` marshalling.
3. Implement `src/_core/parallel.cpp` — 17 algorithms, staged in PRs grouped by family (iteration, transform/reduce, search, sort, fill/copy, scan). Each is ~15 LOC using `HPYX_CALLBACK_GIL`.
4. Implement `src/_core/kernels.cpp` — 5 C++ kernels over `nb::ndarray<T, nb::c_contig>` for `T ∈ {float32, float64, int32, int64}`. Each uses `HPYX_KERNEL_NOGIL`.
5. Implement `src/hpyx/parallel.py` — thin dispatch wrappers. Keyword-only args for `reduce` / `transform_reduce` / scans (per spec §4.6 footgun avoidance).
6. Implement `src/hpyx/kernels.py` — thin dispatch wrappers with dtype checking.
7. Convert `hpyx.multiprocessing.for_loop` into a `DeprecationWarning` shim re-exporting `hpyx.parallel.for_loop`.
8. Tests: `test_parallel.py` (vs stdlib reference), `test_kernels.py` (vs numpy), `test_execution_policy.py` (policy composition), `test_free_threaded.py` (multi-thread submit race detection).

### Plan 4: Benchmark infrastructure + full diagnostics (spec §6.2, §4.9)

**Goal:** land the seven shared fixtures, the authoring contract, the `profile` workflow, and real `enable_tracing` output.

**Major tasks:**
1. Write `benchmarks/conftest.py` — seven fixtures (`pin_cpu`, `seed_rng`, `no_gc`, `hpx_runtime`, `hpx_threads`, `requires_free_threading`, `env_sanity_check`).
2. Write `scripts/run_bench_local.sh` with `bench` / `record` / `compare` subcommands.
3. Write `benchmarks/README.md` (authoring contract + profiling recipes).
4. Rewrite `benchmarks/test_bench_for_loop.py` → `benchmarks/test_bench_parallel.py` per authoring contract.
5. Add `benchmarks/test_bench_kernels.py`, `benchmarks/test_bench_executor.py`, `benchmarks/test_bench_futures.py`, `benchmarks/test_bench_aio.py`.
6. Add dedicated runtime files: `benchmarks/test_bench_thread_scaling.py`, `benchmarks/test_bench_free_threading.py`, `benchmarks/test_bench_cold_start.py`.
7. Implement real `hpyx.debug.enable_tracing(path)` writing JSONL task events.
8. Tests: `test_debug.py` gets cases for the real tracing (un-`xfail` the placeholder).

### Plan 5: Docs, migration guide, CI matrix (spec §§6.3, 6.4, 2.2 docs/)

**Goal:** ship docs for the three audiences, the migration story, the contributor binding guide, and expand CI to the full free-threaded matrix.

**Major tasks:**
1. `docs/adding-a-binding.md` — worked example for adding a new parallel algorithm and a new kernel. Verified by `tests/test_contributor_example.py`.
2. `docs/migration-0.x-to-1.0.md` — before/after snippets for every breaking change.
3. `docs/user-guides/` — `scientific-python.md`, `concurrent-futures.md`, `hpx-native.md`, `dask-integration.md`, `asyncio.md`, `diagnostics.md`, `free-threaded.md`.
4. CI matrix: add `{3.13, 3.13t} × {ubuntu, macos} × {conda-forge, Release}` to `.github/workflows/*.yml`. Nightly job for vendor-build + Debug + full benchmark run (non-gating).
5. Large-graph and error-propagation integration tests.

---

## Self-review notes

**Spec coverage (Phase 0 scope subset of spec §1.6):**
- ✅ Item 5 "Runtime lifecycle: implicit auto-init + explicit `hpyx.init()` + atexit cleanup" — covered by Tasks 3-7, 10-11.
- ✅ Item 7 "Basic diagnostics: `get_num_worker_threads`, `get_worker_thread_id`" — covered by Task 8, 12. `enable_tracing` is stubbed (full impl deferred to Plan 4 per out-of-scope list above; consistent with spec §4.9 which describes the target and §1.5 success criteria that says enable_tracing produces JSONL — this plan ships the stub, Plan 4 ships the real thing).
- Spec §6.2 CMake `profile` preset — covered by Task 3.
- Spec §1.3 "cannot-restart" invariant — covered by Task 4's `g_stopped` flag and tested in Task 11 isolation tests.

Items 1, 2, 3, 4, 6, 8 of spec §1.6 are **explicitly** out of Phase 0 scope and handled by Plans 2-5 above.

**Placeholder scan:** no `TBD`/`TODO`/`FIXME` in this plan. References to "Plan 2/3/4/5 handles X" are scope boundaries, not placeholders.

**Type consistency check:**
- C++ names consistent across `runtime.hpp` and `runtime.cpp`: `runtime_start`, `runtime_stop`, `runtime_is_running`, `num_worker_threads`, `get_worker_thread_id`, `hpx_version_string`.
- Python names consistent across `_runtime.py`, `__init__.py`, `runtime.py`, `debug.py`, tests: `ensure_started`, `shutdown`, `is_running`, `init`, `HPXRuntime`, `get_num_worker_threads`, `get_worker_thread_id`, `enable_tracing`, `disable_tracing`.
- Config keys consistent across `config.py`, `_runtime.py`, tests: `os_threads`, `cfg`, `autoinit`, `trace_path`. Env var names consistent: `HPYX_OS_THREADS`, `HPYX_CFG`, `HPYX_AUTOINIT`, `HPYX_TRACE_PATH`.

**Known caveats:**
- Task 9 Step 4 includes a minor patch to `src/hpyx/executor.py` just to keep the import path working. This is *not* the Plan-2 executor rewrite — it's a one-line fix to avoid `ImportError` during Phase 0 tests. The docstring/behavior of `HPXExecutor.submit` stays broken and is flagged explicitly in the commit message and Plan 2.
- `hpyx.multiprocessing.for_loop` still points at the broken `_core.hpx_for_loop` (par policy raises `NotImplementedError`). Plan 3 deprecates the whole module.
