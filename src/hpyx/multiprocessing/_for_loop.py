"""
Parallel for-loop execution using HPX algorithms.

This module provides the for_loop function that leverages HPX's parallel
algorithms to execute functions over iterables with configurable execution
policies.

.. deprecated::
    This legacy module delegates to ``hpyx.parallel.for_each``. Prefer
    using ``hpyx.parallel.for_each`` or ``hpyx.parallel.for_loop`` directly.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable
from typing import Literal

import numpy as np

from hpyx import _core, _runtime
from hpyx.execution import par as _par, seq as _seq


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
        - 'par' : Parallel execution using available cores

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
    warnings.warn(
        "hpyx.multiprocessing.for_loop is deprecated and will be removed in a "
        "future release. Use hpyx.parallel.for_each(policy, iterable, fn) "
        "instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    if policy not in {"seq", "par"}:
        raise ValueError(f"policy must be 'seq' or 'par', got {policy!r}")
    exec_policy = _par if policy == "par" else _seq
    _runtime.ensure_started()
    if isinstance(iterable, (list, np.ndarray)):
        # Preserve the deprecated transform-and-store contract: for list and
        # ndarray inputs, write function's return value back to each position.
        for i, item in enumerate(iterable):
            iterable[i] = function(item)
    else:
        t = exec_policy._token()
        _core.parallel.for_each(t.kind, t.task, t.chunk, t.chunk_size,
                                iterable, function)
