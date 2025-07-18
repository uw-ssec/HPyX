# ruff: noqa: ARG002 # intentionally disabling ruff linting on this file, false positive flag
"""
This module provides the HPXExecutor class, which is a subclass of Executor
that allows for submitting tasks to the HPX runtime system.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any

import hpyx


class HPXExecutor(Executor):
    """
    HPXExecutor is a subclass of Executor that provides an interface for submitting tasks to the HPX runtime system.
    It allows for asynchronous execution of functions and provides a way to manage the lifecycle of tasks.
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
        Initializes the HPXExecutor with configurable options.

        :param run_hpx_main: Whether to execute hpx_main
        :param allow_unknown: Allow for unknown command line options
        :param aliasing: Enable HPX' short options
        :param os_threads: Number of OS threads to use
        :param diagnostics_on_terminate: Print diagnostics during forced terminate
        :param tcp_enable: Enable the TCP parcelport
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
        Submits a callable to be executed with the given arguments.

        :param fn: The callable to be executed.
        :param args: The positional arguments to pass to the callable.
        :return: An HPXFuture representing the execution of the callable.
        """
        fut: hpyx._core.HPXFuture = Future()
        fut.set_running_or_notify_cancel()
        fut._hpx_cont = hpyx._core.hpx_async_set_result(fut, fn, *args, **kwargs)
        return fut

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """
        Signals the executor to stop accepting new tasks and optionally waits for running tasks to complete.

        :param wait: If True, wait for running tasks to complete before shutting down.
        """
        hpyx._core.stop_hpx_runtime()
