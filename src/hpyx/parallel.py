"""hpyx.parallel — Python-callback parallel algorithms over integer ranges
and iterables.

Every function takes a policy (from ``hpyx.execution``) as the first
argument.  Task-tagged policies (e.g. ``par(task)``) are supported by
:func:`sort`, :func:`stable_sort`, and :func:`transform_reduce`, which return
a :class:`~hpyx.futures.Future`; other algorithms raise ``NotImplementedError``
for task-tagged policies.

For ``par`` and ``par_unseq`` policies with Python callbacks, each iteration
is submitted as an independent ``hpyx.async_`` task on an HPX worker thread.
The ``seq`` and ``unseq`` policies call the C++ layer directly for zero
overhead.  Pure C++ kernels (no Python callback) can use HPX parallel
policies natively — see ``hpyx.kernels``.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from typing import Any, Union

from hpyx import _core, _runtime
from hpyx.execution import Policy
from hpyx.futures import Future, async_


def _task_not_supported(name: str) -> str:
    return (
        f"Task variant of {name} is not yet supported. "
        "Use a synchronous policy (e.g. par, seq) instead."
    )


def _token_fields(policy: Policy) -> tuple:
    t = policy._token()
    return (t.kind, t.task, t.chunk, t.chunk_size)


def for_loop(
    policy: Policy,
    first: int,
    last: int,
    body: Callable[[int], None],
) -> Union[None, Future]:
    """Invoke ``body(i)`` for i in [first, last) under ``policy``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(
            "Task variant of for_loop is not yet supported. "
            "Use a synchronous policy (e.g. par, seq) instead."
        )

    if policy.name in ("par", "par_unseq"):
        futs = [async_(body, i) for i in range(first, last)]
        for f in futs:
            f.result()
    else:
        kind, task_flag, chunk, chunk_size = _token_fields(policy)
        _core.parallel.for_loop(kind, task_flag, chunk, chunk_size, first, last, body)
    return None


def for_each(
    policy: Policy,
    iterable: Any,
    fn: Callable[[Any], None],
) -> Union[None, Future]:
    """Apply ``fn(x)`` to every element in ``iterable`` under ``policy``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(
            "Task variant of for_each is not yet supported. "
            "Use a synchronous policy (e.g. par, seq) instead."
        )

    items = list(iterable)

    if policy.name in ("par", "par_unseq"):
        futs = [async_(fn, item) for item in items]
        for f in futs:
            f.result()
    else:
        kind, task_flag, chunk, chunk_size = _token_fields(policy)
        _core.parallel.for_each(kind, task_flag, chunk, chunk_size, items, fn)
    return None


def transform[T, U](
    policy: Policy,
    iterable: Iterable[T],
    fn: Callable[[T], U],
) -> list[U]:
    """Apply ``fn`` to each element, return a new list of results."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("transform"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(fn, item) for item in items]
        return [f.result() for f in futs]
    return [fn(item) for item in items]


def reduce[T](
    policy: Policy,
    iterable: Iterable[T],
    *,
    init: T,
    op: Callable[[T, T], T],
) -> T:
    """Reduce ``iterable`` with ``op``, starting from ``init``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("reduce"))

    items = list(iterable)
    return functools.reduce(op, items, init)


def _transform_reduce_body(
    policy: Policy,
    items: list,
    init,
    reduce_op,
    transform_op,
):
    if policy.name in ("par", "par_unseq"):
        futs = [async_(transform_op, item) for item in items]
        transformed = [f.result() for f in futs]
    else:
        transformed = [transform_op(item) for item in items]
    return functools.reduce(reduce_op, transformed, init)


def transform_reduce[T, U](
    policy: Policy,
    iterable: Iterable[T],
    *,
    init: U,
    reduce_op: Callable[[U, U], U],
    transform_op: Callable[[T], U],
) -> Union[U, Future]:
    """Transform each element with ``transform_op`` then reduce with ``reduce_op``.

    With a ``task``-tagged policy the entire computation is submitted as a
    single HPX task and a :class:`~hpyx.futures.Future` is returned.
    """
    _runtime.ensure_started()
    items = list(iterable)
    if policy.task:
        return async_(_transform_reduce_body, policy, items, init, reduce_op, transform_op)
    return _transform_reduce_body(policy, items, init, reduce_op, transform_op)


# ---------------------------------------------------------------------------
# Search algorithms
# ---------------------------------------------------------------------------

def count[T](
    policy: Policy,
    iterable: Iterable[T],
    value: T,
) -> int:
    """Count elements equal to ``value``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("count"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(lambda x: x == value, item) for item in items]
        return sum(f.result() for f in futs)
    return sum(1 for item in items if item == value)


