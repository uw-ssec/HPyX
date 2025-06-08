from __future__ import annotations

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

import hpyx
from hpyx.runtime import HPXRuntime


@pytest.mark.parametrize("v_len", range(100_000_000, 600_000_000, 100_000_000))
def test_bench_hpx_dot1d(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with HPXRuntime():
        _ = benchmark(hpyx._core.dot1d, A, B)


@pytest.mark.parametrize("v_len", range(100_000_000, 600_000_000, 100_000_000))
def test_bench_np_dot1d(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    _ = benchmark(np.dot, A, B)


@pytest.mark.skip
@pytest.mark.parametrize("v_len", range(200_000_000, 400_000_000, 100_000_000))
def test_bench_hpx_dot1d_force_single_thread(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with HPXRuntime(os_threads=1):
        _ = benchmark(hpyx._core.dot1d, A, B)


@pytest.mark.skip
@pytest.mark.parametrize("v_len", range(200_000_000, 400_000_000, 100_000_000))
def test_bench_np_dot1d_force_single_threaded(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with threadpool_limits(limits=1):
        _ = benchmark(np.dot, A, B)


@pytest.mark.parametrize("v_len", range(10_000_000, 60_000_000, 10_000_000))
def test_bench_hpx_small_dot1d(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with HPXRuntime():
        _ = benchmark(hpyx._core.dot1d, A, B)


@pytest.mark.parametrize("v_len", range(10_000_000, 60_000_000, 10_000_000))
def test_bench_np_small_dot1d(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    _ = benchmark(np.dot, A, B)


@pytest.mark.parametrize("v_len", range(10_000_000, 60_000_000, 10_000_000))
def test_bench_hpx_dot1d_small_single_thread(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with HPXRuntime(os_threads=1):
        _ = benchmark(hpyx._core.dot1d, A, B)


@pytest.mark.parametrize("v_len", range(10_000_000, 60_000_000, 10_000_000))
def test_bench_np_dot1d_small_single_thread(benchmark, v_len):
    rng = np.random.default_rng()
    A = rng.random(v_len)  # dtype is float64
    B = rng.random(v_len)
    with threadpool_limits(limits=1):
        _ = benchmark(np.dot, A, B)
