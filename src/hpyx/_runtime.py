"""Internal runtime lifecycle for HPyX.

`ensure_started()` is called by every public API that needs the runtime.
It is idempotent, thread-safe, and respects HPYX_AUTOINIT=0 (in which case
it raises instead of auto-starting).

Shutdown is registered with `atexit` on first start; users should not call
`_core.runtime.runtime_stop()` directly.
"""

from __future__ import annotations

import atexit
import threading
from typing import Any

from hpyx import config as _config
from hpyx import _core

_lock = threading.Lock()
_started = False
_started_cfg: dict[str, Any] | None = None
_atexit_registered = False


def _build_cfg_strings(
    *, os_threads: int | None, cfg: list[str]
) -> list[str]:
    """Translate Python kwargs into HPX-style config strings."""
    result: list[str] = []
    if os_threads is not None:
        result.append(f"hpx.os_threads!={int(os_threads)}")
    result.append("hpx.run_hpx_main!=1")
    result.append("hpx.commandline.allow_unknown!=1")
    result.append("hpx.commandline.aliasing!=0")
    result.append("hpx.diagnostics_on_terminate!=0")
    result.append("hpx.parcel.tcp.enable!=0")
    result.extend(cfg)
    return result


def _normalized_cfg(
    *, os_threads: int | None = None, cfg: list[str] | None = None
) -> dict[str, Any]:
    """Merge kwargs → env vars → DEFAULTS into a canonical config dict."""
    env = _config.from_env()
    if os_threads is None:
        os_threads = env["os_threads"]
    if cfg is None:
        cfg = env["cfg"]
    return {
        "os_threads": os_threads,
        "cfg": list(cfg),
        "autoinit": env["autoinit"],
        "trace_path": env["trace_path"],
    }


def ensure_started(
    *, os_threads: int | None = None, cfg: list[str] | None = None
) -> None:
    """Start the HPX runtime if not already started. Idempotent.

    If the runtime is already started with a *different* (os_threads, cfg),
    raises RuntimeError — HPX cannot be reconfigured after start.

    Respects HPYX_AUTOINIT=0 only when called with all defaults; explicit
    kwargs always start the runtime.
    """
    global _started, _started_cfg, _atexit_registered
    normalized = _normalized_cfg(os_threads=os_threads, cfg=cfg)

    with _lock:
        if _started:
            if _started_cfg is not None:
                # Only raise on an explicit conflict — caller passing None means
                # "use whatever is already running".
                conflict_threads = (
                    os_threads is not None
                    and _started_cfg["os_threads"] != os_threads
                )
                conflict_cfg = (
                    cfg is not None
                    and _started_cfg["cfg"] != list(cfg)
                )
                if conflict_threads or conflict_cfg:
                    raise RuntimeError(
                        "HPyX runtime already started with different config: "
                        f"existing={_started_cfg!r}, requested={normalized!r}"
                    )
            return

        explicit = os_threads is not None or cfg is not None
        if not explicit and not normalized["autoinit"]:
            raise RuntimeError(
                "HPyX auto-init is disabled (HPYX_AUTOINIT=0) and no "
                "explicit hpyx.init(...) call was made"
            )

        cfg_strings = _build_cfg_strings(
            os_threads=normalized["os_threads"], cfg=normalized["cfg"]
        )
        _core.runtime.runtime_start(cfg_strings)
        _started = True
        _started_cfg = normalized

        if not _atexit_registered:
            atexit.register(_atexit_shutdown)
            _atexit_registered = True


def _atexit_shutdown() -> None:
    """Called at process exit. Tolerant of double-shutdown."""
    global _started
    if _started:
        try:
            _core.runtime.runtime_stop()
        except Exception:  # noqa: BLE001 — atexit must never raise
            pass
        _started = False


def shutdown() -> None:
    """Explicit shutdown. Irreversible within the process."""
    global _started
    with _lock:
        if _started:
            _core.runtime.runtime_stop()
            _started = False


def is_running() -> bool:
    return _core.runtime.runtime_is_running()


def running_os_threads() -> int | None:
    """Return the os_threads of the running HPX runtime, or None if not started."""
    if not _started:
        return None
    if _started_cfg is None:
        return None
    threads = _started_cfg.get("os_threads")
    return int(threads) if threads is not None else None
