"""hpyx.Future — Python wrapper around hpyx._core.futures.HPXFuture.

The wrapper adds:
- Type identity (the wrapper is what users import as ``hpyx.Future``).
- ``__await__`` for asyncio integration (full body lives in ``hpyx.aio``).
- Logging-aware ``add_done_callback`` (matches concurrent.futures behavior).

The wrapper is thin — most methods delegate directly to the C++ object.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from typing import Any, Callable, Optional

from hpyx import _core


class Future(concurrent.futures.Future):
    """A future backed by the HPX runtime.

    Implements the ``concurrent.futures.Future`` protocol (``result``,
    ``exception``, ``done``, ``running``, ``cancelled``, ``cancel``,
    ``add_done_callback``), plus HPX-native ``.then(fn)`` and asyncio
    ``await`` support.

    Multiple consumers of the same Future are supported — internally
    every Future wraps an ``hpx::shared_future``.
    """

    __slots__ = ()  # base class doesn't use __slots__; this saves nothing but documents intent

    def __init__(self, hpx_fut: "_core.futures.HPXFuture") -> None:
        super().__init__()
        self._hpx = hpx_fut
        self._callbacks: list[Callable[["Future"], None]] | None = None
        self._callback_lock = threading.Lock()
        self._callbacks_registered = False
        # Lock + flag for ``_sync_base_state``. Multiple HPX worker threads
        # may race to flip the inherited base state (the eager
        # ``_sync_on_done`` C++ callback registered below and the user-level
        # ``_drain`` C++ callback both call ``_sync_base_state``). The flag
        # ensures at most one of them invokes the base ``set_result`` /
        # ``set_exception``.
        self._base_state_lock = threading.Lock()
        self._base_state_synced = False
        # Eagerly mirror the underlying HPX state into the inherited
        # ``concurrent.futures.Future._state`` so that stdlib helpers
        # (``concurrent.futures.wait``, ``as_completed``) — which inspect
        # the base ``_state`` directly without going through our public
        # API — observe completion correctly. If the underlying future
        # is already done at construction time, sync immediately;
        # otherwise register a one-shot C++ callback that fires when it
        # completes.
        if self._hpx.done():
            self._sync_base_state()
        else:
            outer = self

            def _sync_on_done(_hpx_fut: "_core.futures.HPXFuture") -> None:
                outer._sync_base_state()

            self._hpx.add_done_callback(_sync_on_done)

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
            # Sync the inherited concurrent.futures.Future state so that
            # stdlib helpers (wait, as_completed) see this Future as done.
            self._sync_base_state()
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
                    # Flip the inherited base-class state first, so any
                    # user callback (or stdlib helper waking up) observes
                    # this Future as done from the concurrent.futures side.
                    outer._sync_base_state()
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

    # ---- internal: base-class state sync ----

    def _sync_base_state(self) -> None:
        """Flip the inherited ``concurrent.futures.Future`` state to match ``_hpx``.

        Required so that stdlib helpers (``concurrent.futures.wait``,
        ``as_completed``) see this Future as done — they read the base
        class's ``_state``, which our overrides of ``done()``/``result()``
        do not touch.

        Idempotent and thread-safe: multiple HPX worker threads may race
        to invoke this (eager ``_sync_on_done`` and user-level ``_drain``
        callbacks both call it). The ``_base_state_lock`` + flag ensure
        the base ``set_result``/``set_exception`` runs at most once.
        Bypasses our public ``set_result``/``set_exception`` overrides
        (which raise) by calling the unbound base methods.
        """
        with self._base_state_lock:
            if self._base_state_synced:
                return
            self._base_state_synced = True
            try:
                value = self._hpx.result()
            except BaseException as exc:  # noqa: BLE001
                concurrent.futures.Future.set_exception(self, exc)
            else:
                concurrent.futures.Future.set_result(self, value)

    # ---- inherited mutators: forbid direct user calls ----

    def set_result(self, result: Any) -> None:
        raise RuntimeError(
            "hpyx.Future state is set by the HPX runtime; "
            "do not call set_result directly"
        )

    def set_exception(self, exception: BaseException | None) -> None:
        raise RuntimeError(
            "hpyx.Future state is set by the HPX runtime; "
            "do not call set_exception directly"
        )

    def set_running_or_notify_cancel(self) -> bool:
        raise RuntimeError(
            "hpyx.Future state is set by the HPX runtime; "
            "do not call set_running_or_notify_cancel directly"
        )

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
