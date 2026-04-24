# HPyX v1 Phase 3: Benchmark Infrastructure + Full Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Land the benchmark infrastructure per spec §6.2 (seven shared fixtures, authoring contract, `run_bench_local.sh` with three subcommands, `profile` CMake preset already exists from Plan 0), plus real `hpyx.debug.enable_tracing` writing JSONL per-task events. End state: `pixi run benchmark` executes all microbenchmarks with HPyX, NumPy, pure-Python, and `ThreadPoolExecutor` baselines in matching groups; `scripts/run_bench_local.sh record <test-id>` produces a flamegraph.svg with resolved C++ frames; `hpyx.debug.enable_tracing("/tmp/out.jsonl")` produces consumable JSONL.

**Architecture:** Pure-Python plus one small C++ addition. Benchmarks use `pytest-benchmark` with seven shared fixtures in `benchmarks/conftest.py`. A new C++ hook in `src/_core/futures.cpp` (optional wrapper around task lambdas) captures per-task timing when tracing is enabled — writes lock-free to a thread-local buffer that Python drains and flushes to JSONL. No CI perf gating in this plan — Phase 1+ per spec §1.3.

**Tech Stack:** `pytest-benchmark`, `py-spy`, `memray`, `Scalene` (new dev deps), `jsonlines` (new stdlib-only via `json`), numpy, concurrent.futures.

**Depends on:** Plans 0-2 merged into `main`.

**Reference documents:**
- Spec: `docs/specs/2026-04-24-hpyx-pythonic-hpx-binding-design.md` §§ 4.9, 6.2, 6.5 (risks 11-14)
- Plan 0: CMakePresets.json already has `profile` preset
- HPX knowledge: `docs/codebase-analysis/hpx/CODEBASE_KNOWLEDGE.md` (for `hpx::get_worker_thread_num`)

