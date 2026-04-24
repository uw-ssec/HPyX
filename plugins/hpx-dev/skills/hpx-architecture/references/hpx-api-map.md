# HPX API Map for Binding Development

Comprehensive map of HPX APIs organized by module, with binding feasibility notes for HPyX. Header paths below refer to locations under `vendor/hpx/libs/{core,full}/<module>/include/hpx/...`.

## Module Quick-Reference

The 30 modules most relevant to binding work:

| Module | Path | Purpose |
|---|---|---|
| `algorithms` | `libs/core/algorithms/` | `for_loop`, `transform`, `sort`, `reduce`, `transform_reduce` |
| `executors` | `libs/core/executors/` | Execution policies, executors, `dataflow` |
| `futures` | `libs/core/futures/` | `hpx::future<T>`, `hpx::shared_future<T>`, `hpx::promise<T>` |
| `async_local` | `libs/core/async_local/` | `hpx::async`, `hpx::sync` |
| `async_base` | `libs/core/async_base/` | `hpx::launch` tags (async, deferred, fork, sync) |
| `async_combinators` | `libs/core/async_combinators/` | `when_all`, `when_any`, `when_some`, `wait_all` |
| `init_runtime` (full) | `libs/full/init_runtime/` | `hpx::init`, `hpx::start`, `hpx::stop`, `hpx::finalize` |
| `init_runtime_local` | `libs/core/init_runtime_local/` | Local-only variant of init/start |
| `runtime_local` | `libs/core/runtime_local/` | `get_os_thread_count`, `run_as_hpx_thread`, `run_as_os_thread` |
| `schedulers` | `libs/core/schedulers/` | `local_priority_queue_scheduler`, etc. |
| `synchronization` | `libs/core/synchronization/` | `mutex`, `condition_variable`, `latch`, `barrier`, `spinlock`, semaphores |
| `lcos_local` | `libs/core/lcos_local/` | Local channels (`hpx::lcos::local::channel<T>`) |
| `resource_partitioner` | `libs/core/resource_partitioner/` | Maps CPUs to named thread pools |
| `functional` | `libs/core/functional/` | `hpx::function<Sig>`, `hpx::bind_front` |
| `errors` | `libs/core/errors/` | `hpx::exception`, `hpx::error_code` |
| `topology` | `libs/core/topology/` | CPU topology via hwloc |
| `version` | `libs/core/version/` | `hpx::complete_version()` |

## Parallel Algorithms (`<hpx/algorithm.hpp>`, `<hpx/numeric.hpp>`)

All algorithms support execution policies: `seq`, `par`, `par_unseq`, `task`. Task variants return `hpx::future<result>` rather than the bare result.

**Note**: `hpx::experimental::for_loop` lives in the `hpx::experimental` namespace (not top-level `hpx`). Variants: `for_loop_strided`, `for_loop_n`, `for_loop_n_strided`.

### Sorting & Ordering
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::sort` | `<hpx/algorithm.hpp>` | Medium | Needs comparison callable, GIL for Python comparator |
| `hpx::stable_sort` | `<hpx/algorithm.hpp>` | Medium | Same as sort |
| `hpx::partial_sort` | `<hpx/algorithm.hpp>` | Medium | Needs nth element parameter |
| `hpx::is_sorted` | `<hpx/algorithm.hpp>` | Low | Returns bool, straightforward |

### Searching
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::find` | `<hpx/algorithm.hpp>` | Low | Returns iterator → index in Python |
| `hpx::find_if` | `<hpx/algorithm.hpp>` | Medium | Needs predicate callable, GIL |
| `hpx::count` | `<hpx/algorithm.hpp>` | Low | Returns count, straightforward |
| `hpx::count_if` | `<hpx/algorithm.hpp>` | Medium | Needs predicate callable |
| `hpx::any_of` / `all_of` / `none_of` | `<hpx/algorithm.hpp>` | Medium | Predicate callable |

### Transformations
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::for_each` | `<hpx/algorithm.hpp>` | Medium | Similar to existing for_loop |
| `hpx::transform` | `<hpx/algorithm.hpp>` | Medium | Output range needed |
| `hpx::copy` / `copy_if` | `<hpx/algorithm.hpp>` | Low-Medium | Iterator-based |
| `hpx::fill` | `<hpx/algorithm.hpp>` | Low | Simple value fill |
| `hpx::generate` | `<hpx/algorithm.hpp>` | Medium | Generator callable |
| `hpx::replace` / `replace_if` | `<hpx/algorithm.hpp>` | Low-Medium | In-place modification |
| `hpx::reverse` | `<hpx/algorithm.hpp>` | Low | In-place |
| `hpx::rotate` | `<hpx/algorithm.hpp>` | Low | In-place |
| `hpx::unique` | `<hpx/algorithm.hpp>` | Medium | Returns new end iterator |

### Reductions
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::reduce` | `<hpx/numeric.hpp>` | Low-Medium | Binary op callable |
| `hpx::transform_reduce` | `<hpx/numeric.hpp>` | Medium | Partially wrapped as dot1d |
| `hpx::inclusive_scan` | `<hpx/numeric.hpp>` | Medium | Output range needed |
| `hpx::exclusive_scan` | `<hpx/numeric.hpp>` | Medium | Output range + init value |
| `hpx::transform_inclusive_scan` | `<hpx/numeric.hpp>` | High | Fused operation |
| `hpx::transform_exclusive_scan` | `<hpx/numeric.hpp>` | High | Fused operation |

