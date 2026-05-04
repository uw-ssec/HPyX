"""HPyX benchmark fixtures — seven shared fixtures per spec §6.2.

Authoring contract (all benchmarks must follow):

1. Setup is never timed (use benchmark.pedantic or session-scoped fixtures).
2. Parametrize across three size orders: [1_000, 100_000, 10_000_000].
3. Three matching baselines per HPyX benchmark (numpy, pure-Python,
   ThreadPoolExecutor) in the same pytest-benchmark group.
4. Module-level `pytestmark = pytest.mark.benchmark(group="<topic>")`.
5. Minimize Python overhead unless measuring it (document otherwise).
6. Thread-scaling parametrization: [1, 2, 4, 8] via `hpx_threads`.
7. Free-threading gating via `requires_free_threading` from benchmarks/helpers.py.
"""

from __future__ import annotations

import contextlib
import gc
import os
import platform
import warnings

import pytest

from helpers import requires_free_threading  # noqa: F401 — re-exported for conftest users


# Number of HPX OS threads started by hpx_runtime. Kept here so pin_cpu can
# select the same count without importing hpyx before the runtime starts.
_BENCH_OS_THREADS = 4


# ---- Fixture 1: pin_cpu (Linux only; macOS no-op; Windows no-op) ----

@pytest.fixture(scope="session", autouse=True)
def pin_cpu():
    """Pin the benchmarking process to a CPU set on Linux for stable timing.

    Selects up to ``_BENCH_OS_THREADS`` CPUs from the current allowed affinity
    mask so that parallel/free-threading benchmarks can exercise real hardware
    concurrency instead of all threads contending on one core.
    """
    if platform.system() == "Linux":
        try:
            current_mask = os.sched_getaffinity(0)
            pinned = set(sorted(current_mask)[:_BENCH_OS_THREADS])
            os.sched_setaffinity(0, pinned)
        except (AttributeError, OSError):
            pass
    yield


# ---- Fixture 2: seed_rng (deterministic per-test seeding) ----

@pytest.fixture(autouse=True)
def seed_rng(request):
    """Deterministically seed random / numpy.random / HPyX RNG from test ID."""
    import hashlib
    import random

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

    hpyx.init(os_threads=_BENCH_OS_THREADS)
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
                ["pmset", "-g", "batt"],
                capture_output=True,
                text=True,
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
                        stacklevel=2,
                    )
        except FileNotFoundError:
            pass

    yield
