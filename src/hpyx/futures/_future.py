"""hpyx.Future — Python wrapper around hpyx._core.futures.HPXFuture.

The wrapper adds:
- Type identity (the wrapper is what users import as ``hpyx.Future``).
- ``__await__`` for asyncio integration (full body lives in ``hpyx.aio``).
- Logging-aware ``add_done_callback`` (matches concurrent.futures behavior).

The wrapper is thin — most methods delegate directly to the C++ object.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from hpyx import _core


class Future:
    """A future backed by the HPX runtime.

    Implements the ``concurrent.futures.Future`` protocol (``result``,
    ``exception``, ``done``, ``running``, ``cancelled``, ``cancel``,
    ``add_done_callback``), plus HPX-native ``.then(fn)`` and asyncio
    ``await`` support.

    Multiple consumers of the same Future are supported — internally
    every Future wraps an ``hpx::shared_future``.
    """

    __slots__ = ("_hpx",)

    def __init__(self, hpx_fut: "_core.futures.HPXFuture") -> None:
        self._hpx = hpx_fut

    # ---- concurrent.futures.Future protocol ----

    def result(self, timeout: Optional[float] = None) -> Any:
        return self._hpx.result(timeout)

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        return self._hpx.exception(timeout)

    def done(self) -> bool:
        return self._hpx.done()

    def running(self) -> bool:
        return self._hpx.running()

    def cancelled(self) -> bool:
        return self._hpx.cancelled()

    def cancel(self) -> bool:
        return self._hpx.cancel()

    def add_done_callback(self, fn: Callable[["Future"], None]) -> None:
        # Wrap so the callback receives the Python Future, not the raw HPXFuture.
        # Match concurrent.futures.Future: swallow callback errors and log.
        outer = self

        def _wrapper(_hpx_fut: "_core.futures.HPXFuture") -> None:
            try:
                fn(outer)
            except BaseException:
                logging.getLogger("hpyx.futures").exception(
                    "exception in Future.add_done_callback"
                )

        self._hpx.add_done_callback(_wrapper)

    # ---- HPX-native ----

    def then(self, fn: Callable[["Future"], Any]) -> "Future":
        # Per spec §4.4: callback receives the resolved Future (so the user
        # can call .result() / .exception() and dispatch on success/failure).
        def _shim(value: Any) -> Any:
            ready = Future(_core.futures.ready_future(value))
            return fn(ready)

        return Future(self._hpx.then(_shim))

    def share(self) -> "Future":
        return Future(self._hpx.share())

    # ---- asyncio bridge ----

    def __await__(self):
        # Lazy import: avoid pulling asyncio at module load.
        from hpyx.aio import _future_await

        return _future_await(self).__await__()

    def __repr__(self) -> str:
        if self.cancelled():
            state = "cancelled"
        elif self.done():
            state = "done"
        elif self.running():
            state = "running"
        else:
            state = "pending"
        return f"<hpyx.Future state={state}>"
