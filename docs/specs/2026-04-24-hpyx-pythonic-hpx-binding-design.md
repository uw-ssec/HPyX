# HPyX v1 — Pythonic HPX Binding Design

**Status:** Draft for review
**Date:** 2026-04-24
**Author:** brainstorming session between Don Setiawan and Claude Opus 4.7
**Relationship to other specs:**
- Sits **alongside** `docs/specs/2026-04-24-hpyx-dask-inspired-array-design.md` (a more ambitious dask-inspired v2 option, kept on the shelf for now).
- **Folds in** benchmarking philosophy and authoring contract from the earlier HPyX benchmarking v0 design.
- **Supersedes** portions of `hpyx_improvement_roadmap.md` (Phases 1–3).

---

## 1. Problem, goal, non-goals

### 1.1 Problem

HPyX today wraps ~5% of HPX, and the wrapped parts are largely non-functional:

- `hpx_async` uses `hpx::launch::deferred`, so Python callables execute in the thread that calls `.get()`, not on HPX workers. There is no actual async execution today.
- `HPXExecutor.submit` calls an unbound `hpyx._core.hpx_async_set_result` symbol and crashes.
- `hpx_for_loop`'s `par` path compiles but raises `NotImplementedError` from the Python layer.
- No future composition (`when_all`, `when_any`, `dataflow`), no `concurrent.futures` conformance, no asyncio integration, no real parallel algorithm coverage beyond `dot1d`.
- Scientific Python users, concurrency-aware Python users, and HPX-familiar users all bounce off the library because what it advertises doesn't work.

### 1.2 Goal

Deliver **v1 of HPyX as a small, Pythonic binding for the HPX C++ library** that serves three overlapping audiences:

- **Scientific Python users** who want `concurrent.futures`-style parallelism with a better scheduler, plus ready-made C++ kernels for common numpy reductions.
- **Concurrency-aware Python developers** who want composable futures (`when_all`, `when_any`, `dataflow`, `.then`) and direct `await` support on HPX futures.
- **HPX-familiar users** who want access to HPX execution policies, chunk-size tuning, and the parallel algorithm surface.

The key integration bet: making `HPXExecutor` a real `concurrent.futures.Executor` lets dask plug in directly (`dask.compute(..., scheduler=HPXExecutor())`). Audience A gets dask.array-style collections without HPyX shipping them — dask already did the work; we just provide the backend.

On free-threaded Python 3.13t, HPyX is the only library that gives Python users truly-concurrent execution of Python-defined parallel work (not just C-extension work that releases the GIL). This is a primary differentiator.

### 1.3 Non-goals for v1

- Collection APIs (no `hpyx.Array`, no `hpyx.delayed`). The dask-inspired spec stays shelved as a possible v2.
- **Distributed / multi-locality computation** — no parcelports, no AGAS, no actions. Target for v2. Impacts user stories 4 (Nelly) and 6 (Marcel, distributed portion).
- **GPU execution (CUDA / ROCm / cuPy integration)** — deferred indefinitely. Impacts user story 7 (Damien).
- Synchronization primitives (`Mutex`, `Latch`, `Channel`) — v1.x.
- Custom executor types (`fork_join`, `limiting`, `annotating`) and resource partitioner — v1.x.
- Numerical convenience layer beyond the curated five-kernel set — v1.x.
- Full APEX / HPX performance-counter surface — v1.x; v1 ships a minimal tracing hook only.
- asv / pyperf / CI-side perf regression gating — Phase 1+ per the benchmarking v0 philosophy. v1 ships `pytest-benchmark` for local loop only.

### 1.4 User-story coverage

| # | Persona | v1 coverage | Notes |
|---|---|---|---|
| 1 | Adam (Python dev new to HPC) | ✓ | `HPXExecutor` + implicit auto-init |
| 2 | Karen (HPX dev) | ✓ | `docs/adding-a-binding.md` contributor guide |
| 3 | Hanna (library dev) | ✓ | `hpyx.init(os_threads=…, cfg=[…])` + `HPYX_*` env vars |
| 4 | Nelly (AI researcher, distributed) | ✗ (v2) | Multi-locality deferred |
| 5 | Carla (web app dev) | ✓ | `HPXExecutor` + asyncio bridge |
| 6 | Marcel (distributed + SciPy) | ✓ partial | SciPy interop via numpy; distributed is v2 |
| 7 | Damien (GPU + cuPy) | ✗ | Non-goal |
| 8 | Reynold (dask compile) | ✓ | Direct via `HPXExecutor(concurrent.futures.Executor)` |
| 9 | Britney (perf metrics) | ✓ partial | `hpyx.debug.enable_tracing` + worker-id queries; full APEX is v1.x |

### 1.5 Success criteria (measurement-earned; no hard numeric gates in v1)

- `hpyx.async_(fn, x, y)` runs `fn` on an HPX worker thread (not the caller) under `launch::async`. Verified by asserting `hpyx.debug.get_worker_thread_id()` inside `fn` returns a valid HPX worker id.
- `dask.compute(arr.sum(), scheduler=hpyx.HPXExecutor())` completes for a non-trivial `dask.array` graph without dask-side changes.
- `await hpyx.async_(fn, x, y)` works inside `asyncio.run(main())` without deadlock.
- `hpyx.parallel.for_loop(par, 0, N, fn)` with a pure-Python `fn` scales with `os_threads` on free-threaded 3.13t; exact speedup is **measured and recorded**, not gated. Absence of scaling on GIL-mode 3.13 is expected and documented.
- `hpyx.kernels.dot(a, b)` on 10M-element float64 arrays is **measurably faster** than single-threaded numpy on an 8-core machine; exact ratio earned from measurement, tracked in nightly benchmark trend.
- `hpyx.kernels.*` performance is within ~5% between GIL-mode 3.13 and free-threaded 3.13t (same C++ code, GIL released throughout).
- Full test suite passes on `{3.13, 3.13t} × {Linux, macOS}`.
- A new contributor can add a new HPX parallel-algorithm binding in <1 day by following `docs/adding-a-binding.md`. Verified by `test_contributor_example.py`.
- `hpyx.debug.enable_tracing(path)` produces a JSONL file usable for load-imbalance diagnosis.

### 1.6 v1 scope, consolidated

1. Fix broken async (`launch::async` + GIL discipline).
2. Future composition + `concurrent.futures.Future` protocol conformance.
3. `HPXExecutor` as real `concurrent.futures.Executor` (enables Reynold via dask).
4. Parallel algorithms: 17 Python-callback algorithms + 5 C++ kernels + chunk-size tuning.
5. Runtime lifecycle: implicit auto-init + explicit `hpyx.init()` + `atexit` cleanup.
6. asyncio bridge Level 2: awaitable `Future` + `hpyx.aio.*` combinators.
7. Basic diagnostics: `hpyx.debug.enable_tracing`, `get_num_worker_threads`, `get_worker_thread_id`.
8. Contributor binding guide: `docs/adding-a-binding.md` with a worked example.

