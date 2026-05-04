"""hpyx.multiprocessing — DEPRECATED.

This subpackage is deprecated and will be removed in a future release.
Use ``hpyx.parallel`` instead, which provides a richer set of parallel
algorithms (for_each, for_loop, transform, reduce, etc.) with explicit
execution policies from ``hpyx.execution``.

Migration:
    Old: ``hpyx.multiprocessing.for_loop(fn, iterable, policy="par")``
    New: ``hpyx.parallel.for_each(hpyx.execution.par, iterable, fn)``
"""

from __future__ import annotations

import warnings as _warnings

from ._for_loop import for_loop

_warnings.warn(
    "hpyx.multiprocessing is deprecated and will be removed in a future release. "
    "Use hpyx.parallel instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["for_loop"]