**Out of scope:**
- asv / pyperf / CI perf gating (Phase 1+ in the spec's forward roadmap)
- Dashboard UI, HTML reports
- Dedicated physical runner setup
- `TARGETS.md` numeric budgets

---

## File Structure

### Created files

| File | Responsibility |
|---|---|
| `benchmarks/conftest.py` | Seven fixtures: `pin_cpu`, `seed_rng`, `no_gc`, `hpx_runtime`, `hpx_threads`, `requires_free_threading`, `env_sanity_check`. |
| `benchmarks/README.md` | Authoring contract + profiling recipes (py-spy, Scalene, memray). |
| `scripts/run_bench_local.sh` | `bench` / `record` / `compare` subcommands. |
| `benchmarks/test_bench_parallel.py` | Replaces `test_bench_for_loop.py`; covers `hpyx.parallel.for_loop`, `for_each`, `transform`, `reduce` with three baselines. |
| `benchmarks/test_bench_kernels.py` | `dot`, `matmul`, `sum`, `max`, `min` vs numpy. |
| `benchmarks/test_bench_executor.py` | `HPXExecutor.map` vs `ThreadPoolExecutor.map` vs `ProcessPoolExecutor.map`. |
| `benchmarks/test_bench_futures.py` | `async_` + `Future.result()` overhead, `dataflow` DAG throughput. |
| `benchmarks/test_bench_aio.py` | `await fut` overhead, `asyncio.wrap_future` overhead. |
| `benchmarks/test_bench_thread_scaling.py` | Dedicated file — function-scoped `hpx_threads` fixture restarting HPX. |
| `benchmarks/test_bench_free_threading.py` | Nogil-gated smoke test: `parallel.for_loop` speedup 1 → 8 threads on 3.13t. |
| `benchmarks/test_bench_cold_start.py` | Dedicated — opts out of session `hpx_runtime`; measures cold init/stop. |
| `src/_core/tracing.hpp` | `TraceEvent` struct + `record_event` hook called from task-body wrappers. |
| `src/_core/tracing.cpp` | Thread-safe ring buffer of events; `register_bindings` exposes `enable`, `disable`, `drain`. |

### Modified files

| File | Change |
|---|---|
| `pixi.toml` | Add dev deps: `pytest-benchmark`, `py-spy`, `memray`, `scalene`. |
| `src/_core/futures.cpp` | Wrap task lambdas with `tracing::record_event` when tracing is enabled. |
| `src/_core/parallel.cpp` | Same per-iteration tracing hook (optional — disabled by default). |
| `src/_core/bind.cpp` | Register `_core.tracing` submodule. |
| `src/hpyx/debug.py` | Replace `enable_tracing` / `disable_tracing` stubs with real implementations. |
| `tests/test_debug.py` | Add tests for real tracing output (JSONL format, event fields). |

### Deleted files

- `benchmarks/test_bench_for_loop.py` — replaced by `test_bench_parallel.py` which follows the v1 authoring contract.

---

## Execution Notes

- Branch from `main` after Plans 0-2 merged.
- `pixi run benchmark` runs benchmarks in the `benchmark-py313t` environment.
- Benchmarks do NOT block PRs in v1 — they're for local and nightly-trend use only.

---

## Task 1: Create implementation branch + add dev dependencies

- [ ] **Step 1: Branch**

```bash
git checkout main
git pull --ff-only
git checkout -b feat/v1-phase-3-benchmarks-diagnostics
```

- [ ] **Step 2: Add dev deps to `pixi.toml`**

Locate the `[feature.benchmark.dependencies]` section (or create it if missing) and ensure these are present:

```toml
[feature.benchmark.dependencies]
pytest-benchmark = ">=4.0"
numpy = ">=1.26"
dask = ">=2024.10"
py-spy = ">=0.3"
memray = ">=1.12"
scalene = ">=1.5"
```

If the `benchmark-py313t` environment doesn't already include `pytest-benchmark`, add:

```toml
[environments]
benchmark-py313t = { features = ["py313t", "libhpx", "hpyx", "benchmark"], solve-group = "py313t" }
```

- [ ] **Step 3: Resolve + commit**

```bash
pixi install
git add pixi.toml pixi.lock
git commit -m "chore(deps): add pytest-benchmark, py-spy, memray, scalene for benchmark env"
```

---

## Task 2: Create `benchmarks/conftest.py` with seven fixtures

**Files:**
- Create: `benchmarks/conftest.py`

- [ ] **Step 1: Write the conftest**

```python
"""HPyX benchmark fixtures — seven shared fixtures per spec §6.2.

Authoring contract (all benchmarks must follow):

1. Setup is never timed (use benchmark.pedantic or session-scoped fixtures).
2. Parametrize across three size orders: [1_000, 100_000, 10_000_000].
3. Three matching baselines per HPyX benchmark (numpy, pure-Python,
   ThreadPoolExecutor) in the same pytest-benchmark group.
4. Module-level `pytestmark = pytest.mark.benchmark(group="<topic>")`.
5. Minimize Python overhead unless measuring it (document otherwise).
6. Thread-scaling parametrization: [1, 2, 4, 8] via `hpx_threads`.
7. Free-threading gating via `requires_free_threading`.
"""

from __future__ import annotations

import contextlib
import gc
import os
import platform
import sys
import sysconfig
import warnings

import pytest


# ---- Fixture 1: pin_cpu (Linux only; macOS no-op; Windows no-op) ----

@pytest.fixture(scope="session", autouse=True)
def pin_cpu():
    """Pin the benchmarking process to CPU 0 on Linux for stable timing."""
    if platform.system() == "Linux":
        try:
            os.sched_setaffinity(0, {0})
        except (AttributeError, OSError):
            pass
    yield


# ---- Fixture 2: seed_rng (deterministic per-test seeding) ----

@pytest.fixture(autouse=True)
def seed_rng(request):
    """Deterministically seed random / numpy.random / HPyX RNG from test ID."""
    import random
    import hashlib
    seed = int(hashlib.blake2b(request.node.nodeid.encode(), digest_size=4).hexdigest(), 16)
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    yield


# ---- Fixture 3: no_gc (opt-in) ----

@pytest.fixture
def no_gc():
    """Disable gc for the duration of the benchmark body. Opt-in."""
    @contextlib.contextmanager
    def _disable():
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            yield
        finally:
            if was_enabled:
                gc.enable()
    return _disable


# ---- Fixture 4: hpx_runtime (session, autouse — started once) ----

@pytest.fixture(scope="session", autouse=True)
def hpx_runtime():
    """Start HPX once per session with a deterministic thread count.

    Dedicated thread-scaling and cold-start files opt out by defining
    their own module-scoped fixtures (see test_bench_thread_scaling.py
    and test_bench_cold_start.py).
    """
    import hpyx
    hpyx.init(os_threads=4)
    yield
    # atexit handles teardown; don't call hpyx.shutdown() here.


# ---- Fixture 5: hpx_threads (function, indirect) ----
# NOTE: this fixture DOES NOT restart HPX. It only asserts that the
# runtime's os_threads matches the parametrization; tests that need a
# different thread count must run in a separate process (e.g., via
# pytest-xdist or a subprocess).

@pytest.fixture
def hpx_threads(request):
    """Parametrization fixture for thread-count sensitive benchmarks.

    Use via @pytest.mark.parametrize("hpx_threads", [1, 2, 4, 8],
                                     indirect=True).

    Yields the value and skips the test if the host has fewer physical
    cores than requested.
    """
    requested = request.param
    available = os.cpu_count() or 1
    if requested > available:
        pytest.skip(
            f"host has {available} CPUs, benchmark requires {requested}"
        )
    yield requested


# ---- Fixture 6: requires_free_threading (marker + skip) ----

requires_free_threading = pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="Benchmark requires free-threaded Python 3.13t "
           "(sysconfig.get_config_var('Py_GIL_DISABLED') == 1)",
)


# ---- Fixture 7: env_sanity_check (session, autouse) ----

@pytest.fixture(scope="session", autouse=True)
def env_sanity_check():
    """Fail on battery power; fail if HPX is Debug build; warn on unknown turbo."""
    # Battery check (Linux + macOS).
    on_battery = False
    if platform.system() == "Linux":
        try:
            with open("/sys/class/power_supply/AC/online") as f:
                on_battery = f.read().strip() == "0"
        except FileNotFoundError:
            pass
    elif platform.system() == "Darwin":
        import subprocess
        try:
            out = subprocess.run(
                ["pmset", "-g", "batt"], capture_output=True, text=True,
                timeout=5,
            ).stdout
            on_battery = "Battery Power" in out
        except Exception:
            pass
    if on_battery and not os.environ.get("HPYX_BENCH_ALLOW_BATTERY"):
        pytest.exit(
            "Refusing to benchmark on battery power "
            "(set HPYX_BENCH_ALLOW_BATTERY=1 to override).",
            returncode=2,
        )

    # HPX build-type check.
    try:
        import hpyx
        version = hpyx._core.runtime.hpx_version_string().lower()
        if "debug" in version:
            pytest.exit(
                "HPX was built in Debug mode; benchmarks require Release. "
                "Rebuild with CMAKE_BUILD_TYPE=Release.",
                returncode=2,
            )
    except Exception:
        pass

    # Turbo-boost check (Linux only, informational).
    if platform.system() == "Linux":
        try:
            with open("/sys/devices/system/cpu/intel_pstate/no_turbo") as f:
                if f.read().strip() == "0":
                    warnings.warn(
                        "Intel Turbo Boost is enabled — benchmark variance "
                        "will be higher. Consider disabling with: "
                        "echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo",
                        UserWarning,
                    )
        except FileNotFoundError:
            pass

    yield
```

- [ ] **Step 2: Smoke-run the conftest**

```bash
pixi run -e benchmark-py313t pytest benchmarks/ --collect-only -q
```

Expected: conftest imports without error; collection shows no benchmark files yet (we haven't created any).

- [ ] **Step 3: Commit**

```bash
git add benchmarks/conftest.py
git commit -m "feat(benchmarks): add seven shared fixtures per spec §6.2"
```

---

## Task 3: Create `benchmarks/README.md`

**Files:**
- Create: `benchmarks/README.md`

- [ ] **Step 1: Write README**

```markdown
# HPyX Benchmarks

Local developer loop for measuring HPyX performance. Uses
`pytest-benchmark`. No CI gating, no dashboards — earn numbers via
measurement, don't assert them up front.

## Quick start

```bash
pixi run benchmark                            # Run full suite
pixi run -e benchmark-py313t pytest benchmarks/test_bench_kernels.py -v
bash scripts/run_bench_local.sh compare       # Compare vs stored baseline
bash scripts/run_bench_local.sh record benchmarks/test_bench_parallel.py::test_for_loop_par_1M
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
    pytest benchmarks/test_bench_kernels.py::test_dot_1M -v
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
    -m pytest benchmarks/test_bench_executor.py::test_executor_map_coarse
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
```

- [ ] **Step 2: Commit**

```bash
git add benchmarks/README.md
git commit -m "docs(benchmarks): add README with authoring contract and profiling recipes"
```

---

## Task 4: Create `scripts/run_bench_local.sh`

**Files:**
- Create: `scripts/run_bench_local.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# scripts/run_bench_local.sh — local developer loop for HPyX benchmarks.
#
# Subcommands:
#   bench [pytest args]     Run the full suite
#   record <test-id>        py-spy flame graph on one test
#   compare                 Compare vs stored baseline
#
# Requires: pixi, py-spy (for record).

set -euo pipefail

subcommand="${1:-}"
shift || true

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

case "$subcommand" in
    bench)
        exec pixi run -e benchmark-py313t pytest benchmarks/ \
            --benchmark-only \
            --benchmark-min-rounds=5 \
            --benchmark-warmup=on \
            --benchmark-autosave \
            "$@"
        ;;

    record)
        test_id="${1:-}"
        if [ -z "$test_id" ]; then
            echo "usage: run_bench_local.sh record <test-id>" >&2
            echo "example: run_bench_local.sh record benchmarks/test_bench_kernels.py::test_dot_1M" >&2
            exit 2
        fi
        output="flame-$(date +%Y%m%d-%H%M%S).svg"
        echo "Recording to $output ..."
        exec py-spy record --native --rate 500 -o "$output" -- \
            pixi run -e benchmark-py313t pytest "$test_id" -v --benchmark-only
        ;;

    compare)
        exec pixi run -e benchmark-py313t pytest-benchmark compare \
            --sort=name
        ;;

    *)
        echo "usage: run_bench_local.sh {bench|record|compare} [args]" >&2
        echo >&2
        echo "  bench [args]        Run full suite with repo defaults" >&2
        echo "  record <test-id>    py-spy native flame graph on one test" >&2
        echo "  compare             pytest-benchmark compare vs stored baseline" >&2
        exit 2
        ;;
