# Benchmarking & Profiling — v0 Starting Point

**Project:** HPyX — Python bindings for HPX (nanobind)
**Status:** Draft
**Version:** 0.1
**Last updated:** 2026-04-24
**Companion doc:** `docs/design-docs/benchmarking_profiling_sdd.md` (full roadmap)

---

## 1. Purpose

This document specifies a **minimal, trustworthy v0** of HPyX's benchmarking and
profiling setup. It exists because today's `benchmarks/` directory has two
ad-hoc files with measurement bugs, no shared fixtures, no profiling build, and
no contract for how baselines are compared. Before we expand the Python API
surface further, we need numbers we can trust.

v0 is deliberately small. Everything beyond v0 — `pyperf`, `asv`, CI jobs, a
dedicated physical runner, macro/memory suites, hard numeric targets — remains
in the companion SDD as the forward roadmap. The SDD is not being deleted; it
is being re-scoped so that this document is "Phase 0" and the existing phases
become "Phase 1+".

## 2. Goals and Non-Goals

### Goals

- **Fix what exists.** Rewrite the current `benchmarks/*.py` files so they
  don't time runtime startup, don't measure Python dunder overhead instead of
  HPX, and don't compare apples to oranges across files.
- **Establish a contract** for how a benchmark is authored, so future additions
  are consistent.
- **Make local profiling reproducible.** Add a `profile` CMake preset and a
  thin run-script so `py-spy`, `Scalene`, and `memray` work out of the box.
- **Prove the free-threading axis** end-to-end with one smoke benchmark, so we
  know the harness will hold when we expand it.

### Non-Goals

- No CI integration in v0. (`bench-smoke` / `bench-full` remain in the SDD.)
- No `pyperf`, no `asv`, no dashboard, no dedicated physical runner.
- No `TARGETS.md` with hard numeric budgets. Targets are earned by measurement,
  not asserted up front.
- No macro or memory suites. v0 is microbenchmarks only.

## 3. Scope Summary (what v0 ships)

1. Align on the `benchmarks/` directory name (matches what's on disk today).
   The SDD is updated to use `benchmarks/` instead of `bench/`.
2. Rewrite the two existing benchmark files to follow the authoring contract
   (Section 5).
3. Add `benchmarks/conftest.py` with shared fixtures (Section 6).
4. Add baselines: **NumPy**, **pure Python**, and
   **`concurrent.futures.ThreadPoolExecutor`** — wired into every HPyX
   microbenchmark through the contract.
5. Add a `profile` CMake preset (Section 7).
6. Add **one** free-threading smoke benchmark for `for_loop`, gated on a
   3.13t interpreter (Section 6, fixture `requires_free_threading`).
7. Add `scripts/run_bench_local.sh` wrapping the common flows.
8. Add `benchmarks/README.md` — a ~one-page contributor doc covering how to
   run, how to add, and how to profile locally.
9. Update the companion SDD to (a) use `benchmarks/`, (b) add Python 3.13
   free-threading as a first-class axis in authoring conventions and risks,
   and (c) mark this document as "Phase 0 / starting point".

## 4. Directory Layout After v0

```
benchmarks/
├── conftest.py                      # shared fixtures (Section 6)
├── README.md                        # contributor doc (Section 8)
├── test_bench_for_loop.py           # rewritten against contract
├── test_bench_hpx_linalg.py         # rewritten against contract
├── test_bench_thread_scaling.py     # new: varies HPX thread count
└── test_bench_free_threading.py     # new: one smoke test, gated on 3.13t

scripts/
└── run_bench_local.sh               # new: pytest-benchmark + py-spy wrapper

CMakePresets.json                    # adds `profile` preset
docs/design-docs/
├── benchmarking_profiling_sdd.md    # updated (see Section 9)
└── 2026-04-24-benchmarking-v0-design.md   # this doc
```

## 5. Benchmark Authoring Contract

Every benchmark file in v0 follows these rules. This contract is the load-
bearing part of v0 — the fixtures and preset exist to make it enforceable.

1. **Setup is never timed.** Runtime startup, array allocation, RNG — all
   outside the timed region. Use `benchmark.pedantic(fn, setup=..., rounds=...,
   iterations=...)` when the default fixture isn't enough. The current
   `test_bench_for_loop.py` violates this by putting `HPXRuntime()` inside the
   timed callable; the rewrite fixes it via the session-scoped `hpx_runtime`
   fixture.

2. **Parametrize on size across three orders of magnitude.** Minimum sizes
   `[1_000, 100_000, 10_000_000]` so fixed call overhead is separable from
   per-element cost visually.

3. **Every HPyX benchmark has matching baselines in the same group.** For a
   benchmark measuring `hpyx.for_loop` applied to operation `f`, we also
   measure the NumPy, pure-Python, and `concurrent.futures.ThreadPoolExecutor`
   equivalents of `f` at the same sizes and in the same `pytest-benchmark`
   group. Absence of a meaningful baseline (e.g. no NumPy equivalent exists)
   must be documented in the test's docstring.

4. **Group names are explicit.** Each file declares
   `pytestmark = pytest.mark.benchmark(group="<topic>")` at module scope. One
   group per "thing being compared" — not one group per file.

5. **Payloads minimize Python overhead unless Python overhead is the point.**
   Avoid patterns like `result.__setitem__(i, arr[i] ** 2)` in the hot path
   when a C-level equivalent is available through the binding. Where a Python
   callback is intrinsic to the binding's design (e.g. `for_loop` with a
   Python lambda), the benchmark's docstring must state that the measurement
   includes callback overhead, so readers don't misread the result.

