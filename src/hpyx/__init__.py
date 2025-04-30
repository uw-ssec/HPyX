from __future__ import annotations

try:
    import hpyx._version as v

    __version__ = v.version
except ImportError:
    __version__ = "0.0.0"  # Fallback version

import atexit

from . import hello
from ._core import add, hpx_hello, init_hpx_runtime, stop_hpx_runtime

cfg = [
    # make sure hpx_main is always executed
    "hpx.run_hpx_main!=1",
    # allow for unknown command line options
    "hpx.commandline.allow_unknown!=1",
    # disable HPX' short options
    "hpx.commandline.aliasing!=0",
    # by default run one thread only (for now)
    "hpx.os_threads!=1",
    # don't print diagnostics during forced terminate
    "hpx.diagnostics_on_terminate!=0",
    # disable the TCP parcelport
    "hpx.parcel.tcp.enable!=0"
]

init_hpx_runtime(cfg)

atexit.register(stop_hpx_runtime)

__all__ = ["add", "hello", "hpx_hello"]