esac
```

- [ ] **Step 2: Make executable and smoke-test**

```bash
chmod +x scripts/run_bench_local.sh
bash scripts/run_bench_local.sh    # prints usage
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run_bench_local.sh
git commit -m "feat(scripts): add run_bench_local.sh with bench/record/compare subcommands"
```

---

## Task 5: Replace `benchmarks/test_bench_for_loop.py` with `test_bench_parallel.py`

**Files:**
- Create: `benchmarks/test_bench_parallel.py`
- Delete: `benchmarks/test_bench_for_loop.py` (if it exists from v0.x)

- [ ] **Step 1: Delete the old file**

```bash
git rm benchmarks/test_bench_for_loop.py 2>/dev/null || true
```

- [ ] **Step 2: Write the new file**

```python
"""Benchmarks for hpyx.parallel — for_loop, for_each, transform, reduce.

Authoring contract: this file demonstrates all seven rules from
benchmarks/README.md. Subsequent benchmark files should follow the
same shape.

Callback overhead disclosure: each parallel algorithm below invokes a
Python lambda per element. On GIL-mode 3.13 this serializes; on 3.13t
it truly parallelizes. We compare against ThreadPoolExecutor to show
the HPyX advantage under 3.13t.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

import hpyx
from hpyx.execution import par, seq, static_chunk_size

pytestmark = pytest.mark.benchmark(group="parallel.for_loop")


SIZES = [1_000, 100_000, 10_000_000]


@pytest.mark.parametrize("size", SIZES)
def test_for_loop_par_hpyx(benchmark, size):
    """HPyX parallel for_loop with a trivial Python body."""
    arr = np.zeros(size, dtype=np.int64)

    def body(i):
        arr[i] = i

    benchmark(lambda: hpyx.parallel.for_loop(par, 0, size, body))


@pytest.mark.parametrize("size", SIZES)
def test_for_loop_seq_hpyx(benchmark, size):
    """HPyX seq for_loop — same body, sequential execution."""
    arr = np.zeros(size, dtype=np.int64)

    def body(i):
        arr[i] = i

    benchmark(lambda: hpyx.parallel.for_loop(seq, 0, size, body))


@pytest.mark.parametrize("size", SIZES)
def test_for_loop_pure_python(benchmark, size):
    """Pure-Python baseline: `for i in range(N)`."""
    arr = np.zeros(size, dtype=np.int64)

    def run():
        for i in range(size):
            arr[i] = i

    benchmark(run)


@pytest.mark.parametrize("size", SIZES)
def test_for_loop_numpy_vectorized(benchmark, size):
    """NumPy baseline: vectorized arange assignment (fastest possible)."""
    arr = np.zeros(size, dtype=np.int64)

    def run():
        arr[:] = np.arange(size)

    benchmark(run)


@pytest.mark.parametrize("size", SIZES)
def test_for_loop_threadpool(benchmark, size):
    """ThreadPoolExecutor baseline — a ceiling on what naive users reach for.

    Note: this is NOT a fair parallel comparison under GIL-mode CPython,
    because the Python callback cannot run concurrently. Under 3.13t it
    approaches real concurrency.
    """
    arr = np.zeros(size, dtype=np.int64)

    def body(i):
        arr[i] = i

    def run():
        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(body, range(size)))

    benchmark(run)


# ---- reduce benchmarks ----

pytestmark_reduce = pytest.mark.benchmark(group="parallel.reduce")
import operator


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_par_hpyx(benchmark, size):
    data = list(range(size))
    benchmark(
        hpyx.parallel.reduce, par, data, init=0, op=operator.add
    )


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_pure_python(benchmark, size):
    data = list(range(size))
    benchmark(sum, data)


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_numpy(benchmark, size):
    data = np.arange(size)
    benchmark(lambda: int(data.sum()))
```

- [ ] **Step 3: Run**

```bash
pixi run -e benchmark-py313t pytest benchmarks/test_bench_parallel.py -v --benchmark-only
```

Expected: all benchmarks run. Inspect the output table — HPyX should be slower than numpy on the vectorized path (expected; we're comparing apples and oranges for visibility) and faster than pure-Python at large sizes. `ThreadPoolExecutor` may be slower than HPyX on 3.13t due to submit overhead.

- [ ] **Step 4: Commit**

```bash
git add benchmarks/test_bench_parallel.py
git commit -m "feat(benchmarks): replace test_bench_for_loop with contract-compliant test_bench_parallel"
```

---

## Task 6: Create `benchmarks/test_bench_kernels.py`

**Files:**
- Create: `benchmarks/test_bench_kernels.py`

- [ ] **Step 1: Write the file**

```python
"""Benchmarks for hpyx.kernels — dot, matmul, sum, max, min.