---

## 2. Architecture and package layout

### 2.1 Layered architecture

```
┌──────────────────────────────────────────────────────────────┐
│  User-facing Python API (hpyx)                               │
│                                                              │
│  ┌── Audience A: Scientific Python ────────────────────┐     │
│  │   hpyx.HPXExecutor (concurrent.futures.Executor)    │     │
│  │   hpyx.kernels.{dot, matmul, sum, max, min}         │     │
│  │   hpyx.parallel.{for_loop, for_each, transform,     │     │
│  │      reduce, transform_reduce, sort, ...17 total}   │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌── Audience B: Concurrency-aware Python ─────────────┐     │
│  │   hpyx.async_, Future (.then, .result,              │     │
│  │      .add_done_callback, concurrent.futures compat) │     │
│  │   hpyx.when_all, when_any, dataflow, shared_future  │     │
│  │   hpyx.aio.{await_all, await_any, ...} + __await__  │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌── Audience C: HPX-familiar ─────────────────────────┐     │
│  │   hpyx.execution.{seq, par, par_unseq, task}        │     │
│  │   hpyx.execution.{static,dynamic,auto,guided}_      │     │
│  │      chunk_size()                                   │     │
│  │   hpyx.debug.{enable_tracing, get_worker_thread_id, │     │
│  │      get_num_worker_threads}                        │     │
│  │   hpyx.init(os_threads=..., cfg=[...])              │     │
│  │   hpyx.HPXRuntime (context manager)                 │     │
│  └─────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────┤
│  Python internals (pure Python)                              │
│  _runtime.py (auto-init, atexit)   config.py (env vars)      │
│  futures/_future.py (Future class, __await__, concurrent.    │
│     futures.Future protocol)                                 │
│  executor.py (HPXExecutor, submit/map/shutdown)              │
│  parallel.py (17 algorithms, uniform policy plumbing)        │
│  kernels.py (5 kernels, thin dispatch to _core)              │
│  aio.py (asyncio combinators)                                │
├──────────────────────────────────────────────────────────────┤
│  Python/C++ boundary (hpyx._core, nanobind)                  │
│  runtime.cpp   — runtime_start / runtime_stop /              │
│                  num_worker_threads / get_worker_thread_id / │
│                  runtime_is_running                          │
│  futures.cpp   — HPXFuture (GIL-aware get/then/done/…),      │
│                  async_submit, when_all, when_any, dataflow, │
│                  ready_future, shared_future                 │
│  parallel.cpp  — 17 algorithms with Python-callback lambdas  │
│                  (nb::gil_scoped_acquire per iteration)      │
│  kernels.cpp   — dot, matmul, sum, max, min over             │
│                  nb::ndarray, GIL released                   │
├──────────────────────────────────────────────────────────────┤
│  HPX C++ runtime (conda-forge hpx >=1.11 or vendor)          │
│  hpx::start/stop, async, dataflow, when_all/any,             │
│  parallel algorithms, work-stealing scheduler                │
└──────────────────────────────────────────────────────────────┘
```

The three audience boxes label typical entry points, not enforced separations. Everyone can mix and match.

### 2.2 Package layout

```
src/
  _core/                             # C++ / nanobind (refactor from flat src/*.cpp)
    bind.cpp                         # NB_MODULE(_core), submodule registrations
    runtime.cpp                      # init, stop, lifecycle query, worker-thread ids
    runtime.hpp
    futures.cpp                      # HPXFuture, async, when_all/any, dataflow
    futures.hpp
    parallel.cpp                     # 17 algorithms with Python-callback lambdas
    parallel.hpp
    kernels.cpp                      # 5 C++-native kernels over nb::ndarray
    kernels.hpp
    policy_dispatch.hpp              # PolicyToken → hpx::execution policy
    gil_macros.hpp                   # HPYX_KERNEL_NOGIL, HPYX_CALLBACK_GIL
  hpyx/
    __init__.py                      # curated public API
    _runtime.py                      # ensure_started, atexit hook, config reader
    _version.py                      # (existing)
    futures/
      __init__.py                    # Future, when_all, when_any, dataflow,
                                     # shared_future, async_
      _future.py                     # Future class (concurrent.futures.Future
                                     # compatible + .then + __await__)
    executor.py                      # HPXExecutor(concurrent.futures.Executor)
    parallel.py                      # 17 Python-callback algorithms
    kernels.py                       # 5 C++ kernels (thin dispatch)
    aio.py                           # __await__ plumbing, await_all, await_any
    execution.py                     # seq, par, par_unseq, task, chunk-size
    runtime.py                       # HPXRuntime context manager
    debug.py                         # enable_tracing, get_num_worker_threads,
                                     # get_worker_thread_id
    config.py                        # env var parsing, defaults
tests/
  test_runtime.py
  test_futures.py
  test_executor.py
  test_parallel.py
  test_kernels.py
  test_aio.py
  test_execution_policy.py
  test_debug.py
  test_free_threaded.py
  test_dask_integration.py           # dask.compute(..., scheduler=HPXExecutor())
  test_contributor_example.py        # from docs/adding-a-binding.md
  test_large_graph.py
  test_error_propagation.py
benchmarks/
  conftest.py                        # seven fixtures
  README.md                          # authoring contract + profiling recipes
  test_bench_kernels.py
  test_bench_executor.py
  test_bench_parallel.py
  test_bench_futures.py
  test_bench_aio.py
  test_bench_thread_scaling.py       # dedicated: function-scoped runtime
  test_bench_free_threading.py       # dedicated: nogil gate
  test_bench_cold_start.py           # dedicated: cold HPXRuntime start/stop
scripts/
  run_bench_local.sh                 # bench | record | compare
docs/
  adding-a-binding.md                # contributor guide (user story #2)
  migration-0.x-to-1.0.md            # BC migration
  user-guides/
    scientific-python.md             # audience A
    concurrent-futures.md            # audience B
    hpx-native.md                    # audience C
    dask-integration.md              # user story #8
    asyncio.md                       # asyncio bridge
    diagnostics.md                   # user story #9
    free-threaded.md                 # 3.13t guidance
```

### 2.3 Invariants