def count_if[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> int:
    """Count elements satisfying ``pred``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("count_if"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        return sum(bool(f.result()) for f in futs)
    return sum(1 for item in items if pred(item))


def find[T](
    policy: Policy,
    iterable: Iterable[T],
    value: T,
) -> int:
    """Return index of first element equal to ``value``, or -1.

    Note: under ``par``/``par_unseq``, all elements are evaluated before
    results are checked — no short-circuit occurs.
    """
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("find"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(lambda x: x == value, item) for item in items]
        for i, f in enumerate(futs):
            if f.result():
                return i
        return -1
    for i, item in enumerate(items):
        if item == value:
            return i
    return -1


def find_if[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> int:
    """Return index of first element satisfying ``pred``, or -1.

    Note: under ``par``/``par_unseq``, all elements are evaluated before
    results are checked — no short-circuit occurs.
    """
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("find_if"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        for i, f in enumerate(futs):
            if f.result():
                return i
        return -1
    for i, item in enumerate(items):
        if pred(item):
            return i
    return -1


def all_of[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> bool:
    """Return True if ``pred`` is true for all elements.

    Note: under ``par``/``par_unseq``, all predicates are launched before any
    result is checked — no short-circuit occurs.
    """
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("all_of"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        return all(f.result() for f in futs)
    return all(pred(item) for item in items)


def any_of[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> bool:
    """Return True if ``pred`` is true for any element.

    Note: under ``par``/``par_unseq``, all predicates are launched before any
    result is checked — no short-circuit occurs.
    """
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("any_of"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        return any(f.result() for f in futs)
    return any(pred(item) for item in items)


def none_of[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> bool:
    """Return True if ``pred`` is false for all elements.

    Note: under ``par``/``par_unseq``, all predicates are launched before any
    result is checked — no short-circuit occurs.
    """
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("none_of"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        return not any(f.result() for f in futs)
    return not any(pred(item) for item in items)


# ---------------------------------------------------------------------------
# Sort algorithms
# ---------------------------------------------------------------------------

def sort[T](
    policy: Policy,
    data: Iterable[T],
    *,
    key: Callable[[T], Any] | None = None,
    reverse: bool = False,
) -> Union[list[T], Future]:
    """Return a new sorted list, dispatching to hpx::sort.

    For ``par`` / ``par_unseq`` policies, hpx::sort with a parallel execution
    policy is used.  With Python-object comparisons the GIL still serializes
    individual comparisons, so throughput gains over ``seq`` are visible only
    when the collection contains types whose C++ ``<`` operator can run GIL-free
    (see hpyx.kernels for pure-C++ numeric kernels).

    With a ``task``-tagged policy the sort is submitted as a single HPX task and
    a :class:`~hpyx.futures.Future` is returned.
    """
    _runtime.ensure_started()
    items = list(data)
    kind, _, chunk, chunk_size = _token_fields(policy)
    if policy.task:
        return async_(_core.parallel.sort, kind, False, chunk, chunk_size, items, key, reverse, False)
    return _core.parallel.sort(kind, False, chunk, chunk_size, items, key, reverse, False)


def stable_sort[T](
    policy: Policy,
    data: Iterable[T],
    *,
    key: Callable[[T], Any] | None = None,
    reverse: bool = False,
) -> Union[list[T], Future]:
    """Return a new sorted list preserving relative order of equal elements.

    Dispatches to hpx::stable_sort.  The same GIL note as :func:`sort` applies.

    With a ``task``-tagged policy a :class:`~hpyx.futures.Future` is returned.
    """
    _runtime.ensure_started()
    items = list(data)
    kind, _, chunk, chunk_size = _token_fields(policy)
    if policy.task:
        return async_(_core.parallel.sort, kind, False, chunk, chunk_size, items, key, reverse, True)
    return _core.parallel.sort(kind, False, chunk, chunk_size, items, key, reverse, True)


# ---------------------------------------------------------------------------
# Fill / copy / iota
# ---------------------------------------------------------------------------

def fill[T](
    policy: Policy,
    n: int,
    value: T,
) -> list[T]:
    """Return a list of ``n`` copies of ``value``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("fill"))

    return [value] * n


def fill_n[T](
    policy: Policy,
    n: int,
    value: T,
) -> list[T]:
    """Alias for :func:`fill`."""
    return fill(policy, n, value)


def copy[T](
    policy: Policy,
    iterable: Iterable[T],
) -> list[T]:
    """Return a new list copy of ``iterable``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("copy"))

    return list(iterable)


def copy_if[T](
    policy: Policy,
    iterable: Iterable[T],
    pred: Callable[[T], bool],
) -> list[T]:
    """Return a list of elements satisfying ``pred``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("copy_if"))

    items = list(iterable)
    if policy.name in ("par", "par_unseq"):
        futs = [async_(pred, item) for item in items]
        return [item for item, f in zip(items, futs, strict=True) if f.result()]
    return [item for item in items if pred(item)]


def iota(
    policy: Policy,
    n: int,
    start: int = 0,
) -> list[int]:
    """Return ``[start, start+1, ..., start+n-1]``."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("iota"))

    return list(range(start, start + n))


# ---------------------------------------------------------------------------
# Scan algorithms
# ---------------------------------------------------------------------------

def inclusive_scan[T](
    policy: Policy,
    iterable: Iterable[T],
    *,
    op: Callable[[T, T], T],
) -> list[T]:
    """Return a list of running totals (inclusive)."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("inclusive_scan"))

    items = list(iterable)
    if not items:
        return []
    result = [items[0]]
    for item in items[1:]:
        result.append(op(result[-1], item))
    return result


def exclusive_scan[T](
    policy: Policy,
    iterable: Iterable[T],
    *,
    init: T,
    op: Callable[[T, T], T],
) -> list[T]:
    """Return a list of running totals starting from ``init`` (exclusive)."""
    _runtime.ensure_started()
    if policy.task:
        raise NotImplementedError(_task_not_supported("exclusive_scan"))

    items = list(iterable)
    if not items:
        return []
    result = [init]
    for item in items[:-1]:
        result.append(op(result[-1], item))
    return result


__all__ = [
    "all_of",
    "any_of",
    "copy",
    "copy_if",
    "count",
    "count_if",
    "exclusive_scan",
    "fill",
    "fill_n",
    "find",
    "find_if",
    "for_each",
    "for_loop",
    "inclusive_scan",
    "iota",
    "none_of",
    "reduce",
    "sort",
    "stable_sort",
    "transform",
    "transform_reduce",
]
