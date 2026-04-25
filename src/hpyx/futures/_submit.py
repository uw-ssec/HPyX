"""
Function submission for asynchronous execution using HPX.

This module provides the submit function for executing functions asynchronously
using the HPX runtime system.
"""

from __future__ import annotations

from collections.abc import Callable

from .._core.futures import HPXFuture, async_submit


def submit(function: Callable, *args, **kwargs) -> HPXFuture:
    """
    Submit a function to be executed asynchronously using HPX.

    This function provides a simple interface for asynchronous execution
    using HPX's async functionality with launch::async policy.

    Parameters
    ----------
    function : callable
        The callable to execute asynchronously.
    *args : tuple
        Variable length argument list to pass to the function.
    **kwargs : dict
        Keyword arguments to pass to the function.

    Returns
    -------
    HPXFuture
        An HPXFuture object representing the result of the asynchronous execution.
        Use .result() to retrieve the result when computation is complete.

    Notes
    -----
    This function requires an active HPX runtime. Ensure that you call
    this function within an HPXRuntime context manager or after hpyx.init().
    """
    return async_submit(function, args, kwargs)