- **One HPX runtime per process.** Started lazily on first use, torn down by `atexit`. Cannot be restarted — HPX constraint. Documented prominently.
- **The C++ binding surface is small.** Four submodules (`runtime`, `futures`, `parallel`, `kernels`) plus shared headers. No binding touches `nb::object` outside a `nb::gil_scoped_acquire` block.
- **`Future` objects are thread-safe** for the `concurrent.futures.Future` subset.
- **`hpyx.parallel.*` callbacks acquire a Python thread state per iteration.** Under GIL-mode 3.13 this serializes iterations (same tax as any threading-based Python parallelism — use `hpyx.kernels.*` for per-element speed). Under free-threaded 3.13t the acquisitions are per-thread-local and iterations execute **truly concurrently** across HPX workers — this is HPyX's principal advantage on 3.13t over `concurrent.futures`, `joblib`, and dask's threaded scheduler.
- **User-authored Python in callbacks is not automatically thread-safe on 3.13t.** Shared mutable state (global counters, non-thread-safe data structures) needs explicit locking. Documented in `docs/user-guides/free-threaded.md`.
- **`hpyx.kernels.*` release the GIL for their full duration.** No `nb::object` access inside kernel bodies. `nb::ndarray` views only.
- **The Python layer is pure Python.** Only `executor.py`, `futures/_future.py`, `parallel.py`, `kernels.py`, `aio.py`, and `_runtime.py` touch `hpyx._core`.

### 2.4 Key design decisions

| Decision | Choice | Why |
|---|---|---|
| Target audiences | All three: scientific Python, concurrency-aware, HPX-familiar | v1 serves each through a distinct entry point over shared backend |
| Relationship to dask-inspired spec | Ships first as a smaller v1; dask layer deferred to possible v2 | Dask integration comes free via `HPXExecutor` so we don't reimplement it |
| asyncio integration | Level 2 — `__await__` on `Future` + `hpyx.aio` combinators | Low surface, big ergonomics win |
| Parallel algorithm strategy | Two tracks — `hpyx.parallel.*` (Python callbacks) + `hpyx.kernels.*` (C++ kernels) | Honest about GIL cost; covers both fine- and coarse-grained workloads |
| Algorithm coverage | 17 Python-callback algorithms + 5 C++ kernels + chunk-size tuning | Once plumbing works, additional algorithms are ~20 lines each |
| Module layout | `src/_core/` (C++) + `src/hpyx/` (Python), flat per-topic Python modules | Matches the three-audience mental model; no premature `_expr/` subpackage |
| BC stance | Clean break at v1. Rewrite `HPXExecutor`, reshape `hpyx.futures`. Keep `HPXRuntime`. `hpyx.multiprocessing` → deprecation shim for one release, then remove | v1 is the right moment to fix broken APIs |
| Runtime lifecycle | Implicit auto-init + explicit `hpyx.init()` override + `atexit` shutdown | HPX can-not-restart constraint forces singleton |
| Benchmarking approach | `pytest-benchmark` only for local loop; no CI perf gating; no hard numeric targets | Phase 1+ adds asv/pyperf/CI gates. Targets earned by measurement. |

---

## 3. C++ `_core` binding surface

### 3.1 `runtime.cpp`

Replaces today's `init_hpx.cpp`. Same suspended-runtime pattern (startup condition variable + HPX spinlock-guarded shutdown signal); names cleaned up.

```cpp
// Thread-safe, idempotent. Returns true if we started the runtime here,
// false if it was already running.
bool runtime_start(std::vector<std::string> cfg = {});

// Blocks until HPX drains. Idempotent.
// Does NOT re-enable starting (HPX can't restart within a process).
void runtime_stop();

bool runtime_is_running();

std::size_t num_worker_threads();
std::size_t get_worker_thread_id();   // returns -1 from non-HPX threads
std::string hpx_version_string();
```

`cfg` takes INI-style `"key!=value"` strings. Defaults set `hpx.os_threads`, `hpx.run_hpx_main!=1`, `hpx.commandline.allow_unknown!=1`, `hpx.parcel.tcp.enable!=0`, `hpx.diagnostics_on_terminate!=0`. Python side layers `hpyx.init(os_threads=N)` on top as sugar.

### 3.2 `futures.cpp`

The module that **fixes the broken `launch::deferred` behavior** — the core correctness improvement in v1.

```cpp
// Python-visible class: _core.futures.HPXFuture
// Wraps hpx::shared_future<nb::object> internally so multiple .then()/.add_done_callback()
// plus __await__ can share the same future.
class HPXFuture {
    hpx::shared_future<nb::object> fut_;
    std::atomic<bool> cancelled_{false};
    std::atomic<bool> running_{false};
public:
    // concurrent.futures.Future-compatible
    nb::object result(std::optional<double> timeout = std::nullopt);
    nb::object exception(std::optional<double> timeout = std::nullopt);
    bool done();
    bool cancelled();
    bool running();
    bool cancel();
    void add_done_callback(nb::callable cb);   // safe from any thread

    // HPX-native
    HPXFuture then(nb::callable cb);
    HPXFuture share() const;
};

// Scheduling primitives — all use hpx::launch::async (NOT deferred).
HPXFuture async_submit(nb::callable fn, nb::args args, nb::kwargs kwargs);
HPXFuture dataflow(nb::callable fn, std::vector<HPXFuture> inputs,
                    nb::kwargs kwargs);
HPXFuture when_all(std::vector<HPXFuture> inputs);      // result: tuple
HPXFuture when_any(std::vector<HPXFuture> inputs);      // result: (index, future)
HPXFuture ready_future(nb::object value);
```

Task-body pattern (applied everywhere a Python callable runs on an HPX worker):

```cpp
auto task = [fn, args, kwargs]() -> nb::object {
    nb::gil_scoped_acquire acquire;
    try {
        return fn(*args, **kwargs);
    } catch (nb::python_error &e) {
        e.restore();          // stash on thread state
        throw;                // HPX captures into future's exception slot
    }
};
fut_ = hpx::async(hpx::launch::async, std::move(task)).share();
```

`result()` releases the GIL during the wait, reacquires before returning, rethrows any captured Python exception with original traceback.

### 3.3 `parallel.cpp`

Houses all 17 Python-callback parallel algorithms. Uses `dispatch_policy` + `HPYX_CALLBACK_GIL` to keep each binding ~15 lines.

```cpp
void parallel_for_loop(PolicyToken tok,
                       std::int64_t first, std::int64_t last,
                       nb::callable body) {
    auto pyfn = [body](std::int64_t i) {
        nb::gil_scoped_acquire acquire;
        body(i);
    };
    dispatch_policy(tok, [&](auto&& policy) {
        hpx::experimental::for_loop(policy, first, last, pyfn);
    });
}

HPXFuture parallel_for_loop_task(PolicyToken tok,
                                 std::int64_t first, std::int64_t last,
                                 nb::callable body);
```

All 17 follow the same shape:

| Family | Algorithms |
|---|---|
| Iteration | `for_loop`, `for_each` |
| Transform / reduce | `transform`, `reduce`, `transform_reduce` |
| Search | `count`, `count_if`, `find`, `find_if`, `all_of`, `any_of`, `none_of` |
| Sort / order | `sort`, `stable_sort` |
| Fill / copy | `fill`, `fill_n`, `copy`, `copy_if`, `iota` |
| Scan | `inclusive_scan`, `exclusive_scan` |

### 3.4 `kernels.cpp`