6. **Thread-scaling benchmarks parametrize on thread count.**
   `@pytest.mark.parametrize("threads", [1, 2, 4, 8])`, configured via the
   `hpx_threads` fixture. Tests are skipped when the host has fewer physical
   cores than the requested thread count.

7. **Free-threading benchmarks gate on interpreter state.** Any benchmark
   that asserts speedup under nogil uses the `requires_free_threading` fixture
   (checks `sysconfig.get_config_var("Py_GIL_DISABLED")`). In v0 this applies
   to exactly one test: a thread-scaling smoke test for `for_loop`.

## 6. Shared Fixtures (`benchmarks/conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `pin_cpu` | session, autouse | `os.sched_setaffinity(0, {0})` on Linux; no-op on macOS (documented as noisier). |
| `seed_rng` | function, autouse | Deterministically seeds `random`, `numpy.random`, and any HPyX RNG from the test id. |
| `no_gc` | function, opt-in | Context-manager fixture that disables `gc` during the timed region. Opt-in per benchmark. |
| `hpx_runtime` | session | Starts `HPXRuntime()` once per session; tears down at exit. Benchmarks reuse instead of start/stop per call. |
| `hpx_threads` | function, indirect | Parametrizes HPX thread count. Used only by `test_bench_thread_scaling.py` and `test_bench_free_threading.py` — see resolution in Section 6.1. |
| `requires_free_threading` | marker + skip | Skips test unless `sysconfig.get_config_var("Py_GIL_DISABLED") == 1`. |
| `env_sanity_check` | session, autouse | Fails on battery power (Linux); fails if HPX was built in Debug mode; warns if turbo-boost state cannot be determined. |

### 6.1 Thread-count vs. session runtime — resolution

A session-scoped `hpx_runtime` conflicts with benchmarks that need to vary
thread count. Resolution: **thread-count-varying benchmarks live in dedicated
files** (`test_bench_thread_scaling.py`, `test_bench_free_threading.py`) and
use a file-local, function-scoped runtime that restarts per parametrization.
All other benchmarks use the session-scoped `hpx_runtime` fixture. This keeps
the fast path fast and the slow path explicit.

## 7. `profile` CMake Preset

Matches release-level optimization so numbers are meaningful, differing only
in debug info, frame pointers, and LTO so `py-spy --native`, `perf`, and
`memray --native` can resolve C++ frames.

```json
{
  "name": "profile",
  "inherits": "release",
  "cacheVariables": {
    "CMAKE_BUILD_TYPE": "RelWithDebInfo",
    "CMAKE_CXX_FLAGS_RELWITHDEBINFO": "-O2 -g -fno-omit-frame-pointer",
    "CMAKE_INTERPROCEDURAL_OPTIMIZATION": "OFF",
    "CMAKE_CXX_VISIBILITY_PRESET": "default"
  }
}
```

Actual wiring follows the `hpx-dev:build-system` skill's conventions for this
repo.

## 8. `scripts/run_bench_local.sh` and Contributor README

### 8.1 `scripts/run_bench_local.sh`

Thin wrapper exposing three subcommands:

