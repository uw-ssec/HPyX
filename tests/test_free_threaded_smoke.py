"""Free-threaded race-detection smoke test.

Hammers hpyx.parallel and hpyx.kernels APIs concurrently from many
Python threads under free-threaded Python (Py_GIL_DISABLED=1) to surface
GIL-handling bugs, races, and segfaults. Skipped on GIL-enabled builds.
"""

from __future__ import annotations

import sys
import sysconfig
import threading

import numpy as np
import pytest

import hpyx
from hpyx import execution, kernels, parallel


def _gil_disabled() -> bool:
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED")) and not sys._is_gil_enabled()


pytestmark = pytest.mark.skipif(
    not _gil_disabled(),
    reason="Free-threaded smoke test requires Py_GIL_DISABLED build with GIL off",
)


N_THREADS = 8
N_ITERS = 50


def _hammer(target, *args):
    errors: list[BaseException] = []

    def worker():
        try:
            for _ in range(N_ITERS):
                target(*args)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, f"Worker errors: {errors[:3]}"


def test_parallel_for_each_concurrent():
    counter = [0]
    lock = threading.Lock()

    def inc(_x):
        with lock:
            counter[0] += 1

    _hammer(parallel.for_each, execution.par, list(range(64)), inc)
    assert counter[0] == N_THREADS * N_ITERS * 64


def test_parallel_transform_concurrent():
    def square(x):
        return x * x

    def go():
        result = parallel.transform(execution.par, range(32), square)
        assert result == [i * i for i in range(32)]

    _hammer(go)


def test_kernels_dot_concurrent():
    a = np.arange(1000, dtype=np.float64)
    b = np.arange(1000, dtype=np.float64)
    expected = float(np.dot(a, b))

    def go():
        assert kernels.dot(a, b) == pytest.approx(expected)

    _hammer(go)


def test_kernels_sum_concurrent():
    a = np.ones(10_000, dtype=np.float64)

    def go():
        assert kernels.sum(a) == pytest.approx(10_000.0)

    _hammer(go)


def test_kernels_min_max_concurrent():
    rng = np.random.default_rng(42)
    a = rng.standard_normal(5_000)
    expected_min = float(a.min())
    expected_max = float(a.max())

    def go():
        assert kernels.min(a) == pytest.approx(expected_min)
        assert kernels.max(a) == pytest.approx(expected_max)

    _hammer(go)


def test_mixed_workload_concurrent():
    """Mix kernels + parallel calls from many threads simultaneously."""
    a = np.arange(2000, dtype=np.float64)

    def workload():
        assert kernels.sum(a) == pytest.approx(float(a.sum()))
        result = parallel.transform(execution.par, range(16), lambda x: x + 1)
        assert result == list(range(1, 17))
        assert kernels.dot(a, a) == pytest.approx(float(np.dot(a, a)))

    _hammer(workload)


def test_runtime_started():
    """Sanity: ensure the runtime is actually running before the smoke test."""
    hpyx.init()
    assert hpyx.is_running()
