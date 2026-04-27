# Architecture Decisions

A running log of significant architecture decisions made during HPyX development. Entries are listed newest-first within each phase.

---

## Phase 1 — Futures, Executor, asyncio Bridge (2026-04-24)

### 2026-04-27: Phase 1 acceptance criteria — all green (Verified)

End-to-end verification of the Phase 1 deliverables specified in epic #116.

**Test suite:** `pixi run test` reports **130 passed, 2 skipped, 1 xfailed**. The two skips are runtime-isolation tests in `tests/test_runtime.py` that intentionally leave the runtime stopped (run them with `pixi run -e test-py313t pytest tests/test_runtime.py -m skip_after_shutdown`). The xfail is `test_get_worker_thread_id_from_hpx_thread_is_valid` (deferred to Plan 2 alongside the parallel-algorithm bindings).

**Acceptance criteria from #116:**

| Criterion | Status |
|---|---|
| `hpyx.async_(fn, x, y)` runs `fn` on an HPX worker under `launch::async` | ✅ verified by `tests/test_futures.py::test_async_submit_runs_on_hpx_worker` |
| `dask.compute(arr.sum(), scheduler=hpyx.HPXExecutor())` completes for a non-trivial graph | ✅ verified by `tests/test_dask_integration.py` (4 patterns) |
| `await hpyx.async_(fn, x, y)` works inside `asyncio.run(main())` | ✅ verified by `tests/test_aio.py::test_await_future` and `test_await_does_not_block_event_loop` |
| Full test suite passes on free-threaded 3.13t | ✅ 130 passed under `test-py313t` |
| `HPYX_ASYNC_MODE=deferred` rollback flag works | ✅ smoke-tested: `python -c "import hpyx; print(hpyx.async_(lambda: 'from-deferred').result())"` returns `from-deferred` |

**Free-threaded scaling smoke test** (verifies real concurrency, not GIL-serialization): `20 × time.sleep(0.1)` submitted via `HPXExecutor` with `os_threads=4` completes in ~0.2–0.5s (serial would be 2.0s). Reproduce with:

```bash
pixi run -e test-py313t python -c "
import time, hpyx
N = 20
start = time.perf_counter()
with hpyx.HPXExecutor() as ex:
    futs = [ex.submit(time.sleep, 0.1) for _ in range(N)]
    for f in futs: f.result()
print(f'{N}x0.1s in {time.perf_counter() - start:.2f}s')
"
```

**Out of scope for Phase 1** (deferred per epic): parallel algorithms (Plan 2), C++ kernels (Plan 2), `hpyx.execution` policy module (Plan 2), benchmark harness + CI gating (Plan 3+), full `enable_tracing` JSONL output (Plan 4), distributed/multi-locality (v2).

### 2026-04-27: Test dependency is `dask-core`, not `dask` — free-threading constraint (Implemented)

- **Decision:** `pixi.toml` adds `dask-core >=2024.10.0` (and `numpy >=1.26`) under `[feature.test.dependencies]`. The full `dask` metapackage is **not** added.
- **Why:** The free-threaded `test-py313t` environment cannot install the full `dask` metapackage because `dask` pulls in `distributed`, which depends on `tornado`, which does not yet ship a `cp313t` build on conda-forge. The `dask-core` noarch package provides `dask.array`, `dask.delayed`, `dask.base.get_scheduler`, and the entire scheduler-resolution code path that HPyX needs to validate the `dask.compute(scheduler=HPXExecutor())` integration. Dropping `distributed` is acceptable for v1 because HPyX is single-process by design (multi-locality / parcelport ships in v2).
- **Result:** `tests/test_dask_integration.py` runs cleanly under `test-py313t` with all four smoke tests passing (`da.array.sum`, chunked matmul, `dask.delayed` chain, multi-stage reductions). `dask.distributed` integration is explicitly out-of-scope for v1; documented in the dask integration section of the usage guide. Will revisit when upstream `tornado` ships a free-threading build.

### 2026-04-27: Dask integration smoke test pinned at the executor boundary (Implemented)

