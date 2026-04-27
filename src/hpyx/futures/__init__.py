"""hpyx.futures — HPX-backed futures API (Pythonic wrapper).

Public names:
    Future, async_, when_all, when_any, dataflow, shared_future, ready_future
"""

from __future__ import annotations

from typing import Any, Callable

from hpyx import _core, _runtime
from hpyx.futures._future import Future


def async_(fn: Callable, *args: Any, **kwargs: Any) -> Future:
    """Submit a callable to an HPX worker; return a Future for its result."""
    _runtime.ensure_started()
    raw = _core.futures.async_submit(fn, args, kwargs)
    return Future(raw)


def when_all(*futures: Future) -> Future:
    """Return a Future that resolves to a tuple of all input results (in order)."""
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    return Future(_core.futures.when_all(raws))


def when_any(*futures: Future) -> Future:
    """Return a Future that resolves to ``(index, futures_list)`` when any input completes."""
    if not futures:
        raise ValueError("when_any requires at least one input")
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    inner = _core.futures.when_any(raws)

    def _wrap_inner(result: Any) -> Any:
        idx, raw_list = result
        return (idx, [Future(r) for r in raw_list])

    # Wrap C++ inner list (HPXFutures) into Python Futures via .then on the inner future.
    return Future(inner).then(lambda fut: _wrap_inner(fut.result()))


def dataflow(fn: Callable, *futures: Future, **kwargs: Any) -> Future:
    """Run ``fn(*resolved_values, **kwargs)`` once all input futures complete."""
    _runtime.ensure_started()
    raws = [f._hpx for f in futures]
    return Future(_core.futures.dataflow(fn, raws, kwargs))


def shared_future(f: Future) -> Future:
    """Return a shareable view of ``f`` (multiple consumers can call .result())."""
    return f.share()


def ready_future(value: Any) -> Future:
    """Return an already-completed Future wrapping ``value``."""
    return Future(_core.futures.ready_future(value))


__all__ = [
    "Future",
    "async_",
    "dataflow",
    "ready_future",
    "shared_future",
    "when_all",
    "when_any",
]
