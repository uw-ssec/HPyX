# Architecture Decisions

A running log of significant architecture decisions made during HPyX development. Entries are listed newest-first within each phase.

---

## Phase 0 — Foundation (2026-04-24)

### 2026-04-24: Move C++ sources into `src/_core/` package (Implemented)

- **Decision:** Move all flat `src/*.cpp` / `src/*.hpp` files into `src/_core/` and rename `init_hpx.*` → `runtime.*`.
- **Why:** The old flat layout put `bind.cpp`, `init_hpx.cpp`, `algorithms.cpp`, and `futures.cpp` all in the same directory as the Python `hpyx/` package, with no structural separation between the top-level module glue and the implementation units. As HPyX grows to cover futures, parallel algorithms, and kernels, each gets its own `.cpp` file under `_core/`. The new layout gives nanobind a clean home (`src/_core/`) and makes it obvious that everything under `_core/` is compiled C++ while `src/hpyx/` is pure Python.
- **Result:** `CMakeLists.txt` updated to reference `src/_core/*.cpp`. No behavior change — 62 existing tests pass unchanged. `init_hpx.cpp` renamed `runtime.cpp` to match its actual responsibility.

### 2026-04-24: Expose runtime API as `_core.runtime` submodule (Implemented)

- **Decision:** Register the HPX runtime bindings on a `_core.runtime` submodule (via `register_bindings(nb::module_&)`) rather than directly on `_core`.
- **Why:** HPyX v1 will expose `_core.futures`, `_core.parallel`, and `_core.kernels` as separate submodules. Keeping runtime on the top-level `_core` namespace would mean future calls like `_core.runtime_start()` sit alongside `_core.dot1d()`, which is confusing. Moving them to `_core.runtime.*` now avoids a breaking rename later.
- **Result:** `_core.runtime_start`, `_core.stop_hpx_runtime`, etc. are removed from the top-level namespace. Replaced by `_core.runtime.runtime_start`, `_core.runtime.runtime_stop`, `_core.runtime.runtime_is_running`, `_core.runtime.num_worker_threads`, `_core.runtime.get_worker_thread_id`, `_core.runtime.hpx_version_string`. Callers in `print_versions.py` updated.

### 2026-04-24: Release GIL during `hpx::start` construction (Implemented)

- **Decision:** `runtime_start` releases the GIL (`nb::gil_scoped_release`) around the `new global_runtime_manager(cfg)` call instead of holding it.
- **Why:** The original `init_hpx_runtime` held a `nb::gil_scoped_acquire` around runtime construction. Under GIL-mode Python this was harmless but redundant. Under **free-threaded Python 3.13t** it is a bug: `hpx::start` spawns OS threads that eventually call Python-side callbacks; if the GIL is held during the blocking startup CV wait, any new thread that tries to acquire the GIL deadlocks. The fix is to release the GIL before calling `hpx::start` so worker threads can proceed.
- **Result:** `runtime_start` correctly supports both GIL-mode and free-threaded builds. Smoke-tested with `sysconfig.get_config_var("Py_GIL_DISABLED") == 1` on Python 3.13t.

### 2026-04-24: `g_stopped` flag prevents in-process restart (Implemented)

- **Decision:** Add an `std::atomic<bool> g_stopped` flag that is set to `true` on `runtime_stop` and causes `runtime_start` to throw `RuntimeError` on any subsequent call.
- **Why:** HPX explicitly prohibits restarting the runtime within the same process (it uses process-global singletons for the scheduler, AGAS, etc.). Without this flag, calling `_core.runtime.runtime_start()` after a stop would silently fail or crash. The flag surfaces the constraint as a clear Python exception.
- **Result:** `RuntimeError: HPyX runtime has been stopped and cannot restart within this process` is raised on any restart attempt. Tested in `tests/test_runtime.py::test_shutdown_makes_further_init_raise`.

