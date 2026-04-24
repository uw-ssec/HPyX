"""Diagnostics and tracing hooks.

Phase-0 scope: query-only (worker thread count + current thread id).
`enable_tracing` / `disable_tracing` are stubbed and raise — full
JSONL-output implementation ships in Plan 4.
"""

from __future__ import annotations

from hpyx import _core, _runtime


def get_num_worker_threads() -> int:
    """Return the number of HPX worker OS threads in the default pool."""
    _runtime.ensure_started()
    return int(_core.runtime.num_worker_threads())


def get_worker_thread_id() -> int:
    """Return the caller's HPX worker thread id, or -1 if not on an HPX thread."""
    _runtime.ensure_started()
    return int(_core.runtime.get_worker_thread_id())


def enable_tracing(path: str | None = None) -> None:
    """Start capturing per-task events as JSONL. Ships in v1.x."""
    raise NotImplementedError("hpyx.debug.enable_tracing ships in v1.x (Plan 4)")


def disable_tracing() -> None:
    """Stop capturing per-task events. Ships in v1.x."""
    raise NotImplementedError("hpyx.debug.disable_tracing ships in v1.x (Plan 4)")
