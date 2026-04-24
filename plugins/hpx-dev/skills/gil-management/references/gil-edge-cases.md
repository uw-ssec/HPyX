# GIL & Runtime Edge Cases

Supplementary rules and gotchas that come up when the four core GIL rules in `SKILL.md` are not sufficient. Each applies only in specific HPyX scenarios but can produce hard-to-diagnose crashes or hangs.

## Single-Runtime Constraint

HPX allows only one runtime per process. The `rts` singleton in `src/init_hpx.cpp` enforces this. Once `stop_hpx_runtime()` completes, **the runtime cannot be restarted**. `HPXRuntime`/`HPXExecutor` instances are single-use per process lifetime. Tests must not create a second `HPXRuntime` after the first has exited.

Attempting `hpx::start` after `hpx::stop` has completed is undefined behavior — it may hang, crash, or silently misbehave.

## `hpx::finalize` Must Run on an HPX Thread

`hpx::finalize()` must execute in an HPX thread context. In `global_runtime_manager::hpx_main`, it is called from the function that was passed to `hpx::start` — that function runs as an HPX thread.

Calling `hpx::finalize()` from a plain OS thread (like Python's main thread) is **incorrect** and may hang or crash. Shutdown is orchestrated instead by:

1. The Python destructor releases the GIL and signals the shutdown condition variable.
2. `hpx_main`, still on an HPX thread, wakes and calls `hpx::finalize()`.
3. `hpx::stop()` (called from the Python thread) then blocks until worker threads exit.

## HPX Thread Stack Size (64 KB)

HPX lightweight threads default to **64 KB stacks**. Deep Python call stacks triggered inside an HPX-scheduled callable may overflow:

- Recursive Python functions
- NumPy operations that call back into Python (e.g., `__array_function__` protocols)
- Nested generator chains or deep decorator stacks

Python call frames are roughly 1–4 KB each; a recursion depth of ~100 can exhaust the stack.

**Mitigation**: prefer `hpx::launch::deferred` (which runs on the calling OS thread with its normal, much larger stack) over `hpx::launch::async` when binding operations that may traverse substantial Python stack.

## `hpx::spinlock` vs `hpx::mutex` vs `std::mutex`

| Primitive | Behavior | Condition variable pair |
|---|---|---|
| `hpx::spinlock` | Busy-waits; does NOT yield HPX thread | `hpx::condition_variable_any` |
| `hpx::mutex` | Suspends HPX thread on contention | `hpx::condition_variable` |
| `std::mutex` | Blocks the OS thread | `std::condition_variable` |

**Do not mix**: `std::condition_variable` requires `std::mutex`; `hpx::condition_variable` requires `hpx::mutex`. `hpx::condition_variable_any` is the flexible variant that works with `hpx::spinlock` or any BasicLockable.

### Why `init_hpx.cpp` mixes them

- **Startup handshake** (`startup_mtx_` / `startup_cond_`) uses `std::mutex` / `std::condition_variable` because the wait occurs **before** HPX is fully initialized — HPX primitives are not yet safe to use.
- **Shutdown flag** (`mtx_` / `cond_`) uses `hpx::spinlock` / `hpx::condition_variable_any` because it runs **inside** `hpx_main` (an HPX thread) with a very short critical section (just flipping `rts_`).

### When to choose which

- **`hpx::spinlock`**: very short critical sections (flag flip, single pointer swap) where the cost of yielding is higher than the spin.
- **`hpx::mutex`**: anything that may contend for more than a few cycles. Yields the HPX thread properly.
- **`std::mutex`**: only when the code runs outside any HPX thread context (e.g., early init, post-shutdown).

## Parallel Algorithms on Python Objects Are a Trap

`hpx::experimental::for_loop(hpx::execution::par, ...)` on Python objects requires GIL acquire/release per iteration. This creates severe contention and potential deadlock — there is no performance benefit, only overhead.

The Python layer (`_for_loop.py`) correctly raises `NotImplementedError` for `par` when iterating Python objects. Do not attempt to "fix" this by adding a parallel path that calls into Python.

For real parallelism, algorithms must operate on **raw C++ data** (e.g., `double*` from `nb::ndarray.data()`) without touching `nb::object`. See `dot1d` in `src/algorithms.cpp` as the canonical pattern.

## Executor and Policy Object Lifetime

Execution policy objects (`hpx::execution::par`, `seq`, etc.) are `constexpr` global singletons — safe to use from any thread without lifetime concerns.

Custom executor objects (`fork_join_executor`, `thread_pool_executor`, etc.) must **outlive all tasks dispatched through them**. A stack-allocated executor in a bound function that returns before its tasks complete is undefined behavior. Hold executors as module-level statics, members of a long-lived class, or via `std::shared_ptr` captured into the task.

## Free-Threaded Python 3.13 (`3.13t`)

HPyX targets `python-freethreading = 3.13.*`. In free-threaded Python:

- `nb::gil_scoped_acquire` / `release` are **no-ops at the Python level** — the GIL is optional.
- Python reference counting is thread-safe (atomic refcounts).
- **Thread safety cannot rely on the GIL** — use explicit `std::mutex` or atomics for shared state.
- HPX worker threads are still not Python threads regardless of GIL mode — the `FREE_THREADED` nanobind flag only enables building against the free-threaded ABI.

The GIL management patterns in `SKILL.md` remain correct under free-threading because they are framed around "this code may run on an HPX worker thread, not a Python thread" rather than GIL-specific semantics.
