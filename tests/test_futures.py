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


# ---- Python Future wrapper (hpyx.Future, hpyx.async_) ----

def test_async_returns_hpyx_Future():
    fut = hpyx.async_(lambda: 42)
    assert isinstance(fut, hpyx.Future)
    assert fut.result() == 42


def test_Future_concurrent_futures_protocol():
    import concurrent.futures
    fut = hpyx.async_(lambda: "hi")
    for method in ("result", "exception", "done", "running", "cancelled",
                   "cancel", "add_done_callback"):
        assert callable(getattr(fut, method))
    assert fut.result() == "hi"


def test_Future_then_chain():
    fut = hpyx.async_(lambda: 10).then(lambda f: f.result() * 2).then(lambda f: f.result() + 1)
    assert fut.result() == 21


def test_when_all_free_function():
    f1 = hpyx.async_(lambda: 1)
    f2 = hpyx.async_(lambda: 2)
    assert hpyx.when_all(f1, f2).result() == (1, 2)


def test_dataflow_free_function():
    f1 = hpyx.async_(lambda: 3)
    f2 = hpyx.async_(lambda: 4)
    out = hpyx.dataflow(lambda a, b: a * b, f1, f2)
    assert out.result() == 12


def test_shared_future_is_idempotent():
    f = hpyx.async_(lambda: 99)
    s = hpyx.shared_future(f)
    assert s.result() == 99
    assert s.result() == 99  # can call twice


def test_ready_future_is_immediately_done():
    f = hpyx.ready_future(7)
    assert f.done()
    assert f.result() == 7


def test_async_with_args_and_kwargs():
    def worker(a, b, *, c=0):
        return a + b + c
    fut = hpyx.async_(worker, 1, 2, c=10)
    assert fut.result() == 13


def test_Future_add_done_callback_invokes():
    import threading
    called = threading.Event()
    captured = []

    def cb(fut):
        captured.append(fut.result())
        called.set()

    f = hpyx.async_(lambda: 42)
    f.add_done_callback(cb)
    assert called.wait(timeout=5.0)
    assert captured == [42]


def test_Future_repr():
    f = hpyx.ready_future(1)
    r = repr(f)
    assert "hpyx.Future" in r


def test_when_any_empty_raises():
    with pytest.raises(ValueError, match="at least one"):
        hpyx.when_any()


def test_add_done_callback_fifo_order():
    """Per concurrent.futures.Future contract: callbacks fire in insertion order."""
    import threading
    fut = hpyx.async_(lambda: 42)
    captured: list[int] = []
    done = threading.Event()
    n = 5

    def make_cb(i):
        def cb(_f):
            captured.append(i)
            if len(captured) == n:
                done.set()
        return cb

    for i in range(n):
        fut.add_done_callback(make_cb(i))
    assert done.wait(timeout=5.0)
    assert captured == list(range(n))


def test_add_done_callback_already_done_runs_synchronously():
    """Per concurrent.futures.Future: callbacks added to already-done futures
    run synchronously on the calling thread."""
    import threading
    fut = hpyx.ready_future(42)
    caller_tid = threading.get_ident()
    callback_tid: list[int] = []

    def cb(_f):
        callback_tid.append(threading.get_ident())

    fut.add_done_callback(cb)
    assert callback_tid == [caller_tid]


def test_then_short_circuits_on_upstream_exception():
    """Per spec §5.2: .then's fn is not invoked when upstream raises."""
    invoked: list[bool] = []

    def upstream():
        raise ValueError("upstream-fail")

    def cb(_f):
        invoked.append(True)
        return "should-not-see"

    chained = hpyx.async_(upstream).then(cb)
    with pytest.raises(ValueError, match="upstream-fail"):
        chained.result()
    assert invoked == []


def test_then_passes_self_not_intermediate():
    """Verify .then's callback receives the upstream Future (not a fresh ready_future).

    Confirms the I5 fix — no wasteful intermediate Future is created.
    """
    captured_futures: list = []

    def cb(f):
        captured_futures.append(f)
        return f.result() * 2

    upstream = hpyx.async_(lambda: 10)
    chained = upstream.then(cb)
    assert chained.result() == 20
    assert len(captured_futures) == 1
    # The captured Future must be the upstream itself (semantic equivalence
    # — same .result()).
    assert captured_futures[0].result() == 10


# ---- HPYX_ASYNC_MODE rollback behavior ----
#
# These tests prove the C++ side actually honors the env var, separately from
# the Python config layer (which only validates and lowercases the value).

def test_async_mode_deferred_runs_in_caller_thread(monkeypatch):
    """HPYX_ASYNC_MODE=deferred restores v0.x launch::deferred semantics.

    Under deferred, hpx::async returns a future where the callable is not
    scheduled — it runs synchronously when .result() is called, on the
    calling thread. This is the documented rollback path per spec risk #1.
    """
    monkeypatch.setenv("HPYX_ASYNC_MODE", "deferred")
    caller_tid = threading.get_ident()
    fut = hpyx.async_(threading.get_ident)
    # The callable runs synchronously on the caller thread when .result()
    # is invoked, so the captured tid matches the caller's tid.
    assert fut.result() == caller_tid


def test_async_mode_default_runs_on_hpx_worker(monkeypatch):
    """Default HPYX_ASYNC_MODE (async) runs the callable on an HPX worker."""
    monkeypatch.delenv("HPYX_ASYNC_MODE", raising=False)
    caller_tid = threading.get_ident()
    fut = hpyx.async_(threading.get_ident)
    worker_tid = fut.result()
    # The callable runs on an HPX worker — different thread than the caller.
    assert worker_tid != caller_tid