### 2026-04-24: `hpyx._runtime` as the single auto-init authority (Implemented)

- **Decision:** All public Python APIs that need the HPX runtime call `hpyx._runtime.ensure_started()` rather than calling `_core.runtime.runtime_start()` directly.
- **Why:** Without a central authority, every public function would need to independently manage the "has it started yet?" check, the env-var config merge, the conflicting-config error, and the `atexit` registration. That logic would be duplicated across `hpyx.futures`, `hpyx.parallel`, `hpyx.debug`, etc. `_runtime.ensure_started()` is the single place where the lifecycle invariants are enforced.
- **Result:** `hpyx.debug`, `hpyx.runtime.HPXRuntime`, and `hpyx.__init__.init` all delegate to `_runtime.ensure_started()`. The `threading.Lock` in `_runtime` makes it safe for concurrent callers on free-threaded 3.13t.

### 2026-04-24: `atexit` owns HPX shutdown (Implemented)

- **Decision:** `_runtime.ensure_started()` registers `_atexit_shutdown` with Python's `atexit` module on first start. `HPXRuntime.__exit__` is a no-op. There is no automatic teardown at the end of a `with HPXRuntime():` block.
- **Why:** In v0.x, `HPXRuntime.__exit__` called `_core.stop_hpx_runtime()`. This caused two problems: (1) after the context manager exited, any subsequent HPyX call in the same process would fail because HPX can't restart; (2) users writing scripts with multiple `with HPXRuntime():` blocks got silent failures. The atexit approach means the runtime lives for the entire process lifetime — which matches what users actually want 99% of the time.
- **Result:** `HPXRuntime.__exit__` returns `None`. Process cleanup happens via `atexit`. Users who need early shutdown call `hpyx.shutdown()` explicitly and understand the restart constraint.

### 2026-04-24: `CMakePresets.json` with `profile` preset for native profiling (Implemented)

- **Decision:** Add a `profile` preset with `RelWithDebInfo` + `-fno-omit-frame-pointer` + IPO off.
- **Why:** `py-spy --native`, `perf`, and `memray --native` all require C++ frames to be resolvable in the symbol table. A default Release build omits frame pointers (compiler optimization) and enables IPO (inlines away call boundaries), making profiler output unreadable for C++ code. The `profile` preset keeps optimization level (`-O2`) while trading a small performance overhead for reliable frame resolution.
- **Result:** `cmake --preset profile` produces a build suitable for `py-spy record --native -- python my_benchmark.py`. Used by `scripts/run_bench_local.sh` (lands in Plan 4).

### 2026-04-24: `hpyx.config` as pure-Python env-var parser (Implemented)

- **Decision:** `hpyx.config` is a pure-Python module (`from_env()` + `DEFAULTS`), not a C++ binding.
- **Why:** Config values are only needed at Python startup time (before the first `_core.runtime.runtime_start` call). There is no need for C++ to know about `HPYX_OS_THREADS` — Python builds the HPX config strings and passes them as a `list[str]`. Keeping the config layer in Python makes it easy to test with `monkeypatch`, import without a compiled extension, and extend without touching C++.
- **Result:** `tests/test_config.py` has 15 pure-Python tests with no build dependency. Env-var precedence is validated with `monkeypatch`.

### 2026-04-24: `hpyx.debug.enable_tracing` stubbed in Phase 0 (Implemented)

- **Decision:** `enable_tracing` and `disable_tracing` raise `NotImplementedError("ships in v1.x (Plan 4)")` rather than being absent from the public API.
- **Why:** Advertising the tracing surface in Phase 0 stabilizes the public API shape so documentation and user code can reference `hpyx.debug.enable_tracing(path)` consistently. The stub prevents silent `AttributeError`s if someone tries to use it early and gives a clear error message explaining when it ships.
- **Result:** `hpyx.debug` is importable and documented from Phase 0 onward. Full JSONL-output implementation deferred to Plan 4.
