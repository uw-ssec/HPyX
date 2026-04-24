---
name: benchmarking
description: Generates `pytest-benchmark` scripts for HPyX bindings, runs HPX vs NumPy/pure-Python comparisons, measures thread scaling and binding overhead, and interprets timing results. Use when the user asks about "benchmarking", "performance testing", "pytest-benchmark", "benchmark HPX vs Python", "benchmark HPX vs NumPy", "measure binding overhead", "profile HPyX", "threadpoolctl", "benchmark scaling", "performance comparison", mentions the "benchmarks/" directory or "pixi run benchmark", or asks about performance characteristics of HPyX operations.
---

# HPyX Benchmarking

## Benchmark Infrastructure

HPyX uses pytest-benchmark for performance testing:

- **Location**: `benchmarks/` directory
- **Environment**: `benchmark-py313t` pixi environment
- **Dependencies**: `pytest-benchmark>=5.1.0`, `threadpoolctl>=3.6.0`
- **Run command**: `pixi run benchmark`

## Running Benchmarks

```bash
# Run all benchmarks
pixi run benchmark

# Run specific benchmarks by keyword
pixi run benchmark keyword_expression="dot1d"

# The underlying command (for reference):
pytest ./benchmarks \
    --benchmark-group-by=func \
    --benchmark-warmup=on \
    --benchmark-min-rounds=3 \
    --benchmark-time-unit=ms
```

### Useful pytest-benchmark Options

```bash
# Save results for comparison
pytest ./benchmarks --benchmark-save=baseline

# Compare against saved results
pytest ./benchmarks --benchmark-compare=baseline

# Generate JSON output
pytest ./benchmarks --benchmark-json=results.json

# Disable benchmarks (run tests only)
pytest ./benchmarks --benchmark-disable
```

## Benchmark Patterns

### Pattern 1: HPX vs NumPy Comparison

Compare HPyX bindings against NumPy equivalents — the primary benchmark pattern in this project.

```python
import numpy as np
import pytest
from hpyx.runtime import HPXRuntime
import hpyx

@pytest.mark.parametrize("size", [10_000_000, 50_000_000, 100_000_000])
def test_bench_hpx_operation(benchmark, size):
    """Benchmark HPX implementation."""
    rng = np.random.default_rng()
    data = rng.random(size)
    with HPXRuntime():
        _ = benchmark(hpyx._core.operation, data)

@pytest.mark.parametrize("size", [10_000_000, 50_000_000, 100_000_000])
def test_bench_numpy_operation(benchmark, size):
    """Benchmark NumPy equivalent."""
    rng = np.random.default_rng()
    data = rng.random(size)
    _ = benchmark(np.operation, data)
```

Reference: `benchmarks/test_bench_hpx_linalg.py`

### Pattern 2: Thread Scaling

Measure how performance scales with thread count:

```python
@pytest.mark.parametrize("threads", [1, 2, 4, 8])
@pytest.mark.parametrize("size", [1_000_000, 10_000_000])
def test_bench_scaling(benchmark, threads, size):
    """Benchmark thread scaling."""
    data = np.random.random(size)
    def run():
        with HPXRuntime(os_threads=threads):
            return hpyx._core.operation(data)
    benchmark(run)
```

### Pattern 3: Single-Thread Controlled Comparison

Use `threadpoolctl` to force single-threaded NumPy for fair comparison:

```python
from threadpoolctl import threadpool_limits

@pytest.mark.parametrize("size", [10_000_000, 50_000_000])
def test_bench_hpx_single_thread(benchmark, size):
    data = np.random.random(size)
    with HPXRuntime(os_threads=1):
        _ = benchmark(hpyx._core.operation, data)

@pytest.mark.parametrize("size", [10_000_000, 50_000_000])
def test_bench_numpy_single_thread(benchmark, size):
    data = np.random.random(size)
    with threadpool_limits(limits=1):
        _ = benchmark(np.operation, data)
```

Reference: `benchmarks/test_bench_hpx_linalg.py` (single-thread variants)

### Pattern 4: HPX vs Pure Python

Compare against pure Python loops to show binding overhead:

