"""
HPXRuntime context manager for managing HPX runtime lifecycle.

This module provides the HPXRuntime class that serves as a context manager
for managing the High Performance ParalleX (HPX) runtime lifecycle. It allows
for configuration of the runtime parameters and ensures that the runtime is
properly started and stopped in a controlled manner.

The HPXRuntime is designed to be used in with-statements to guarantee proper
cleanup of HPX resources.
"""

from __future__ import annotations

from types import TracebackType

import hpyx


class HPXRuntime:
    """
    A context manager for managing the HPX runtime lifecycle.
    
    HPXRuntime provides a convenient way to initialize and manage the High
    Performance ParalleX (HPX) runtime system. It ensures that the runtime
    is properly configured, started, and stopped in a controlled manner.
    
    The class is designed to be used as a context manager with Python's
    'with' statement, guaranteeing proper cleanup of HPX resources even
    if exceptions occur.
    
    Examples
    --------
    >>> with HPXRuntime(os_threads=4) as runtime:
    ...     # HPX runtime is active here
    ...     # Use HPX functions and operations
    ...     pass
    # HPX runtime is automatically stopped here
    """

    def __init__(
        self,
        run_hpx_main: bool = True,
        allow_unknown: bool = True,
        aliasing: bool = False,
        os_threads: str = "auto",
        diagnostics_on_terminate: bool = False,
        tcp_enable: bool = False,
    ) -> None:
        """
        Initialize the HPX runtime with configuration parameters.
        
        Parameters
        ----------
        run_hpx_main : bool, default True
            Whether to execute hpx_main function.
        allow_unknown : bool, default True
            Allow unknown command line options to be passed through.
        aliasing : bool, default False
            Enable HPX short command line option aliases.
        os_threads : str, default "auto"
            Number of OS threads for the HPX runtime. Can be an integer
            as a string or "auto" for automatic detection.
        diagnostics_on_terminate : bool, default False
            Print diagnostic information during forced runtime termination.
        tcp_enable : bool, default False
            Enable the TCP parcelport for distributed computing.
                
        Notes
        -----
        The runtime is initialized immediately upon object creation.
        Use this class as a context manager to ensure proper cleanup.
        """
        cfg = [
            f"hpx.run_hpx_main!={int(run_hpx_main)}",
            f"hpx.commandline.allow_unknown!={int(allow_unknown)}",
            f"hpx.commandline.aliasing!={int(aliasing)}",
            f"hpx.diagnostics_on_terminate!={int(diagnostics_on_terminate)}",
            f"hpx.parcel.tcp.enable!={int(tcp_enable)}",
        ]

        if os_threads != "auto":
            cfg.append(f"hpx.os_threads!={os_threads}")
        hpyx._core.init_hpx_runtime(cfg)

    def __enter__(self: HPXRuntime) -> HPXRuntime:
        """
        Enter the runtime context.
        
        Returns
        -------
        HPXRuntime
            The HPXRuntime instance for use in the with-statement context.
            
        Notes
        -----
        The HPX runtime is already initialized in __init__, so this method
        simply returns self to support the context manager protocol.
        """
        return self

    def __exit__(
        self: HPXRuntime,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the runtime context and cleanup HPX resources.
        
        Parameters
        ----------
        exc_type : type[BaseException] or None
            The exception type if an exception was raised in the
            with-block, None otherwise.
        exc_value : BaseException or None
            The exception instance if an exception was raised in the
            with-block, None otherwise.
        traceback : TracebackType or None
            The traceback object if an exception was raised in the
            with-block, None otherwise.
                
        Notes
        -----
        This method ensures that the HPX runtime is properly stopped
        regardless of whether the with-block completed normally or
        raised an exception.
        """
        hpyx._core.stop_hpx_runtime()
