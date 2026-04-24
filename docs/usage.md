# HPyX Usage Guide

This guide provides comprehensive examples and usage patterns for HPyX, the Python bindings for the HPX C++ Parallelism Library. HPyX enables high-performance parallel computing in Python by leveraging HPX's advanced parallel execution capabilities.

!!! note "v1 API"
    HPyX v1 introduces a new runtime lifecycle — the HPX runtime now **auto-initializes** on first use. `hpyx.init()` replaces the old `HPXRuntime(...)` kwargs pattern.
    See [Runtime Management](#runtime-management) for the full details.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Runtime Management](#runtime-management)
3. [Configuration](#configuration)
4. [Diagnostics](#diagnostics)
5. [Asynchronous Programming with Futures](#asynchronous-programming-with-futures)
6. [Parallel Processing with for_loop](#parallel-processing-with-for_loop)
7. [Working with NumPy](#working-with-numpy)
8. [Error Handling](#error-handling)
9. [Performance Considerations](#performance-considerations)
10. [Best Practices](#best-practices)

## Getting Started

HPyX provides a clean Python interface to HPX's parallel computing capabilities. The main components are:

- `hpyx.init()` / `hpyx.shutdown()` / `hpyx.is_running()` — runtime lifecycle
- `HPXRuntime` — optional context manager for explicit scoping
- `hpyx.config` — environment-variable-driven configuration
- `hpyx.debug` — worker thread diagnostics
- `hpyx.futures.submit` — submit functions for asynchronous execution
- `hpyx.multiprocessing.for_loop` — parallel iteration over collections

### Basic Import

```python
import hpyx
from hpyx.futures import submit
from hpyx.multiprocessing import for_loop
```

## Runtime Management

### Auto-initialization (recommended)

In v1, HPyX **auto-initializes** the HPX runtime the first time any API that needs it is called. You do not need to call `hpyx.init()` explicitly unless you want to configure thread count before the first use.

```python
from hpyx.futures import submit

# Runtime starts automatically on first submit
future = submit(lambda: 42)
print(future.get())  # 42
```

### Explicit initialization

Call `hpyx.init()` before any parallel work if you want to control the thread count or pass custom HPX config strings:

```python
import hpyx

hpyx.init(os_threads=8)          # use 8 HPX worker threads
# or with extra HPX cfg strings:
hpyx.init(os_threads=4, cfg=["hpx.stacks.small_size=0x20000"])
```

`hpyx.init()` is **idempotent** — calling it multiple times with the same arguments is a no-op. Calling it with *different* arguments after the runtime is already running raises `RuntimeError` (HPX cannot be reconfigured in-process).

```python
hpyx.init(os_threads=4)
hpyx.init(os_threads=4)  # OK — no-op
hpyx.init(os_threads=8)  # RuntimeError: already started with different config
```

### Querying runtime state

```python
import hpyx

print(hpyx.is_running())  # True once started, False before first init
```

### Shutdown

HPyX registers an `atexit` handler on first start, so **you normally do not need to call `hpyx.shutdown()` explicitly**. It will run automatically when the Python process exits.

If you need to force an early shutdown (e.g., in a test harness):

```python
hpyx.shutdown()
# HPX cannot restart within the same process after shutdown
```

!!! warning "HPX cannot restart"
    Once `hpyx.shutdown()` is called (or the atexit handler fires), calling `hpyx.init()` again in the same process raises `RuntimeError`. Plan your process lifecycle accordingly.

### HPXRuntime context manager

`HPXRuntime` is an optional convenience wrapper. It calls `hpyx.init()` on `__enter__` and is a no-op on `__exit__` — it does **not** shut the runtime down when the `with` block exits (HPX cannot restart).

```python
from hpyx import HPXRuntime

with HPXRuntime(os_threads=4):
    # runtime is guaranteed to be running here
    from hpyx.futures import submit
    future = submit(lambda: "hello from HPX")
    print(future.get())

# runtime is still running here — atexit owns shutdown
print(hpyx.is_running())  # True
```

`HPXRuntime` is most useful when you want to be explicit about the startup point in a script or test, or for backward compatibility with v0.x code.

## Configuration

### Environment variables

HPyX reads configuration from environment variables at runtime startup. These take effect when `hpyx.init()` (or auto-init) first runs.

| Variable | Type | Default | Description |
|---|---|---|---|
| `HPYX_OS_THREADS` | int | `None` (HPX default) | Number of HPX worker OS threads |
| `HPYX_CFG` | str | `""` | Semicolon-separated HPX config strings |
| `HPYX_AUTOINIT` | bool | `true` | Set to `0`/`false` to disable auto-init |
| `HPYX_TRACE_PATH` | str | `None` | Path for JSONL trace output (v1.x) |

**Precedence:** explicit `hpyx.init()` kwargs > environment variables > built-in defaults.

```bash
# Run with 16 HPX threads
HPYX_OS_THREADS=16 python my_script.py

# Disable auto-init (require explicit hpyx.init() call)
HPYX_AUTOINIT=0 python my_script.py

# Pass HPX config strings
HPYX_CFG="hpx.stacks.small_size=0x20000;hpx.os_threads!=4" python my_script.py
```

### Reading config programmatically

```python
from hpyx import config

# See all defaults
print(config.DEFAULTS)
# {'os_threads': None, 'cfg': [], 'autoinit': True, 'trace_path': None}

# Read current env-var layer
cfg = config.from_env()
print(cfg["os_threads"])   # e.g. 8 if HPYX_OS_THREADS=8 is set, else None
```

### Disabling auto-init

Set `HPYX_AUTOINIT=0` to require an explicit `hpyx.init()` call before any HPyX API is used. This is useful in library code where you want the caller to control when the runtime starts.

```python
# With HPYX_AUTOINIT=0 in the environment:
import hpyx
from hpyx.futures import submit

# This would raise RuntimeError without an explicit init:
hpyx.init(os_threads=4)  # must come first

future = submit(lambda: 42)
print(future.get())
```

## Diagnostics

The `hpyx.debug` module exposes worker thread introspection.

```python
import hpyx
from hpyx import debug

hpyx.init(os_threads=4)

# Number of HPX worker OS threads in the default pool
print(debug.get_num_worker_threads())  # 4

# Thread id of the calling thread (-1 if not an HPX worker thread)
print(debug.get_worker_thread_id())    # -1 (called from main Python thread)
```

`get_worker_thread_id()` returns `-1` when called from a non-HPX thread (e.g., the Python main thread or a `threading.Thread`). When called from within an HPX task it returns the 0-based worker index.

!!! note "Tracing"
    `debug.enable_tracing(path)` and `debug.disable_tracing()` are stubbed in v1.0 and raise `NotImplementedError`. Full JSONL-output tracing ships in v1.x (Plan 4).

## Asynchronous Programming with Futures

HPyX provides futures-based asynchronous programming through the `submit` function, which allows you to execute functions asynchronously and retrieve results later.

### Basic Future Usage

```python
from hpyx.futures import submit

def add(a, b):
    return a + b

# Runtime auto-initializes on first submit
future = submit(add, 5, 3)
result = future.get()
print(f"5 + 3 = {result}")  # Output: 5 + 3 = 8
```

### Multiple Futures

```python
from hpyx.futures import submit

def square(x):
    return x * x

futures = [submit(square, i) for i in range(5)]
results = [f.get() for f in futures]
print(f"Squares: {results}")  # Output: Squares: [0, 1, 4, 9, 16]
```

### Complex Data Types

```python
from hpyx.futures import submit

def process_data(data_dict):
    return {
        'sum': sum(data_dict['values']),
        'count': len(data_dict['values']),
        'avg': sum(data_dict['values']) / len(data_dict['values'])
    }

input_data = {'values': [1, 2, 3, 4, 5]}
future = submit(process_data, input_data)
result = future.get()
print(f"Statistics: {result}")
# Output: Statistics: {'sum': 15, 'count': 5, 'avg': 3.0}
```

### Lambda Functions

```python
from hpyx.futures import submit

future = submit(lambda x: x ** 2 + 2 * x + 1, 5)
print(future.get())  # 36
```

## Parallel Processing with for_loop

The `for_loop` function provides parallel iteration over collections, applying a transformation function to each element in-place.

### Basic for_loop Usage

```python
from hpyx.multiprocessing import for_loop

def double(x):
    return x * 2

with HPXRuntime():
    data = [1, 2, 3, 4, 5]
    for_loop(double, data, "seq")  # Sequential execution
    print(f"Doubled: {data}")  # Output: Doubled: [2, 4, 6, 8, 10]
```

### Execution Policies

```python
from hpyx.multiprocessing import for_loop

def increment(x):
    return x + 1

with HPXRuntime():
    data = list(range(100))
    
    # Sequential execution
    for_loop(increment, data, "seq")
    
    # Parallel execution (when available)
    # for_loop(increment, data, "par")
```

### String Processing

```python
from hpyx.multiprocessing import for_loop

def to_uppercase(s):
    return s.upper()

with HPXRuntime():
    words = ["hello", "world", "python", "hpx"]
    for_loop(to_uppercase, words, "seq")
    print(f"Uppercase: {words}")
    # Output: Uppercase: ['HELLO', 'WORLD', 'PYTHON', 'HPX']
```

### Complex Object Transformation

```python
from hpyx.multiprocessing import for_loop

def update_record(record):
    return {
        'id': record['id'],
        'value': record['value'] * 1.1,  # Apply 10% increase
        'processed': True
    }

with HPXRuntime():
    records = [
        {'id': 1, 'value': 100},
        {'id': 2, 'value': 200},
        {'id': 3, 'value': 300}
    ]
    
    for_loop(update_record, records, "seq")
    print(f"Updated records: {records}")
```

### Mathematical Operations

```python
from hpyx.multiprocessing import for_loop
import math

def apply_formula(x):
    # Complex mathematical transformation
    return math.sqrt(x + 1) * 2

with HPXRuntime():
    data = [float(i) for i in range(10)]
    for_loop(apply_formula, data, "seq")
    print(f"Transformed: {[round(x, 2) for x in data]}")
```

## Working with NumPy

HPyX integrates well with NumPy arrays, enabling high-performance numerical computing.

### NumPy Array Processing with submit

```python
import numpy as np
from hpyx.futures import submit

def array_statistics(arr):
    return {
        'mean': np.mean(arr),
        'std': np.std(arr),
        'min': np.min(arr),
        'max': np.max(arr),
        'sum': np.sum(arr)
    }

with HPXRuntime():
    # Create a random array
    data = np.random.random(10000)
    
    # Process asynchronously
    future = submit(array_statistics, data)
    stats = future.get()
    
    print(f"Array statistics: {stats}")
```

### Matrix Operations

```python
import numpy as np
from hpyx.futures import submit

def matrix_multiply(a, b):
    return np.dot(a, b)

def matrix_eigenvalues(matrix):
    return np.linalg.eigvals(matrix)

with HPXRuntime():
    # Create matrices
    A = np.random.random((100, 100))
    B = np.random.random((100, 100))
    
    # Asynchronous matrix multiplication
    mult_future = submit(matrix_multiply, A, B)
    
    # Asynchronous eigenvalue computation
    eigen_future = submit(matrix_eigenvalues, A)
    
    # Get results
    product = mult_future.get()
    eigenvals = eigen_future.get()
    
    print(f"Product shape: {product.shape}")
    print(f"Number of eigenvalues: {len(eigenvals)}")
```

### NumPy with for_loop

```python
import numpy as np
from hpyx.multiprocessing import for_loop

def normalize_element(x):
    # Simple normalization: scale to [0, 1]
    return (x - x.min()) / (x.max() - x.min()) if x.max() != x.min() else x

with HPXRuntime():
    # Create array
    arr = np.array([1.5, 2.7, 3.1, 4.9, 0.8])
    
    # Apply transformation function
    def scale_up(x):
        return x * 10
    
    for_loop(scale_up, arr, "seq")
    print(f"Scaled array: {arr}")
```

### Large Array Processing

```python
import numpy as np
from hpyx.futures import submit

def process_large_array(size):
    # Create and process a large array
    arr = np.random.normal(0, 1, size)
    
    # Apply complex transformations
    normalized = (arr - np.mean(arr)) / np.std(arr)
    processed = np.exp(-0.5 * normalized**2)  # Gaussian-like transformation
    
    return {
        'original_size': size,
        'processed_mean': np.mean(processed),
        'processed_std': np.std(processed),
        'nonzero_count': np.count_nonzero(processed > 0.1)
    }

with HPXRuntime():
    # Process multiple large arrays concurrently
    sizes = [100000, 200000, 300000]
    futures = []
    
    for size in sizes:
        future = submit(process_large_array, size)
        futures.append((size, future))
    
    # Collect results
    for size, future in futures:
        result = future.get()
        print(f"Array size {size}: {result}")
```

## Error Handling

Proper error handling is essential when working with asynchronous operations and parallel processing.

### Exception Handling with Futures

```python
from hpyx.futures import submit

def risky_operation(x):
    if x < 0:
        raise ValueError("Negative values not allowed")
    return 1 / x

with HPXRuntime():
    # Submit operations that might fail
    futures = []
    for value in [2, 0, -1, 4]:
        future = submit(risky_operation, value)
        futures.append((value, future))
    
    # Handle results and exceptions
    for value, future in futures:
        try:
            result = future.get()
            print(f"f({value}) = {result}")
        except ZeroDivisionError:
            print(f"f({value}): Division by zero error")
        except ValueError as e:
            print(f"f({value}): {e}")
        except Exception as e:
            print(f"f({value}): Unexpected error: {e}")
```

### Runtime Initialization Errors

```python
from hpyx.futures import submit

def safe_computation():
    try:
        with HPXRuntime():
            future = submit(lambda: "Success!")
            return future.get()
    except Exception as e:
        print(f"Runtime initialization failed: {e}")
        return None

result = safe_computation()
if result:
    print(f"Computation result: {result}")
```

### Robust Error Handling Pattern

```python
from hpyx.futures import submit
import traceback

def robust_parallel_computation(data_list):
    """
    Process a list of data items with robust error handling.
    """
    results = []
    errors = []
    
    def process_item(item):
        # Simulate processing that might fail
        if item < 0:
            raise ValueError(f"Negative value: {item}")
        return item ** 2
    
    try:
        with HPXRuntime():
            futures = []
            
            # Submit all tasks
            for i, item in enumerate(data_list):
                future = submit(process_item, item)
                futures.append((i, item, future))
            
            # Collect results
            for i, item, future in futures:
                try:
                    result = future.get()
                    results.append((i, item, result))
                except Exception as e:
                    error_info = {
                        'index': i,
                        'item': item,
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }
                    errors.append(error_info)
    
    except Exception as e:
        print(f"Runtime error: {e}")
        return None, [{'error': str(e), 'traceback': traceback.format_exc()}]
    
    return results, errors

# Example usage
data = [1, 2, -3, 4, 5, -6]
results, errors = robust_parallel_computation(data)

print("Successful results:")
for i, item, result in results:
    print(f"  [{i}] {item} -> {result}")

print("\nErrors:")
for error in errors:
    print(f"  [{error['index']}] {error['item']}: {error['error']}")
```

## Performance Considerations

### Choosing Between submit and for_loop

- Use `submit` for:
  - Independent tasks that can run asynchronously
  - Tasks with different execution times
  - When you need to handle results individually
  - Complex computations that benefit from parallelization

- Use `for_loop` for:
  - Uniform operations on collections
  - In-place transformations
  - Simple element-wise operations
  - When all operations are similar in complexity

### Optimal Threading Configuration

```python
import time
import multiprocessing

def cpu_bound_task(n):
    return sum(i * i for i in range(n))

def benchmark_threading(thread_counts, task_size=100000):
    """Benchmark different thread configurations."""
    results = {}
    
    for threads in thread_counts:
        print(f"Testing with {threads} threads...")
        
        start_time = time.time()
        
        # Use string for "auto", integer for specific count
        thread_config = "auto" if threads == "auto" else threads
        
        with HPXRuntime(os_threads=thread_config):
            from hpyx.futures import submit
            
            # Submit multiple tasks
            futures = []
            for i in range(10):
                future = submit(cpu_bound_task, task_size)
                futures.append(future)
            
            # Wait for completion
            for future in futures:
                future.get()
        
        elapsed = time.time() - start_time
        results[threads] = elapsed
        print(f"  Completed in {elapsed:.2f} seconds")
    
    return results

# Benchmark different configurations
thread_configs = ["auto", 1, 2, 4, multiprocessing.cpu_count()]
results = benchmark_threading(thread_configs)

print("\nPerformance Summary:")
for threads, time_taken in results.items():
    print(f"  {threads} threads: {time_taken:.2f}s")
```

### Memory-Efficient Processing

```python
import numpy as np
from hpyx.futures import submit

def process_chunk(chunk_data):
    """Process a chunk of data efficiently."""
    # Perform in-place operations when possible
    result = np.square(chunk_data, out=chunk_data)
    return np.sum(result)

def memory_efficient_processing(total_size, chunk_size=10000):
    """Process large datasets in chunks to manage memory usage."""
    
    # Generate data in chunks
    chunk_futures = []
    
    for start in range(0, total_size, chunk_size):
        end = min(start + chunk_size, total_size)
        chunk = np.random.random(end - start)
        
        future = submit(process_chunk, chunk)
        chunk_futures.append(future)
    
    # Collect results
    total_sum = 0
    for future in chunk_futures:
        chunk_sum = future.get()
        total_sum += chunk_sum
    
    return total_sum

# Process 1 million elements in chunks
result = memory_efficient_processing(1000000, chunk_size=50000)
print(f"Total sum: {result}")
```

## Best Practices

### 1. Always Use Context Managers

```python
# Good: Proper resource management
with HPXRuntime():
    # Your parallel code here
    pass

# Avoid: Manual runtime management (easy to forget cleanup)
```

### 2. Handle Exceptions Gracefully

```python
from hpyx.futures import submit

def reliable_computation(data):
    try:
        with HPXRuntime():
            future = submit(your_function, data)
            return future.get()
    except Exception as e:
        print(f"Computation failed: {e}")
        return None
```

### 3. Use Appropriate Data Structures

```python
# Good: Use NumPy for numerical data
import numpy as np
data = np.array([1, 2, 3, 4, 5])

# Good: Use appropriate Python collections
from collections import deque
task_queue = deque()

# Avoid: Inefficient data structures for large datasets
# large_list = [0] * 1000000  # Consider NumPy instead
```

### 4. Batch Operations When Possible

```python
from hpyx.futures import submit

def batch_processing(items, batch_size=100):
    """Process items in batches for better efficiency."""
    
    def process_batch(batch):
        return [item * 2 for item in batch]
    
    futures = []
    
    # Create batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        future = submit(process_batch, batch)
        futures.append(future)
    
    # Collect results
    results = []
    for future in futures:
        batch_result = future.get()
        results.extend(batch_result)
    
    return results

# Process large list efficiently
large_list = list(range(10000))
processed = batch_processing(large_list, batch_size=500)
```

### 5. Profile and Measure Performance

```python
import time
from hpyx.futures import submit

def measure_performance(func, *args, **kwargs):
    """Measure execution time of a function."""
    start_time = time.time()
    result = func(*args, **kwargs)
    elapsed = time.time() - start_time
    return result, elapsed

def parallel_computation(n):
    future = submit(lambda: sum(range(n)))
    return future.get()

def sequential_computation(n):
    return sum(range(n))

# Compare performance
n = 1000000

parallel_result, parallel_time = measure_performance(parallel_computation, n)
sequential_result, sequential_time = measure_performance(sequential_computation, n)

print(f"Parallel: {parallel_result} in {parallel_time:.4f}s")
print(f"Sequential: {sequential_result} in {sequential_time:.4f}s")
print(f"Speedup: {sequential_time / parallel_time:.2f}x")
```

### 6. Design for Scalability

```python
from hpyx.futures import submit
import multiprocessing

def scalable_computation(data, max_workers=None):
    """Design computation to scale with available resources."""
    
    if max_workers is None:
        max_workers = multiprocessing.cpu_count()
    
    chunk_size = max(1, len(data) // max_workers)
    
    def process_chunk(chunk):
        return sum(x * x for x in chunk)
    
    futures = []
    
    # Divide work into chunks
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        future = submit(process_chunk, chunk)
        futures.append(future)
    
    # Combine results
    total = sum(future.get() for future in futures)
    return total

# Automatically scale to available cores
data = list(range(100000))
result = scalable_computation(data)
print(f"Result: {result}")
```

This usage guide provides a comprehensive overview of HPyX capabilities and patterns. For more advanced use cases and the latest API updates, refer to the source code and test files in the HPyX repository.
