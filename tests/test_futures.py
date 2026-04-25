"""Tests for hpyx.futures — HPXFuture class and combinators."""

import threading
import time

import pytest

import hpyx
from hpyx._core import futures as core_futures


# ---- HPXFuture construction and .result() ----

def test_ready_future_result_returns_immediately():
    fut = core_futures.ready_future(42)
    assert fut.result() == 42
    assert fut.done()


def test_ready_future_result_with_object():
    fut = core_futures.ready_future({"a": 1, "b": [2, 3]})
    assert fut.result() == {"a": 1, "b": [2, 3]}


def test_async_submit_runs_on_hpx_worker():
    captured_worker_id = []

    def body():
        captured_worker_id.append(hpyx.debug.get_worker_thread_id())
        return "ok"

    fut = core_futures.async_submit(body, (), {})
    assert fut.result() == "ok"
    # The callable ran on an HPX worker, so worker id must be in [0, N)
    assert captured_worker_id[0] >= 0
    assert captured_worker_id[0] < hpyx.debug.get_num_worker_threads()


def test_async_submit_preserves_exceptions():
    def boom():
        raise ValueError("boom")

    fut = core_futures.async_submit(boom, (), {})
    with pytest.raises(ValueError, match="boom"):
        fut.result()


def test_async_submit_exception_method():
    def boom():
        raise RuntimeError("xyz")

    fut = core_futures.async_submit(boom, (), {})
    exc = fut.exception()
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "xyz"


# ---- when_all / when_any / dataflow / shared_future ----


def test_when_all_returns_tuple_of_values():
    f1 = core_futures.ready_future(1)
    f2 = core_futures.ready_future(2)
    f3 = core_futures.ready_future(3)
    combined = core_futures.when_all([f1, f2, f3])
    assert combined.result() == (1, 2, 3)


def test_when_all_empty_input():
    combined = core_futures.when_all([])
    assert combined.result() == ()


def test_when_all_waits_for_slow_future():
    def slow():
        time.sleep(0.05)
        return "slow-result"

    fast = core_futures.ready_future("fast-result")
    slow_fut = core_futures.async_submit(slow, (), {})
    combined = core_futures.when_all([fast, slow_fut])
    assert combined.result() == ("fast-result", "slow-result")


def test_when_all_first_failure_surfaces():
    """Per spec §5.2: first-to-fail wins in when_all."""
    def boom():
        raise ValueError("first-failure")

    f_ok = core_futures.ready_future(42)
    f_bad = core_futures.async_submit(boom, (), {})
    combined = core_futures.when_all([f_ok, f_bad])
    with pytest.raises(ValueError, match="first-failure"):
        combined.result()


def test_when_any_returns_index_and_futures_list():
    def slow():
        time.sleep(0.5)
        return "slow"

    f_slow = core_futures.async_submit(slow, (), {})
    f_fast = core_futures.ready_future("fast")
    result = core_futures.when_any([f_slow, f_fast]).result()
    idx, futures_list = result
    assert idx == 1  # the ready future is index 1
    assert futures_list[idx].result() == "fast"


def test_dataflow_combines_inputs_into_fn():
    f1 = core_futures.ready_future(10)
    f2 = core_futures.ready_future(20)

    def add(a, b):
        return a + b

    combined = core_futures.dataflow(add, [f1, f2])
    assert combined.result() == 30


def test_dataflow_with_three_inputs():
    f1 = core_futures.ready_future(1)
    f2 = core_futures.ready_future(2)
    f3 = core_futures.ready_future(3)

    def total(a, b, c):
        return a + b + c

    combined = core_futures.dataflow(total, [f1, f2, f3])
    assert combined.result() == 6


def test_dataflow_propagates_exception_from_input():
    """Per acceptance: dataflow handles exceptions from input futures
    (propagates without calling fn)."""
    sentinel = []

    def add(a, b):
        sentinel.append("called")
        return a + b

    def boom():
        raise ValueError("upstream")

    f_bad = core_futures.async_submit(boom, (), {})
    f_ok = core_futures.ready_future(1)
    combined = core_futures.dataflow(add, [f_bad, f_ok])
    with pytest.raises(ValueError, match="upstream"):
        combined.result()
    # fn should not have been invoked
    assert sentinel == []


def test_dataflow_propagates_exception_from_fn():
    f1 = core_futures.ready_future(1)
    f2 = core_futures.ready_future(2)

    def bad(a, b):
        raise RuntimeError("fn-error")

    combined = core_futures.dataflow(bad, [f1, f2])
    with pytest.raises(RuntimeError, match="fn-error"):
        combined.result()


def test_dataflow_passes_kwargs():
    f1 = core_futures.ready_future(2)
    f2 = core_futures.ready_future(3)

    def fn(a, b, *, scale=1, offset=0):
        return (a + b) * scale + offset

    out = core_futures.dataflow(fn, [f1, f2], {"scale": 10, "offset": 1})
    assert out.result() == 51


def test_shared_future_returns_future_with_same_value():
    """shared_future is a no-op since HPXFuture already wraps shared_future."""
    fut = core_futures.async_submit(lambda: 99, (), {})
    s = core_futures.shared_future(fut)
    assert s.result() == 99


def test_shared_future_can_be_consumed_twice():
    """shared_future result can be retrieved multiple times."""
    fut = core_futures.ready_future("hello")
    s = core_futures.shared_future(fut)
    assert s.result() == "hello"
    assert s.result() == "hello"