- **Decision:** `tests/test_dask_integration.py` exercises four code paths: `da.arange(...).sum().compute(scheduler=ex)`, chunked 64×64 matmul against a numpy reference, `dask.delayed` graph compilation, and multi-stage reductions (`mean`, `var`). All four use the `with hpyx.HPXExecutor() as ex:` pattern and pass `scheduler=ex` to `.compute()`. No HPyX-side adapter or dask-side patch is required.
- **Why:** The Phase 1 epic (#116) lists `dask.compute(arr.sum(), scheduler=hpyx.HPXExecutor())` as a top-level acceptance criterion. Pinning the integration with a smoke test (rather than a benchmark or stress test) catches regressions cheaply: any change to `HPXExecutor`'s submit/map/shutdown surface that breaks dask's scheduler resolution will fail these tests in CI before reaching users. The four flavors are deliberately diverse — array reductions, dense linear algebra, lazy graphs, and back-to-back compute calls — so a regression in any one of them shows up as a specific test failure rather than a generic "dask doesn't work."
- **Result:** All 4 tests pass; the dask integration story for v1 is now contractually pinned. Future executor changes that break the `concurrent.futures.Executor` interface will fail at least one of these tests.

### 2026-04-27: `hpyx.Future` inherits from `concurrent.futures.Future` (Implemented)

- **Decision:** `hpyx.futures._future.Future` is a real subclass of `concurrent.futures.Future`. The original Task 5 implementation used composition with duck-typing; the inheritance change went in to support `asyncio.wrap_future` and `loop.run_in_executor`, which both perform `isinstance(fut, concurrent.futures.Future)` checks before threading state through their internals.
- **Why:** The Phase 1 spec (§4.4 acceptance criteria) calls out `asyncio.wrap_future(hpyx_future)` and `loop.run_in_executor(HPXExecutor(), fn, ...)` as required. Both stdlib helpers reject duck-typed futures with `AssertionError: concurrent.futures.Future is expected`. There is no `register()` mechanism on `concurrent.futures.Future` (it is a regular class, not an `ABCMeta`), so virtual subclassing is not an option. Direct inheritance is the only way to satisfy the `isinstance` contract while keeping our custom `result`/`exception`/`done`/etc. semantics. The base class's internal state machine (`_state`, `_condition`, `_waiters`, `_done_callbacks`) becomes dead weight that we synchronize with our `_hpx` future via a private helper (see the next ADR).
- **Result:** `__slots__ = ()` documents that we add no slots beyond what the base class allocates (which has no `__slots__` of its own, so memory savings are not on the table). `super().__init__()` runs in our `__init__`, every method we expose is overridden to delegate to `_hpx`, and `isinstance(hpyx.async_(fn), concurrent.futures.Future)` is now `True`. `tests/test_aio.py::test_wrap_future_works` and `test_run_in_executor_with_HPXExecutor` confirm the integration.

### 2026-04-27: Mirror inherited `_state` so `concurrent.futures.wait` / `as_completed` work (Implemented)

- **Decision:** Whenever the underlying `_hpx` future settles, we eagerly call `concurrent.futures.Future.set_result(self, value)` (or `set_exception`) on `self` to flip the inherited `_state` from `PENDING` to `FINISHED`. The sync is gated by an instance `_base_state_lock` and `_base_state_synced` flag so the operation runs at most once per Future. We register the eager sync in `__init__` (one-shot continuation on the C++ `_hpx`) and we also call it from the `_drain` callback path so user callbacks observe a settled base state.
- **Why:** `concurrent.futures.wait` and `as_completed` do not call `add_done_callback` on subclassed futures — they read `_state` and `_waiters` directly through the base class's `_AcquireFutures` context manager. Without an eager mirror, the base state stayed `PENDING` forever and `wait([fut])` returned `not_done={fut}` even after `fut.result()` succeeded. Putting the sync in `__init__` rather than only in `_drain` ensures interop works regardless of whether the user calls `add_done_callback` (they don't, when calling `concurrent.futures.wait`). The lock + flag prevents the eager and `_drain` paths from racing into `InvalidStateError: FINISHED`.
- **Result:** `tests/test_aio.py::test_hpyx_Future_visible_in_concurrent_futures_wait` and `test_hpyx_Future_visible_in_concurrent_futures_as_completed` confirm interop. The cost per Future is one extra HPX continuation registration plus one extra `_hpx.result()` invocation when the future settles — small but not free; revisit if profiling shows it dominates fan-out workloads.

### 2026-04-27: Override `set_result` / `set_exception` / `set_running_or_notify_cancel` to raise (Implemented)

- **Decision:** The three "setter" methods inherited from `concurrent.futures.Future` are overridden to raise `RuntimeError("hpyx.Future state is set by the HPX runtime; do not call <method> directly")`. The internal sync helper (previous ADR) calls the unbound base methods directly (`concurrent.futures.Future.set_result(self, value)`) to bypass our own override.
- **Why:** Without these overrides, user code can call `fut.set_result('foo')` on an in-flight HPyX future, succeed silently, and corrupt the inherited `_state` to `FINISHED` while `_hpx` keeps running and eventually returns the real value. The reviewer demonstrated this directly: `fut.set_result('user_value'); fut.result()` returned `42` (the real result) while `fut._state` was `'FINISHED'` and `fut.done()` returned `False` — three different views of the same Future, none of them correct. Raising `RuntimeError` on the public API forces the divergence into a loud failure mode.
- **Result:** `tests/test_aio.py::test_set_result_raises`, `test_set_exception_raises`, and `test_set_running_or_notify_cancel_raises` confirm the public methods reject user calls. The internal eager-sync continues to work because it calls `concurrent.futures.Future.set_result(self, value)` (explicit unbound method invocation) which bypasses MRO lookup and never hits our overridden raise.

### 2026-04-27: `Future.__await__` bridges via `loop.create_future()` + `call_soon_threadsafe` (Implemented)

