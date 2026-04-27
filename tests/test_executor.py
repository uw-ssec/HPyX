"""Tests for hpyx.HPXExecutor — concurrent.futures.Executor conformance."""

import concurrent.futures
import threading

import pytest

import hpyx


# ---- Protocol conformance ----

def test_HPXExecutor_is_concurrent_futures_Executor_subclass():
    assert issubclass(hpyx.HPXExecutor, concurrent.futures.Executor)


def test_submit_returns_future_like_object():
    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(lambda: 42)
        assert fut.result() == 42


def test_submit_preserves_args_and_kwargs():
    def worker(a, b, *, c=0):
        return a + b + c

    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(worker, 1, 2, c=10)
        assert fut.result() == 13


def test_submit_propagates_exception():
    def boom():
        raise ValueError("boom")

    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(boom)
        with pytest.raises(ValueError, match="boom"):
            fut.result()


def test_submit_returns_hpyx_Future():
    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(lambda: 1)
        assert isinstance(fut, hpyx.Future)


# ---- map ----

def test_map_basic():
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda x: x * x, range(5)))
        assert results == [0, 1, 4, 9, 16]


def test_map_two_iterables():
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda a, b: a + b, range(5), range(5, 10)))
        assert results == [5, 7, 9, 11, 13]


def test_map_propagates_exception():
    def pick(x):
        if x == 3:
            raise RuntimeError("no 3!")
        return x

    with hpyx.HPXExecutor() as ex:
        with pytest.raises(RuntimeError, match="no 3"):
            list(ex.map(pick, range(5)))


def test_map_empty_input():
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda x: x, []))
        assert results == []


def test_map_truncates_to_shortest_iterable():
    """Per stdlib: map silently truncates to the shortest iterable."""
    with hpyx.HPXExecutor() as ex:
        results = list(ex.map(lambda a, b: a + b, [1, 2, 3], [10, 20]))
        assert results == [11, 22]


# ---- shutdown ----

def test_shutdown_is_idempotent():
    ex = hpyx.HPXExecutor()
    ex.shutdown()
    ex.shutdown()  # must not raise


def test_submit_after_shutdown_raises():
    ex = hpyx.HPXExecutor()
    ex.shutdown()
    with pytest.raises(RuntimeError, match="shut ?down"):
        ex.submit(lambda: 1)


def test_map_after_shutdown_raises():
    ex = hpyx.HPXExecutor()
    ex.shutdown()
    with pytest.raises(RuntimeError, match="shut ?down"):
        list(ex.map(lambda x: x, range(3)))


def test_context_manager_shuts_down():
    with hpyx.HPXExecutor() as ex:
        fut = ex.submit(lambda: 1)
        fut.result()
    # After __exit__, submit must raise.
    with pytest.raises(RuntimeError, match="shut ?down"):
        ex.submit(lambda: 2)


def test_separate_handles_independent_shutdown():
    """Per spec: shutdown on one handle does not affect another."""
    ex_a = hpyx.HPXExecutor()
    ex_b = hpyx.HPXExecutor()
    ex_a.shutdown()
    # ex_b is still usable
    assert ex_b.submit(lambda: "ok").result() == "ok"
    ex_b.shutdown()


# ---- max_workers reconciliation ----

def test_max_workers_warning_when_mismatched(recwarn):
    # The session fixture starts the runtime with os_threads=4.
    # Specifying a different max_workers after the runtime is up should WARN.
    ex = hpyx.HPXExecutor(max_workers=99)
    assert any("max_workers" in str(w.message) for w in recwarn.list)
    ex.shutdown()


def test_max_workers_matches_runtime_no_warning(recwarn):
    # The session fixture starts the runtime with os_threads=4.
    ex = hpyx.HPXExecutor(max_workers=4)
    msgs = [str(w.message) for w in recwarn.list]
    assert not any("max_workers" in m for m in msgs)
    ex.shutdown()


# ---- cross-thread submit ----

def test_submit_from_multiple_threads():
    N = 50
    results = [None] * N
    with hpyx.HPXExecutor() as ex:
        def submit_and_wait(i):
            results[i] = ex.submit(lambda x=i: x * 2).result()
        ts = [threading.Thread(target=submit_and_wait, args=(i,)) for i in range(N)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    assert results == [i * 2 for i in range(N)]