Group per kernel. Each has three baselines: single-threaded numpy,
pure-Python, and ThreadPoolExecutor (where meaningful)."""

from __future__ import annotations

import numpy as np
import pytest

import hpyx


SIZES = [1_000, 100_000, 10_000_000]


# ---- dot ----

group_dot = pytest.mark.benchmark(group="kernels.dot")


@pytest.mark.parametrize("size", SIZES)
@group_dot
def test_dot_hpyx(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    b = np.random.rand(size).astype(np.float64)
    benchmark(hpyx.kernels.dot, a, b)


@pytest.mark.parametrize("size", SIZES)
@group_dot
def test_dot_numpy(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    b = np.random.rand(size).astype(np.float64)
    benchmark(np.dot, a, b)


@pytest.mark.parametrize("size", SIZES)
@group_dot
def test_dot_pure_python(benchmark, size):
    a = np.random.rand(size).astype(np.float64).tolist()
    b = np.random.rand(size).astype(np.float64).tolist()
    benchmark(lambda: sum(x * y for x, y in zip(a, b)))


# ---- matmul ----

group_matmul = pytest.mark.benchmark(group="kernels.matmul")
MATMUL_SIZES = [64, 256, 1024]


@pytest.mark.parametrize("n", MATMUL_SIZES)
@group_matmul
def test_matmul_hpyx(benchmark, n):
    A = np.random.rand(n, n).astype(np.float64)
    B = np.random.rand(n, n).astype(np.float64)
    benchmark(hpyx.kernels.matmul, A, B)


@pytest.mark.parametrize("n", MATMUL_SIZES)
@group_matmul
def test_matmul_numpy(benchmark, n):
    A = np.random.rand(n, n).astype(np.float64)
    B = np.random.rand(n, n).astype(np.float64)
    benchmark(lambda: A @ B)


# ---- sum / max / min ----

group_sum = pytest.mark.benchmark(group="kernels.sum")


@pytest.mark.parametrize("size", SIZES)
@group_sum
def test_sum_hpyx(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(hpyx.kernels.sum, a)


@pytest.mark.parametrize("size", SIZES)
@group_sum
def test_sum_numpy(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(np.sum, a)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.benchmark(group="kernels.max")
def test_max_hpyx(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(hpyx.kernels.max, a)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.benchmark(group="kernels.max")
def test_max_numpy(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(np.max, a)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.benchmark(group="kernels.min")
def test_min_hpyx(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(hpyx.kernels.min, a)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.benchmark(group="kernels.min")
def test_min_numpy(benchmark, size):
    a = np.random.rand(size).astype(np.float64)
    benchmark(np.min, a)
```

- [ ] **Step 2: Run + commit**

```bash
pixi run -e benchmark-py313t pytest benchmarks/test_bench_kernels.py -v --benchmark-only
git add benchmarks/test_bench_kernels.py
git commit -m "feat(benchmarks): add kernels benchmarks — dot, matmul, sum, max, min vs numpy"
```

---

## Task 7: Create `benchmarks/test_bench_executor.py`

```python
"""HPXExecutor.map vs ThreadPoolExecutor vs ProcessPoolExecutor.

