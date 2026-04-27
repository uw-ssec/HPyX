"""Tests for the asyncio bridge (awaitable Future, hpyx.aio combinators)."""

import asyncio
import threading
import time

import pytest

import hpyx


# ---- direct await on Future ----

def test_await_future():
    async def main():
        fut = hpyx.async_(lambda: 42)
        return await fut

    assert asyncio.run(main()) == 42


def test_await_future_with_exception():
    def boom():
        raise ValueError("boom")

    async def main():
        fut = hpyx.async_(boom)
        return await fut

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(main())


def test_await_does_not_block_event_loop():
    """A pending HPX future should not starve the asyncio event loop."""
    async def main():
        loop_iterations = 0

        async def counter():
            nonlocal loop_iterations
            while loop_iterations < 100:
                loop_iterations += 1
                await asyncio.sleep(0.001)

        def slow():
            time.sleep(0.1)
            return "slow-result"

        fut = hpyx.async_(slow)
        counter_task = asyncio.create_task(counter())
        result = await fut
        await counter_task
        return result, loop_iterations

    result, iterations = asyncio.run(main())
    assert result == "slow-result"
    # If awaiting blocked the loop, iterations would stay near 0.
    # The counter task ran while the HPX task was pending.
    assert iterations >= 50


# ---- asyncio.wrap_future compat ----

def test_wrap_future_works():
    async def main():
        fut = hpyx.async_(lambda: "ok")
        wrapped = asyncio.wrap_future(fut)
        return await wrapped

    assert asyncio.run(main()) == "ok"


# ---- loop.run_in_executor ----

def test_run_in_executor_with_HPXExecutor():
    async def main():
        loop = asyncio.get_running_loop()
        with hpyx.HPXExecutor() as ex:
            return await loop.run_in_executor(ex, pow, 2, 10)

    assert asyncio.run(main()) == 1024


# ---- hpyx.aio combinators ----

def test_aio_await_all():
    async def main():
        f1 = hpyx.async_(lambda: 1)
        f2 = hpyx.async_(lambda: 2)
        f3 = hpyx.async_(lambda: 3)
        return await hpyx.aio.await_all(f1, f2, f3)

    assert asyncio.run(main()) == (1, 2, 3)


def test_aio_await_all_propagates_first_failure():
    async def main():
        def boom():
            raise ValueError("boom")
        f_ok = hpyx.async_(lambda: 42)
        f_bad = hpyx.async_(boom)
        return await hpyx.aio.await_all(f_ok, f_bad)

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(main())


def test_aio_await_any():
    async def main():
        def slow():
            time.sleep(0.2)
            return "slow"

        f_slow = hpyx.async_(slow)
        f_fast = hpyx.async_(lambda: "fast")
        idx, futs = await hpyx.aio.await_any(f_slow, f_fast)
        return idx, futs[idx].result()

    idx, result = asyncio.run(main())
    assert idx == 1
    assert result == "fast"


# ---- edge cases ----

def test_await_already_done_future():
    async def main():
        fut = hpyx.ready_future(99)
        return await fut

    assert asyncio.run(main()) == 99


def test_await_in_two_concurrent_tasks():
    """Two coroutines awaiting independent HPX futures should both complete."""
    async def main():
        f1 = hpyx.async_(lambda: 1)
        f2 = hpyx.async_(lambda: 2)

        async def task(f):
            return await f

        return await asyncio.gather(task(f1), task(f2))

    assert asyncio.run(main()) == [1, 2]


# ---- concurrent.futures interop ----

def test_hpyx_Future_visible_in_concurrent_futures_wait():
    """Per C1 fix: concurrent.futures.wait() must see completed hpyx Futures."""
    import concurrent.futures
    fut = hpyx.async_(lambda: 42)
    fut.result()  # ensure completion
    done, not_done = concurrent.futures.wait([fut], timeout=2.0)
    assert fut in done
    assert not_done == set()


def test_hpyx_Future_visible_in_concurrent_futures_as_completed():
    """Per C1 fix: concurrent.futures.as_completed() must yield completed hpyx Futures."""
    import concurrent.futures
    f1 = hpyx.async_(lambda: 1)
    f2 = hpyx.async_(lambda: 2)
    f3 = hpyx.async_(lambda: 3)
    results = []
    for f in concurrent.futures.as_completed([f1, f2, f3], timeout=2.0):
        results.append(f.result())
    assert sorted(results) == [1, 2, 3]


def test_set_result_raises():
    """Per C2 fix: user calls to set_result must raise."""
    fut = hpyx.async_(lambda: 1)
    with pytest.raises(RuntimeError, match="HPX runtime"):
        fut.set_result("user_value")


def test_set_exception_raises():
    """Per C2 fix: user calls to set_exception must raise."""
    fut = hpyx.async_(lambda: 1)
    with pytest.raises(RuntimeError, match="HPX runtime"):
        fut.set_exception(ValueError("user-raised"))


def test_set_running_or_notify_cancel_raises():
    """Per C2 fix: user calls to set_running_or_notify_cancel must raise."""
    fut = hpyx.async_(lambda: 1)
    with pytest.raises(RuntimeError, match="HPX runtime"):
        fut.set_running_or_notify_cancel()
