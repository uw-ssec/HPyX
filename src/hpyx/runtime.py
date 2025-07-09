from __future__ import annotations

import hpyx


class HPXRuntime:
    def __init__(
        self,
        run_hpx_main=True,
        allow_unknown=True,
        aliasing=False,
        os_threads="auto",
        diagnostics_on_terminate=False,
        tcp_enable=False,
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

    def __enter__(self) -> HPXRuntime:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        hpyx._core.stop_hpx_runtime()
