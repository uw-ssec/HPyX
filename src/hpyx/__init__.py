"""HPyX: Pythonic bindings for the HPX C++ parallel runtime."""

from __future__ import annotations

try:
    from hpyx._version import version as __version__
except ImportError:
    __version__ = "0.0.0"

from hpyx import _runtime, aio, config, debug, execution, futures, kernels, parallel
from hpyx._runtime import is_running, shutdown
from hpyx.executor import HPXExecutor
from hpyx.futures import (
    Future,
    async_,
    dataflow,
    ready_future,
    shared_future,
    when_all,
    when_any,
)
from hpyx.runtime import HPXRuntime


def init(
    *,
    os_threads: int | None = None,
    cfg: list[str] | None = None,
) -> None:
    """Explicitly start the HPX runtime. Idempotent within a process."""
    _runtime.ensure_started(os_threads=os_threads, cfg=cfg)


__all__ = [
    "Future",
    "HPXExecutor",
    "HPXRuntime",
    "__version__",
    "aio",
    "async_",
    "config",
    "dataflow",
    "debug",
    "execution",
    "futures",
    "init",
    "kernels",
    "is_running",
    "parallel",
    "ready_future",
    "shared_future",
    "shutdown",
    "when_all",
    "when_any",
]