- **Decision:** `hpyx.Future.__await__` lazy-imports `hpyx.aio._future_await`. That coroutine creates an `asyncio.Future` on the running event loop, registers an `_on_done` callback on the hpyx Future via `add_done_callback`, and posts the result/exception back via `loop.call_soon_threadsafe` from the HPX worker thread that completes the future. The asyncio Future is what the user's `await` resumes on.
- **Why:** HPX continuations fire on worker threads, not on the asyncio event loop's thread. The only documented thread-safe primitive for waking up the loop from a foreign thread is `loop.call_soon_threadsafe`. The bridge is intentionally minimal: no thread pool, no synchronization queue, just one `add_done_callback` registration and one `call_soon_threadsafe` invocation per `await`. The `if not aio_fut.done():` guard runs **inside** the lambda passed to `call_soon_threadsafe`, so the check executes on the loop thread under loop ownership — no race, no missing wakeup.
- **Result:** `tests/test_aio.py::test_await_does_not_block_event_loop` registers an asyncio counter task that increments while a 100ms HPX `time.sleep` is in flight; the counter reliably runs ≥50 iterations, proving the loop is not starved. Direct `await`, exception propagation, already-done futures, and `asyncio.gather` over multiple HPyX futures all work.

### 2026-04-27: Loop-closed posts logged at WARNING and dropped silently (Implemented)

- **Decision:** When `loop.call_soon_threadsafe` raises `RuntimeError` (because the event loop has been closed before the HPX future completed), `hpyx.aio` catches the exception, logs at `WARNING` on the `hpyx.aio` logger, and drops the result/exception silently. The HPX worker thread does not re-raise.
- **Why:** Re-raising on a worker thread would tear down the HPX runtime — a pathological response to a benign user error (closing the loop with pending work). Spec §5.2 explicitly classifies this as a WARNING-level event so users who configured logging see a message but unconfigured users (the common case) see nothing. We initially shipped at `DEBUG`, but the reviewer flagged that as functionally invisible — DEBUG is off by default — and we upgraded to WARNING per spec.
- **Result:** Verified manually: a coroutine that creates an HPX future and lets `asyncio.run` exit before the future completes does not crash; a `WARNING:hpyx.aio:hpyx.aio: dropping result; event loop is closed` line appears when the user enables warning-level logging.

### 2026-04-27: `await_all` / `await_any` are async wrappers around `when_all` / `when_any` (Implemented)

- **Decision:** `hpyx.aio.await_all(*futures)` and `hpyx.aio.await_any(*futures)` are `async def` functions that lazy-import `hpyx.futures.when_all` / `when_any`, build the combined Future, and `await` it. The combined Future's `__await__` does the loop-bridge work via `_future_await`.
- **Why:** Users writing async functions want a single-call pattern (`await hpyx.aio.await_all(f1, f2, f3)`) rather than `await hpyx.when_all(f1, f2, f3)` (which also works, but reads less idiomatically inside `async def`). The lazy `from hpyx.futures import when_all` avoids the `aio` ↔ `futures` import cycle that would otherwise trigger when both modules need each other. The `async def` wrapping costs one extra coroutine frame per call, which the reviewer flagged as unnecessary; we kept the async signature for API clarity (the helpers are documented as awaitables, not Future-returners) and accept the negligible per-call overhead.
- **Result:** `tests/test_aio.py::test_aio_await_all`, `test_aio_await_all_propagates_first_failure`, and `test_aio_await_any` cover the happy path, exception short-circuit, and the index-and-list return shape. Exception semantics match `when_all` (first-to-fail wins; siblings finish but the chain raises the first), explicitly diverging from `asyncio.gather`'s default behavior of consuming exceptions.

### 2026-04-27: `hpyx.aio` imports `Future` unconditionally for runtime introspection (Implemented)

- **Decision:** `src/hpyx/aio.py` does `from hpyx.futures._future import Future` at module level (not under `TYPE_CHECKING`). The annotations on `_future_await`, `await_all`, and `await_any` use `Future` directly rather than the `"Future"` string forward-ref.
- **Why:** With the gated import, `typing.get_type_hints(hpyx.aio.await_all)` raised `NameError: name 'Future' is not defined` because the runtime resolution couldn't find the symbol. This breaks Sphinx autodoc with `autodoc_typehints = "description"`, FastAPI parameter introspection, and any tool that reflects on signatures. Importing `Future` from `_future` (the leaf module, not the `hpyx.futures` package init) keeps the import cycle benign: `_future.py` does not import `hpyx.aio` at module load (`__await__` uses a function-local import), so `aio.py` → `_future.py` is safe.
- **Result:** `typing.get_type_hints(hpyx.aio._future_await)` now resolves cleanly. The `from __future__ import annotations` directive at the top of `aio.py` keeps annotations lazy, so the new top-level import has no measurable startup cost.

### 2026-04-27: `HPXExecutor` is a true `concurrent.futures.Executor` subclass (Implemented)

- **Decision:** `hpyx.HPXExecutor` inherits from `concurrent.futures.Executor` and implements `submit`, `map`, and `shutdown` directly. `submit(fn, /, *args, **kwargs)` returns `hpyx.async_(fn, *args, **kwargs)`. `__enter__`/`__exit__` are inherited from the stdlib base.
- **Why:** The dask integration story (`dask.compute(arr.sum(), scheduler=HPXExecutor())`) only works if `isinstance(ex, concurrent.futures.Executor)` is true — dask's scheduler resolution checks the protocol structurally. Subclassing the stdlib base gives that for free, plus `loop.run_in_executor`, `asyncio.wrap_future`, and any third-party library that already targets the stdlib. The previous v0.x executor inherited from `Executor` but its `submit` was broken (referenced an unbound `hpx_async_set_result`); the rewrite makes that contract real.
- **Result:** `tests/test_executor.py` confirms `issubclass(hpyx.HPXExecutor, concurrent.futures.Executor)`, basic `submit`/`map`/`shutdown` semantics, args/kwargs forwarding, and exception propagation. The dask smoke test ships in a follow-up task.

