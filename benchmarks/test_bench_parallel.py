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

import operator
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

import hpyx
from hpyx.execution import par, seq

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


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_par_hpyx(benchmark, size):
    """HPyX parallel reduce."""
    data = list(range(size))
    benchmark(
        hpyx.parallel.reduce, par, data, init=0, op=operator.add
    )


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_pure_python(benchmark, size):
    """Pure-Python sum baseline."""
    data = list(range(size))
    benchmark(sum, data)


@pytest.mark.parametrize("size", SIZES)
@pytestmark_reduce
def test_reduce_numpy(benchmark, size):
    """NumPy sum baseline."""
    data = np.arange(size)
    benchmark(lambda: int(data.sum()))
