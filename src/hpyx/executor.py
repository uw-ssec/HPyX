"""hpyx.HPXExecutor — a concurrent.futures.Executor backed by HPX.

All instances share one process-wide HPX runtime (HPX cannot host multiple
runtimes in a single process). ``shutdown()`` marks this executor handle
unusable but does not stop the runtime — atexit owns process-level
teardown because HPX cannot restart in-process.

Examples
--------
>>> import hpyx
>>> with hpyx.HPXExecutor() as ex:
...     fut = ex.submit(pow, 2, 10)
...     print(fut.result())  # 1024

For dask integration:

>>> import dask.array as da
>>> with hpyx.HPXExecutor() as ex:
...     result = da.arange(1e6).sum().compute(scheduler=ex)
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Executor
from typing import Any

from hpyx import _runtime
from hpyx.futures import Future, async_


class HPXExecutor(Executor):
    """A real ``concurrent.futures.Executor`` backed by HPX.

    Parameters
    ----------
    max_workers : int | None, optional
        Advisory. HPX's worker pool is process-global; ``max_workers``
        seeds ``os_threads`` on the implicit init if the runtime isn't
        started yet. If the runtime is already started with a different
        ``os_threads``, a ``UserWarning`` is emitted and the existing
        pool is used unchanged.

    Notes
    -----
    Multiple ``HPXExecutor`` instances share the process-global HPX
    runtime. Calling ``.shutdown()`` on one handle does not affect
    other handles or stop the runtime — ``atexit`` owns process-level
    teardown because HPX cannot restart in-process.
    """

    def __init__(self, max_workers: int | None = None) -> None:
        self._closed = False
        self._lock = threading.Lock()
        if max_workers is None:
            _runtime.ensure_started()
            return
        if _runtime.is_running():
            running_threads = _runtime.running_os_threads()
            if running_threads is not None and running_threads != max_workers:
                warnings.warn(
                    f"HPXExecutor(max_workers={max_workers}) differs from the "
                    f"running HPX runtime's os_threads={running_threads}; "
                    f"using the runtime pool as-is (HPX cannot be reconfigured "
                    f"after start).",
                    UserWarning,
                    stacklevel=2,
                )
        else:
            _runtime.ensure_started(os_threads=max_workers)

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        with self._lock:
            closed = self._closed
        if closed:
            raise RuntimeError("cannot schedule new futures after shutdown")
        return async_(fn, *args, **kwargs)

    def map(
        self,
        fn: Callable[..., Any],
        *iterables: Iterable[Any],
        timeout: float | None = None,
        chunksize: int = 1,  # noqa: ARG002 — accepted for protocol; unused (Plan 3 revisits)
    ) -> Iterator[Any]:
        # Submit every item eagerly, then yield results in order. This
        # matches concurrent.futures.ThreadPoolExecutor.map semantics —
        # silent truncation to the shortest iterable.
        with self._lock:
            closed = self._closed
        if closed:
            raise RuntimeError("cannot schedule new futures after shutdown")
        futures = [self.submit(fn, *group) for group in zip(*iterables)]

        def _iter() -> Iterator[Any]:
            try:
                for fut in futures:
                    yield fut.result(timeout=timeout)
            except GeneratorExit:
                for fut in futures:
                    fut.cancel()
                raise

        return _iter()

    def shutdown(
        self,
        wait: bool = True,  # noqa: ARG002 — accepted for protocol; HPX shutdown is process-level
        *,
        cancel_futures: bool = False,  # noqa: ARG002 — accepted for protocol; not implemented in v1
    ) -> None:
        # Per-handle shutdown. Does NOT stop the HPX runtime — atexit
        # owns teardown because HPX cannot restart within a process.
        with self._lock:
            self._closed = True


__all__ = ["HPXExecutor"]
