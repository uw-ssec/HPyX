# HPyX for HPX-familiar users

If you know HPX, here's the one-page mental map from C++ HPX to Python
HPyX.

## API mapping

| HPX C++ | HPyX Python |
|---|---|
| `hpx::init` / `hpx::start` | `hpyx.init(os_threads=...)` (or implicit on first use) |
| `hpx::stop` / `hpx::finalize` | `hpyx.shutdown()` (rarely needed — atexit) |
| `hpx::async(launch::async, fn)` | `hpyx.async_(fn, *args, **kwargs)` |
| `hpx::future<T>` | `hpyx.Future` (wraps `hpx::shared_future<nb::object>`) |
| `.then(cb)` | `.then(cb)` |
| `hpx::when_all(fs)` | `hpyx.when_all(*fs)` |
| `hpx::when_any(fs)` | `hpyx.when_any(*fs)` |
| `hpx::dataflow(fn, fs)` | `hpyx.dataflow(fn, *fs)` |
| `hpx::make_ready_future(x)` | `hpyx.ready_future(x)` |
| `hpx::execution::par` | `hpyx.execution.par` |
| `hpx::execution::par(hpx::execution::task)` | `hpyx.execution.par(hpyx.execution.task)` |
| `hpx::execution::par.with(static_chunk_size(1000))` | `hpyx.execution.par.with_(hpyx.execution.static_chunk_size(1000))` |
| `hpx::experimental::for_loop` | `hpyx.parallel.for_loop` |
| `hpx::transform_reduce` | `hpyx.parallel.transform_reduce` (callback track) or `hpyx.kernels.dot/sum` (kernel track) |
| `hpx::sort` | `hpyx.parallel.sort` |
| `hpx::get_num_worker_threads` | `hpyx.debug.get_num_worker_threads()` |
| `hpx::get_worker_thread_num` | `hpyx.debug.get_worker_thread_id()` |

## What's NOT bound (v2026.5.20)

- `hpx::mutex`, `hpx::latch`, `hpx::barrier`, `hpx::channel`, etc.
  (synchronization primitives are planned for a future release).
- `hpx::fork_join_executor`, `hpx::limiting_executor`, `hpx::annotating_executor`.
- `hpx::resource::partitioner` (custom thread pools).
- `hpx::stop_token` / real cancellation.
- `hpx::id_type`, components, actions, AGAS (distributed — v2).

## Knobs you have

- `hpyx.init(os_threads=N, cfg=["hpx.stacks.small_size=0x20000", ...])`
  — the `cfg` list is raw HPX config strings.
- `HPYX_OS_THREADS`, `HPYX_CFG`, `HPYX_ASYNC_MODE`, `HPYX_AUTOINIT`,
  `HPYX_TRACE_PATH` env vars.
- Per-call chunk-size via `policy.with_(hpyx.execution.static_chunk_size(N))`.

## Performance expectations

- Kernels (`hpyx.kernels.dot`, etc.) release the GIL for their full
  duration and scale with worker count.
- `hpyx.parallel.*` invokes a Python lambda per iteration. On GIL-mode
  3.13 this serializes. On 3.13t it scales.
- `hpyx.async_` uses `launch::async`; expect comparable overhead to
  direct `hpx::async` in C++.
