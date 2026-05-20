# Using HPyX as a dask scheduler

HPyX's `HPXExecutor` is a `concurrent.futures.Executor`, which dask
accepts directly as a scheduler. This enables dask users to get HPX's
lightweight-task scheduler without any dask-side changes.

## Basic usage

```python
import dask.array as da
import hpyx

with hpyx.HPXExecutor() as ex:
    x = da.random.random((10_000, 10_000), chunks=(1_000, 1_000))
    result = x.mean().compute(scheduler=ex)
```

Also works with `dask.delayed`:

```python
from dask import delayed
import hpyx

@delayed
def parse(path):
    return open(path).read().strip()

@delayed
def combine(texts):
    return "\n".join(texts)

texts = [parse(p) for p in paths]
summary = combine(texts)

with hpyx.HPXExecutor() as ex:
    result = summary.compute(scheduler=ex)
```

## When this beats dask's threaded scheduler

- On **free-threaded Python 3.13t**, HPyX truly parallelizes Python
  callbacks (dask's threaded scheduler still suffers GIL serialization
  on non-C-extension code).
- For graphs with **very many small tasks**, HPX's lightweight-task
  scheduler scales past the ~10k-task point where dask's threaded
  scheduler starts paying serious overhead.

## When to keep using dask's default

- **Distributed workloads** — HPyX v2026.5.20 is single-process. Use
  `dask.distributed.Client`.
- **Process-based parallelism for GIL-bound code on GIL-mode 3.13** —
  `scheduler='processes'` avoids the GIL entirely at the cost of
  pickling. If you can't switch to 3.13t, this may still be faster.

## Caveats

- `HPXExecutor(max_workers=N)` is advisory (HPX pool is process-global).
  Set `hpyx.init(os_threads=N)` before creating any executors if you
  need a specific thread count.
- Dask's "worker" abstraction doesn't exist here — every `submit` goes
  to HPX's shared scheduler. No affinity, no resource restrictions.
