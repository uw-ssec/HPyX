"""Shared helpers for HPyX benchmark test modules.

Import from here rather than from conftest to get IDE support and explicit
dependency tracking::

    from helpers import requires_free_threading
"""

from __future__ import annotations

import sysconfig

import pytest

requires_free_threading = pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"),
    reason="Benchmark requires free-threaded Python 3.13t "
           "(sysconfig.get_config_var('Py_GIL_DISABLED') == 1)",
)

__all__ = ["requires_free_threading"]