Five C++-native kernels. No `nb::object` inside; GIL released for the duration.

```cpp
template <typename T>
double kernel_dot(nb::ndarray<const T, nb::c_contig> a,
                  nb::ndarray<const T, nb::c_contig> b);

template <typename T>
nb::ndarray<T, nb::c_contig> kernel_matmul(nb::ndarray<const T, nb::c_contig> A,
                                           nb::ndarray<const T, nb::c_contig> B);

template <typename T> T kernel_sum(nb::ndarray<const T, nb::c_contig> a);
template <typename T> T kernel_max(nb::ndarray<const T, nb::c_contig> a);
template <typename T> T kernel_min(nb::ndarray<const T, nb::c_contig> a);
```

Each instantiated for `float32`, `float64`, `int32`, `int64`. Body pattern:

```cpp
template <typename T>
double kernel_dot(nb::ndarray<const T, nb::c_contig> a,
                  nb::ndarray<const T, nb::c_contig> b) {
    if (a.size() != b.size())
        throw std::invalid_argument("dot: size mismatch");
    const T* ap = a.data();
    const T* bp = b.data();
    std::size_t n = a.size();
    nb::gil_scoped_release release;
    return static_cast<double>(
        hpx::transform_reduce(hpx::execution::par,
            ap, ap + n, bp, T{0},
            std::plus<T>{}, std::multiplies<T>{}));
}
```

### 3.5 `policy_dispatch.hpp`

```cpp
struct PolicyToken {
    enum class Kind { seq, par, par_unseq, unseq };
    enum class Chunk { none, static_, dynamic_, auto_, guided };
    Kind kind;
    bool task;              // par(task), seq(task), etc.
    Chunk chunk;
    std::size_t chunk_size;
};

template <typename Fn>
auto dispatch_policy(const PolicyToken& t, Fn&& fn);
```

The Python-side `hpyx.execution.par.with_(static_chunk_size(1000))` yields a `PolicyToken` and passes it through. The dispatcher uses `if constexpr` to inline one policy path per call site.

### 3.6 `gil_macros.hpp`

```cpp
#define HPYX_KERNEL_NOGIL   nb::gil_scoped_release _hpyx_release_
#define HPYX_CALLBACK_GIL   nb::gil_scoped_acquire _hpyx_acquire_
```

Documented in the contributor guide.

### 3.7 `bind.cpp`

```cpp
NB_MODULE(_core, m) {
    m.doc() = "HPyX C++/Python bridge (nanobind)";

    auto m_rt    = m.def_submodule("runtime");
    auto m_fut   = m.def_submodule("futures");
    auto m_par   = m.def_submodule("parallel");
    auto m_kern  = m.def_submodule("kernels");

    runtime::register_bindings(m_rt);
    futures::register_bindings(m_fut);
    parallel::register_bindings(m_par);
    kernels::register_bindings(m_kern);
}
```

Each submodule file exposes `void register_bindings(nb::module_&)`. Keeps `bind.cpp` at ~30 lines.

### 3.8 Build changes (`CMakeLists.txt`)

```cmake
nanobind_add_module(_core FREE_THREADED
    src/_core/bind.cpp
    src/_core/runtime.cpp
    src/_core/futures.cpp
    src/_core/parallel.cpp
    src/_core/kernels.cpp
)
```

Unchanged link: `HPX::hpx` + `HPX::wrap_main` + `HPX::iostreams_component`. `FREE_THREADED` flag already set today.

---

## 4. Python API surface

### 4.1 `hpyx.__init__`

Curated re-exports:

```python
from hpyx import (
    # Runtime control
    init, shutdown, is_running, HPXRuntime,
    # Execution policies (submodule)
    execution,
    # Futures and composition
    async_, Future, when_all, when_any, dataflow, shared_future, ready_future,
    # Executor
    HPXExecutor,
    # Parallel algorithm namespaces
    parallel, kernels,
    # asyncio bridge
    aio,
    # Diagnostics
    debug,
    # Config
    config,
)
```

### 4.2 `hpyx.runtime` and `hpyx._runtime`

```python
# Public
def init(
    *,
    os_threads: int | None = None,        # defaults to os.cpu_count()
    cfg: list[str] | None = None,         # extra HPX "key!=value" strings
) -> None: ...

def shutdown() -> None: ...
def is_running() -> bool: ...

class HPXRuntime:
    def __init__(self, *, os_threads: int | None = None,
                 cfg: list[str] | None = None): ...
    def __enter__(self) -> "HPXRuntime": ...
    def __exit__(self, *exc) -> None: ...
```

```python
# Internal
def ensure_started() -> None:
    """Called by every public API needing the runtime.
    Idempotent, thread-safe. Reads env vars on first call,
    registers atexit hook."""
```

Env vars honored by `ensure_started` (via `config.py`):
- `HPYX_OS_THREADS` — integer, overrides auto-detect
- `HPYX_CFG` — semicolon-separated list of extra HPX config strings
- `HPYX_AUTOINIT` — `"0"` disables implicit init (useful for testing)

### 4.3 `hpyx.execution`

```python
seq = SeqPolicy()
par = ParPolicy()
par_unseq = ParUnseqPolicy()
unseq = UnseqPolicy()
task = TaskTag()              # combines with seq/par via call: par(task)

# Chunk size modifiers
static_chunk_size(n: int)  -> ChunkSize
dynamic_chunk_size(n: int) -> ChunkSize
auto_chunk_size()          -> ChunkSize
guided_chunk_size()        -> ChunkSize

# Composition
par.with_(static_chunk_size(1000))
par(task).with_(dynamic_chunk_size(100))
```

Each policy carries a `PolicyToken` and a serialization hook so it can be passed to `_core` as a single struct.

### 4.4 `hpyx.futures`

```python
# hpyx/futures/_future.py
class Future:
    # concurrent.futures.Future protocol
    def result(self, timeout: float | None = None) -> Any: ...
    def exception(self, timeout: float | None = None) -> BaseException | None: ...
    def done(self) -> bool: ...
    def cancelled(self) -> bool: ...
    def running(self) -> bool: ...
    def cancel(self) -> bool: ...
    def add_done_callback(self, fn: Callable[["Future"], None]) -> None: ...

    # HPX-native
    def then(self, fn: Callable[["Future"], Any]) -> "Future": ...
    def share(self) -> "Future": ...

    # asyncio bridge
    def __await__(self): ...

# hpyx/futures/__init__.py (free functions)
def async_(fn: Callable, *args, **kwargs) -> Future: ...
def when_all(*futures: Future) -> Future: ...                 # result: tuple
def when_any(*futures: Future) -> Future: ...                 # result: (index, Future)
def dataflow(fn: Callable, *futures: Future) -> Future: ...   # N-input continuation
def shared_future(f: Future) -> Future: ...
def ready_future(value: Any) -> Future: ...
```

### 4.5 `hpyx.executor`

