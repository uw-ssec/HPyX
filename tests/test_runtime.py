"""Tests for hpyx runtime lifecycle."""

import pytest

import hpyx
from hpyx import HPXRuntime, _runtime, is_running


def test_ensure_started_is_idempotent():
    _runtime.ensure_started()
    assert is_running()
    _runtime.ensure_started()
    assert is_running()


def test_init_idempotent_with_same_args():
    hpyx.init(os_threads=4)
    hpyx.init(os_threads=4)
    assert is_running()


def test_init_raises_on_conflicting_threads():
    with pytest.raises(RuntimeError, match="different config"):
        hpyx.init(os_threads=2)


def test_init_raises_on_conflicting_cfg():
    with pytest.raises(RuntimeError, match="different config"):
        hpyx.init(cfg=["hpx.stacks.small_size=0x40000"])


def test_is_running_true_during_session():
    assert is_running()


def test_running_os_threads_reflects_session_config():
    """The session fixture starts the runtime with os_threads=4."""
    assert _runtime.running_os_threads() == 4


def test_HPXRuntime_context_manager():
    assert is_running()
    with HPXRuntime() as rt:
        assert rt is not None
        assert is_running()
    assert is_running()


def test_HPXRuntime_nested_is_idempotent():
    with HPXRuntime():
        with HPXRuntime():
            assert is_running()
        assert is_running()
    assert is_running()


def test_ensure_started_honors_explicit_over_env(monkeypatch):
    monkeypatch.setenv("HPYX_OS_THREADS", "16")
    _runtime.ensure_started(os_threads=4)
    assert is_running()
    with pytest.raises(RuntimeError, match="different config"):
        _runtime.ensure_started(os_threads=16)


@pytest.mark.skip_after_shutdown
def test_shutdown_makes_further_init_raise():
    hpyx.shutdown()
    assert not is_running()
    with pytest.raises(RuntimeError, match="cannot restart"):
        hpyx.init()


@pytest.mark.skip_after_shutdown
def test_shutdown_is_idempotent():
    hpyx.shutdown()
    hpyx.shutdown()
    assert not is_running()
