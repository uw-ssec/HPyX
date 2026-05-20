# Diagnostics and tracing

HPyX ships a minimal diagnostics surface in `hpyx.debug`.

## Worker thread queries

```python
import hpyx

print(hpyx.debug.get_num_worker_threads())   # e.g., 8
print(hpyx.debug.get_worker_thread_id())     # -1 on the main Python thread
```

Inside a task, `get_worker_thread_id()` returns the HPX worker id
(in `[0, N)` for `N = num_worker_threads`):

```python
def worker_body(i):
    print(f"iteration {i} on worker {hpyx.debug.get_worker_thread_id()}")

hpyx.parallel.for_loop(hpyx.execution.par, 0, 10, worker_body)
```

## Per-task tracing

Capture start time, duration, and worker id for every `async_`-submitted
task:

```python
import hpyx

hpyx.debug.enable_tracing("/tmp/hpyx-trace.jsonl")
try:
    # ... your code ...
    fut = hpyx.async_(work, 42)
    fut.result()
finally:
    hpyx.debug.disable_tracing()
```

The output is newline-delimited JSON:

```
{"name": "work", "worker_thread_id": 3, "start_ns": 12345, "duration_ns": 980}
{"name": "work", "worker_thread_id": 1, "start_ns": 12400, "duration_ns": 1020}
```

Useful for:
- Detecting load imbalance across workers (count events per `worker_thread_id`).
- Identifying slow tasks (top-N by `duration_ns`).
- Seeing scheduling gaps (differences in `start_ns` between sibling tasks).

Load into pandas:

```python
import pandas as pd
df = pd.read_json("/tmp/hpyx-trace.jsonl", lines=True)
df.groupby("worker_thread_id")["duration_ns"].describe()
```

## Environment variables

| Variable | Effect |
|---|---|
| `HPYX_TRACE_PATH` | If set, `enable_tracing()` can be called without an explicit path. |
| `HPYX_OS_THREADS` | Initial worker count (default: `os.cpu_count()`). |
| `HPYX_AUTOINIT` | `0` disables implicit init; explicit `hpyx.init(...)` is required. |
| `HPYX_CFG` | Semicolon-separated extra HPX config strings. |
| `HPYX_ASYNC_MODE` | `deferred` for v0.x rollback; default is `async` (v1 behavior). |

## What's NOT in v1 diagnostics

- Full APEX / HPX performance counter surface.
- Real-time task viewer / dashboard.
- Flame-graph tooling (see `scripts/run_bench_local.sh record`
  using py-spy for that).
- HPX's own LTTNG / tracing hooks.

These are forward-roadmap items.
