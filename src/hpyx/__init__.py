from __future__ import annotations

try:
    import hpyx._version as v

    __version__ = v.version
except ImportError:
    __version__ = "0.0.0"  # Fallback version

from . import hello
from ._core import add

__all__ = ["add", "hello"]
