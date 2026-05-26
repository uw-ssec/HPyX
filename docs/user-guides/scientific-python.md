# HPyX for scientific Python users

If you reach for `joblib.Parallel`, `concurrent.futures.ThreadPoolExecutor`,
or loop over numpy arrays and wish Python had real parallelism — HPyX
is for you.

## Quick wins

### 1. Parallel numpy reductions

```python
import numpy as np
import hpyx

a = np.random.rand(10_000_000)
total = hpyx.kernels.sum(a)           # beats single-threaded np.sum for large arrays
norm_sq = hpyx.kernels.dot(a, a)      # parallel dot product
```

Supported dtypes: `float32`, `float64`, `int32`, `int64`. Non-contiguous
arrays raise — use `np.ascontiguousarray(a)` first.

### 2. Parallel function over a list

```python
def expensive_analysis(x):
    # ... CPU-bound work ...
    return result

import hpyx
with hpyx.HPXExecutor() as ex:
    results = list(ex.map(expensive_analysis, inputs))
```

Under GIL-mode Python 3.13 this is comparable to `ThreadPoolExecutor`
(serializes on the GIL). Under free-threaded 3.13t the Python code
actually runs concurrently — see `docs/user-guides/free-threaded.md`.

### 3. Dask as a frontend for HPX

If you're already using `dask.array` or `dask.delayed`:

```python
import dask.array as da
import hpyx

with hpyx.HPXExecutor() as ex:
    x = da.random.random((10_000, 10_000), chunks=(1_000, 1_000))
    result = (x @ x.T).sum().compute(scheduler=ex)
```

HPyX's executor implements `concurrent.futures.Executor`, which dask
accepts directly. No other changes.

## When to use what

| Workload | Tool |
|---|---|
| Reduction over a numpy array (sum, max, dot) | `hpyx.kernels.*` |
| Custom per-element transform in pure Python | `hpyx.parallel.for_loop` on 3.13t; `hpyx.HPXExecutor.map` otherwise |
| Collection-level ops (blocked array, lazy graph) | `dask.array` with `scheduler=HPXExecutor()` |
| Ad hoc task graph of Python functions | `hpyx.async_` + `hpyx.dataflow` / `hpyx.when_all` |

## Caveats

- The C++ kernels require C-contiguous numpy arrays. Use `np.ascontiguousarray`
  when in doubt.
- Per-element Python callbacks are slow under GIL-mode 3.13 (GIL
  acquire/release per iteration). Switch to 3.13t or use `hpyx.kernels`
  for hot paths.
