# Migrating from HPyX v2025.8.28 to v2026.5.20

HPyX v2026.5.20 is a clean-break rewrite of the initial `v2025.8.28` release.
Most `v2025.8.28` code is either broken (`HPXExecutor.submit` referenced an
unbound symbol and crashed) or did not actually parallelize (`hpx_async` used
`launch::deferred`, running on the calling thread). v2026.5.20 fixes all of
this and introduces a Pythonic surface aligned with `concurrent.futures`,
asyncio, and dask.

## TL;DR

- `hpyx.HPXRuntime` still works. Using it is now optional.
- `hpyx.HPXExecutor` now works (it used to crash). Signature unchanged.
- `hpyx.futures.submit` removed — use `hpyx.async_` or `HPXExecutor().submit()`.
- `hpyx.multiprocessing.for_loop` deprecated; use `hpyx.parallel.for_loop`.
- `hpx_async` now runs on HPX worker threads (was: deferred, run by caller).

## Breaking changes

### 1. `hpx_async` no longer uses `launch::deferred`

**Before (v2025.8.28):**
```python
fut = hpyx._core.hpx_async(slow_function, arg1, arg2)
# Nothing happens until .get() — the callable runs in the calling thread.
result = fut.get()
```

**After (v2026.5.20):**
```python
fut = hpyx.async_(slow_function, arg1, arg2)
# Already running on an HPX worker thread.
result = fut.result()
```

Emergency rollback: set `HPYX_ASYNC_MODE=deferred` to restore `v2025.8.28`
semantics. This flag will be removed in a future release — fix any code that
depended on deferred-evaluation timing.

### 2. `hpyx.HPXExecutor` is now real

**Before (v2025.8.28):** `executor.submit()` crashed (referenced unbound
`hpx_async_set_result`).

**After (v2026.5.20):** works like `concurrent.futures.ThreadPoolExecutor`:

```python
with hpyx.HPXExecutor() as ex:
    fut = ex.submit(pow, 2, 10)
    print(fut.result())  # 1024

    results = list(ex.map(my_fn, range(100)))
```

The `max_workers` parameter is advisory — HPX's worker pool is
process-global. See `docs/user-guides/concurrent-futures.md`.

### 3. `hpyx.futures.submit` removed

Used to be a free function. Replace with `hpyx.async_` or the executor.

**Before:**
```python
from hpyx.futures import submit
fut = submit(fn, 1, 2)
```

**After:**
```python
import hpyx
fut = hpyx.async_(fn, 1, 2)
# OR:
with hpyx.HPXExecutor() as ex:
    fut = ex.submit(fn, 1, 2)
```

### 4. `hpyx.multiprocessing.for_loop` deprecated

Still works in v2026.5.20 with a `DeprecationWarning`; will be removed in a
future release.

**Before:**
```python
from hpyx.multiprocessing import for_loop
for_loop(lambda x: x + 1, data, policy="par")
```

**After:**
```python
from hpyx import parallel
from hpyx.execution import par

def body(i):
    data[i] = data[i] + 1

parallel.for_loop(par, 0, len(data), body)
```

### 5. `hpyx._core.dot1d` → `hpyx.kernels.dot`

The C++ kernel got a better home.

**Before:**
```python
from hpyx._core import dot1d
result = dot1d(a, b)
```

**After:**
```python
import hpyx
result = hpyx.kernels.dot(a, b)
```

### 6. `hpyx.HPXRuntime` exit is now a no-op

**Before (v2025.8.28):** exiting the context manager shut down HPX.

**After (v2026.5.20):** exiting does nothing — `atexit` owns shutdown. This
matters only if you had code that expected `HPXRuntime()` to reset the
runtime; that was never actually safe (HPX cannot restart within a process),
and v2026.5.20 documents it explicitly.

## Non-breaking additions

- `hpyx.init(os_threads=...)`, `hpyx.shutdown()`, `hpyx.is_running()`
- `hpyx.async_`, `hpyx.Future`, `hpyx.when_all`, `hpyx.when_any`,
  `hpyx.dataflow`, `hpyx.shared_future`, `hpyx.ready_future`
- `hpyx.parallel` — 17 Python-callback parallel algorithms
- `hpyx.kernels` — 5 C++-native kernels (dot, matmul, sum, max, min)
- `hpyx.execution` — policy objects + chunk-size modifiers
- `hpyx.aio` — asyncio-friendly combinators; direct `await fut` works
- `hpyx.debug.enable_tracing(path)` — per-task JSONL event log

## Audience-specific guides

Pick the one matching your use case:

- `docs/user-guides/scientific-python.md` — numpy-heavy code wanting parallelism
- `docs/user-guides/concurrent-futures.md` — migrating from ThreadPoolExecutor/joblib
- `docs/user-guides/hpx-native.md` — HPX-familiar users exploiting policy tuning

And for specific integrations:

- `docs/user-guides/dask-integration.md` — use `HPXExecutor` as a dask scheduler
- `docs/user-guides/asyncio.md` — awaitable futures in FastAPI/Jupyter
- `docs/user-guides/free-threaded.md` — 3.13t guidance and gotchas
