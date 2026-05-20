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
        pass  # trivial spin

    benchmark(lambda: hpyx.parallel.for_loop(par, 0, work, body))
