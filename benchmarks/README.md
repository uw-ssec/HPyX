# HPyX Benchmarks

Local developer loop for measuring HPyX performance. Uses
`pytest-benchmark`. No CI gating, no dashboards — earn numbers via
measurement, don't assert them up front.

## Quick start

```bash
pixi run benchmark                            # Run full suite
pixi run -e benchmark-py313t pytest benchmarks/test_bench_kernels.py -v
bash scripts/run_bench_local.sh compare       # Compare vs stored baseline
bash scripts/run_bench_local.sh record benchmarks/test_bench_parallel.py::test_for_loop_par_hpyx
```

## Authoring contract

Every new benchmark file follows these seven rules (enforced by fixtures
and naming):

1. **Setup is never timed.** Use `benchmark.pedantic(fn, setup=..., rounds=...)`
   or the session-scoped `hpx_runtime` fixture. Never construct
   `HPXRuntime()` inside a timed callable.
2. **Parametrize across three size orders.** Minimum `[1_000, 100_000, 10_000_000]`.
   Makes fixed call overhead visually separable from per-element cost.
3. **Three matching baselines per HPyX benchmark**, in the same
   pytest-benchmark group: NumPy equivalent, pure-Python equivalent,
   `concurrent.futures.ThreadPoolExecutor` equivalent. Absence is
   explicitly documented in the test's docstring.
4. **Explicit group names** via module-level
   `pytestmark = pytest.mark.benchmark(group="<topic>")`. One group per
   "thing being compared."
5. **Minimize Python overhead unless measuring it.** When a Python
   callback is intrinsic (e.g., `parallel.for_loop`), the test's
   docstring says so.
6. **Thread-scaling parametrization** via
   `@pytest.mark.parametrize("hpx_threads", [1, 2, 4, 8], indirect=True)`.
   Tests skip when fewer cores available.
7. **Free-threading gating** — benchmarks that assert speedup under
   nogil decorate with `@requires_free_threading`.

## Profiling recipes

All three require building with the `profile` CMake preset:

```bash
cmake --preset profile
cmake --build build/profile
```

### py-spy (cross-language flame graphs)

```bash
py-spy record --native --rate 500 -o flame.svg -- \
    pixi run -e benchmark-py313t \
    pytest benchmarks/test_bench_kernels.py::test_dot_hpyx -v
```

### Scalene (per-line Python vs native)

```bash
pixi run -e benchmark-py313t \
    scalene --html --outfile scalene.html -- \
    -m pytest benchmarks/test_bench_kernels.py -k dot
```

### memray (allocation flame graphs)

```bash
pixi run -e benchmark-py313t \
    python -m memray run --native -o memray.bin \
    -m pytest benchmarks/test_bench_executor.py::test_executor_map_hpyx
pixi run -e benchmark-py313t memray flamegraph memray.bin
```

## Caveats

- `ThreadPoolExecutor` baseline is a ceiling on what naive users reach
  for — not a fair parallel comparison. Labeled accordingly in test
  docstrings.
- macOS benchmarks are noisier than Linux; `pin_cpu` is a no-op on
  macOS. Use Linux for authoritative numbers.
- The free-threading smoke test proves the harness works on 3.13t, not
  that HPyX scales linearly everywhere. No performance claims derived
  from one test.
- Session-scoped `hpx_runtime` hides cold-start regressions — see
  `test_bench_cold_start.py` which explicitly measures them.
