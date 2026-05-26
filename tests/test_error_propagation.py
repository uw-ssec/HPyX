"""Verify exceptions propagate correctly through the full surface."""

import pytest

import hpyx
from hpyx.execution import par


def test_exception_through_then_chain():
    def boom():
        raise ValueError("top")

    # Per spec §5.2: .then's fn is NOT invoked when upstream raises.
    fut = hpyx.async_(boom).then(lambda f: f.result() + 1)
    with pytest.raises(ValueError, match="top"):
        fut.result()


def test_exception_in_then_callback_propagates():
    def boom(f):
        raise RuntimeError("in-then")

    fut = hpyx.async_(lambda: 0).then(boom)
    with pytest.raises(RuntimeError, match="in-then"):
        fut.result()


def test_exception_in_dataflow_input_propagates():
    def ok():
        return 1

    def boom():
        raise KeyError("from-input")

    out = hpyx.dataflow(lambda a, b: a + b,
                        hpyx.async_(ok), hpyx.async_(boom))
    with pytest.raises(KeyError, match="from-input"):
        out.result()


def test_exception_in_parallel_for_loop_propagates():
    def body(i):
        if i == 50:
            raise ValueError(f"iter-{i}")

    with pytest.raises((ValueError, RuntimeError), match="iter-"):
        hpyx.parallel.for_loop(par, 0, 100, body)


def test_kernel_shape_mismatch_raises_synchronously():
    import numpy as np
    a = np.ones(10, dtype=np.float64)
    b = np.ones(11, dtype=np.float64)
    with pytest.raises((ValueError, Exception), match="size|shape|length"):
        hpyx.kernels.dot(a, b)


def test_exception_propagates_through_when_all():
    def fast_boom():
        raise ValueError("fast")

    f1 = hpyx.async_(fast_boom)
    f2 = hpyx.async_(lambda: 42)
    with pytest.raises((ValueError, RuntimeError)):
        hpyx.when_all(f1, f2).result()
