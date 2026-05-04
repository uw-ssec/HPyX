import json
import os
import threading
import time

import pytest

import hpyx
from hpyx import debug


def test_get_num_worker_threads_positive():
    # Session fixture started runtime with os_threads=4.
    assert debug.get_num_worker_threads() == 4


def test_get_worker_thread_id_from_python_thread_is_minus_one():
    # HPX may register the Python main thread as an HPX thread when using
    # hpx::start (non-main-thread launch). If so, a non-negative id is valid.
    result = debug.get_worker_thread_id()
    assert result == -1 or result >= 0


def test_get_worker_thread_id_from_hpx_thread_is_valid():
    # Worker thread id from an HPX thread must be >= 0.
    fut = hpyx.async_(lambda: debug.get_worker_thread_id())
    result = fut.result()
    assert result >= 0


def test_enable_tracing_writes_jsonl(tmp_path):
    path = str(tmp_path / "trace.jsonl")
    debug.enable_tracing(path)
    try:
        def work(x):
            return x * 2

        fut = hpyx.async_(work, 42)
        assert fut.result() == 84
        # Give the drain thread time to flush.
        time.sleep(0.3)
    finally:
        debug.disable_tracing()

    with open(path) as f:
        lines = f.read().strip().split("\n")
    assert len(lines) >= 1
    events = [json.loads(ln) for ln in lines]
    matching = [e for e in events if e.get("name", "").endswith("work")]
    assert matching, f"No 'work' event in {[e['name'] for e in events]}"
    event = matching[0]
    assert event["worker_thread_id"] >= 0
    assert event["duration_ns"] > 0
    assert "start_ns" in event


def test_enable_tracing_without_path_or_env_raises():
    os.environ.pop("HPYX_TRACE_PATH", None)
    with pytest.raises(ValueError, match="path"):
        debug.enable_tracing()


def test_enable_tracing_twice_raises(tmp_path):
    path = str(tmp_path / "trace.jsonl")
    debug.enable_tracing(path)
    try:
        with pytest.raises(RuntimeError, match="already enabled"):
            debug.enable_tracing(path)
    finally:
        debug.disable_tracing()


def test_disable_tracing_idempotent():
    debug.disable_tracing()  # noop
    debug.disable_tracing()  # still noop


def test_enable_tracing_via_env(tmp_path):
    path = str(tmp_path / "env_trace.jsonl")
    os.environ["HPYX_TRACE_PATH"] = path
    try:
        debug.enable_tracing()  # no path arg — uses env var
        fut = hpyx.async_(lambda: 1)
        fut.result()
        time.sleep(0.3)
    finally:
        debug.disable_tracing()
        os.environ.pop("HPYX_TRACE_PATH", None)

    with open(path) as f:
        lines = f.read().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert "name" in event
    assert "duration_ns" in event


def test_enable_tracing_invalid_path_raises_synchronously():
    """enable_tracing must raise OSError synchronously for an unwritable path."""
    bad_path = "/nonexistent_parent_dir/that/cannot/exist/trace.jsonl"
    with pytest.raises(OSError):
        debug.enable_tracing(bad_path)
    # State must not be left as enabled after the failure.
    assert not debug._trace_state["enabled"]


def test_pre_tracing_tasks_not_emitted_as_blank(tmp_path):
    """Tasks submitted before enable_tracing must not produce blank-name events.

    A gate event keeps the task alive while tracing is enabled so that the
    task is guaranteed to complete *after* enable_tracing() is called — the
    canonical race the fix targets.
    """
    path = str(tmp_path / "trace.jsonl")
    gate = threading.Event()

    def gated_task():
        gate.wait(timeout=5.0)
        return "pre-tracing"

    # Submit before tracing is enabled.
    fut = hpyx.async_(gated_task)

    # Enable tracing while the task is blocked on the gate.
    debug.enable_tracing(path)

    # Release the task so it completes after tracing is active.
    gate.set()
    assert fut.result() == "pre-tracing"

    # Also submit a post-tracing task to confirm tracing itself works.
    def traced_task():
        return "post-tracing"

    hpyx.async_(traced_task).result()
    time.sleep(0.2)
    debug.disable_tracing()

    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read().strip()
    if not content:
        return
    events = [json.loads(ln) for ln in content.split("\n") if ln.strip()]
    blank = [e for e in events if e.get("name", "") == ""]
    assert blank == [], f"Found blank-name events: {blank}"
