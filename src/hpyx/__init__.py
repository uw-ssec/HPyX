"""HPyX: Pythonic bindings for the HPX C++ parallel runtime."""

from __future__ import annotations

try:
    from hpyx._version import version as __version__
except ImportError:
    __version__ = "0.0.0"

from hpyx import _runtime, config, debug
from hpyx._runtime import is_running, shutdown

from hpyx.executor import HPXExecutor
from hpyx.runtime import HPXRuntime
from hpyx import futures, multiprocessing


def init(
    *,
    os_threads: int | None = None,
    cfg: list[str] | None = None,
) -> None:
    """Explicitly start the HPX runtime. Idempotent within a process.

    Raises RuntimeError if the runtime is already started with conflicting
    config, or if the runtime was previously stopped (HPX cannot restart).
    """
    _runtime.ensure_started(os_threads=os_threads, cfg=cfg)


__all__ = [
    "HPXExecutor",
    "HPXRuntime",
    "__version__",
    "config",
    "debug",
    "futures",
    "init",
    "is_running",
    "multiprocessing",
    "shutdown",
]