```python
@pytest.mark.parametrize("size", [100_000, 1_000_000])
def test_bench_hpx_for_loop(benchmark, size):
    arr = list(range(size))
    def run():
        with HPXRuntime():
            hpyx.multiprocessing.for_loop(lambda x: x * 2, arr, "seq")
    benchmark(run)

@pytest.mark.parametrize("size", [100_000, 1_000_000])
def test_bench_python_for_loop(benchmark, size):
    arr = list(range(size))
    def run():
        for i in range(len(arr)):
            arr[i] = arr[i] * 2
    benchmark(run)
```

### Pattern 5: Binding Overhead Measurement

Isolate the overhead of crossing the Python/C++ boundary:

```python
def test_bench_submit_overhead(benchmark):
    """Measure async submit overhead (trivial function)."""
    with HPXRuntime():
        def noop():
            return 42
        def run():
            f = hpyx.futures.submit(noop)
            return f.get()
        benchmark(run)

def test_bench_python_call_overhead(benchmark):
    """Baseline: Python function call overhead."""
    def noop():
        return 42
    benchmark(noop)
```

## Best Practices

### Data Setup Outside Benchmark

Create data before the benchmarked function, not inside it:

```python
# CORRECT: Data created once, benchmark measures only the operation
def test_bench(benchmark, size):
    data = np.random.random(size)  # Outside benchmark
    with HPXRuntime():
        _ = benchmark(hpyx._core.dot1d, data, data)

# WRONG: Data creation is measured too
def test_bench(benchmark, size):
    def run():
        data = np.random.random(size)  # Inside benchmark — wrong!
        return hpyx._core.dot1d(data, data)
    benchmark(run)
```

### Runtime Lifecycle in Benchmarks

Place `HPXRuntime()` context based on what to measure:

```python
# Measure only the operation (exclude runtime startup):
def test_bench_operation(benchmark, size):
    data = np.random.random(size)
    with HPXRuntime():           # Started once
        _ = benchmark(op, data)  # Operation measured many times

# Measure operation + runtime startup:
def test_bench_with_startup(benchmark, size):
    data = np.random.random(size)
    def run():
        with HPXRuntime():       # Started each iteration
            return op(data)
    benchmark(run)
```

### Size Ranges

Use parametrize with ranges that reveal scaling behavior:

- **Small**: 100K — 1M elements (shows overhead)
- **Medium**: 1M — 50M elements (shows steady-state throughput)
- **Large**: 100M — 500M elements (shows memory bandwidth limits)

### Naming Convention

Follow the pattern `test_bench_{implementation}_{operation}`:
- `test_bench_hpx_dot1d` — HPX implementation
- `test_bench_np_dot1d` — NumPy baseline
- `test_bench_python_for_loop` — Pure Python baseline

## End-to-End Benchmarking Workflow

```
1. Write benchmark            → follow patterns above, parametrize by size
2. Run (pixi run benchmark)   → verify no HPX init errors in stderr
3. Spot-check correctness     → print one result, compare against NumPy
4. Inspect StdDev / Mean      → ratio should be small (<5%)
5. Save baseline              → pytest --benchmark-save=baseline
6. Iterate and compare        → pytest --benchmark-compare=baseline
```

## Analyzing Results

Before trusting timing data, verify each of the following and apply the remediation if the check fails:

| Check | Remediation if failing |
|---|---|
| HPXRuntime started cleanly (no init errors in stderr) | Re-enter `pixi shell -e benchmark-py313t`; check TCP is disabled (`hpx.parcel.tcp.enable!=0`) |
| Results numerically correct (spot-check against NumPy) | Bug in the binding — not a performance issue; fix correctness first |
| StdDev small relative to Mean (< 5%) | Increase `--benchmark-min-rounds`, disable CPU frequency scaling, kill background processes, or pin CPUs with `taskset` |
| Warmup sufficient | Keep `--benchmark-warmup=on`; for cold-cache benchmarks set `--benchmark-warmup=off` explicitly |

Key metrics to evaluate:

1. **HPX vs NumPy ratio** — Target: HPX competitive or faster for large data
2. **Thread scaling efficiency** — Near-linear up to core count; plateau beyond indicates memory bandwidth limits
3. **Binding overhead** — Small constant overhead acceptable for large workloads; if dominant at all sizes, the binding is misconfigured
4. **Memory bandwidth** — Throughput-bound operations cap at `num_sockets × per-socket-BW`

## Additional Resources

### Reference Files

- **`references/benchmark-analysis.md`** — Guide to interpreting benchmark results, common performance bottlenecks, and optimization strategies for C++/Python bindings
