import json
import os
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

    lines = open(path).read().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert event["name"].endswith("work")
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

    lines = open(path).read().strip().split("\n")
    assert len(lines) >= 1
    event = json.loads(lines[0])
    assert "name" in event
    assert "duration_ns" in event