## Futures & Async (`<hpx/future.hpp>`)

### Future Combinators
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::when_all` | `<hpx/future.hpp>` | Medium | Takes vector of futures, returns future of vector |
| `hpx::when_any` | `<hpx/future.hpp>` | Medium | Returns first completed future |
| `hpx::when_each` | `<hpx/future.hpp>` | High | Callback for each completion |
| `hpx::when_some` | `<hpx/future.hpp>` | High | Wait for N completions |
| `hpx::dataflow` | `<hpx/future.hpp>` | High | Dataflow graph execution |
| `hpx::make_ready_future` | `<hpx/future.hpp>` | Low | Creates pre-completed future |

### Async Variants
| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::async` (async launch) | `<hpx/future.hpp>` | Medium | True parallel execution, complex GIL |
| `hpx::async` (deferred launch) | `<hpx/future.hpp>` | Low | Already wrapped |
| `hpx::async` (fork launch) | `<hpx/future.hpp>` | Medium | Child-stealing, complex |

## Synchronization (`libs/core/synchronization/`)

| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::latch` | `hpx/synchronization/latch.hpp` | Medium | C++20 `std::latch` equivalent |
| `hpx::barrier<F>` | `hpx/synchronization/barrier.hpp` | Medium | Reusable barrier |
| `hpx::mutex` | `hpx/synchronization/mutex.hpp` | Medium | Yields HPX thread on contention |
| `hpx::recursive_mutex` | `hpx/synchronization/recursive_mutex.hpp` | Medium | Re-entrant variant |
| `hpx::shared_mutex` | `hpx/synchronization/shared_mutex.hpp` | Medium | Reader-writer lock |
| `hpx::condition_variable` | `hpx/synchronization/condition_variable.hpp` | High | Requires `hpx::mutex` |
| `hpx::spinlock` | `hpx/synchronization/spinlock.hpp` | High | **Busy-wait** — does NOT yield HPX thread; only short critical sections |
| `hpx::counting_semaphore<N>` | `hpx/synchronization/counting_semaphore.hpp` | Medium | C++20 equivalent |
| `hpx::binary_semaphore` | `hpx/synchronization/binary_semaphore.hpp` | Medium | Convenience alias |
| `hpx::lcos::local::channel<T>` | `hpx/lcos_local/channel.hpp` | High | SPSC/MPSC/MPMC channels |

## Execution Policies & Executors (`libs/core/executors/`)

Policies live in `libs/core/executors/include/hpx/executors/execution_policy.hpp`.

| API | Binding Feasibility | Notes |
|---|---|---|
| `hpx::execution::seq` | Low | Sequential, `sequenced_executor` |
| `hpx::execution::par` | Low | Parallel, `parallel_executor` (HPX thread pool) |
| `hpx::execution::par_unseq` | Low | Parallel + SIMD hints |
| `hpx::execution::unseq` | Low | SIMD only, single thread |
| `hpx::execution::task` (tag) | Medium | Append to par/seq: `par(task)` → algorithms return `hpx::future<result>` |
| `hpx::execution::non_task` (tag) | Low | Strips the task tag |

**Executor types** (`libs/core/executors/include/hpx/executors/`):

| Executor | Header | Notes |
|---|---|---|
| `parallel_executor` | `parallel_executor.hpp` | Default for `par` |
| `sequenced_executor` | `sequenced_executor.hpp` | Default for `seq`; runs in calling thread |
| `fork_join_executor` | `fork_join_executor.hpp` | Reusable threads; low-overhead bulk work |
| `thread_pool_executor` | `thread_pool_executor.hpp` | Wraps a specific `hpx::thread_pool_base` |
| `limiting_executor<E>` | `limiting_executor.hpp` | Task-count limiter |
| `annotating_executor<E>` | `annotating_executor.hpp` | Task names for profiling |

Bind an executor to a policy: `hpx::execution::par.on(my_executor)`.

**Chunk size parameters** (`libs/core/execution/include/hpx/execution/executors/`): `static_chunk_size(n)`, `dynamic_chunk_size(n)`, `auto_chunk_size()`, `guided_chunk_size()`. Applied via `par.with(hpx::execution::static_chunk_size(1000))`.

## Distributed Computing

| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::find_here()` | `<hpx/runtime.hpp>` | Low | Returns locality ID |
| `hpx::find_all_localities()` | `<hpx/runtime.hpp>` | Low | Returns locality IDs |
| `hpx::components` | Various | High | Distributed objects, complex |
| `hpx::actions` | Various | High | Remote procedure calls |
| AGAS | Various | Very High | Active Global Address Space |
| Parcelport (TCP) | Various | High | Network transport |
| Parcelport (MPI) | Various | High | MPI transport |

## Performance Counters

| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::performance_counters::get_counter` | Various | Medium | Query runtime metrics |
| Thread idle rates | Various | Medium | Scheduling efficiency |
| Queue lengths | Various | Medium | Work distribution |
| Memory usage | Various | Medium | Allocation tracking |

## Binding Feasibility Legend

- **Low**: Straightforward binding, minimal GIL concerns, direct type mapping
- **Medium**: Requires GIL management for callbacks, iterator→index translation, or output buffer management
- **High**: Complex template metaprogramming, lifetime management, or distributed state
- **Very High**: Requires significant design work, may need new architectural patterns
