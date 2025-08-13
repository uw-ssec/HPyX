"""
Parallel for-loop execution using HPX algorithms.

This module provides the for_loop function that leverages HPX's parallel
algorithms to execute functions over iterables with configurable execution
policies.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Literal

from .._core import hpx_for_loop


def for_loop(
    function: Callable, iterable: Iterable, policy: Literal["seq", "par"] = "seq"
) -> None:
    """
    Execute a function over an iterable using HPX's parallel for_loop.

    This function applies a given function to each element in an iterable
    using HPX's optimized parallel for_loop algorithm. The execution can
    be configured to run sequentially or in parallel.

    Parameters
    ----------
    function : callable
        The callable to apply to each element in the iterable.
        The function should accept a single argument (the iterable element).
    iterable : iterable
        The iterable to process. Elements will be passed to the
        function one by one.
    policy : {'seq', 'par'}, default 'seq'
        Execution policy for the loop.
        - 'seq' : Sequential execution
        - 'par' : Parallel execution using available cores (*not yet implemented*)

    Notes
    -----
    This method will modify the iterable in place if the provided function
    modifies its arguments. The original iterable may be changed after
    this function completes.

    This function requires an active HPX runtime. Ensure that you call
    this function within an HPXRuntime context manager.

    Examples
    --------
    >>> from hpyx import HPXRuntime
    >>> data = [1, 2, 3, 4, 5]
    >>> def square_inplace(x):
    ...     x[0] = x[0] ** 2  # Modify in place
    >>> with HPXRuntime() as runtime:
    ...     for_loop(square_inplace, enumerate(data), policy="seq")
    ...     print(data)  # data is now modified
    """
    if policy == "par":
        msg = "Parallel execution policy is not yet implemented in this version."
        raise NotImplementedError(msg)
    hpx_for_loop(function, iterable, policy)