```python
from concurrent.futures import Executor

class HPXExecutor(Executor):
    def __init__(self, max_workers: int | None = None):
        """max_workers is advisory only — HPX's thread pool is process-global.
        If runtime isn't started yet, max_workers seeds implicit init as
        os_threads. If the runtime is already started with a different
        os_threads, a warning is emitted."""

    def submit(self, fn: Callable, *args, **kwargs) -> Future: ...
    def map(self, fn, *iterables, timeout=None, chunksize=1): ...
    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Marks this executor handle unusable. Does NOT stop the HPX runtime
        (HPX can't restart). Subsequent submit() raises RuntimeError."""
```

Dask usage (critical user-story-8 path):

```python
import dask.array as da
import hpyx

with hpyx.HPXExecutor() as ex:
    x = da.random.random((10_000, 10_000), chunks=(1_000, 1_000))
    result = (x @ x.T).sum().compute(scheduler=ex)
```

### 4.6 `hpyx.parallel`

Every algorithm has the same shape: first arg is a policy (a `PolicyToken`-carrying object), remaining args match the HPX algorithm.

```python
# Iteration
def for_loop(policy, first: int, last: int, body) -> None | Future: ...
def for_each(policy, iterable, fn) -> None | Future: ...

# Transform / reduce
def transform(policy, src, dst, fn) -> None | Future: ...
def reduce(policy, iterable, *, init=0, op=operator.add) -> Any | Future: ...
def transform_reduce(policy, iterable, *, init=0,
                     reduce_op=operator.add, transform_op=identity) -> Any | Future: ...

# Search
def count(policy, iterable, value) -> int | Future: ...
def count_if(policy, iterable, pred) -> int | Future: ...
def find(policy, iterable, value) -> int | Future: ...           # -1 if not found
def find_if(policy, iterable, pred) -> int | Future: ...
def all_of(policy, iterable, pred) -> bool | Future: ...
def any_of(policy, iterable, pred) -> bool | Future: ...
def none_of(policy, iterable, pred) -> bool | Future: ...

# Sort / order
def sort(policy, iterable, key=None, reverse=False) -> None | Future: ...
def stable_sort(policy, iterable, key=None, reverse=False) -> None | Future: ...

# Fill / copy / iota
def fill(policy, iterable, value) -> None | Future: ...
def fill_n(policy, iterable, n: int, value) -> None | Future: ...
def copy(policy, src, dst) -> None | Future: ...
def copy_if(policy, src, dst, pred) -> int | Future: ...
def iota(policy, iterable, start=0) -> None | Future: ...

# Scans
def inclusive_scan(policy, src, dst, *, op=operator.add, init=None) -> None | Future: ...
def exclusive_scan(policy, src, dst, *, init=0, op=operator.add) -> None | Future: ...
```

When the policy carries the `task` tag, return type switches to `Future[T]`. Implemented as a uniform decorator in `parallel.py`.

**Note on keyword-only args:** `reduce`, `transform_reduce`, `inclusive_scan`, and `exclusive_scan` make `init` / `op` / `reduce_op` / `transform_op` keyword-only to avoid a footgun — `hpyx.parallel.reduce(par, arr, operator.mul)` would otherwise silently pass `operator.mul` as `init`. Writers must use `hpyx.parallel.reduce(par, arr, op=operator.mul)`.

### 4.7 `hpyx.kernels`

```python
def dot(a: np.ndarray, b: np.ndarray) -> float | int: ...      # scalar
def matmul(A: np.ndarray, B: np.ndarray) -> np.ndarray: ...    # 2D
def sum(a: np.ndarray) -> float | int: ...
def max(a: np.ndarray) -> float | int: ...
def min(a: np.ndarray) -> float | int: ...
```

Accepts `float32 | float64 | int32 | int64`. Non-contiguous or other dtypes raise `TypeError` pointing at `hpyx.parallel.*` or numpy.

### 4.8 `hpyx.aio`

```python
async def await_all(*futures: Future) -> tuple: ...
async def await_any(*futures: Future) -> tuple[int, Future]: ...

# Async variants of the 17 parallel algorithms (wrap policy(task))
async def for_loop(policy, first, last, body) -> None: ...
async def transform_reduce(policy, iterable, init=0,
                           reduce_op=..., transform_op=...) -> Any: ...
# ... etc
```

Example:

```python
import asyncio, hpyx, operator

async def main():
    f1 = hpyx.async_(parse, path1)
    a = await f1                                       # direct await

    b, c = await hpyx.aio.await_all(
        hpyx.async_(parse, path2),
        hpyx.async_(parse, path3),
    )

    total = await hpyx.aio.transform_reduce(
        hpyx.execution.par, arr, 0.0,
        operator.add, lambda x: x * x,
    )

asyncio.run(main())
```

### 4.9 `hpyx.debug`

```python
def enable_tracing(path: str | None = None) -> None:
    """Capture per-task events: (task_name, worker_thread_id, start_time,
    duration) as newline-delimited JSON. path=None prints to stderr."""

def disable_tracing() -> None: ...

def get_num_worker_threads() -> int: ...
def get_worker_thread_id() -> int: ...   # -1 if called from non-HPX thread
```

### 4.10 `hpyx.config`

```python
DEFAULTS = {
    "os_threads": None,        # → os.cpu_count()
    "cfg": [],
    "autoinit": True,
    "trace_path": None,
}

def from_env() -> dict: ...    # reads HPYX_* env vars
```

Precedence: `hpyx.init()` kwargs > env vars > defaults.

---

## 5. Runtime lifecycle, error handling, thread safety

### 5.1 Runtime lifecycle

```
UNSTARTED ──(ensure_started)──► RUNNING ──(atexit | shutdown)──► STOPPED
                                   ▲                                │
                                   └── cannot transition back ──────┘
```

**Implicit auto-init path:** every public API calls `ensure_started()`. The function is guarded by a Python `threading.Lock`, idempotent, reads env vars once, registers `atexit.register(runtime_stop)`.

**Explicit-init path:**

```python
import hpyx
hpyx.init(os_threads=4, cfg=["hpx.stacks.small_size=0x20000"])
# ... normal use; atexit still owns shutdown ...
```

`hpyx.init()` raises `RuntimeError("HPyX runtime already started with different config")` if called a second time with conflicting args. With identical args or no args, no-op.

**Shutdown:** preferred path is `atexit`. Manual `hpyx.shutdown()` is irreversible; any subsequent `hpyx.*` call raises `RuntimeError("HPyX runtime has been stopped and cannot restart within this process")`. We emit a loud warning on first manual shutdown.

**Multiple `HPXExecutor` instances:** all share one process-wide runtime. `HPXExecutor.shutdown()` marks that handle unusable but does **not** tear down the runtime. Documented prominently.

**Test fixture pattern:**

