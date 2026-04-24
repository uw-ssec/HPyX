---
name: hpx-architecture
description: Maps HPX C++ library components to their `vendor/hpx/` source locations, tracks which HPX features are already wrapped in HPyX, and identifies unwrapped candidates for new Python bindings. Use when the user asks about "HPX architecture", "HPX components", "HPX APIs", "what HPX features to wrap", "HPX parallel algorithms", "HPX futures", "HPX distributed computing", "HPX AGAS", "HPX performance counters", "HPX execution policies", or mentions "vendor/hpx", "HPX source", or asks what parts of HPX are available for binding.
---

# HPX Architecture Knowledge

## HPyX-Specific Context

The HPX source lives at `vendor/hpx/` as a git submodule (HPX 2.0.0, tag 20250630). Key source directories:

- `vendor/hpx/libs/core/` — 84 modules — shared-memory, single-process functionality. This is what HPyX needs.
- `vendor/hpx/libs/full/` — 36 modules — distributed runtime, AGAS, parcelports, actions. HPyX links against it only for `init_runtime` and aggregator headers.
- `vendor/hpx/components/` — Runtime components (performance counters, iostreams)
- `vendor/hpx/examples/` — C++ usage examples
- `vendor/hpx/docs/sphinx/` — Official documentation

## Core vs Full Split

Understanding this split is critical for binding work. Headers and libraries live in two parallel hierarchies:

| Layer | Path | Used by HPyX |
|---|---|---|
| `libs/core/` | Shared-memory primitives: futures, algorithms, executors, synchronization, schedulers | All binding code should prefer these headers |
| `libs/full/` | Distributed runtime: AGAS, parcelports, actions, components, collectives | Only `libs/full/init_runtime/` (for `hpx::start`/`hpx::stop`) |

