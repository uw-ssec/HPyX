# Software Design Document: Benchmarking & Profiling Infrastructure

**Project:** Python Bindings (nanobind) — Performance Measurement Subsystem
**Status:** Draft
**Version:** 0.1
**Last updated:** 2026-04-24

---

## 1. Purpose

This document describes the design of a benchmarking and profiling subsystem for a Python binding built on top of a C++ library using **nanobind**. The subsystem is responsible for:

1. Measuring the performance of the Python-facing API under representative workloads.
2. Detecting regressions automatically as the C++ library and the binding layer evolve.
3. Providing actionable insight into *where* time is spent across the Python / nanobind / C++ boundary.
4. Producing comparable, reproducible numbers suitable for release notes and public claims.

Performance of the underlying C++ algorithms is out of scope except where it interacts with binding design (e.g. GIL handling, copy vs. view semantics, batching).

## 2. Scope

**In scope**

- Microbenchmarks for individual binding entry points.
- Macro / end-to-end benchmarks simulating realistic user workloads.
- Cross-language profiling (Python + native C++ stacks unified).
- Memory profiling, including allocations that cross the language boundary.
- Continuous performance tracking over time on a dedicated runner.
- Developer-facing tooling for local investigation.

**Out of scope**

- Correctness testing (covered by the existing `pytest` test suite).
- Profiling of pure-C++ code paths that are not reachable from Python.
- GPU profiling (unless bindings are explicitly added for GPU paths).

## 3. Goals and Non-Goals

### Goals

- **Reproducibility.** Any contributor can run the benchmark suite locally and get results within ~5% of the CI numbers.
- **Regression detection.** A regression >5% in any tracked benchmark should fail CI, or at minimum produce a visible alert.
- **Boundary visibility.** For every hot binding call, we can attribute time to (a) Python interpreter overhead, (b) nanobind marshalling, and (c) native C++ work.
- **Low friction.** Writing a new benchmark should be as easy as writing a `pytest` test.
- **Longitudinal data.** Performance history is retained per-commit and browsable via a web dashboard.

### Non-Goals

- Replacing the functional test suite.
- Benchmarking third-party Python code that merely uses our library.
- Perfect statistical parity across different hardware — we compare within a host, not across hosts.

## 4. System Context

```
            ┌────────────────────────┐
   user  ─► │   Python API surface   │  (pure-Python wrappers, if any)
            └────────────┬───────────┘
                         │
            ┌────────────▼───────────┐
            │ nanobind binding layer │  ← allocations, type conversions,
            └────────────┬───────────┘    GIL release/acquire
                         │
            ┌────────────▼───────────┐
            │  C++ core library      │  ← algorithms under test
            └────────────────────────┘
```

The subsystem instruments the top three layers. The C++ core is treated as a black box here, but the profilers we use can descend into it when their stacks are resolvable.

## 5. Toolchain

### 5.1 Benchmarking

| Tool | Role | Rationale |
|---|---|---|
| `pytest-benchmark` | Primary microbenchmark harness | Low barrier; discovers benchmarks like tests; produces JSON artifacts. |
| `pyperf` | Statistically rigorous runs for "published" numbers | Multi-process isolation, warmup, system tuning (`pyperf system tune`). |
| `asv` (airspeed velocity) | Longitudinal tracking across commits | Produces a browsable HTML dashboard; used by NumPy/SciPy/pandas. |

### 5.2 Profiling

| Tool | Role | Rationale |
|---|---|---|
| `py-spy --native` | Unified Python + C++ sampling flame graphs | Attaches to running processes; no code changes; resolves both stacks. |
| `Scalene` | Per-line split of Python vs. native time, CPU, memory, GPU | Fastest way to find where nanobind overhead or C++ work dominates. |
| `memray --native` | Memory allocations with native stacks | Detects leaks and churn caused by the binding layer. |
| `perf` + FlameGraph | Deep-dive on C++ hotspots identified above | Lower-level, kernel-aware; Linux only. |
| `callgrind` / KCachegrind | Instruction-level analysis when needed | Slow but exact; useful for verifying optimization theories. |

### 5.3 Build configuration for profiling

C++ code must be built with:

