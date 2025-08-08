"""hpyx package.

Python interface for the C++ HPX library.
"""

from __future__ import annotations

try:
    import hpyx._version as v

    __version__ = v.version
except ImportError:
    __version__ = "0.0.0"  # Fallback version

from . import hello, multiprocessing
from ._core import add, hpx_hello
from .executor import HPXExecutor
from .runtime import HPXRuntime

__all__ = ["HPXExecutor", "HPXRuntime", "add", "hello", "hpx_hello", "multiprocessing"]