```python
# tests/conftest.py
@pytest.fixture(scope="session", autouse=True)
def _hpx_runtime():
    hpyx.init(os_threads=4, cfg=[...])
    yield
    # atexit handles shutdown
```

Plus a `@pytest.mark.skip_after_shutdown` marker for tests that would need a post-shutdown runtime.

### 5.2 Error handling

**Python exceptions in tasks:**

1. Callable raises → `nb::python_error` caught in task lambda → restored on HPX thread state → HPX captures into future's exception slot → `Future.result()` reraises with original traceback.
2. Multiple concurrent failures: **first-to-fail wins.** `when_all` collects all but only surfaces the first. Siblings that have already started finish; dependents short-circuit.
3. `Future.add_done_callback` callbacks that raise: caught, logged at WARNING via `hpyx.debug`, swallowed. Matches `concurrent.futures.Future`.

**Kernel errors** (shape / dtype / contiguity):
- Mismatched sizes → `ValueError` synchronous to caller.
- Unsupported dtype → `TypeError` with pointer to `hpyx.parallel.*` or numpy.
- Non-contiguous input → `TypeError` with hint to call `np.ascontiguousarray()`. We do not silently copy — performance would degrade invisibly.

**Runtime errors:**
- `hpyx.async_` after `shutdown()` → `RuntimeError("HPyX runtime has been stopped")`.
- `hpyx.init()` with conflicting args after start → `RuntimeError` with both values.
- Bad HPX config → HPX raises during `runtime_start`; we catch in `ensure_started`, leave state `UNSTARTED`, re-raise.

**Asyncio error path:**
- Awaiting a `Future` whose task raised → exception propagates through `await`, same as `asyncio.Future`.
- Event loop closed when HPX task resolves → we log at WARNING, drop the notification.

### 5.3 Thread safety

**`Future`** is thread-safe for concurrent `result`/`done`/`add_done_callback`/`cancel`/`exception` + multiple concurrent `.then()` calls. Internal `hpx::shared_future` handles fan-out.

**`HPXExecutor`** is thread-safe for `submit`/`map`/`shutdown`. One `shutdown()` caller wins; others see shutdown state on next submit.

**User-authored callbacks on free-threaded 3.13t:**
- Multiple HPX workers can run `hpyx.parallel.*` Python callbacks truly concurrently.
- Shared mutable state in user code is not automatically thread-safe. Users must lock manually (`threading.Lock`, `queue.Queue`, etc.).
- Covered in `docs/user-guides/free-threaded.md`: shared dicts, logging, numpy ops with internal locks, global counters.

**User-authored callbacks on GIL-mode 3.13:** GIL provides accidental serialization. Callbacks that rely on this will race on 3.13t. We warn in docs but don't attempt runtime detection.

### 5.4 Cancellation

v1 offers a **stub cancellation model**:

- `Future.cancel()` before task starts → marked cancelled, never scheduled → returns `True`.
- `Future.cancel()` after task is running → returns `False`. Task continues to completion.
- `Future.cancel()` after completion → returns `False`.
- `Future.cancelled()` reflects the above.
- No mid-flight cancellation. No `CancelledError` delivered into running tasks.

Real cancellation tokens (`hpx::stop_token`) are an HPX capability but wiring them through Python is v1.x work.

### 5.5 Invariants summary

- Runtime is a process-singleton. Lazy start. Stopped only at atexit or explicit shutdown. No restart.
- Multiple `HPXExecutor` instances share that singleton. Their `shutdown()` is per-handle.
- `Future` is thread-safe for `concurrent.futures.Future` operations and `.then`.
- Python exceptions cross the HPX boundary with original tracebacks; first-to-fail wins.
- Cancellation is stubbed to not-yet-started tasks only.
- On 3.13t, user callbacks handle their own thread safety for shared state.

---

## 6. Testing, benchmarks, CI, migration, risks

### 6.1 Test strategy

Two-tier pyramid.

**Unit tests** (fast, in-process, pytest):

| File | Covers |
|---|---|
| `test_runtime.py` | init, shutdown, is_running, HPXRuntime, env var precedence, post-shutdown errors |
| `test_futures.py` | Future.result/done/cancelled/add_done_callback/exception, .then chains, when_all/when_any/dataflow, exception propagation, timeout |
| `test_executor.py` | concurrent.futures.Executor protocol conformance, submit/map/shutdown, max_workers reconciliation warnings |
| `test_parallel.py` | All 17 algorithms vs Python reference (itertools/functools/math); policy dispatch |
| `test_kernels.py` | 5 kernels × 4 dtypes vs numpy reference; shape/contiguity error paths |
| `test_aio.py` | __await__ on Future, asyncio.wrap_future, loop.run_in_executor, await_all/await_any, loop-closed handling |
| `test_execution_policy.py` | seq/par/par_unseq/task composition, chunk-size modifiers, with_() chaining |
| `test_debug.py` | enable_tracing JSONL format, worker-id query from HPX and non-HPX threads |
| `test_free_threaded.py` | Multi-thread submit, concurrent add_done_callback, parallel callback race detection via shared-queue sentinel |

**Integration tests** (slower, cross-component):

| File | Covers |
|---|---|
| `test_dask_integration.py` | `dask.compute(arr.sum(), scheduler=HPXExecutor())` smoke (user story 8) |
| `test_contributor_example.py` | Executes worked example from `docs/adding-a-binding.md` end-to-end |
| `test_large_graph.py` | 10k+ futures via dataflow/when_all, scheduler doesn't degrade |
| `test_error_propagation.py` | Exceptions from deep .then chains, mixed dataflow children, kernel failures |

**Property-based tests** (hypothesis):
- Random well-typed policy tokens + algorithms vs stdlib reference.
- Random ndarray shapes and dtypes for kernels vs numpy reference.
- Random future DAGs (up to ~50 nodes) vs topological-sort reference execution.

**Reference-comparison tests** — every algorithm and kernel has a companion that runs numpy/stdlib on same input with tolerance assertions.

### 6.2 Benchmarks and profiling

Folded from the earlier HPyX benchmarking v0 design.

**Framework: `pytest-benchmark`** — deliberately minimal for v1 — local developer loop only. `pyperf` multi-process isolation, `asv` continuous tracking, dedicated physical runners, and CI-side perf gating all stay in the forward roadmap (Phase 1+).

**No numeric targets in v1.** No `TARGETS.md`. Targets are earned by measurement. §1.5 success criteria use measurable properties, not hard ratios.

**Seven-rule authoring contract:**

