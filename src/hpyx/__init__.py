"""
HPyX: Python interface for the C++ HPX library.

HPyX provides Python bindings for the High Performance ParalleX (HPX) library,
enabling high-performance parallel and distributed computing in Python applications.

Important
---------
The futures and multiprocessing modules require an active HPX runtime.
Use the HPXRuntime context manager to ensure proper initialization and
cleanup before calling functions from these modules:

    >>> from hpyx import HPXRuntime, futures, multiprocessing
    >>> with HPXRuntime() as runtime:
    ...     # Use futures and multiprocessing functions here
    ...     result = futures.submit(my_function, args)

Alternatively, use HPXExecutor as a standalone context manager for
task-based execution.
"""

from __future__ import annotations

try:
    import hpyx._version as v

    __version__ = v.version
except ImportError:
    __version__ = "0.0.0"  # Fallback version

from . import futures, multiprocessing
from .executor import HPXExecutor
from .runtime import HPXRuntime

__all__ = ["HPXExecutor", "HPXRuntime", "futures", "multiprocessing"]
