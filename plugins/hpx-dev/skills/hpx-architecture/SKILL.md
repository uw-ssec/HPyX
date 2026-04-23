---
name: hpx-architecture
description: Maps HPX C++ library components to their `vendor/hpx/` source locations, tracks which HPX features are already wrapped in HPyX, and identifies unwrapped candidates for new Python bindings. Use when the user asks about "HPX architecture", "HPX components", "HPX APIs", "what HPX features to wrap", "HPX parallel algorithms", "HPX futures", "HPX distributed computing", "HPX AGAS", "HPX performance counters", "HPX execution policies", or mentions "vendor/hpx", "HPX source", or asks what parts of HPX are available for binding.
---

# HPX Architecture Knowledge

## HPyX-Specific Context

The HPX source lives at `vendor/hpx/` as a git submodule. Key source directories:

- `vendor/hpx/libs/` — Core library modules (algorithms, futures, threading, etc.)
- `vendor/hpx/components/` — Runtime components (performance counters, iostreams)
- `vendor/hpx/examples/` — C++ usage examples
- `vendor/hpx/docs/sphinx/` — Official documentation

## Currently Wrapped in HPyX

The following HPX features have Python bindings in `src/`:

| HPX Feature | C++ Source | Python API |
|---|---|---|
| `hpx::async` (deferred) | `src/futures.cpp` | `hpyx.futures.submit()` |
| `hpx::future<T>` | `src/bind.cpp` | `hpyx._core.future` |
| `hpx::experimental::for_loop` | `src/algorithms.cpp` | `hpyx.multiprocessing.for_loop()` |
| `hpx::transform_reduce` (dot product) | `src/algorithms.cpp` | `hpyx._core.dot1d()` |
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

### Future Work — Distributed Computing

- `hpx::find_here()` / `hpx::find_all_localities()` — Locality discovery
- `hpx::components` — Distributed objects
- `hpx::actions` — Remote procedure calls
- AGAS (Active Global Address Space) — Distributed naming
- Parcelport — Network transport layer
- TCP/MPI parcelports for inter-node communication

### Utility — Performance Counters

- `hpx::performance_counters` — Runtime metrics
- Thread scheduling statistics
- Memory allocation tracking
- Network bandwidth monitoring

## Key HPX Headers

When adding new bindings, include the appropriate HPX headers:

```cpp
#include <hpx/algorithm.hpp>     // Parallel algorithms
#include <hpx/future.hpp>        // Futures
#include <hpx/numeric.hpp>       // Numeric algorithms
#include <hpx/execution.hpp>     // Execution policies
#include <hpx/hpx_start.hpp>     // Runtime management
#include <hpx/iostream.hpp>      // HPX I/O streams
#include <hpx/latch.hpp>         // Synchronization primitives
#include <hpx/version.hpp>       // Version info
```

## Execution Policy Model

HPX execution policies control how algorithms dispatch work:

```
seq          → Single thread, caller's thread
par          → HPX thread pool, parallel tasks
par_unseq    → Parallel + vectorization hints
task(policy) → Returns future<result> instead of blocking
```

When binding algorithms, always expose the `policy` parameter to Python to let users choose between sequential and parallel execution.

## Additional Resources

### Reference Files

For detailed HPX API documentation and component maps:
- **`references/hpx-api-map.md`** — Comprehensive map of HPX APIs organized by module with binding feasibility notes
- **`references/hpx-distributed.md`** — Detailed guide to HPX distributed computing features (AGAS, actions, components, parcelports)
