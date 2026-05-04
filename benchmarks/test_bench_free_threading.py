"""Nogil smoke benchmark — proves parallel.for_loop scales with a Python body on 3.13t."""

from __future__ import annotations

import sysconfig

import pytest

import hpyx
from hpyx.execution import par, seq

pytestmark = [
    pytest.mark.benchmark(group="free_threading"),
    pytest.mark.skipif(
        not sysconfig.get_config_var("Py_GIL_DISABLED"),
        reason="Requires free-threaded Python 3.13t",
    ),
]


def _body(i):
    # Give each iteration enough work to amortize the GIL-acquire cost.
    s = 0
    for _ in range(500):
        s += i
    return s


def test_for_loop_par_nogil(benchmark):
    """Parallel for_loop with Python body under 3.13t.

    Under GIL-mode 3.13, this would serialize. Under 3.13t it scales.
    Compare this test's mean vs test_for_loop_seq_nogil (same work,
    seq policy) — the speedup is the free-threaded win.
    """
    benchmark(lambda: hpyx.parallel.for_loop(par, 0, 10_000, _body))


def test_for_loop_seq_nogil(benchmark):
    benchmark(lambda: hpyx.parallel.for_loop(seq, 0, 10_000, _body))
