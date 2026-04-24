"""HPXRuntime context manager — optional convenience wrapper.

Using this is no longer required in v1 — HPyX auto-initializes on first
use. This context manager remains for users who want explicit lifecycle
scoping in scripts and tests, and for backward compatibility with v0.x
code.

Exit does NOT shut down the runtime (HPX can't restart within a process).
Shutdown is owned by `atexit`; call `hpyx.shutdown()` explicitly if you
need to force an early stop.
"""

from __future__ import annotations

from hpyx import _runtime


class HPXRuntime:
    """Context manager that ensures the HPX runtime is running.

    Parameters
    ----------
    os_threads : int | None
        Number of HPX worker OS threads. Defaults to HPYX_OS_THREADS env
        var or os.cpu_count().
    cfg : list[str] | None
        Extra HPX config strings (e.g., ["hpx.stacks.small_size=0x20000"]).
    """

    def __init__(
        self,
        *,
        os_threads: int | None = None,
        cfg: list[str] | None = None,
    ) -> None:
        self._os_threads = os_threads
        self._cfg = cfg

    def __enter__(self) -> "HPXRuntime":
        _runtime.ensure_started(os_threads=self._os_threads, cfg=self._cfg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None
