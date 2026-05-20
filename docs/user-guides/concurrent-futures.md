# HPyX for concurrent.futures users

HPyX's `HPXExecutor` is a real `concurrent.futures.Executor`. If your
code currently uses `ThreadPoolExecutor` or `ProcessPoolExecutor`,
swapping in `HPXExecutor` is usually a one-line change.

## Drop-in swap

```python
# Before:
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = [ex.submit(my_fn, x) for x in inputs]
    results = [f.result() for f in futures]

# After:
import hpyx
with hpyx.HPXExecutor() as ex:
    futures = [ex.submit(my_fn, x) for x in inputs]
    results = [f.result() for f in futures]
```

## What you gain

- **True parallelism on 3.13t.** `ThreadPoolExecutor` serializes Python
  callbacks on the GIL; `HPXExecutor` on 3.13t runs them concurrently.
- **Lightweight tasks.** HPX's scheduler can handle millions of tasks
  cheaply; `ThreadPoolExecutor` gets expensive past ~10k.
- **Composable futures.** `future.then(fn)`, `hpyx.when_all`, `hpyx.dataflow`
  are first-class — unlike stdlib futures.

## What's different

### 1. `max_workers` is advisory

HPX's worker pool is process-global. `HPXExecutor(max_workers=8)` seeds
the pool on the first executor created; subsequent executors with
different `max_workers` emit a warning and reuse the existing pool.
Control the pool explicitly with `hpyx.init(os_threads=8)`.

### 2. `shutdown()` doesn't stop the runtime

Calling `.shutdown()` on an executor marks that handle unusable but
does not tear down HPX — HPX cannot restart in-process. `atexit` owns
teardown.

### 3. Cancellation is limited

`future.cancel()` returns `True` only if the task hadn't started yet.
Mid-flight cancellation isn't supported in v1.

## Composing beyond stdlib

```python
import hpyx

# Chain continuations:
hpyx.async_(load).then(parse).then(transform).result()

# Wait for multiple:
f1 = hpyx.async_(fetch, url1)
f2 = hpyx.async_(fetch, url2)
combined = hpyx.dataflow(merge, f1, f2)

# First of many:
idx, futures_list = hpyx.when_any(f1, f2, f3).result()
```

All of these are inexpressible with plain `ThreadPoolExecutor`.
