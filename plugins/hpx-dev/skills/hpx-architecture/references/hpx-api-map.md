# HPX API Map for Binding Development

Comprehensive map of HPX APIs organized by module, with binding feasibility notes for HPyX.

## Parallel Algorithms (`<hpx/algorithm.hpp>`)

All algorithms support execution policies: `seq`, `par`, `par_unseq`, `task`.

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

## Synchronization (`<hpx/latch.hpp>`, `<hpx/barrier.hpp>`)

| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::latch` | `<hpx/latch.hpp>` | Medium | Count-down synchronization |
| `hpx::barrier` | `<hpx/barrier.hpp>` | Medium | Reusable barrier |
| `hpx::mutex` | `<hpx/mutex.hpp>` | Medium | Lightweight mutex |
| `hpx::shared_mutex` | `<hpx/shared_mutex.hpp>` | Medium | Reader-writer lock |
| `hpx::condition_variable` | `<hpx/condition_variable.hpp>` | High | Complex lifetime |

## Execution Policies & Executors (`<hpx/execution.hpp>`)

| API | Header | Binding Feasibility | Notes |
|---|---|---|---|
| `hpx::execution::seq` | `<hpx/execution.hpp>` | Low | Already used |
| `hpx::execution::par` | `<hpx/execution.hpp>` | Low | Already used |
| `hpx::execution::par_unseq` | `<hpx/execution.hpp>` | Low | Vectorization hint |
| `hpx::execution::task` | `<hpx/execution.hpp>` | Medium | Returns future |
| Custom executors | `<hpx/execution.hpp>` | High | Thread pool control |

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
