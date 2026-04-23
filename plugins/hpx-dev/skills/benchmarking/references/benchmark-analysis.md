# Benchmark Analysis Guide

Guide to interpreting benchmark results and optimizing HPyX binding performance.

## Understanding pytest-benchmark Output

### Key Metrics
- **Min**: Fastest iteration — best-case performance, least noise
- **Max**: Slowest iteration — may include GC pauses, context switches
- **Mean**: Average across all iterations — most representative
- **StdDev**: Variation — high StdDev suggests interference (GC, OS scheduling)
- **Median**: Middle value — robust against outliers
- **Rounds**: Number of benchmark iterations — more rounds = more reliable
- **OPS**: Operations per second — inverse of mean time

### Which Metric to Use
- **Comparing implementations**: Use **median** (robust to outliers)
- **Worst-case analysis**: Use **max** (but discount GC pauses)
- **Best achievable**: Use **min** (shows theoretical maximum)
- **Reporting**: Use **mean ± StdDev** (standard practice)

## Common Performance Patterns

### Pattern 1: Binding Overhead Dominates (Small Data)

```
HPX dot1d (1K elements):   0.05 ms
NumPy dot  (1K elements):  0.001 ms
```

**Diagnosis**: For small data, the cost of crossing Python→C++→HPX exceeds computation time.

**Action**: This is expected. Document the crossover point where HPX becomes faster. Typical crossover: 100K-1M elements.

### Pattern 2: Memory Bandwidth Limit (Large Data)

```
HPX dot1d (500M elements): 250 ms
NumPy dot  (500M elements): 240 ms
```

**Diagnosis**: At very large sizes, both implementations saturate memory bandwidth. Parallel execution doesn't help because all cores share the memory bus.

**Action**: Expected for memory-bound operations. Report bandwidth utilization: `2 * N * sizeof(double) / time = GB/s`.

### Pattern 3: Linear Thread Scaling

```
1 thread:  100 ms
2 threads:  52 ms (1.92x)
4 threads:  27 ms (3.70x)
8 threads:  15 ms (6.67x)
```

**Diagnosis**: Near-linear scaling indicates compute-bound workload with good load balancing.

**Action**: Ideal result. Report scaling efficiency: `speedup / threads * 100%`.

### Pattern 4: GIL Contention (Python Callbacks)

```
HPX for_loop (par, Python callback): 150 ms
HPX for_loop (seq, Python callback):  50 ms
Pure Python loop:                      45 ms
```

**Diagnosis**: Parallel execution with Python callbacks is slower than sequential because the GIL serializes Python calls.

**Action**: This is a known limitation with GIL-enabled Python. With free-threading (Python 3.13t), parallel Python callbacks should scale better. For GIL-enabled builds, recommend pure C++ lambdas for parallel work.

### Pattern 5: Runtime Startup Overhead

```
With runtime in benchmark:  500 ms (first), 15 ms (subsequent)
Without runtime in benchmark: 15 ms
```

**Diagnosis**: HPXRuntime initialization is expensive (~200-500ms).

**Action**: Always initialize runtime outside the benchmark loop. Document startup cost separately.

## Optimization Strategies

### For Compute-Bound Operations
1. Increase thread count (`HPXRuntime(os_threads=N)`)
2. Use `par_unseq` policy for vectorization
3. Minimize Python callback overhead (use pure C++ when possible)

### For Memory-Bound Operations
1. Process data in cache-friendly chunks
2. Use NUMA-aware allocation on multi-socket systems
3. Avoid unnecessary copies between Python and C++

### For Reducing Binding Overhead
1. Batch operations (process arrays, not scalars)
2. Use ndarray for zero-copy data transfer
3. Minimize Python↔C++ round trips

### For GIL Contention
1. Use free-threading Python (3.13t)
2. Keep Python callbacks minimal
3. Do bulk work in C++ and only return results to Python
4. Use deferred execution to avoid true parallel GIL acquisition

## Benchmarking Best Practices

### Controlling Variables
- Pin to specific CPU cores: `taskset -c 0-3 python benchmark.py`
- Disable CPU frequency scaling: `cpupower frequency-set -g performance`
- Close other applications
- Run multiple times and check consistency

### Statistical Validity
- Use `--benchmark-min-rounds=5` minimum
- Check StdDev < 10% of Mean
- If StdDev is high, increase rounds or check for interference
- Use `--benchmark-warmup=on` to exclude JIT/cache warming

### Comparing Results Over Time
```bash
# Save baseline
pytest benchmarks/ --benchmark-save=baseline

# After changes, compare
pytest benchmarks/ --benchmark-compare=baseline

# Generate JSON for automated analysis
pytest benchmarks/ --benchmark-json=results.json
```

### Reporting Template

```markdown
## Performance Report: <feature>

**Environment:**
- CPU: [model, cores, frequency]
- Memory: [size, speed]
- Python: 3.13 (free-threading: yes/no)
- HPX: [version]
- NumPy: [version]

**Results:**
[Table with implementations, sizes, timings]

**Key Findings:**
1. Crossover point: HPX faster than NumPy at [N] elements
2. Thread scaling: [X]% efficiency at [N] threads
3. Binding overhead: [Y] ms constant cost
4. Memory bandwidth utilization: [Z] GB/s

**Recommendations:**
- [Optimization suggestions]
```