Group: executor.map. Highlights free-threaded advantage — on 3.13t,
HPXExecutor.map with Python callbacks scales (other executors don't)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import pytest

import hpyx

pytestmark = pytest.mark.benchmark(group="executor.map")

SIZES = [100, 1_000, 10_000]


def _cpu_bound(x):
    s = 0
    for i in range(1000):
        s += (i ^ x) & 0xFF
    return s


@pytest.mark.parametrize("n", SIZES)
def test_executor_map_hpyx(benchmark, n):
    with hpyx.HPXExecutor() as ex:
        benchmark(lambda: list(ex.map(_cpu_bound, range(n))))


@pytest.mark.parametrize("n", SIZES)
def test_executor_map_threadpool(benchmark, n):
    with ThreadPoolExecutor(max_workers=4) as ex:
        benchmark(lambda: list(ex.map(_cpu_bound, range(n))))


@pytest.mark.parametrize("n", SIZES)
def test_executor_map_processpool(benchmark, n):
    # Process pool adds pickling + IPC overhead — small-N is often slower
    # than single-threaded. Included to show the tradeoff.
    with ProcessPoolExecutor(max_workers=4) as ex:
        benchmark(lambda: list(ex.map(_cpu_bound, range(n))))


@pytest.mark.parametrize("n", SIZES)
def test_executor_map_single_threaded(benchmark, n):
    benchmark(lambda: list(map(_cpu_bound, range(n))))
```

Commit: `feat(benchmarks): add executor.map benchmarks`.

---

## Task 8: Create `benchmarks/test_bench_futures.py`

```python
"""Future / dataflow throughput benchmarks."""

from __future__ import annotations

import pytest

import hpyx

pytestmark = pytest.mark.benchmark(group="futures")


def test_async_plus_get_overhead(benchmark):
    """Single async_ + result(). Measures fixed per-call overhead."""
    benchmark(lambda: hpyx.async_(lambda: 0).result())


def test_async_plus_get_pure_python(benchmark):
    """Pure-Python baseline — calling a no-op function directly."""
    benchmark(lambda: (lambda: 0)())


def test_then_chain_depth_10(benchmark):
    def chain():
        f = hpyx.async_(lambda: 0)
        for _ in range(10):
            f = f.then(lambda _: 0)
        return f.result()
    benchmark(chain)


@pytest.mark.parametrize("width", [10, 100, 1000])
def test_dataflow_fan_in(benchmark, width):
    def run():
        futs = [hpyx.async_(lambda i=i: i) for i in range(width)]
        return hpyx.dataflow(lambda *xs: sum(xs), *futs).result()
    benchmark(run)


@pytest.mark.parametrize("width", [10, 100, 1000])
def test_when_all_fan_in(benchmark, width):
    def run():
        futs = [hpyx.async_(lambda i=i: i) for i in range(width)]
        return hpyx.when_all(*futs).result()
    benchmark(run)
```

Commit: `feat(benchmarks): add futures/dataflow throughput benchmarks`.

---

## Task 9: Create `benchmarks/test_bench_aio.py`

```python
"""asyncio bridge overhead benchmarks."""

from __future__ import annotations

import asyncio

import pytest

import hpyx

pytestmark = pytest.mark.benchmark(group="aio")


def test_await_future_overhead(benchmark):
    async def run():
        fut = hpyx.async_(lambda: 0)
        return await fut
    benchmark(lambda: asyncio.run(run()))


def test_wrap_future_overhead(benchmark):
    async def run():
        fut = hpyx.async_(lambda: 0)
        return await asyncio.wrap_future(fut)
    benchmark(lambda: asyncio.run(run()))


@pytest.mark.parametrize("width", [10, 100])
def test_aio_await_all(benchmark, width):
    async def run():
        futs = [hpyx.async_(lambda i=i: i) for i in range(width)]
        return await hpyx.aio.await_all(*futs)
    benchmark(lambda: asyncio.run(run()))
```

Commit: `feat(benchmarks): add aio overhead benchmarks`.

---

## Task 10: Create `benchmarks/test_bench_thread_scaling.py` (dedicated)

**Files:**
- Create: `benchmarks/test_bench_thread_scaling.py`

This file needs to vary `os_threads` across parametrizations but HPX can't restart within a process. We handle this by running each parametrization in a subprocess via pytest-xdist-style isolation (or accept that only the session-wide thread count is measurable — and instead simulate scaling by submitting varying workloads).

The pragmatic choice: **parametrize the number of SIMULTANEOUS outstanding tasks**, not the `os_threads`. This still reveals scheduler behavior and parallelism.

```python
"""Thread-scaling microbenchmarks.

Note on restart: HPX cannot restart within a process, so this file does
NOT vary os_threads across parametrizations. Instead, it runs a fixed
work set with the session's os_threads=4 and parametrizes the number of
simultaneous tasks. True os_threads sweep requires a subprocess harness
(see test_bench_cold_start.py for an example of the pattern).
"""

from __future__ import annotations

import pytest

import hpyx
from hpyx.execution import par

pytestmark = pytest.mark.benchmark(group="thread_scaling")


@pytest.mark.parametrize("work", [1_000, 10_000, 100_000, 1_000_000])
def test_for_loop_scaling_workload(benchmark, work):
    def body(i):
        # trivial spin
        pass
    benchmark(lambda: hpyx.parallel.for_loop(par, 0, work, body))
```

Commit: `feat(benchmarks): add thread_scaling (workload-parametrized)`.

---

## Task 11: Create `benchmarks/test_bench_free_threading.py`

**Files:**
- Create: `benchmarks/test_bench_free_threading.py`

```python
"""Nogil smoke benchmark — proves parallel.for_loop scales with a Python body on 3.13t."""

from __future__ import annotations

import sysconfig

import pytest

import hpyx
from hpyx.execution import par, seq

pytestmark = [
    pytest.mark.benchmark(group="free_threading"),
    pytest.mark.skipif(
        not sysconfig.get_config_var("Py_GIL_DISABLED"),
        reason="Requires free-threaded Python 3.13t",
    ),
]


def _body(i):
    # Give each iteration enough work to amortize the GIL-acquire cost.
    s = 0
    for _ in range(500):
        s += i
    return s


def test_for_loop_par_nogil(benchmark):
    """Parallel for_loop with Python body under 3.13t.

    Under GIL-mode 3.13, this would serialize. Under 3.13t it scales.
    Compare this test's mean vs test_for_loop_seq_nogil (same work,
    seq policy) — the speedup is the free-threaded win.
    """
    benchmark(lambda: hpyx.parallel.for_loop(par, 0, 10_000, _body))


def test_for_loop_seq_nogil(benchmark):
    benchmark(lambda: hpyx.parallel.for_loop(seq, 0, 10_000, _body))
```

Commit: `feat(benchmarks): add free-threading smoke test`.

---

## Task 12: Create `benchmarks/test_bench_cold_start.py` (dedicated)

**Files:**
- Create: `benchmarks/test_bench_cold_start.py`

This file must measure cold `HPXRuntime()` start/stop, which means it CANNOT use the session `hpx_runtime` fixture. It uses subprocess isolation.

```python
"""Cold-start microbenchmark.

Measures the wall-clock cost of a fresh HPyX runtime init/shutdown in
an isolated subprocess. This is the only Phase-3 benchmark that opts
out of the session `hpx_runtime` fixture — it measures what the
fixture is hiding.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.benchmark(group="cold_start")


def _run_cold_start_subprocess():
    """Run a fresh interpreter + hpyx.init()/shutdown(), return elapsed seconds."""
    code = """
import time
import hpyx
t0 = time.perf_counter()
hpyx.init(os_threads=4)
hpyx.shutdown()
print(time.perf_counter() - t0)
""".strip()
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return float(result.stdout.strip())


def test_cold_start_init_and_shutdown(benchmark):
    """One init + one shutdown in a fresh interpreter."""
    benchmark.pedantic(
        _run_cold_start_subprocess,
        rounds=5,
        iterations=1,
    )
```

Note: this is not a "microbenchmark" in the typical sense — each measurement spawns a new Python process. But it's the only way to measure cold-start without HPX's cannot-restart constraint breaking the measurement.

Commit: `feat(benchmarks): add cold-start measurement (subprocess-isolated)`.

---

## Task 13: Implement real `hpyx.debug.enable_tracing`

**Files:**
- Create: `src/_core/tracing.hpp`
- Create: `src/_core/tracing.cpp`
- Modify: `src/_core/bind.cpp` (register submodule)
- Modify: `src/_core/futures.cpp` (record `async_submit` events)
- Modify: `src/hpyx/debug.py` (replace stubs with real impl)
- Modify: `tests/test_debug.py` (replace xfail with real tests)

Design: a thread-safe ring buffer of `TraceEvent` structs on the C++ side. Python side drains and flushes to JSONL on timer or on disable.

- [ ] **Step 1: Write `src/_core/tracing.hpp`**

```cpp
#pragma once

#include <nanobind/nanobind.h>

#include <atomic>
#include <cstdint>
#include <string>

namespace hpyx::tracing {

struct TraceEvent {
    std::string name;
    std::int64_t worker_thread_id;
    std::int64_t start_ns;   // steady_clock since init
    std::int64_t duration_ns;
};

// Global enable flag — zero-cost when disabled (one atomic load).
extern std::atomic<bool> g_enabled;

inline bool is_enabled() { return g_enabled.load(std::memory_order_acquire); }

void record(TraceEvent event);

void register_bindings(nanobind::module_& m);

}  // namespace hpyx::tracing
```

- [ ] **Step 2: Write `src/_core/tracing.cpp`**

```cpp
#include "tracing.hpp"
#include "runtime.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <atomic>
#include <chrono>
#include <mutex>
#include <vector>

namespace nb = nanobind;
using namespace nb::literals;

namespace hpyx::tracing {

std::atomic<bool> g_enabled{false};

namespace {
std::mutex g_mtx;
std::vector<TraceEvent> g_buffer;
}  // namespace

void record(TraceEvent event) {
    if (!is_enabled()) return;
    std::lock_guard<std::mutex> lk(g_mtx);
    g_buffer.push_back(std::move(event));
}

static void enable() {
    g_enabled.store(true, std::memory_order_release);
}

static void disable() {
    g_enabled.store(false, std::memory_order_release);
}

static std::vector<TraceEvent> drain() {
    std::vector<TraceEvent> out;
    std::lock_guard<std::mutex> lk(g_mtx);
    std::swap(out, g_buffer);
    return out;
}

void register_bindings(nb::module_& m) {
    nb::class_<TraceEvent>(m, "TraceEvent")
        .def_ro("name", &TraceEvent::name)
        .def_ro("worker_thread_id", &TraceEvent::worker_thread_id)
        .def_ro("start_ns", &TraceEvent::start_ns)
        .def_ro("duration_ns", &TraceEvent::duration_ns);
    m.def("enable", &enable);
    m.def("disable", &disable);
    m.def("is_enabled", &is_enabled);
    m.def("drain", &drain);
}

}  // namespace hpyx::tracing
```

- [ ] **Step 3: Hook tracing into `src/_core/futures.cpp::async_submit`**

Find `make_python_task` and `async_submit`. Replace `async_submit` with:

```cpp
static HPXFuture async_submit(nb::callable fn, nb::args args, nb::kwargs kwargs) {
    if (!hpyx::runtime::runtime_is_running()) {
        throw std::runtime_error(
            "HPyX runtime is not running. Call hpyx.init() first.");
    }
    auto policy = resolve_launch_policy();

    // Capture task name (fn.__name__ or repr) for tracing.
    std::string task_name;
    if (hpyx::tracing::is_enabled()) {
        nb::gil_scoped_acquire acquire;
        try {
            task_name = nb::cast<std::string>(fn.attr("__name__"));
        } catch (...) {
            task_name = "<anonymous>";
        }
    }

    auto task = [fn, args, kwargs, task_name]() -> nb::object {
        auto start = std::chrono::steady_clock::now();
        nb::gil_scoped_acquire acquire;
        nb::object result;
        try {
            result = fn(*args, **kwargs);
        } catch (nb::python_error& e) {
            e.restore();
            throw;
        }
        if (hpyx::tracing::is_enabled()) {
            auto end = std::chrono::steady_clock::now();
            hpyx::tracing::record(hpyx::tracing::TraceEvent{
                task_name,
                static_cast<std::int64_t>(hpx::get_worker_thread_num()),
                std::chrono::duration_cast<std::chrono::nanoseconds>(
                    start.time_since_epoch()).count(),
                std::chrono::duration_cast<std::chrono::nanoseconds>(
                    end - start).count(),
            });
        }
        return result;
    };
    nb::gil_scoped_release release;
    auto fut = hpx::async(policy, std::move(task)).share();
    return HPXFuture(std::move(fut));
}
```

Add `#include "tracing.hpp"` to `futures.cpp`.

- [ ] **Step 4: Register tracing submodule in `bind.cpp`**

```cpp
auto m_tracing = m.def_submodule("tracing");
hpyx::tracing::register_bindings(m_tracing);
```

Add `#include "tracing.hpp"`.

- [ ] **Step 5: Update CMakeLists.txt**

```cmake
nanobind_add_module(
    _core FREE_THREADED
    src/_core/bind.cpp
    src/_core/runtime.cpp
    src/_core/futures.cpp
    src/_core/parallel.cpp
    src/_core/kernels.cpp
    src/_core/tracing.cpp
)
```

- [ ] **Step 6: Replace stubs in `src/hpyx/debug.py`**

```python
from __future__ import annotations

import json
import threading
import time
from typing import Optional, TextIO

from hpyx import _core, _runtime


def get_num_worker_threads() -> int:
    _runtime.ensure_started()
    return int(_core.runtime.num_worker_threads())


def get_worker_thread_id() -> int:
    _runtime.ensure_started()
    return int(_core.runtime.get_worker_thread_id())


_trace_state = {
    "enabled": False,
    "path": None,
    "file": None,
    "thread": None,
    "stop": None,
}


def _drain_loop(path: str, stop_event: threading.Event) -> None:
    """Background thread: periodically drain C++ ring buffer to JSONL."""
    with open(path, "a", encoding="utf-8") as f:
        while not stop_event.is_set():
            events = _core.tracing.drain()
            for ev in events:
                f.write(json.dumps({
                    "name": ev.name,
                    "worker_thread_id": ev.worker_thread_id,
                    "start_ns": ev.start_ns,
                    "duration_ns": ev.duration_ns,
                }) + "\n")
            f.flush()
            stop_event.wait(timeout=0.1)
        # Final drain.
        for ev in _core.tracing.drain():
            f.write(json.dumps({
                "name": ev.name,
                "worker_thread_id": ev.worker_thread_id,
                "start_ns": ev.start_ns,
                "duration_ns": ev.duration_ns,
            }) + "\n")


def enable_tracing(path: Optional[str] = None) -> None:
    """Start capturing per-task trace events to a JSONL file.

    Parameters
    ----------
    path : str | None
        File path to write events to. If None, uses HPYX_TRACE_PATH env
        var or raises.
    """
    if _trace_state["enabled"]:
        raise RuntimeError("tracing is already enabled — call disable_tracing first")

    import os
    if path is None:
        path = os.environ.get("HPYX_TRACE_PATH")
    if path is None:
        raise ValueError(
            "enable_tracing requires a path argument or HPYX_TRACE_PATH env var"
        )

    _runtime.ensure_started()
    _core.tracing.enable()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_drain_loop, args=(path, stop_event), daemon=True,
    )
    thread.start()

    _trace_state["enabled"] = True
    _trace_state["path"] = path
    _trace_state["thread"] = thread
    _trace_state["stop"] = stop_event


def disable_tracing() -> None:
    """Stop capturing. Flushes buffered events to the output file."""
    if not _trace_state["enabled"]:
        return

    _core.tracing.disable()
    _trace_state["stop"].set()
    _trace_state["thread"].join(timeout=5.0)

    _trace_state["enabled"] = False
    _trace_state["path"] = None
    _trace_state["thread"] = None
    _trace_state["stop"] = None


__all__ = [
    "disable_tracing",
    "enable_tracing",
    "get_num_worker_threads",
    "get_worker_thread_id",
]
```

- [ ] **Step 7: Replace tests in `tests/test_debug.py`**

Remove the xfail markers on `enable_tracing`/`disable_tracing`. Add real tests:

```python
def test_enable_tracing_writes_jsonl(tmp_path):
    import json
    path = str(tmp_path / "trace.jsonl")
    hpyx.debug.enable_tracing(path)
    try:
        def work(x):
            return x * 2
        fut = hpyx.async_(work, 42)
        assert fut.result() == 84
        # Give the drain thread time to flush.
        import time
        time.sleep(0.3)
    finally:
        hpyx.debug.disable_tracing()

    lines = open(path).read().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event["name"] == "work"
    assert event["worker_thread_id"] >= 0
    assert event["duration_ns"] > 0


def test_enable_tracing_without_path_or_env_raises():
    import os
    os.environ.pop("HPYX_TRACE_PATH", None)
    with pytest.raises(ValueError, match="path"):
        hpyx.debug.enable_tracing()


def test_enable_tracing_twice_raises(tmp_path):
    path = str(tmp_path / "trace.jsonl")
    hpyx.debug.enable_tracing(path)
    try:
        with pytest.raises(RuntimeError, match="already enabled"):
            hpyx.debug.enable_tracing(path)
    finally:
        hpyx.debug.disable_tracing()


def test_disable_tracing_idempotent():
    hpyx.debug.disable_tracing()  # noop
    hpyx.debug.disable_tracing()  # still noop
```

Remove the old `test_enable_tracing_is_stubbed` / `test_disable_tracing_is_stubbed` tests.

- [ ] **Step 8: Rebuild + test + commit**

```bash
pixi run -e test-py313t pip install --force-reinstall --no-build-isolation -ve .
pixi run -e test-py313t pytest tests/test_debug.py -v
git add -A
git commit -m "feat(debug): implement enable_tracing writing JSONL per-task events"
```

---

## Task 14: Final benchmark run + PR

- [ ] **Step 1: Run the entire benchmark suite**

```bash
bash scripts/run_bench_local.sh bench
```

Expected: all benchmarks complete, pytest-benchmark prints a summary table grouped by `group=...`.

- [ ] **Step 2: Smoke-test record**

```bash
bash scripts/run_bench_local.sh record benchmarks/test_bench_kernels.py::test_dot_hpyx -k "size0"
```

Expected: produces `flame-YYYYMMDD-HHMMSS.svg` with resolved C++ frames (look for `hpx::transform_reduce` in the graph).

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/v1-phase-3-benchmarks-diagnostics
gh pr create --draft --title "feat(benchmarks,debug): v1 Phase 3" --body "$(cat <<'EOF'
## Summary

- `benchmarks/conftest.py` with the seven shared fixtures
- `benchmarks/README.md` with authoring contract + profiling recipes
- `scripts/run_bench_local.sh` with bench/record/compare subcommands
- Replaced `test_bench_for_loop.py` with contract-compliant `test_bench_parallel.py`
- Six new benchmark files (kernels, executor, futures, aio, thread_scaling, free_threading, cold_start)
- Real `hpyx.debug.enable_tracing` writing JSONL per-task events (backed by a thread-safe ring buffer in `src/_core/tracing.cpp`)

## Spec

§ 4.9 (debug), § 6.2 (benchmark infra), § 6.5 risks 11-14

## Test plan

- [x] `pixi run -e test-py313t pytest tests/test_debug.py` — tracing works end-to-end
- [x] `bash scripts/run_bench_local.sh bench` — full suite runs without error
- [x] `bash scripts/run_bench_local.sh record <id>` — produces flamegraph
- [x] `bash scripts/run_bench_local.sh compare` — no stored baseline yet, graceful message

## What's NOT in this PR

- asv / pyperf / CI gating (Phase 1+ per spec)
- Docs (Plan 5)
- CI matrix updates (Plan 5)
EOF
)"
```

---

## Self-review notes

**Spec coverage (Phase 3):**
- Spec §4.9 (debug module) — Task 13.
- Spec §6.2 (seven fixtures, authoring contract, profile preset) — Tasks 2, 3, 4, 5.
- Spec §1.6 item 7 (basic diagnostics) — fully realized in Task 13.

**Placeholder scan:** None.

**Type consistency:**
- `TraceEvent` fields consistent between C++ (`src/_core/tracing.cpp`) and JSONL (`src/hpyx/debug.py`).
- Benchmark group names: `parallel.for_loop`, `parallel.reduce`, `kernels.dot`, `kernels.matmul`, `kernels.sum`, `kernels.max`, `kernels.min`, `executor.map`, `futures`, `aio`, `thread_scaling`, `free_threading`, `cold_start` — one per focus area.

**Known caveats:**
- Thread-scaling benchmark varies workload size, not `os_threads`, because HPX can't restart. True os_threads sweep is a subprocess harness (Phase 1+).
- Cold-start measurements include Python interpreter startup time (~100-300ms). Subtract a baseline `python -c "pass"` measurement to isolate the HPyX init cost.
- Tracing overhead is non-zero when enabled — benchmarks should run without `HPYX_TRACE_PATH` set.
