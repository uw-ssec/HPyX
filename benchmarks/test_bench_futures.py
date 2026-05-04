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
