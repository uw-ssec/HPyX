"""HPXExecutor.map vs ThreadPoolExecutor vs ProcessPoolExecutor.

Group: executor.map. Highlights free-threaded advantage — on 3.13t,
HPXExecutor.map with Python callbacks scales (other executors don't).
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

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
