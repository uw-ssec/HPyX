from __future__ import annotations

from concurrent.futures import Executor, Future

from hpyx._core import hpx_async_set_result, init_hpx_runtime, stop_hpx_runtime


class HPXExecutor(Executor):
    """
    HPXExecutor is a subclass of Executor that provides an interface for submitting tasks to the HPX runtime system.
    It allows for asynchronous execution of functions and provides a way to manage the lifecycle of tasks.
    """

    def __init__(
        self,
        run_hpx_main=True,
        allow_unknown=True,
        aliasing=False,
        os_threads=1,
        diagnostics_on_terminate=False,
        tcp_enable=False,
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

        init_hpx_runtime(cfg)

    def submit(self, fn, /, *args, **kwargs) -> Future:
        """
        Submits a callable to be executed with the given arguments.

        :param fn: The callable to be executed.
        :param args: The positional arguments to pass to the callable.
        :return: An HPXFuture representing the execution of the callable.
        """
        fut: Future = Future()
        fut.set_running_or_notify_cancel()
        fut._hpx_cont = hpx_async_set_result(fut, fn, *args, **kwargs)
        return fut

    def shutdown(self) -> None:
        """
        Signals the executor to stop accepting new tasks and optionally waits for running tasks to complete.

        :param wait: If True, wait for running tasks to complete before shutting down.
        """
        stop_hpx_runtime()
