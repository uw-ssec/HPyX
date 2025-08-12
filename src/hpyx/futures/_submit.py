"""
Function submission for asynchronous execution using HPX.

This module provides the submit function for executing functions asynchronously
using the HPX runtime system with a deferred execution policy.
"""

from __future__ import annotations

from collections.abc import Callable

from .._core import future, hpx_async


def submit(function: Callable, *args) -> future:
    """
    Submit a function to be executed asynchronously using HPX.
    
    This function provides a simple interface for asynchronous execution
    using HPX's async functionality with a deferred launch policy. The
    function will be executed when the result is requested.

    Parameters
    ----------
    function : callable
        The callable to execute asynchronously. Must be serializable
        if used in distributed contexts.
    *args : tuple
        Variable length argument list to pass to the function.

    Returns
    -------
    hpx_future
        An HPX future object representing the result of the asynchronous execution.
        The future can be used to retrieve the result when computation is
        complete or to check execution status.
        
    Notes
    -----
    Under the hood, this uses `hpx::async` with `hpx::launch::deferred`
    policy, meaning the function execution is deferred until the result
    is explicitly requested via the future.
    
    This function requires an active HPX runtime. Ensure that you call
    this function within an HPXRuntime context manager.
        
    Examples
    --------
    >>> from hpyx import HPXRuntime
    >>> def square(x):
    ...     return x * x
    >>> with HPXRuntime() as runtime:
    ...     future_result = submit(square, 5)
    ...     result = future_result.get()  # This triggers execution
    ...     print(result)  # Outputs: 25
    """
    return hpx_async(function, *args)
