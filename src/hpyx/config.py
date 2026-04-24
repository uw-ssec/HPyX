"""Configuration for the HPyX runtime.

Precedence: explicit hpyx.init() kwargs > environment variables > DEFAULTS.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULTS: dict[str, Any] = {
    "os_threads": None,
    "cfg": [],
    "autoinit": True,
    "trace_path": None,
    "async_mode": "async",
}

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str, *, var_name: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(
        f"{var_name}={value!r} is not a recognized boolean "
        f"(use one of: 0, 1, true, false, yes, no, on, off)"
    )


def from_env() -> dict[str, Any]:
    """Build a config dict from HPYX_* environment variables.

    Returns a fresh copy of DEFAULTS with any present env vars layered on top.
    Unset env vars leave the default value unchanged.
    """
    cfg = dict(DEFAULTS)
    cfg["cfg"] = list(DEFAULTS["cfg"])  # defensive — don't share the default list

    raw_threads = os.environ.get("HPYX_OS_THREADS")
    if raw_threads is not None:
        try:
            cfg["os_threads"] = int(raw_threads)
        except ValueError as exc:
            raise ValueError(
                f"HPYX_OS_THREADS={raw_threads!r} must be an integer"
            ) from exc

    raw_cfg = os.environ.get("HPYX_CFG")
    if raw_cfg is not None:
        cfg["cfg"] = [entry for entry in raw_cfg.split(";") if entry]

    raw_autoinit = os.environ.get("HPYX_AUTOINIT")
    if raw_autoinit is not None:
        cfg["autoinit"] = _parse_bool(raw_autoinit, var_name="HPYX_AUTOINIT")

    raw_trace = os.environ.get("HPYX_TRACE_PATH")
    if raw_trace is not None:
        cfg["trace_path"] = raw_trace

    raw_async_mode = os.environ.get("HPYX_ASYNC_MODE")
    if raw_async_mode is not None:
        lowered = raw_async_mode.strip().lower()
        if lowered not in {"async", "deferred"}:
            raise ValueError(
                f"HPYX_ASYNC_MODE={raw_async_mode!r} must be 'async' or 'deferred'"
            )
        cfg["async_mode"] = lowered

    return cfg