The build flag `HPX_WITH_NETWORKING=FALSE` (set by HPyX's `scripts/build.sh`) disables parcelports. The conda-forge `hpx>=1.11.0` package has networking ON but HPyX disables TCP at runtime via `hpx.parcel.tcp.enable!=0`.

**Do not attempt to bind:** AGAS, `hpx::id_type`, components, actions, parcels, `find_all_localities()`. These require the full distributed runtime and serialization infrastructure.

## Runtime Model

HPyX uses the non-blocking start pattern (`src/init_hpx.cpp`):

| Function | Purpose | Context |
|---|---|---|
| `hpx::start(f, argc, argv, params)` | Non-blocking: starts runtime on background threads, schedules `f` as HPX task | Called from Python thread |
| `hpx::stop()` | Blocks until runtime drains and worker OS threads join | Called from Python thread (destructor) |
| `hpx::finalize()` | Signals shutdown | **Must be called from an HPX thread** (typically from the registered `hpx_main` function) |
| `hpx::suspend()` / `hpx::resume()` | Pause/unpause worker pools without stopping | Not currently exposed |

**Single-runtime constraint**: HPX can only have one active runtime per process. Once `hpx::stop()` returns, the runtime **cannot be restarted** in the same process. `HPXRuntime`/`HPXExecutor` instances are therefore single-use per process lifetime.

## Currently Wrapped in HPyX

The following HPX features have Python bindings in `src/`:

| HPX Feature | C++ Source | Python API |
|---|---|---|
| `hpx::async` (deferred only) | `src/futures.cpp` | `hpyx.futures.submit()` |
| `hpx::future<T>` | `src/bind.cpp` | `hpyx._core.future` |
| `hpx::experimental::for_loop` (note namespace) | `src/algorithms.cpp` | `hpyx.multiprocessing.for_loop()` |
| `hpx::transform_reduce` (dot product on `double*`) | `src/algorithms.cpp` | `hpyx._core.dot1d()` |
| Runtime init/shutdown | `src/init_hpx.cpp` | `hpyx._core.init_hpx_runtime()` / `stop_hpx_runtime()` |
| `hpx::get_num_worker_threads` | `src/bind.cpp` | `hpyx._core.get_num_worker_threads()` |

## Unwrapped HPX Features (Candidates for Binding)

### High Priority — Parallel Algorithms (`vendor/hpx/libs/core/algorithms/`)

- `hpx::for_each` — Apply function to range (parallel)
- `hpx::transform` — Transform range into output
- `hpx::reduce` — Parallel reduction
- `hpx::sort` / `hpx::stable_sort` — Parallel sorting
- `hpx::count` / `hpx::count_if` — Parallel counting
- `hpx::find` / `hpx::find_if` — Parallel search
- `hpx::copy` / `hpx::copy_if` — Parallel copy
- `hpx::fill` — Parallel fill
- `hpx::transform_reduce` — Fused transform + reduce (partially wrapped as `dot1d`)
- `hpx::inclusive_scan` / `hpx::exclusive_scan` — Prefix sums

### High Priority — Execution Policies

- `hpx::execution::seq` — Sequential (wrapped)
- `hpx::execution::par` — Parallel (partially wrapped)
- `hpx::execution::par_unseq` — Parallel unsequenced
- `hpx::execution::task` — Returns future instead of blocking
- Custom executors for thread pool control

### Medium Priority — Synchronization & Concurrency

- `hpx::latch` — Thread synchronization barrier
- `hpx::barrier` — Reusable barrier
- `hpx::mutex` / `hpx::shared_mutex` — Lightweight mutexes
- `hpx::when_all` / `hpx::when_any` — Future combinators
- `hpx::dataflow` — Dataflow-based task execution

### Utility — Performance Counters

`hpx::performance_counters` exposes runtime metrics (thread scheduling statistics, memory allocation tracking, queue lengths). Medium-feasibility binding target if runtime introspection becomes a priority.

For distributed-runtime features explicitly out of scope, see the "Core vs Full Split" section above and `references/hpx-distributed.md`.

## Key HPX Headers

When adding new bindings, include the appropriate HPX headers. The aggregator headers pull in most of what's needed:

```cpp
#include <hpx/algorithm.hpp>     // Parallel algorithms (libs/full/include → libs/core/algorithms)
#include <hpx/future.hpp>        // Futures + async_combinators
#include <hpx/numeric.hpp>       // Numeric algorithms (reduce, transform_reduce, scan)
#include <hpx/execution.hpp>     // Execution policies and executors
#include <hpx/hpx_start.hpp>     // hpx::start / hpx::stop (libs/full/init_runtime)
#include <hpx/hpx_finalize.hpp>  // hpx::finalize
#include <hpx/iostream.hpp>      // hpx::cout
#include <hpx/latch.hpp>         // Synchronization primitives
#include <hpx/version.hpp>       // Version info
```

For fine-grained dependencies, prefer specific headers under `libs/core/<module>/include/hpx/<module>/` rather than the catch-all `<hpx/hpx.hpp>` (faster compilation).

## Execution Policy Model

HPX execution policies control how algorithms dispatch work:

```
seq          → Single thread, caller's thread
par          → HPX thread pool, parallel tasks
par_unseq    → Parallel + vectorization hints
task(policy) → Returns future<result> instead of blocking
```

When binding algorithms, always expose the `policy` parameter to Python to let users choose between sequential and parallel execution.

## Adding a New Binding

At a high level:

1. Identify the HPX header in `libs/core/<module>/include/hpx/...` using the API map.
2. Write the Nanobind wrapper in `src/<feature>.cpp` + `src/<feature>.hpp`.
3. Register with `m.def(...)` in `src/bind.cpp` and add the source to `CMakeLists.txt`.
4. Validate: `pip install --no-build-isolation -ve .` → import the symbol → run `pixi run test`.

For the full step-by-step scaffolding workflow with concrete code examples, see the **add-binding** skill. For GIL rules that apply to any binding touching Python, see the **gil-management** skill.

## Additional Resources

### Reference Files

For detailed HPX API documentation and component maps:
- **`references/hpx-api-map.md`** — Comprehensive map of HPX APIs organized by module with binding feasibility notes
- **`references/hpx-distributed.md`** — Detailed guide to HPX distributed computing features (AGAS, actions, components, parcelports)
