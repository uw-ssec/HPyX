# HPyX on free-threaded Python 3.13t

Free-threaded Python 3.13 (built with `Py_GIL_DISABLED=1`) removes the
global interpreter lock. HPyX gets a material performance advantage on
3.13t: multiple HPX workers can execute Python callbacks truly
concurrently, not serialized on the GIL.

## What changes for you

- `hpyx.parallel.for_loop(par, 0, N, fn)` with a Python `fn` scales
  with `os_threads`. Under GIL-mode 3.13 it didn't (GIL serialized).
- `hpyx.HPXExecutor.map(fn, items)` similarly scales with Python
  callables.
- `hpyx.async_` + `.then` chains run in parallel without blocking
  the submitting thread.

The C++ kernels in `hpyx.kernels` behave the same on both builds
(they release the GIL for their duration).

## What you need to watch for

### 1. User-authored thread safety

Under GIL-mode Python, sloppy code often "works" because the GIL
serializes execution. On 3.13t, shared mutable state is a real race.

```python
counter = 0                   # global

def body(i):
    global counter
    counter += 1              # UNSAFE on 3.13t — lost updates

hpyx.parallel.for_loop(par, 0, 1000, body)
# counter might be < 1000 on 3.13t.
```

Fix:

```python
import threading
_lock = threading.Lock()
counter = 0

def body(i):
    global counter
    with _lock:
        counter += 1
```

Or use `threading.local()` / per-thread accumulators / a `queue.Queue`.

### 2. Numpy and 3.13t

Numpy ≥ 2.0 is largely 3.13t-compatible but some operations still hold
internal locks. If your `hpyx.parallel.*` body calls such an operation,
you'll see partial serialization.

As of HPyX v2026.5.20, consult the upstream numpy docs for
currently-locked operations — this changes as numpy improves.

When in doubt, switch hot paths to `hpyx.kernels.*` (pure C++, no numpy
dependency at runtime).

### 3. Third-party libraries

Many libraries are not yet fully 3.13t-clean. When running HPyX on
3.13t, watch for:
- Sudden slowdowns (indicates hidden locks).
- Flaky test failures in shared state.

Report issues upstream — the ecosystem is improving rapidly.

## Verifying you're on 3.13t

```python
import sysconfig
print(sysconfig.get_config_var("Py_GIL_DISABLED"))  # 1 on 3.13t, 0 or None on GIL-mode
```

HPyX's benchmark `benchmarks/test_bench_free_threading.py` is gated on this flag —
it runs on 3.13t and skips cleanly on GIL-mode.

## Benchmark: proof that 3.13t matters

Run:

```bash
bash scripts/run_bench_local.sh bench -k free_threading
```

On a 4-core machine with `os_threads=4`:
- `test_for_loop_par_nogil` under 3.13t: expect ~3-4× speedup over the
  seq version.
- Under GIL-mode 3.13: near-identical to seq (GIL serialization).
