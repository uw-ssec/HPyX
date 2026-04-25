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
