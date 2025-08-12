"""
HPyX futures subpackage for asynchronous computation support.

This subpackage provides support for futures-based asynchronous computation
in HPyX. It includes utilities for submitting functions for asynchronous
execution using the HPX runtime system.

The futures module offers a simplified interface for asynchronous task
execution, complementing the more comprehensive HPXExecutor class.

Important
---------
All functions in this module require an active HPX runtime. Use the
HPXRuntime context manager to ensure proper initialization and cleanup
of the HPX runtime system before calling any functions from this module.
"""

from __future__ import annotations

from ._submit import submit

__all__ = ["submit"]
