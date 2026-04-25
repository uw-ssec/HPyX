"""hpyx.Future — Python wrapper around hpyx._core.futures.HPXFuture.

The wrapper adds:
- Type identity (the wrapper is what users import as ``hpyx.Future``).
- ``__await__`` for asyncio integration (full body lives in ``hpyx.aio``).
- Logging-aware ``add_done_callback`` (matches concurrent.futures behavior).

The wrapper is thin — most methods delegate directly to the C++ object.
"""

from __future__ import annotations

import logging
import threading
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

    __slots__ = ("_hpx", "_callbacks", "_callback_lock", "_callbacks_registered")

    def __init__(self, hpx_fut: "_core.futures.HPXFuture") -> None:
        self._hpx = hpx_fut
        self._callbacks: list[Callable[["Future"], None]] | None = None
        self._callback_lock = threading.Lock()
        self._callbacks_registered = False

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
        # Per concurrent.futures.Future contract:
        #   - callbacks fire in insertion order (FIFO)
        #   - callbacks added to already-done futures run synchronously on
        #     the calling thread
        #   - exceptions raised in callbacks are logged and swallowed
        #
        # The HPX C++ side makes no FIFO guarantee across multiple
        # ``add_done_callback`` registrations, so we register exactly ONE
        # C++ callback that drains a Python-side ``list[Callable]``. The
        # first call sets up the drain; subsequent calls just append.
        if self.done():
            try:
                fn(self)
            except BaseException:
                logging.getLogger("hpyx.futures").exception(
                    "exception in Future.add_done_callback"
                )
            return
        with self._callback_lock:
            if self._callbacks is None:
                self._callbacks = []
            self._callbacks.append(fn)
            if not self._callbacks_registered:
                self._callbacks_registered = True
                outer = self

                def _drain(_hpx_fut: "_core.futures.HPXFuture") -> None:
                    with outer._callback_lock:
                        cbs = outer._callbacks or []
                        outer._callbacks = None
                    log = logging.getLogger("hpyx.futures")
                    for cb in cbs:
                        try:
                            cb(outer)
                        except BaseException:
                            log.exception(
                                "exception in Future.add_done_callback"
                            )

                self._hpx.add_done_callback(_drain)

    # ---- HPX-native ----

    def then(self, fn: Callable[["Future"], Any]) -> "Future":
        # Per spec §4.4: callback receives the resolved Future. If the upstream
        # future raised, ``fn`` is NOT invoked — the exception propagates through
        # the chain unchanged (matches dataflow / when_all short-circuit behavior).
        # Use ``add_done_callback`` if you need to handle both success and failure.
        captured_self = self

        def _shim(_value: Any) -> Any:
            return fn(captured_self)

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
