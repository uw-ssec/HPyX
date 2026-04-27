"""hpyx.aio — asyncio integration for hpyx Futures.

Provides the internal ``_future_await`` used by ``Future.__await__``,
plus the ``await_all`` and ``await_any`` combinators.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# Imported unconditionally (not under TYPE_CHECKING) so that
# ``typing.get_type_hints()`` on these functions resolves the ``Future``
# reference at runtime. Importing the leaf module ``hpyx.futures._future``
# directly avoids triggering ``hpyx.futures.__init__`` here.
from hpyx.futures._future import Future


_logger = logging.getLogger("hpyx.aio")


async def _future_await(fut: Future) -> Any:
    """Bridge a hpyx.Future into an asyncio-awaitable coroutine.

    Used by ``Future.__await__``. Wraps the hpyx Future into an
    ``asyncio.Future`` and posts the result back to the event loop via
    ``loop.call_soon_threadsafe`` from the HPX worker thread that
    completes the future.

    Edge cases:
    - If the asyncio Future is already done (cancelled mid-flight),
      the result post is a no-op.
    - If the loop is closed by the time the HPX future fires, we log
      a warning and drop the result silently — re-raising would
      crash an HPX worker thread that has nothing useful to do with it.
    """
    loop = asyncio.get_running_loop()
    aio_fut: asyncio.Future = loop.create_future()

    def _on_done(_hpx_fut: Future) -> None:
        # Runs on an HPX worker thread (or the calling thread, if the
        # hpyx Future was already done when add_done_callback was made).
        try:
            value = _hpx_fut.result()
        except BaseException as exc:  # noqa: BLE001
            _post_exception(loop, aio_fut, exc)
        else:
            _post_result(loop, aio_fut, value)

    fut.add_done_callback(_on_done)
    return await aio_fut


def _post_result(loop: asyncio.AbstractEventLoop, aio_fut: asyncio.Future, value: Any) -> None:
    def _set() -> None:
        if not aio_fut.done():
            aio_fut.set_result(value)
    try:
        loop.call_soon_threadsafe(_set)
    except RuntimeError:
        # Loop is closed; drop silently with a warning log.
        _logger.warning("hpyx.aio: dropping result; event loop is closed")


def _post_exception(
    loop: asyncio.AbstractEventLoop,
    aio_fut: asyncio.Future,
    exc: BaseException,
) -> None:
    def _set() -> None:
        if not aio_fut.done():
            aio_fut.set_exception(exc)
    try:
        loop.call_soon_threadsafe(_set)
    except RuntimeError:
        _logger.warning("hpyx.aio: dropping exception; event loop is closed")


async def await_all(*futures: Future) -> tuple:
    """Await all input futures; return a tuple of their results in order.

    Unlike :func:`asyncio.gather`, exceptions are NOT consumed — the
    first exception raised aborts the operation (matches ``when_all``).
    """
    from hpyx.futures import when_all
    combined = when_all(*futures)
    return await combined


async def await_any(*futures: Future) -> tuple[int, list[Future]]:
    """Await any input future; return ``(index, futures_list)``.

    The element at ``futures_list[index]`` is the one that completed;
    others may still be pending. ``futures_list`` is a Python list of
    :class:`hpyx.Future` wrappers.
    """
    from hpyx.futures import when_any
    combined = when_any(*futures)
    return await combined


__all__ = ["await_all", "await_any"]