- `bench [pytest args]` — runs `pytest benchmarks/ --benchmark-only` with
  repo defaults (e.g. `--benchmark-min-rounds=5`).
- `record <test-id>` — runs the selected benchmark under
  `py-spy record --native --rate 500 -o flame.svg -- …`.
- `compare` — runs `pytest-benchmark compare` against the locally stored
  baseline.

The script does not install tooling; it assumes `py-spy` is on `PATH` and
falls back with an actionable error message otherwise.

### 8.2 `benchmarks/README.md`

Three sections, ~one page total:

1. **How to run.** `pixi run bench`, how to filter (`-k`), how to save and
   compare a baseline with `pytest-benchmark`.
2. **How to add a benchmark.** Inlines the 7-rule contract from Section 5
   with one worked example (the rewritten `for_loop` square benchmark).
3. **How to profile locally.** One copy-pasteable command each for `py-spy`
   (cross-language flame graph), `Scalene` (per-line Python vs. native),
   `memray` (allocation flame graph). Prerequisite note: build with the
   `profile` preset.

Everything else — `pyperf` usage, `asv` dashboard, CI behavior, regression
thresholds — is deferred to the companion SDD and linked from the README.

## 9. Changes to the Companion SDD

The existing `benchmarking_profiling_sdd.md` is updated, not replaced:

1. All `bench/` references changed to `benchmarks/` to match reality.
2. Section 6 ("Benchmark Suite Design") and Section 10 ("Metrics and Targets")
   gain **Python 3.13 free-threading as a first-class axis**: thread-scaling
   speedup targets are stated under both GIL and nogil interpreters, and the
   authoring conventions reference the `requires_free_threading` fixture.
3. Section 12 ("Risks and Mitigations") adds a row for "free-threading
   interpreter availability in CI".
4. Section 13 ("Rollout Plan") is prefixed with a new "Phase 0 — Starting
   point" entry pointing at this document; the existing Phases 1–5 are
   renumbered as Phases 1–5 of the expansion from Phase 0.

## 10. Acceptance Criteria

v0 is done when all of the following are true:

- `benchmarks/conftest.py` exists with the seven fixtures in Section 6.
- The two existing benchmark files are rewritten to follow Section 5's
  contract, and each HPyX microbenchmark has NumPy, pure-Python, and
  `concurrent.futures.ThreadPoolExecutor` baselines in the same group.
- `test_bench_thread_scaling.py` exists and runs on the default interpreter.
- `test_bench_free_threading.py` exists, passes under a 3.13t interpreter,
  and skips cleanly under standard CPython 3.13.
- `CMakePresets.json` has a `profile` preset and a `profile`-preset build
  produces an extension with resolvable C++ frames under `py-spy dump`.
- `scripts/run_bench_local.sh` runs the three subcommands end-to-end on a
  developer machine.
- `benchmarks/README.md` is written and links to the companion SDD.
- The companion SDD reflects the changes in Section 9.

## 11. Risks and Mitigations (v0-specific)

| Risk | Mitigation |
|---|---|
| Session-scoped `hpx_runtime` hides per-call startup regressions. | A dedicated micro-benchmark (in a file that opts out of the `hpx_runtime` session fixture) measures cold `HPXRuntime()` start/stop explicitly. Exact file location decided during implementation. |
| `concurrent.futures` baseline is misleading for CPU-bound work under the GIL. | Baselines are labeled; the benchmark docstring calls out that `ThreadPoolExecutor` on GIL CPython is a ceiling on what naive users reach for, not a fair parallel comparison. |
| Free-threading smoke test provides false confidence. | Scope is explicit: "the harness works end-to-end," not "HPyX scales linearly." No performance claims derived from v0. |
| macOS noise invalidates comparisons. | Documented in README; `pin_cpu` is a no-op on macOS; developer loop remains usable, but "authoritative" numbers are Linux-only (consistent with the SDD). |

## 12. Out of Scope (tracked in companion SDD)

- `pyperf` multi-process isolation runs for published numbers.
- `asv` continuous tracking and HTML dashboard.
- `bench-smoke` and `bench-full` GitHub Actions workflows.
- Dedicated physical runner, `pyperf system tune`.
- Macro/end-to-end and memory-shape suites.
- `memray` and `py-spy` artifact uploads on tagged releases.
- `TARGETS.md` numeric budgets.
