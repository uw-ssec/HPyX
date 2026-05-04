"""Tests for hpyx.execution policy objects and chunk-size modifiers."""

import pytest

from hpyx import execution as ex


def test_singletons_exist():
    assert ex.seq.name == "seq"
    assert ex.par.name == "par"
    assert ex.par_unseq.name == "par_unseq"
    assert ex.unseq.name == "unseq"


def test_policy_call_with_task_tag_sets_task():
    par_task = ex.par(ex.task)
    assert par_task.task is True
    assert par_task.name == "par"


def test_policy_with_static_chunk_size():
    p = ex.par.with_(ex.static_chunk_size(1000))
    token = p._token()
    assert token.chunk_size == 1000
    assert p.chunk_name == "static"


def test_policy_with_dynamic_chunk_size():
    p = ex.par.with_(ex.dynamic_chunk_size(50))
    assert p._token().chunk_size == 50
    assert p.chunk_name == "dynamic"


def test_policy_with_auto_chunk_size():
    p = ex.par.with_(ex.auto_chunk_size())
    assert p.chunk_name == "auto"


def test_policy_with_guided_chunk_size():
    p = ex.par.with_(ex.guided_chunk_size())
    assert p.chunk_name == "guided"


def test_task_policy_with_chunk_size():
    p = ex.par(ex.task).with_(ex.static_chunk_size(100))
    assert p.task is True
    assert p.chunk_name == "static"
    assert p._token().chunk_size == 100


def test_policy_is_immutable():
    p1 = ex.par
    p2 = p1.with_(ex.static_chunk_size(10))
    assert p1.chunk_name == "none"
    assert p2.chunk_name == "static"
    assert p1 is not p2


def test_policy_repr():
    assert "par" in repr(ex.par)
    assert "par_task" in repr(ex.par(ex.task)).replace(" ", "_").lower() or \
           "task" in repr(ex.par(ex.task))


def test_non_task_policy_raises_on_task_tag_reapply():
    with pytest.raises(TypeError, match="already"):
        ex.par(ex.task)(ex.task)
