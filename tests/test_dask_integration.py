"""Smoke test for dask + hpyx.HPXExecutor integration (user story #8)."""

from __future__ import annotations

import pytest

pytest.importorskip("dask")
pytest.importorskip("dask.array")
pytest.importorskip("numpy")

import dask.array as da
import numpy as np
from dask import delayed

import hpyx


def test_dask_array_sum_via_HPXExecutor():
    """The headline integration: dask.array.sum via HPXExecutor scheduler."""
    with hpyx.HPXExecutor() as ex:
        x = da.arange(1000, chunks=100)
        result = x.sum().compute(scheduler=ex)
    assert int(result) == sum(range(1000))


def test_dask_array_matmul_via_HPXExecutor():
    """Non-trivial graph: chunked matmul produces correct result."""
    rng = np.random.default_rng(42)
    a_np = rng.random((64, 64))
    b_np = rng.random((64, 64))
    a = da.from_array(a_np, chunks=(16, 16))
    b = da.from_array(b_np, chunks=(16, 16))

    with hpyx.HPXExecutor() as ex:
        c = (a @ b).compute(scheduler=ex)

    np.testing.assert_allclose(c, a_np @ b_np, rtol=1e-10)


def test_dask_delayed_chain_via_HPXExecutor():
    """Dask's delayed graph compiles to futures and runs through HPXExecutor."""

    @delayed
    def inc(x):
        return x + 1

    @delayed
    def total(xs):
        return sum(xs)

    results = [inc(i) for i in range(10)]
    final = total(results)

    with hpyx.HPXExecutor() as ex:
        assert final.compute(scheduler=ex) == sum(range(1, 11))


def test_dask_array_reduction_via_HPXExecutor():
    """Multi-stage reduction graph (mean -> variance) succeeds end-to-end."""
    rng = np.random.default_rng(0)
    arr_np = rng.random(10_000)
    arr = da.from_array(arr_np, chunks=1000)

    with hpyx.HPXExecutor() as ex:
        mean = arr.mean().compute(scheduler=ex)
        var = arr.var().compute(scheduler=ex)

    np.testing.assert_allclose(mean, arr_np.mean(), rtol=1e-10)
    np.testing.assert_allclose(var, arr_np.var(), rtol=1e-10)
