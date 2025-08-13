# ruff: noqa: ARG002 # intentionally disabling ruff linting on this file, false positive flag
"""
HPXExecutor implementation for asynchronous task execution.

This module provides the HPXExecutor class, which is a subclass of 
concurrent.futures.Executor that allows for submitting tasks to the HPX 
runtime system for parallel and asynchronous execution.

The HPXExecutor manages the HPX runtime lifecycle and provides a familiar
interface compatible with Python's concurrent.futures framework.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any

import hpyx


class HPXExecutor(Executor):
    """
    An Executor subclass for submitting tasks to the HPX runtime system.
    
    HPXExecutor provides an interface for asynchronous execution of functions
    using the High Performance ParalleX (HPX) runtime. It manages the lifecycle
    of tasks and allows for parallel computation with configurable runtime
    parameters.
    
    This executor is compatible with Python's concurrent.futures interface,
    making it easy to integrate HPX-based parallelism into existing code.
    
    Examples
    --------
    >>> def compute_square(x):
    ...     return x * x
    >>> with HPXExecutor(os_threads=4) as executor:
    ...     future = executor.submit(compute_square, 10)
    ...     result = future.result()
    ...     print(result)  # Outputs: 100
    
    Notes
    -----
    This class is currently in active development and may undergo changes.
    We recommend using the HPXRuntime context manager rather than this
    executor directly for managing the HPX runtime lifecycle.
    """

    def __init__(
        self,
        run_hpx_main: bool = True,
        allow_unknown: bool = True,
        aliasing: bool = False,
        os_threads: int = 1,
        diagnostics_on_terminate: bool = False,
        tcp_enable: bool = False,
    ) -> None:
        """
        Initialize the HPXExecutor with configurable runtime options.

        Parameters
        ----------
        run_hpx_main : bool, default True
            Whether to execute hpx_main function.
        allow_unknown : bool, default True
            Allow unknown command line options to be passed through.
        aliasing : bool, default False
            Enable HPX short command line option aliases.
        os_threads : int, default 1
            Number of OS threads for the HPX runtime to use.
        diagnostics_on_terminate : bool, default False
            Print diagnostic information during forced runtime termination.
        tcp_enable : bool, default False
            Enable the TCP parcelport for distributed computing.
                
        Notes
        -----
        The executor automatically initializes the HPX runtime with the 
        provided configuration. Only one HPXExecutor should be active
        at a time within a process.
        """
        cfg = [
            f"hpx.run_hpx_main!={int(run_hpx_main)}",
            f"hpx.commandline.allow_unknown!={int(allow_unknown)}",
            f"hpx.commandline.aliasing!={int(aliasing)}",
            f"hpx.os_threads!={os_threads}",
            f"hpx.diagnostics_on_terminate!={int(diagnostics_on_terminate)}",
            f"hpx.parcel.tcp.enable!={int(tcp_enable)}",
        ]

        hpyx._core.init_hpx_runtime(cfg)

    def submit(self: HPXExecutor, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        """
        Submit a callable for asynchronous execution with given arguments.

        Parameters
        ----------
        fn : callable
            The callable to be executed. Must be serializable if used in
            distributed contexts.
        *args : tuple
            Positional arguments to pass to the callable.
        **kwargs : dict
            Keyword arguments to pass to the callable.

        Returns
        -------
        HPXFuture
            An HPXFuture representing the execution of the callable. The future
            can be used to retrieve the result when computation is complete or
            to check execution status.
            
        Notes
        -----
        The returned future is compatible with Python's concurrent.futures
        interface but uses HPX's asynchronous execution system internally.
        """
        fut: hpyx._core.HPXFuture = Future()
        fut.set_running_or_notify_cancel()
        fut._hpx_cont = hpyx._core.hpx_async_set_result(fut, fn, *args, **kwargs)
        return fut

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """
        Signal the executor to stop accepting new tasks and shutdown.

        Clean shutdown involves stopping the HPX runtime and optionally waiting
        for running tasks to complete before termination.

        Parameters
        ----------
        wait : bool, default True
            If True, wait for currently running tasks to complete before
            shutting down. If False, shutdown immediately.
        cancel_futures : bool, default False
            Currently not implemented. Reserved for future use
            to cancel pending futures during shutdown.
                
        Notes
        -----
        After shutdown is called, no new tasks can be submitted to this
        executor. The HPX runtime will be stopped and cannot be restarted
        within the same process.
        """
        hpyx._core.stop_hpx_runtime()
