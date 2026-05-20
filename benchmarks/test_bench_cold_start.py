"""Cold-start microbenchmark.

Measures the wall-clock cost of a fresh HPyX runtime init/shutdown in
an isolated subprocess. This is the only Phase-3 benchmark that opts
out of the session `hpx_runtime` fixture — it measures what the
fixture is hiding.
"""

from __future__ import annotations

import subprocess
import sys

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
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def test_cold_start_init_and_shutdown(benchmark):
    """One init + one shutdown in a fresh interpreter."""
    benchmark.pedantic(
        _run_cold_start_subprocess,
        rounds=5,
        iterations=1,
    )
