"""
This module provides the HPXRuntime class for managing the HPX runtime lifecycle.
It allows for configuration of the runtime and provides context management for starting and stopping the HPX runtime
"""

from __future__ import annotations

from types import TracebackType

import hpyx


class HPXRuntime:
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
        return self

    def __exit__(
        self: HPXRuntime,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        hpyx._core.stop_hpx_runtime()
