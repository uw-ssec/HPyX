"""Benchmarks for hpyx.kernels — dot, matmul, sum, max, min.

Group per kernel. Each has three baselines: single-threaded numpy,
pure-Python, and ThreadPoolExecutor (where meaningful).
"""

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


# ---- sum ----

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


# ---- max ----

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


# ---- min ----

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