1. **Setup is never timed.** Use `benchmark.pedantic(..., setup=..., rounds=...)` or session-scoped fixtures. Never construct `HPXRuntime()` inside the timed callable. (Today's `test_bench_for_loop.py` violates this — fix as part of v1.)
2. **Parametrize across three size orders** — minimum `[1_000, 100_000, 10_000_000]`. Makes fixed call overhead visually separable from per-element cost.
3. **Three matching baselines per HPyX benchmark**, in the same `pytest-benchmark` group: NumPy equivalent, pure-Python equivalent, `concurrent.futures.ThreadPoolExecutor` equivalent. Absence of any baseline is documented in the test's docstring.
4. **Explicit group names** via module-level `pytestmark = pytest.mark.benchmark(group="<topic>")`. One group per "thing being compared."
5. **Minimize Python overhead unless measuring it.** When a Python callback is intrinsic, docstring states callback overhead is part of measurement.
6. **Thread-scaling parametrization** via `@pytest.mark.parametrize("threads", [1, 2, 4, 8])` with `hpx_threads` fixture. Skip when fewer physical cores available.
7. **Free-threading gating.** Benchmarks asserting speedup under nogil use `requires_free_threading` fixture (checks `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`). Skip cleanly on GIL-mode 3.13.

**Seven shared fixtures** in `benchmarks/conftest.py`:

| Fixture | Scope | Purpose |
|---|---|---|
| `pin_cpu` | session, autouse | `os.sched_setaffinity(0, {0})` on Linux; no-op on macOS (noisier — documented) |
| `seed_rng` | function, autouse | Deterministic seeding of `random`, `numpy.random`, HPyX RNG from test ID |
| `no_gc` | function, opt-in | Context manager disabling gc during timed region |
| `hpx_runtime` | session | Starts `HPXRuntime()` once per session; reused |
| `hpx_threads` | function, indirect | Parametrizes HPX thread count; restarts HPX per parametrization in dedicated files |
| `requires_free_threading` | marker + skip | Skip unless `Py_GIL_DISABLED == 1` |
| `env_sanity_check` | session, autouse | Fail on battery power; fail if HPX built Debug; warn if turbo-boost state unknown |

**Thread count vs session runtime resolution:** thread-count-varying benchmarks live in dedicated files (`test_bench_thread_scaling.py`, `test_bench_free_threading.py`) that opt out of session `hpx_runtime` and restart HPX per parametrization. This sidesteps the HPX cannot-restart constraint by using process-per-parametrization via pytest-xdist or manual subprocess if needed.

**CMake `profile` preset** in `CMakePresets.json`:

```json
{
  "name": "profile",
  "inherits": "default",
  "cacheVariables": {
    "CMAKE_BUILD_TYPE": "RelWithDebInfo",
    "CMAKE_CXX_FLAGS_RELWITHDEBINFO": "-O2 -g -fno-omit-frame-pointer",
    "CMAKE_INTERPROCEDURAL_OPTIMIZATION": "OFF",
    "CMAKE_CXX_VISIBILITY_PRESET": "default"
  }
}
```

Release-level optimization + frame pointers + debug info so `py-spy --native`, `perf`, and `memray --native` resolve C++ frames.

**`scripts/run_bench_local.sh` subcommands:**
- `bench [pytest args]` — runs `pytest benchmarks/ --benchmark-only` with repo defaults.
- `record <test-id>` — runs under `py-spy record --native --rate 500 -o flame.svg -- …` for cross-language flame graphs.
- `compare` — runs `pytest-benchmark compare` against locally stored baseline.

Documented in `benchmarks/README.md` alongside copy-pasteable commands for `py-spy`, `Scalene`, and `memray` (all require the `profile` preset for useful native frames).

**Benchmark file layout:**

```
benchmarks/
  conftest.py
  README.md
  test_bench_kernels.py           # dot, matmul, sum vs numpy (one group per kernel)
  test_bench_executor.py          # HPXExecutor.map vs ThreadPool vs ProcessPool
  test_bench_parallel.py          # parallel.for_loop/transform/reduce — callback track
  test_bench_futures.py           # future/callback overhead, dataflow DAG throughput
  test_bench_aio.py               # await fut vs asyncio.wrap_future
  test_bench_thread_scaling.py    # dedicated: function-scoped runtime
  test_bench_free_threading.py    # dedicated: nogil smoke
  test_bench_cold_start.py        # dedicated: cold HPXRuntime start/stop
```

`test_bench_cold_start.py` directly addresses the risk that session-scoped `hpx_runtime` hides per-call startup regressions.

### 6.3 CI matrix

Functional CI only in v1 — **no perf gating.**

| Dimension | Values |
|---|---|
| Python build | `3.13` (GIL-mode), `3.13t` (free-threaded) |
| OS | `ubuntu-latest`, `macos-latest` |
| HPX source | `conda-forge hpx >=1.11` (primary), vendor-build (nightly only) |
| Build type | `Release` (primary), `Debug` (Linux only) |

Full unit + integration suite runs every PR across `{3.13, 3.13t} × {ubuntu, macos} × {conda-forge, Release}`. Vendor-build + Debug are nightly. Nightly job also runs full benchmarks for trend visibility but does not gate PRs. Benchmark artifacts (pytest-benchmark JSON + flamegraphs) stored as nightly artifacts; no dashboard in v1.

### 6.4 Migration notes (0.x → 1.0)

| 0.x | v1.0 |
|---|---|
| `from hpyx import HPXRuntime` | Unchanged. Still works. Optional now — auto-init is default. |
| `from hpyx import HPXExecutor` | Unchanged import path. Signature change: now a real `concurrent.futures.Executor`. `submit()` that used to crash now works. |
| `from hpyx.futures import submit` | **Removed.** Use `hpyx.HPXExecutor().submit(fn, *args)` or `hpyx.async_(fn, *args)`. |
| `from hpyx.multiprocessing import for_loop` | **Deprecation shim** in v1.0 re-exporting `hpyx.parallel.for_loop`, emits `DeprecationWarning`. Module removed in v1.1. |
| `hpyx._core.hpx_async` | Semantics changed: now uses `launch::async`, runs on HPX workers. Calls that relied on deferred-evaluation timing will see real concurrency. |
| `hpyx._core.hpx_async_add` | **Removed.** Was a debug artifact. |
| `hpyx._core.future` (class) | Replaced by `hpyx._core.futures.HPXFuture`. Python users should use `hpyx.Future` rather than reaching into `_core`. |

Shipped in `docs/migration-0.x-to-1.0.md` with before/after snippets for every breaking change.

### 6.5 Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Switching `hpx_async` from `launch::deferred` to `launch::async` surfaces GIL bugs the deferred model papered over. Real debugging likely. | High | Feature flag `HPYX_ASYNC_MODE=deferred\|async`, default to async once tests pass; keep deferred path for emergency rollback through v1.0, remove in v1.1. |
| 2 | Free-threaded Python 3.13t is still stabilizing. Numpy, pytest, and other deps may have 3.13t-specific bugs. | Medium | CI matrix dimension forces early breakage. `docs/user-guides/free-threaded.md` lists known rough edges. No hard 3.13t requirement for end users until ecosystem matures. |
| 3 | HPX can't restart — pytest isolation assumption breaks. | Medium | Session-scoped fixture; `@pytest.mark.skip_after_shutdown` marker; `test_runtime.py::test_cannot_restart` encodes the constraint. |
| 4 | `HPXExecutor.shutdown()` doesn't actually shut down the runtime. Surprises `concurrent.futures` users. | Low | Documented prominently in `docs/user-guides/concurrent-futures.md` and in docstring. Not fixable without HPX runtime-restart support. |
| 5 | Per-iteration GIL acquire overhead on GIL-mode 3.13 makes `hpyx.parallel.*` look slow vs numpy. Users benchmark naively and dismiss. | Medium | Benchmarks show both modes clearly. Docs: "GIL-mode: use `hpyx.kernels.*` or dask-on-HPXExecutor; free-threaded: parallel.* is fast." |
| 6 | Numpy/scipy free-threaded maturity — user callbacks calling numpy may partially serialize on 3.13t. | Medium | `docs/user-guides/free-threaded.md` lists known 3.13t-clean numpy APIs; benchmarks detect future improvements. |
| 7 | Asyncio `call_soon_threadsafe` + free-threaded 3.13t thread-safety edge cases. | Low | `test_aio.py` covers edge cases (loop closed, event loop in different thread, cancellation across threads). |
| 8 | Dask integration doesn't Just Work because dask assumes certain executor behavior. | Medium | `test_dask_integration.py` smoke on a real dask.array graph. Issues fixed in v1.0.x; we don't claim "full dask compatibility" — just the `scheduler=HPXExecutor()` path. |
| 9 | Contributor friction adding new HPX bindings — `HPYX_KERNEL` + `HPYX_CALLBACK_GIL` macros and `PolicyToken` dispatch are subtle. | Low | `docs/adding-a-binding.md` walks a worked example. `test_contributor_example.py` keeps it accurate. |
| 10 | Scope creep — "add one more HPX feature" delays v1. | Medium | v1 scope is frozen at 8 items (§1.6). Everything else goes in v1.x backlog tracked in `ROADMAP.md`. |
| 11 | Session-scoped `hpx_runtime` benchmark fixture hides per-call startup regressions. | Low | `test_bench_cold_start.py` opts out and measures cold start/stop explicitly. Regressions show up in nightly trend. |
| 12 | `ThreadPoolExecutor` benchmark baseline is misleading for CPU-bound work under GIL. | Low | Baselines labeled; docstrings note `ThreadPoolExecutor` on GIL CPython is a ceiling on what naive users reach for, not a fair parallel comparison. |
| 13 | Free-threading smoke benchmark gives false confidence — one test on 3.13t doesn't prove scaling everywhere. | Low | Scope of `test_bench_free_threading.py` is explicit: "harness works end-to-end on 3.13t," not "HPyX scales linearly everywhere." |
| 14 | macOS benchmark noise invalidates comparisons. | Low | `benchmarks/README.md` documents this. `pin_cpu` no-op on macOS. Authoritative numbers come from Linux. |

### 6.6 Delivery checklist

- [ ] `src/_core/` refactor from flat `src/*.cpp` — one PR.
- [ ] `runtime.cpp` rewrite with GIL discipline + atexit — one PR.
- [ ] `futures.cpp` rewrite with `launch::async` + `HPXFuture` + combinators — two PRs (core class, then combinators).
- [ ] `parallel.cpp` with 17 algorithms — staged PRs grouped by family (iteration, transform/reduce, search, sort, fill/copy, scan).
- [ ] `kernels.cpp` with 5 kernels — one PR.
- [ ] `policy_dispatch.hpp` + `gil_macros.hpp` — lands with first `parallel.cpp` PR.
- [ ] Python `hpyx/futures/_future.py` + `hpyx/executor.py` + `hpyx/aio.py` — one PR each.
- [ ] `hpyx/parallel.py` + `hpyx/kernels.py` + `hpyx/execution.py` — one PR each.
- [ ] `hpyx/debug.py`, `hpyx/config.py` — folded into runtime PR.
- [ ] `docs/adding-a-binding.md`, `docs/migration-0.x-to-1.0.md`, user guides — one docs PR.
- [ ] CI matrix updates — one PR.
- [ ] `test_dask_integration.py`, `test_contributor_example.py`, `test_free_threaded.py` — one PR.
- [ ] `benchmarks/conftest.py` with seven fixtures — one PR.
- [ ] Rewrite `benchmarks/test_bench_for_loop.py` to follow authoring contract — folded into `parallel.cpp` PR.
- [ ] `CMakePresets.json` with `profile` preset — one PR.
- [ ] `scripts/run_bench_local.sh` + `benchmarks/README.md` — one PR.
- [ ] `test_bench_thread_scaling.py`, `test_bench_free_threading.py`, `test_bench_cold_start.py` — one PR each after primary benchmark PRs land.

### 6.7 Out of scope for v1 (Phase 1+)

- `pyperf` multi-process isolation runs.
- `asv` continuous tracking + HTML dashboard.
- `bench-smoke` and `bench-full` GitHub Actions workflows.
- Dedicated physical runner with `pyperf system tune`.
- Macro/end-to-end and memory-shape suites.
- `memray` / `py-spy` artifact uploads on tagged releases.
- `TARGETS.md` numeric budgets.
- Regression thresholds and CI gating.

---

## 7. Open questions the implementation plan must answer

Deferred to the writing-plans stage; noted here so they are not lost:

- Exact representation of `PolicyToken` on the Python side — a dataclass instance, a packed tuple, or a small class hierarchy? Trade-off is ergonomics of `par.with_(...)` composition vs dispatch cost.
- Serialization strategy for `PolicyToken` across the nanobind boundary — pass as struct-by-value, bind as an opaque handle, or unpack into primitive args? Probably struct-by-value; decide at plan stage.
- Kernel dispatch layer — typed `nb::overload_cast` vs a single `nb::object`-taking shim that dispatches via dtype introspection. Matters for error message quality.
- `add_done_callback` execution thread — always on HPX worker, or should we offer an opt-in to post back to the submitting thread via a thread-local queue? Affects asyncio bridge performance.
- Whether `hpyx.aio`'s async parallel-algorithm helpers should accept any policy or auto-append `task` — ergonomics call.
- Cold-start micro-benchmark implementation given the cannot-restart constraint — pytest-xdist per-subprocess, or an explicit subprocess harness.
- Whether `HPXExecutor.shutdown(wait=True)` should block on pending tasks from this executor handle or return immediately (both are `concurrent.futures.Executor`-compliant; the former matches `ThreadPoolExecutor` behavior).
- Exact behavior of `HPXExecutor.map(chunksize=N)` when HPX already has its own chunk sizing — should chunksize be ignored, used to group submissions, or passed through as `static_chunk_size`?
- Packaging story for the `hpx-dev` plugin skills documented with v1 — do we continue to maintain them alongside this spec, or roll them into the contributor guide?