- `-O2` (release-like optimization) **and** `-g` (debug info) **and** `-fno-omit-frame-pointer`.
- Symbol visibility preserved (`-fvisibility=default` for the extension module or explicit `NB_MODULE` exports).
- Link-time optimization disabled for profiling builds (it collapses frames py-spy needs).

A dedicated CMake preset `profile` produces this configuration so profiling builds do not interfere with release builds.

## 6. Benchmark Suite Design

### 6.1 Directory layout

```
bench/
├── conftest.py              # shared fixtures: warm caches, pin CPU, seed RNG
├── micro/
│   ├── test_call_overhead.py   # no-op calls, argument conversion costs
│   ├── test_array_ingest.py    # numpy/buffer → C++ paths
│   ├── test_return_paths.py    # C++ → Python object construction
│   └── test_gil.py             # threaded calls with/without GIL release
├── macro/
│   ├── test_pipeline_small.py
│   ├── test_pipeline_large.py
│   └── test_realistic_workload.py
├── memory/
│   └── test_allocation_shape.py
└── asv_bench/                # mirror of above adapted for asv
    ├── benchmarks.py
    └── asv.conf.json
```

### 6.2 Categories of benchmark

1. **Call-overhead microbenchmarks.** Measure the floor cost of invoking a binding: no-op functions, trivial returns, per-argument-type overhead. These catch regressions in nanobind itself or in how we're using it.
2. **Data-ingest microbenchmarks.** Measure `numpy.ndarray`, `bytes`, `str`, `list`, and custom-type conversion on the way in. Vary sizes (1, 1K, 1M elements) to separate fixed cost from per-element cost.
3. **Return-path microbenchmarks.** Measure object construction, buffer protocol, and ownership transfer on the way out.
4. **GIL behavior.** Confirm long C++ calls release the GIL and scale with threads. Benchmark both with-GIL and without-GIL variants.
5. **End-to-end workloads.** A small number of representative pipelines drawn from real users, sized to run in seconds, not minutes.
6. **Memory shape.** Peak RSS, allocation count, and allocation sizes for each macro benchmark.

### 6.3 Authoring conventions

- Every benchmark is parametrized on input size to separate O(1) from O(n) costs.
- Every benchmark has a companion "baseline" — either the previous implementation, a pure-Python equivalent, or a direct `ctypes` call — to give numbers meaning.
- Setup is never timed. Use `pytest-benchmark`'s `benchmark.pedantic()` when fine control is needed.
- Each file declares a `pytestmark = pytest.mark.benchmark(group="…")` so results cluster sensibly in the report.

### 6.4 Environment controls

A `conftest.py` fixture:

- Pins the process to a single CPU (`os.sched_setaffinity`) on Linux.
- Disables Python's GC during timed regions where appropriate.
- Seeds all RNGs deterministically.
- Fails loudly if the machine is on battery, has turbo boost enabled, or is running a debug build.

## 7. Profiling Workflow

### 7.1 Developer local loop

1. Build with the `profile` CMake preset.
2. Run the target benchmark under py-spy:
   ```
   py-spy record --native --rate 500 -o flame.svg -- \
       pytest bench/macro/test_pipeline_small.py -k large
   ```
3. Open `flame.svg`; identify hot frames.
4. For Python-side detail: re-run under Scalene.
   ```
   scalene --cli --profile-all bench/macro/test_pipeline_small.py
   ```
5. For memory: `memray run --native … && memray flamegraph …`.
6. Iterate.

### 7.2 CI profiling artifacts

On every tagged release candidate, CI runs py-spy and memray over the macro suite and uploads the SVG flame graphs as build artifacts, so reviewers can inspect without reproducing locally.

## 8. Continuous Tracking (asv)

- A dedicated, consistent physical runner (same hardware, same OS image) runs `asv run` nightly against `main` and on every merge.
- Results are published to a static site (e.g. GitHub Pages) under `/perf/`.
- `asv continuous HEAD~1 HEAD` runs on every PR touching code in `src/` or `bench/`, posting a summary comment.
- A configurable regression threshold (default 5%) marks PR runs as failed.
- Historical JSON is kept in a separate long-lived repository so dashboard rebuilds are cheap.

## 9. CI Integration

