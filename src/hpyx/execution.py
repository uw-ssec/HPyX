"""hpyx.execution — HPX-style execution policies for parallel algorithms.

Usage
-----
    import hpyx
    from hpyx.execution import par, seq, task, static_chunk_size

    hpyx.parallel.for_loop(par, 0, 1_000_000, fn)
    hpyx.parallel.for_loop(par.with_(static_chunk_size(10_000)), ...)

Note: task-tagged policies (e.g. ``par(task)``) are supported by
``hpyx.parallel.sort``, ``hpyx.parallel.stable_sort``, and
``hpyx.parallel.transform_reduce``, which return a Future.  Other
``hpyx.parallel`` functions raise ``NotImplementedError`` for task-tagged
policies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

_KIND_SEQ = 0
_KIND_PAR = 1
_KIND_PAR_UNSEQ = 2
_KIND_UNSEQ = 3

_CHUNK_NONE = 0
_CHUNK_STATIC = 1
_CHUNK_DYNAMIC = 2
_CHUNK_AUTO = 3
_CHUNK_GUIDED = 4


@dataclass(frozen=True)
class _Token:
    """Wire-level token passed to C++. Matches PolicyToken in policy_dispatch.hpp."""
    kind: int
    task: bool
    chunk: int
    chunk_size: int


@dataclass(frozen=True)
class ChunkSize:
    """Opaque holder for a chunk-size strategy."""
    kind: int
    size: int = 0


def static_chunk_size(n: int) -> ChunkSize:
    """Fixed `n` elements per task."""
    if n <= 0:
        raise ValueError(f"static_chunk_size(n) requires n > 0, got {n}")
    return ChunkSize(kind=_CHUNK_STATIC, size=n)


def dynamic_chunk_size(n: int) -> ChunkSize:
    """Dynamic (load-balanced) chunks of `n` elements."""
    if n <= 0:
        raise ValueError(f"dynamic_chunk_size(n) requires n > 0, got {n}")
    return ChunkSize(kind=_CHUNK_DYNAMIC, size=n)


def auto_chunk_size() -> ChunkSize:
    """Let HPX pick chunk size automatically."""
    return ChunkSize(kind=_CHUNK_AUTO)


def guided_chunk_size() -> ChunkSize:
    """Guided (shrinking) chunks."""
    return ChunkSize(kind=_CHUNK_GUIDED)


class _TaskTag:
    """Singleton sentinel for the task modifier."""
    __slots__ = ()
    def __repr__(self) -> str:
        return "task"


task = _TaskTag()


class _Policy:
    """Base execution policy. Frozen at the object level — `with_()` returns copies."""

    __slots__ = ("name", "_kind", "task", "chunk_name", "_chunk_kind", "_chunk_size")

    def __init__(
        self,
        *,
        name: str,
        kind: int,
        task: bool = False,
        chunk_name: str = "none",
        chunk_kind: int = _CHUNK_NONE,
        chunk_size: int = 0,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "task", task)
        object.__setattr__(self, "chunk_name", chunk_name)
        object.__setattr__(self, "_chunk_kind", chunk_kind)
        object.__setattr__(self, "_chunk_size", chunk_size)

    def __setattr__(self, key, value):
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __call__(self, tag):
        if not isinstance(tag, _TaskTag):
            raise TypeError(f"Policy(...) only accepts `task`, got {tag!r}")
        if self.task:
            raise TypeError("Policy already has task tag applied")
        return _Policy(
            name=self.name,
            kind=self._kind,
            task=True,
            chunk_name=self.chunk_name,
            chunk_kind=self._chunk_kind,
            chunk_size=self._chunk_size,
        )

    def with_(self, chunk: ChunkSize) -> "_Policy":
        _chunk_names = {
            _CHUNK_NONE: "none",
            _CHUNK_STATIC: "static",
            _CHUNK_DYNAMIC: "dynamic",
            _CHUNK_AUTO: "auto",
            _CHUNK_GUIDED: "guided",
        }
        return _Policy(
            name=self.name,
            kind=self._kind,
            task=self.task,
            chunk_name=_chunk_names[chunk.kind],
            chunk_kind=chunk.kind,
            chunk_size=chunk.size,
        )

    def _token(self) -> _Token:
        return _Token(
            kind=self._kind,
            task=self.task,
            chunk=self._chunk_kind,
            chunk_size=self._chunk_size,
        )

    def __repr__(self) -> str:
        suffix = ""
        if self.task:
            suffix += "_task"
        if self.chunk_name != "none":
            suffix += f"[{self.chunk_name}]"
        return f"<Policy {self.name}{suffix}>"


# Module-level singletons
seq = _Policy(name="seq", kind=_KIND_SEQ)
par = _Policy(name="par", kind=_KIND_PAR)
par_unseq = _Policy(name="par_unseq", kind=_KIND_PAR_UNSEQ)
unseq = _Policy(name="unseq", kind=_KIND_UNSEQ)

# Public alias for type annotations.
Policy = _Policy


__all__ = [
    "ChunkSize",
    "Policy",
    "auto_chunk_size",
    "dynamic_chunk_size",
    "guided_chunk_size",
    "par",
    "par_unseq",
    "seq",
    "static_chunk_size",
    "task",
    "unseq",
]