### 2026-04-27: Per-handle `shutdown()`; `atexit` owns process-level HPX teardown (Implemented)

- **Decision:** `HPXExecutor.shutdown()` sets `self._closed = True` and returns. It does not call `_runtime.shutdown()` and does not stop the HPX runtime. Subsequent `submit`/`map` on the same handle raise `RuntimeError("cannot schedule new futures after shutdown")`. Other live `HPXExecutor` handles continue to work. The HPX runtime itself only stops when the `atexit` handler fires at process exit.
- **Why:** HPX is a process-global singleton: it cannot host multiple runtimes per process and cannot restart after a stop. Tying executor lifetime to runtime lifetime would mean a single `with HPXExecutor():` block ends the runtime forever, which is hostile to scripts that want multiple sequential `with` blocks. Decoupling per-handle shutdown from process-level teardown matches user mental models from `concurrent.futures.ThreadPoolExecutor` (where a shutdown thread pool's threads also disappear, but the *process* keeps running) while respecting HPX's hard restart constraint.
- **Result:** `test_separate_handles_independent_shutdown` and `test_context_manager_shuts_down` confirm the per-handle semantics. `test_submit_after_shutdown_raises` and `test_map_after_shutdown_raises` confirm the post-shutdown error path. The error message intentionally matches the stdlib `ThreadPoolExecutor` exactly.

### 2026-04-27: `max_workers` is advisory; mismatches with the running runtime warn instead of erroring (Implemented)

- **Decision:** `HPXExecutor(max_workers=N)` does one of three things: (1) if the runtime is not yet started, seeds `_runtime.ensure_started(os_threads=N)`; (2) if the runtime is started with `os_threads=N` already, no-op; (3) if the runtime is started with a *different* `os_threads`, emit a `UserWarning` and use the existing pool unchanged. `max_workers=None` always just calls `ensure_started()` with no thread override.
- **Why:** HPX's worker pool is process-global and cannot be reconfigured after start. A strict implementation that raised on mismatch would break legitimate use cases like "library X spins up an executor with `max_workers=8`, then library Y constructs a second one with `max_workers=4`" — both libraries should keep working, and only one of them gets to seed the pool. The warning surfaces the conflict so the user can correct it (typically by initializing the runtime explicitly with `hpyx.init(os_threads=...)` before either library imports), while still letting both libraries run.
- **Result:** `test_max_workers_warning_when_mismatched` confirms the warning fires; `test_max_workers_matches_runtime_no_warning` confirms there's no warning when values match. The warning message names the actual running thread count and explains why HPX can't be reconfigured.

### 2026-04-27: `_runtime.running_os_threads()` public accessor instead of `_started_cfg` private access (Implemented)

- **Decision:** `src/hpyx/_runtime.py` exposes `running_os_threads() -> int | None` returning the currently-running runtime's `os_threads`, or `None` if the runtime is not started. `HPXExecutor.__init__` calls this instead of reaching into `_runtime._started_cfg["os_threads"]`.
- **Why:** Reaching into a leading-underscore module-private dict is a code smell, and the original implementation wrapped it in a broad `try/except Exception # noqa: BLE001` to defend against schema drift. Exposing a typed accessor (a) eliminates the defensive try/except, (b) gives a clear contract for any future caller that needs the same information (Plan 3 will likely want it), (c) makes the executor-runtime boundary explicit.
- **Result:** `test_running_os_threads_reflects_session_config` confirms the accessor returns the value passed to `hpyx.init(os_threads=...)`. The executor's `__init__` is two lines shorter and no longer touches private names.

### 2026-04-27: `_closed` flag guarded by `threading.Lock` for free-threaded 3.13t (Implemented)

- **Decision:** `HPXExecutor` keeps a `threading.Lock` on the instance. Reads of `self._closed` in `submit` / `map` and the write in `shutdown` are all done under the lock.
- **Why:** Under GIL-mode CPython, single-attribute Python writes are effectively atomic. Under **free-threaded 3.13t** that is no longer guaranteed for the broader memory model — torn reads are theoretically possible, and stdlib `ThreadPoolExecutor` itself uses an explicit `_shutdown_lock` for the same flag. Explicitly locking matches stdlib behavior and removes a class of TOCTOU races where one thread sees `_closed=False` and submits a task while another thread is in the middle of `shutdown()`.
- **Result:** The 50-thread cross-thread submit test continues to pass. The lock overhead is negligible (one acquire/release per `submit`/`shutdown` call).

### 2026-04-27: `HPXExecutor.map` matches stdlib's silent-truncation `zip` (Implemented)

- **Decision:** `HPXExecutor.map(fn, *iterables)` uses bare `zip(*iterables)`, which silently truncates to the shortest input. The earlier draft used `zip(*iterables, strict=True)` (which would raise `ValueError` on length mismatch), but we reverted to match stdlib `Executor.map`.
- **Why:** Substitutability with `concurrent.futures.ThreadPoolExecutor` is the whole point of the v1 executor — dask, asyncio, and other consumers may pass iterables with different lengths and expect stdlib semantics. `strict=True` was the safer choice in isolation (catches a footgun) but the wrong choice for a drop-in replacement (changes a documented behavior). We chose substitutability and document the truncation behavior in the user guide.
- **Result:** `test_map_truncates_to_shortest_iterable` pins the new behavior. `test_map_two_iterables` (lengths matched) continues to work unchanged.

### 2026-04-27: `chunksize` accepted but unused; not deprecated, no warning (Implemented)

- **Decision:** `HPXExecutor.map` accepts a `chunksize: int = 1` keyword for protocol parity but currently ignores it. No warning is emitted; the docstring notes the limitation.
- **Why:** stdlib's `ThreadPoolExecutor.map` also ignores `chunksize` (only `ProcessPoolExecutor` honors it), so silent ignore is the conservative stdlib-aligned choice. Emitting a warning every time a user passes the parameter would create noise in code that targets `ProcessPoolExecutor.map` and was ported as-is. Real chunk-size tuning lives at the parallel-algorithm layer (`hpyx.parallel.for_loop(par, chunk_size=...)`) which lands in Plan 3.
- **Result:** `# noqa: ARG002` suppresses lint complaints; the docstring tells users to pre-chunk manually if they need fine-grained control. No test assertion needed (silent no-op matches stdlib).

### 2026-04-27: Drop legacy `hpyx.futures.submit` shim outright; no deprecation window (Implemented)

- **Decision:** `src/hpyx/futures/_submit.py` and `tests/test_submit.py` are deleted. `hpyx.futures.__init__.py` no longer re-exports `submit`. The v0.x `from hpyx.futures import submit; submit(fn, ...).get()` pattern now raises `ImportError` immediately.
- **Why:** The v0.x `submit` shim was already broken before this rewrite (it called the deferred-only `hpx_async`, returning a future that secretly ran on the calling thread). Keeping it around as a deprecation-warned shim would let user code keep limping along on the broken behavior. Deleting it forces an early visible failure (`ImportError` is louder than a warning) and pushes users to the new `hpyx.async_` / `HPXExecutor` API. The v1.0 release notes call this out as a breaking change; the migration is mechanical (`from hpyx.futures import submit` → `import hpyx`, `submit(fn, ...)` → `hpyx.async_(fn, ...)`, `.get()` → `.result()`).
- **Result:** `tests/test_submit.py` is gone; coverage moved to `tests/test_executor.py` and `tests/test_futures.py`. `docs/usage.md` examples were rewritten to use the new API in the same commit, so the docs site has no broken examples on merge.

### 2026-04-24: `hpyx.Future` is a thin Python shell over `_core.futures.HPXFuture` (Implemented)

- **Decision:** `src/hpyx/futures/_future.py::Future` wraps `_core.futures.HPXFuture` in a class with `__slots__ = ("_hpx", "_callbacks", "_callback_lock", "_callbacks_registered")`. Most methods (`result`, `exception`, `done`, `running`, `cancelled`, `cancel`, `share`) are one-line delegations to the C++ object. The wrapper is what users see as `hpyx.Future`.
- **Why:** Two layers of indirection are needed because the C++ side cannot construct the Python `Future` class without a circular import, and because some semantics — FIFO callback ordering, synchronous fast-path on done futures, structured logging of callback errors, lazy asyncio import — are easier (and cheaper to test) in Python than in nanobind. `__slots__` keeps the per-Future overhead small for fan-out workloads and prevents accidental attribute additions.
- **Result:** `tests/test_futures.py` covers `isinstance(fut, hpyx.Future)`, `concurrent.futures.Future` protocol attribute conformance, `.then` chains, `add_done_callback` invocation, and `repr()`. The wrapper file is 137 lines.

### 2026-04-24: Lazy `__await__` import keeps `asyncio` off the import path (Implemented)

- **Decision:** `Future.__await__` does `from hpyx.aio import _future_await` inside the method body, not at module load time.
- **Why:** Two problems are solved at once. (1) `hpyx.aio` is created in a later Phase 1 task; the wrapper has to ship in the meantime without an unresolved import. (2) Most users never `await` a Future — they call `.result()` — so loading `asyncio` at import time would impose a cold-start cost on every consumer. Lazy import defers the cost to the first `await fut`, where it is already paid.
- **Result:** `import hpyx` does not pull `asyncio` into `sys.modules`; `await hpyx.async_(fn)` works the moment `hpyx.aio` lands. Verified via `assert "hpyx.aio" not in sys.modules` after `import hpyx`.

### 2026-04-24: Python-side FIFO queue for `add_done_callback` (Implemented)

- **Decision:** Each Python `Future` keeps an optional `list[Callable]` of pending callbacks behind a `threading.Lock`. The first `add_done_callback(fn)` call registers exactly one C++ `_drain` callback; subsequent calls just append to the list. When the underlying `HPXFuture` fires, `_drain` snapshots and clears the list (under the lock) and invokes each user callback in insertion order.
- **Why:** `concurrent.futures.Future.add_done_callback` documents that callbacks fire **in insertion order**. The HPX `.then` chain makes no FIFO guarantee across multiple registrations: calling `_hpx.add_done_callback(cb1); _hpx.add_done_callback(cb2)` may fire `cb2` before `cb1` depending on scheduler order. Centralizing the registration in one C++ callback that drains a Python-managed list restores FIFO semantics without touching the C++ side.
- **Result:** `test_add_done_callback_fifo_order` registers 5 callbacks and asserts the invocation list equals `[0, 1, 2, 3, 4]`. The lock makes registration safe across threads on free-threaded 3.13t.

### 2026-04-24: Synchronous fast-path when `add_done_callback` runs on a done Future (Implemented)

- **Decision:** `Future.add_done_callback(fn)` checks `self.done()` first. If the future is already complete, it calls `fn(self)` synchronously on the calling thread and returns — no C++ registration, no thread switch.
- **Why:** `concurrent.futures.Future` runs callbacks synchronously on the calling thread when added to an already-completed future. Without this fast-path, HPyX would dispatch the callback to an HPX worker, which is a different thread than the caller and surprises users who rely on stdlib semantics (sequence-builder patterns, post-completion bookkeeping). The C++ side already has a `!fut_.valid()` synchronous branch but does not handle the `done()` case.
- **Result:** `test_add_done_callback_already_done_runs_synchronously` registers a callback on a `hpyx.ready_future(42)` and asserts the callback's thread id equals the caller's. Errors raised in the synchronous path are caught and logged via the same `hpyx.futures` logger that the async path uses.

### 2026-04-24: `.then(fn)` reuses the upstream `Future` instead of allocating a fresh `ready_future` (Implemented)

- **Decision:** `Future.then(fn)`'s shim closure captures `self` and calls `fn(self)`. It does NOT wrap the resolved value in a new `_core.futures.ready_future` to construct a separate Future for `fn`.
- **Why:** The upstream `self` is already a fully-resolved Future by the time the shim runs (that is what triggered the continuation), so passing it directly is semantically identical to building a fresh `ready_future(value)` — and free. Allocating a new `HPXFuture` plus wrapper per stage costs O(N) extra `make_ready_future`, INCREF, and Python heap allocations on deep `.then` chains. Capturing `self` drops the per-stage cost to one closure.
- **Result:** `test_then_passes_self_not_intermediate` chains `.then` and asserts the captured Future's `.result()` matches the upstream. No measurable overhead on chain depths up to 100.

### 2026-04-24: `.then(fn)` short-circuits on upstream exceptions (Documented)

- **Decision:** When the upstream Future raises, `fn` is **not invoked**. The exception propagates through the `.then` chain unchanged. The class docstring is explicit about this; users who need success-or-failure dispatch use `add_done_callback`.
- **Why:** This matches the C++ side (`HPXFuture::then` and `dataflow_impl` both short-circuit on the sentinel exception payload) and matches `concurrent.futures.Future` (which has no `.then` but its analogue, the `add_done_callback`-driven chains, also propagate exceptions unchanged). The alternative — invoke `fn` with the failed Future and let it dispatch — was the original wrapper comment but is not what the C++ binding actually does, and "split the API across two semantics" is worse than "one chain, one rule." We chose to lock the rule and document it clearly.
- **Result:** `test_then_short_circuits_on_upstream_exception` confirms the shim is never called when the upstream raises. Docstring on `Future.then` directs users to `add_done_callback` for failure handling.

### 2026-04-24: `hpyx.when_any()` with empty input raises `ValueError` instead of hanging (Implemented)

- **Decision:** The Python `when_any(*futures)` function raises `ValueError("when_any requires at least one input")` when called with no arguments. The guard is at the wrapper level, not in C++.
- **Why:** `hpx::when_any` on an empty `vector` returns a future that never resolves. Surfacing that as a `ValueError` at the Python boundary turns a silent-hang programmer error into a fast, debuggable failure. We chose the wrapper level over the C++ side because the C++ binding is shared with internal callers that may have already filtered the input list, and Python is where the user-facing error lives. `when_all([])` returning `()` (a sensible neutral element) does not need the same guard.
- **Result:** `test_when_any_empty_raises` confirms the exception fires. Hang-free behavior validated by the test running to completion in < 0.05s.

### 2026-04-24: Implement `dataflow` via `when_all().then()` rather than `hpx::dataflow` (Implemented)

- **Decision:** The C++ binding for `dataflow(fn, inputs, kwargs)` calls `hpx::when_all(raws).then(continuation)` rather than `hpx::dataflow(launch, fn, raws)`. The continuation receives a single `hpx::future<std::vector<hpx::shared_future<PyPayload>>>`, walks it for sentinel exceptions, and only then builds the `*args` tuple and invokes `fn`.
- **Why:** `hpx::dataflow` has two relevant overloads: a variadic form that forwards each input as a separate argument, and a range form that forwards a `std::vector<future<T>>` as one argument. Mixing the two through Python — where N is decided at runtime, but the lambda signature is fixed at compile time — leads to a compile-time pack-vs-vector mismatch. Going through `when_all().then()` collapses the call site to a single, fixed, range-style continuation; we then unpack the vector inside the lambda where we already need to walk it for sentinel detection. The semantics are identical to `hpx::dataflow` for our use case (N inputs → call fn) and there is no measurable scheduling difference for Python-typed payloads.
- **Result:** `dataflow_impl` in `src/_core/futures.cpp` is ~50 lines of straight-line code with no template metaprogramming. Tests cover: positive path with 2 and 3 inputs, exception propagation from inputs (first-to-fail short-circuits without invoking `fn`), exception from `fn` itself, and kwargs forwarding.

### 2026-04-24: `nb::handle` with `nb::dict()` default for `dataflow` kwargs, not `nb::kwargs` (Implemented)

- **Decision:** The C++ signature is `dataflow_impl(nb::callable fn, std::vector<HPXFuture> inputs, nb::handle kwargs)`, validated at runtime with `PyDict_Check`, and registered as `m.def("dataflow", &dataflow_impl, "fn"_a, "inputs"_a, "kwargs"_a = nb::dict())`. Users call it positionally (`dataflow(fn, [f1, f2], {"k": v})`) or by name (`dataflow(fn, [f1, f2], kwargs={"k": v})`).
- **Why:** Nanobind's `nb::kwargs` cannot coexist with named-argument annotations on the *preceding* positional parameters. The static_assert in `nb_func.h` requires `nargs_provided == nargs`, but `nb::kwargs` is counted as one of `nargs` while never accepting an `"_a"` annotation. The two ways out are (a) drop named annotations entirely, which loses keyword-call ergonomics for `fn` and `inputs`, or (b) use `nb::handle` with a runtime `PyDict_Check` and pass an empty dict default. Option (b) preserves the explicit `dataflow(fn=..., inputs=..., kwargs=...)` call shape while keeping nanobind's signature renderer happy.
- **Result:** Tests pass for positional, keyword, and missing-kwargs paths. The `nb::dict()` default is shared across calls, but our code only reads from it (Py_INCREFs and forwards to `PyObject_Call`), so no mutation hazard exists. If a future caller starts mutating it, we will switch to a per-call factory.

### 2026-04-24: Capture input `HPXFuture` wrappers in `when_any` continuation, not reconstruct (Implemented)

- **Decision:** `when_any_impl` captures the original `std::vector<HPXFuture>` in a `std::shared_ptr` before launching the continuation, then returns a `(index, [HPXFuture, ...])` tuple where the list contains the *same wrapper instances* the caller passed in.
- **Why:** The result tuple needs to give the caller a way to retrieve both the winner's value (via `result()`) and to inspect the laggards. Reconstructing fresh `HPXFuture` wrappers from each `hpx::shared_future<PyPayload>` would lose the per-wrapper `cancelled_` and `running_` atomic flags that `concurrent.futures.Future` semantics require. Capturing the original wrappers is also free: `HPXFuture` is copy-cheap (a `shared_future` plus two `shared_ptr<atomic>` flags), and the `shared_ptr<vector<HPXFuture>>` keeps the wrappers alive until the continuation runs.
- **Result:** `tests/test_futures.py::test_when_any_returns_index_and_futures_list` passes. The list-of-futures pattern matches `concurrent.futures.wait()`'s "done set / not-done set" output shape closely enough that the upcoming Python wrapper can map between them without rebuilding state.

### 2026-04-24: Store `shared_ptr<PyObject>` (PyPayload) in the future state, not `nb::object` (Implemented)

- **Decision:** The HPX future state holds `PyPayload = std::shared_ptr<PyObject>` with a custom GIL-acquiring deleter (`GILDecref`) instead of `nb::object`. `HPXFuture` wraps `hpx::shared_future<PyPayload>`.
- **Why:** `nb::object`'s destructor calls `Py_DECREF` unconditionally. HPX may copy/move the future state on a worker thread that does not hold the GIL (during scheduling, when continuations fire, when shared states are reaped). A bare `nb::object` decrementing without the GIL races with the interpreter and corrupts refcounts. `shared_ptr<PyObject>` is GIL-safe at every point: the control block uses atomic counters (no GIL needed for copy/move), and the deleter does `PyGILState_Ensure()` → `Py_DECREF` → `PyGILState_Release()` so the actual reference release always happens with the GIL held.
- **Result:** `tests/test_futures.py` covers `async_submit` running on an HPX worker, exception preservation, and the `exception()` method — all five pass. The pattern carries over to `then()` continuations and `add_done_callback` for the same reason.

### 2026-04-24: Box Python exceptions in a sentinel tuple, not `std::exception_ptr` (Implemented)

- **Decision:** When the user's callable raises, the lambda catches `nb::python_error`, calls `PyErr_Fetch` / `PyErr_NormalizeException`, and packs the result into a 4-tuple sentinel `("__hpyx_exc__", exc_type, exc_value, exc_tb)` stored as a `PyPayload`. `result()` and `exception()` detect the sentinel via `is_exc_sentinel()` and re-raise via `PyErr_SetRaisedException` (Python 3.12+).
- **Why:** `nb::python_error` carries `PyObject*` references that are GIL-thread-local. Letting it propagate through `std::exception_ptr` is unsafe — HPX may rethrow it on a different thread that has no Python interpreter state attached, crashing the process. Boxing the exception into a `PyPayload` while the original GIL is still held captures owned references that can travel through HPX's machinery and be unboxed on the consumer thread.
- **Result:** `pytest.raises(ValueError, match="boom")` works correctly through `fut.result()`, and `fut.exception()` returns the original Python exception value with its traceback intact.

### 2026-04-24: `HPYX_ASYNC_MODE` env var for `launch::async` rollback (Implemented)

- **Decision:** Add `async_mode` to `hpyx.config.DEFAULTS` (`"async"` by default), parsed from `HPYX_ASYNC_MODE` (`"async"` or `"deferred"`, case-insensitive). The C++ `async_submit` reads the env var directly via `std::getenv` and selects `hpx::launch::async` (default) or `hpx::launch::deferred` (rollback).
- **Why:** Spec risk #1 — switching `hpx_async` from `launch::deferred` to `launch::async` is the core correctness fix in v1, but it is also a behavior change that could expose latent GIL or threading bugs in user code. A no-touch rollback flag lets operators flip back to v0.x semantics without rebuilding or downgrading. The deferred path is intentionally preserved (not deleted) so the rollback is real and tested.
- **Result:** `HPYX_ASYNC_MODE=deferred python -c "import hpyx; ..."` returns the user's value but runs the callable in the calling thread on `.result()`. Tested as part of the issue #120 acceptance criteria. Will be removed in a future minor release once the `launch::async` path is proven in production.

### 2026-04-24: Use `nb::handle` for `args` and `kwargs` parameters in `async_submit` (Implemented)

- **Decision:** The C++ binding signature is `async_submit(nb::callable fn, nb::handle args, nb::handle kwargs)`, validated at runtime with `PyTuple_Check` / `PyDict_Check`. The C++ parameter names are `call_args` / `call_kwargs` (not `args` / `kwargs`).
- **Why:** Nanobind treats the `args` and `kwargs` parameter **names** as a hint to render them as `*args` / `**kwargs` in the generated Python signature, even when the type is a concrete `nb::tuple` / `nb::dict`. With `nb::object` or `nb::tuple` as the type and a positional-named parameter, the rendered signature collapses to `(fn, **args)`, which makes the function impossible to call as `async_submit(fn, args_tuple, kwargs_dict)`. Using `nb::handle` plus runtime type checks avoids the auto-collection and gives a clean three-positional signature.
- **Result:** `core_futures.async_submit(body, (), {})` works. The Python wrapper in `src/hpyx/futures/_submit.py` calls it as `async_submit(function, args, kwargs)` with explicit tuple/dict.

### 2026-04-24: `HPXFuture` wraps `shared_future`, not `future`, internally (Implemented)

- **Decision:** Every `HPXFuture` holds a `hpx::shared_future<PyPayload>` (not `hpx::future<PyPayload>`). `share()` is a no-op that copies the wrapper. `async_submit` calls `.share()` on the result of `hpx::async` before constructing `HPXFuture`.
- **Why:** Python `concurrent.futures.Future` allows `result()` to be called multiple times (it caches the value). It allows `add_done_callback` to be registered after the future has completed. It allows `.then()` chains. All three need the underlying state to be sharable — `hpx::future<T>` is a single-consumer move-only handle; `hpx::shared_future<T>` is a multi-consumer copyable handle. Using `shared_future` everywhere matches Python semantics and removes a class of move-after-use bugs.
- **Result:** Multiple `.result()` calls return the same value. `.then()` and `add_done_callback` capture `*this` by copy without invalidating the original. `share()` is exposed for API parity but is internally a no-op.

### 2026-04-24: Pixi/uv archive cache is invalidated by deleting `~/Library/Caches/rattler/cache/uv-cache/archive-v0/*/hpyx/` (Operational)

- **Decision:** When local rebuilds appear to silently revert the installed `_core.cpython-313t-darwin.so` to an older version, manually clear the rattler/uv archive cache before reinstalling.
- **Why:** Pixi declares hpyx as `[feature.hpyx.pypi-dependencies]: hpyx = { path = ".", editable = true }`. Pixi syncs this through uv, which keeps a content-addressed archive cache at `~/Library/Caches/rattler/cache/uv-cache/archive-v0/`. Even with `pip install --force-reinstall --no-cache-dir`, the cached `.so` from an earlier successful build can be restored, masking source changes. Symptom: source has `async_submit(nb::handle, ...)` but compiled binary still shows `async_submit_impl(nb::callable, nb::args)` strings, and the installed `.so` timestamp predates the build output.
- **Result:** The recipe is `for d in ~/Library/Caches/rattler/cache/uv-cache/archive-v0/*/; do [ -d "${d}hpyx" ] && rm -rf "$d"; done && pip install --no-build-isolation --no-cache-dir --force-reinstall -ve .`. Captured here so future contributors do not lose hours debugging "the build isn't picking up my changes."

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