Two jobs, both on the dedicated runner:

**`bench-smoke`** — runs on every PR.
- Builds with `profile` preset.
- Runs the `micro/` suite under `pytest-benchmark` with `--benchmark-min-rounds=5`.
- Compares against the baseline stored for `main` using `pytest-benchmark compare`.
- Fails if any benchmark regresses by more than the configured threshold.
- Target wall-clock: under 5 minutes.

**`bench-full`** — runs nightly and on release tags.
- Runs micro + macro + memory suites.
- Runs `asv run` and publishes the dashboard.
- Uploads py-spy and memray artifacts for macro benchmarks.
- Target wall-clock: under 45 minutes.

## 10. Metrics and Targets

Initial targets (to be tuned once the first runs land):

| Metric | Target |
|---|---|
| No-op binding call overhead | < 150 ns median |
| 1M-float numpy ingest | < 2 µs fixed + < 1 ns/element |
| GIL-released C++ call, 8 threads | > 6× speedup vs. single thread |
| Macro pipeline "small" | < 200 ms median, < 5% p99/median spread |
| Peak RSS for macro pipeline "large" | < 1.5× C++-only equivalent |
| Allocation count per macro run | Within 10% of previous release |

These are tracked in `bench/TARGETS.md` and reviewed each release.

## 11. Directory & File Inventory (new)

```
bench/                          # new
CMakePresets.json               # add `profile` preset
.github/workflows/bench.yml     # new
docs/perf/                      # new, human-readable performance notes
scripts/
  run_bench_local.sh            # thin wrapper around common flows
  compare_against_main.sh
bench/TARGETS.md                # performance budgets
```

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Noisy CI results cause false regressions. | Dedicated physical runner; `pyperf system tune`; multiple rounds; median-based comparison; generous initial thresholds, tightened over time. |
| Profiling build diverges from release build, misleading results. | `profile` preset differs only in `-g` and frame pointers; LTO and optimization level match release. |
| Binding design locked in by benchmarks (premature optimization). | Benchmarks measure outcomes, not implementation; refactors are fine as long as budgets hold. |
| Long nightly runs block the runner. | Macro suite is size-bounded; cap total wall-clock at 45 min; split into sharded jobs if exceeded. |
| Symbol resolution fails for C++ frames in py-spy. | CI step verifies `py-spy dump` against a running benchmark shows resolved C++ frames; build fails otherwise. |

## 13. Rollout Plan

1. **Phase 1 — Skeleton.** Land `bench/` directory, `conftest.py`, three illustrative microbenchmarks, `profile` CMake preset, local run script. No CI yet. *(≈1 week)*
2. **Phase 2 — Smoke CI.** Add `bench-smoke` job; establish baseline on `main`; tune thresholds against a week of noise data. *(≈1 week)*
3. **Phase 3 — Macro + memory.** Add macro and memory suites; wire memray/py-spy artifact uploads on nightly. *(≈2 weeks)*
4. **Phase 4 — asv dashboard.** Stand up the dedicated runner, publish the dashboard, add PR continuous comparisons. *(≈2 weeks)*
5. **Phase 5 — Harden.** Tighten thresholds, document the workflow in `docs/perf/`, write a contributor guide for adding benchmarks. *(ongoing)*

## 14. Open Questions

- Which physical machine hosts the asv runner? (Needs owner + access policy.)
- Do we publish performance numbers externally with each release, or keep them internal for now?
- Should we add a Windows and/or macOS benchmark job, or Linux-only for v1?
- What is the authoritative baseline commit for the first release — the last tagged release or the state of `main` at Phase 2 completion?

## 15. References

- nanobind documentation — https://nanobind.readthedocs.io/
- pytest-benchmark — https://pytest-benchmark.readthedocs.io/
- pyperf — https://pyperf.readthedocs.io/
- asv (airspeed velocity) — https://asv.readthedocs.io/
- py-spy — https://github.com/benfred/py-spy
- Scalene — https://github.com/plasma-umass/scalene
- memray — https://github.com/bloomberg/memray

---

*Appendix A: example `conftest.py`, example `asv.conf.json`, and a reference `bench-smoke` GitHub Actions workflow — to be added in Phase 1.*
