"""Diagnostics and tracing hooks."""

from __future__ import annotations

import json
import os
import threading
from typing import Optional

from hpyx import _core, _runtime


def get_num_worker_threads() -> int:
    """Return the number of HPX worker OS threads in the default pool."""
    _runtime.ensure_started()
    return int(_core.runtime.num_worker_threads())


def get_worker_thread_id() -> int:
    """Return the caller's HPX worker thread id, or -1 if not on an HPX thread."""
    _runtime.ensure_started()
    return int(_core.runtime.get_worker_thread_id())


_trace_state: dict = {
    "enabled": False,
    "path": None,
    "thread": None,
    "stop": None,
}


def _drain_loop(path: str, stop_event: threading.Event) -> None:
    """Background thread: periodically drain C++ ring buffer to JSONL."""
    with open(path, "a", encoding="utf-8") as f:
        while not stop_event.is_set():
            events = _core.tracing.drain()
            for ev in events:
                f.write(
                    json.dumps(
                        {
                            "name": ev.name,
                            "worker_thread_id": ev.worker_thread_id,
                            "start_ns": ev.start_ns,
                            "duration_ns": ev.duration_ns,
                        }
                    )
                    + "\n"
                )
            f.flush()
            stop_event.wait(timeout=0.1)
        # Final drain after stop signal.
        for ev in _core.tracing.drain():
            f.write(
                json.dumps(
                    {
                        "name": ev.name,
                        "worker_thread_id": ev.worker_thread_id,
                        "start_ns": ev.start_ns,
                        "duration_ns": ev.duration_ns,
                    }
                )
                + "\n"
            )


def enable_tracing(path: Optional[str] = None) -> None:
    """Start capturing per-task trace events to a JSONL file.

    Parameters
    ----------
    path : str | None
        File path to write events to. Falls back to ``HPYX_TRACE_PATH``
        env var if not provided.
    """
    if _trace_state["enabled"]:
        raise RuntimeError("tracing is already enabled — call disable_tracing first")

    if path is None:
        path = os.environ.get("HPYX_TRACE_PATH")
    if path is None:
        raise ValueError(
            "enable_tracing requires a path argument or HPYX_TRACE_PATH env var"
        )

    # Validate the path is openable synchronously so callers get an immediate
    # error instead of a silent failure inside the daemon drain thread.
    try:
        with open(path, "a"):
            pass
    except OSError as exc:
        raise OSError(
            f"enable_tracing: cannot open trace path {path!r}: {exc}"
        ) from exc

    _runtime.ensure_started()
    _core.tracing.enable()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_drain_loop,
        args=(path, stop_event),
        daemon=True,
    )
    thread.start()

    _trace_state["enabled"] = True
    _trace_state["path"] = path
    _trace_state["thread"] = thread
    _trace_state["stop"] = stop_event


def disable_tracing() -> None:
    """Stop capturing. Flushes buffered events to the output file."""
    if not _trace_state["enabled"]:
        return

    _core.tracing.disable()
    _trace_state["stop"].set()
    _trace_state["thread"].join(timeout=5.0)

    _trace_state["enabled"] = False
    _trace_state["path"] = None
    _trace_state["thread"] = None
    _trace_state["stop"] = None


__all__ = [
    "disable_tracing",
    "enable_tracing",
    "get_num_worker_threads",
    "get_worker_thread_id",
]
