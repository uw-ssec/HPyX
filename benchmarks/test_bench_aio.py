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
