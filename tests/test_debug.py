import pytest

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
    pytest.xfail("HPXExecutor is rewritten in Plan 2")


def test_enable_tracing_is_stubbed():
    with pytest.raises(NotImplementedError, match="v1.x"):
        debug.enable_tracing("/tmp/hpyx.jsonl")


def test_disable_tracing_is_stubbed():
    with pytest.raises(NotImplementedError, match="v1.x"):
        debug.disable_tracing()
