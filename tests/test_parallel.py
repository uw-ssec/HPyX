"""Tests for hpyx.parallel — Python-callback parallel algorithms."""

import operator
import threading

import pytest

import hpyx
from hpyx.execution import par, par_unseq, seq, static_chunk_size, task, unseq


# ---- for_loop (seq) ----

def test_for_loop_seq_calls_body_in_order():
    order = []
    hpyx.parallel.for_loop(seq, 0, 10, lambda i: order.append(i))
    assert order == list(range(10))


def test_for_loop_seq_large_range():
    count = 0
    lock = threading.Lock()

    def body(i):
        nonlocal count
        with lock:
            count += 1

    hpyx.parallel.for_loop(seq, 0, 1000, body)
    assert count == 1000


def test_for_loop_seq_with_chunk_size():
    count = 0
    lock = threading.Lock()

    def body(i):
        nonlocal count
        with lock:
            count += 1

    hpyx.parallel.for_loop(seq.with_(static_chunk_size(10)), 0, 100, body)
    assert count == 100


def test_for_loop_propagates_exception():
    def body(i):
        if i == 5:
            raise ValueError(f"fail at {i}")

    with pytest.raises((ValueError, RuntimeError), match="fail at 5"):
        hpyx.parallel.for_loop(seq, 0, 10, body)


def test_for_loop_empty_range():
    called = False

    def body(i):
        nonlocal called
        called = True

    hpyx.parallel.for_loop(seq, 0, 0, body)
    assert not called


def test_for_loop_task_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.for_loop(seq(task), 0, 10, lambda i: None)


# ---- for_loop (par) ----

def test_for_loop_par_visits_all():
    result = set()
    lock = threading.Lock()

    def body(i):
        with lock:
            result.add(i)

    hpyx.parallel.for_loop(par, 0, 100, body)
    assert result == set(range(100))


def test_for_loop_par_unseq_visits_all():
    result = set()
    lock = threading.Lock()

    def body(i):
        with lock:
            result.add(i)

    hpyx.parallel.for_loop(par_unseq, 0, 50, body)
    assert result == set(range(50))


def test_for_loop_par_empty_range():
    called = False

    def body(i):
        nonlocal called
        called = True

    hpyx.parallel.for_loop(par, 0, 0, body)
    assert not called


def test_for_loop_par_propagates_exception():
    def body(i):
        if i == 5:
            raise ValueError(f"fail at {i}")

    with pytest.raises((ValueError, RuntimeError), match="fail at 5"):
        hpyx.parallel.for_loop(par, 0, 10, body)


# ---- for_each (seq) ----

def test_for_each_seq_mutates_in_order():
    data = [0, 1, 2, 3, 4]
    result = []
    hpyx.parallel.for_each(seq, data, lambda x: result.append(x))
    assert result == [0, 1, 2, 3, 4]


def test_for_each_seq_visits_every_element():
    data = list(range(50))
    result = set()
    lock = threading.Lock()

    def visit(x):
        with lock:
            result.add(x)

    hpyx.parallel.for_each(seq, data, visit)
    assert result == set(range(50))


def test_for_each_empty_iterable():
    called = False

    def fn(x):
        nonlocal called
        called = True

    hpyx.parallel.for_each(seq, [], fn)
    assert not called


def test_for_each_task_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.for_each(seq(task), [1, 2, 3], lambda x: None)


# ---- for_each (par) ----

def test_for_each_par_visits_all():
    data = list(range(100))
    result = set()
    lock = threading.Lock()

    def visit(x):
        with lock:
            result.add(x)

    hpyx.parallel.for_each(par, data, visit)
    assert result == set(range(100))


def test_for_each_par_unseq_visits_all():
    data = list(range(50))
    result = set()
    lock = threading.Lock()

    def visit(x):
        with lock:
            result.add(x)

    hpyx.parallel.for_each(par_unseq, data, visit)
    assert result == set(range(50))


def test_for_each_par_empty():
    called = False

    def fn(x):
        nonlocal called
        called = True

    hpyx.parallel.for_each(par, [], fn)
    assert not called


# ===========================================================================
# transform
# ===========================================================================

def test_transform_seq():
    result = hpyx.parallel.transform(seq, [1, 2, 3], lambda x: x * 2)
    assert result == [2, 4, 6]


def test_transform_par():
    result = hpyx.parallel.transform(par, [1, 2, 3, 4, 5], lambda x: x ** 2)
    assert result == [1, 4, 9, 16, 25]


def test_transform_empty():
    assert hpyx.parallel.transform(seq, [], lambda x: x) == []
    assert hpyx.parallel.transform(par, [], lambda x: x) == []


def test_transform_seq_propagates_exception():
    def bad(x):
        if x == 3:
            raise ValueError("fail at 3")
        return x

    with pytest.raises((ValueError, RuntimeError), match="fail at 3"):
        hpyx.parallel.transform(seq, [1, 2, 3, 4], bad)


def test_transform_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.transform(seq(task), [1], lambda x: x)


# ===========================================================================
# reduce
# ===========================================================================

def test_reduce_seq_sum():
    result = hpyx.parallel.reduce(seq, [1, 2, 3, 4], init=0, op=operator.add)
    assert result == 10


def test_reduce_par_sum():
    result = hpyx.parallel.reduce(par, [1, 2, 3, 4], init=0, op=operator.add)
    assert result == 10


def test_reduce_seq_product():
    result = hpyx.parallel.reduce(seq, [1, 2, 3, 4], init=1, op=operator.mul)
    assert result == 24


def test_reduce_empty():
    assert hpyx.parallel.reduce(seq, [], init=0, op=operator.add) == 0
    assert hpyx.parallel.reduce(par, [], init=42, op=operator.add) == 42


def test_reduce_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.reduce(seq(task), [1], init=0, op=operator.add)


def test_reduce_keyword_only_enforcement():
    with pytest.raises(TypeError):
        hpyx.parallel.reduce(seq, [1, 2], 0, operator.add)


# ===========================================================================
# transform_reduce
# ===========================================================================

def test_transform_reduce_seq():
    result = hpyx.parallel.transform_reduce(
        seq, [1, 2, 3], init=0, reduce_op=operator.add, transform_op=lambda x: x * x
    )
    assert result == 14


def test_transform_reduce_par():
    result = hpyx.parallel.transform_reduce(
        par, [1, 2, 3], init=0, reduce_op=operator.add, transform_op=lambda x: x * x
    )
    assert result == 14


def test_transform_reduce_empty():
    result = hpyx.parallel.transform_reduce(
        seq, [], init=0, reduce_op=operator.add, transform_op=lambda x: x
    )
    assert result == 0


def test_transform_reduce_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.transform_reduce(
            seq(task), [1], init=0, reduce_op=operator.add, transform_op=lambda x: x
        )


def test_transform_reduce_keyword_only_enforcement():
    with pytest.raises(TypeError):
        hpyx.parallel.transform_reduce(seq, [1], 0, operator.add, lambda x: x)


# ===========================================================================
# count / count_if
# ===========================================================================

def test_count_seq():
    assert hpyx.parallel.count(seq, [1, 2, 2, 3, 2], 2) == 3


def test_count_par():
    assert hpyx.parallel.count(par, [1, 2, 2, 3, 2], 2) == 3


def test_count_empty():
    assert hpyx.parallel.count(seq, [], 5) == 0
    assert hpyx.parallel.count(par, [], 5) == 0


def test_count_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.count(seq(task), [1], 1)


def test_count_if_seq():
    assert hpyx.parallel.count_if(seq, [1, 2, 3, 4, 5], lambda x: x > 3) == 2


def test_count_if_par():
    assert hpyx.parallel.count_if(par, [1, 2, 3, 4, 5], lambda x: x > 3) == 2


def test_count_if_empty():
    assert hpyx.parallel.count_if(seq, [], lambda x: True) == 0
    assert hpyx.parallel.count_if(par, [], lambda x: True) == 0


def test_count_if_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.count_if(seq(task), [1], lambda x: True)


# ===========================================================================
# find / find_if
# ===========================================================================

def test_find_seq():
    assert hpyx.parallel.find(seq, [10, 20, 30], 20) == 1


def test_find_par():
    assert hpyx.parallel.find(par, [10, 20, 30], 20) == 1


def test_find_not_present():
    assert hpyx.parallel.find(seq, [1, 2, 3], 99) == -1
    assert hpyx.parallel.find(par, [1, 2, 3], 99) == -1


def test_find_empty():
    assert hpyx.parallel.find(seq, [], 1) == -1
    assert hpyx.parallel.find(par, [], 1) == -1


def test_find_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.find(seq(task), [1], 1)


def test_find_if_seq():
    assert hpyx.parallel.find_if(seq, [1, 2, 3, 4], lambda x: x > 2) == 2


def test_find_if_par():
    assert hpyx.parallel.find_if(par, [1, 2, 3, 4], lambda x: x > 2) == 2


def test_find_if_not_found():
    assert hpyx.parallel.find_if(seq, [1, 2, 3], lambda x: x > 10) == -1
    assert hpyx.parallel.find_if(par, [1, 2, 3], lambda x: x > 10) == -1


def test_find_if_empty():
    assert hpyx.parallel.find_if(seq, [], lambda x: True) == -1
    assert hpyx.parallel.find_if(par, [], lambda x: True) == -1


def test_find_if_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.find_if(seq(task), [1], lambda x: True)


# ===========================================================================
# all_of / any_of / none_of
# ===========================================================================

def test_all_of_seq_true():
    assert hpyx.parallel.all_of(seq, [2, 4, 6], lambda x: x % 2 == 0) is True


def test_all_of_seq_false():
    assert hpyx.parallel.all_of(seq, [2, 3, 6], lambda x: x % 2 == 0) is False


def test_all_of_par():
    assert hpyx.parallel.all_of(par, [2, 4, 6], lambda x: x % 2 == 0) is True
    assert hpyx.parallel.all_of(par, [2, 3, 6], lambda x: x % 2 == 0) is False


def test_all_of_empty():
    assert hpyx.parallel.all_of(seq, [], lambda x: False) is True
    assert hpyx.parallel.all_of(par, [], lambda x: False) is True


def test_all_of_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.all_of(seq(task), [1], lambda x: True)


def test_any_of_seq():
    assert hpyx.parallel.any_of(seq, [1, 3, 5], lambda x: x == 3) is True
    assert hpyx.parallel.any_of(seq, [1, 3, 5], lambda x: x == 2) is False


def test_any_of_par():
    assert hpyx.parallel.any_of(par, [1, 3, 5], lambda x: x == 3) is True
    assert hpyx.parallel.any_of(par, [1, 3, 5], lambda x: x == 2) is False


def test_any_of_empty():
    assert hpyx.parallel.any_of(seq, [], lambda x: True) is False
    assert hpyx.parallel.any_of(par, [], lambda x: True) is False


def test_any_of_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.any_of(seq(task), [1], lambda x: True)


def test_none_of_seq():
    assert hpyx.parallel.none_of(seq, [1, 3, 5], lambda x: x % 2 == 0) is True
    assert hpyx.parallel.none_of(seq, [1, 2, 5], lambda x: x % 2 == 0) is False


def test_none_of_par():
    assert hpyx.parallel.none_of(par, [1, 3, 5], lambda x: x % 2 == 0) is True
    assert hpyx.parallel.none_of(par, [1, 2, 5], lambda x: x % 2 == 0) is False


def test_none_of_empty():
    assert hpyx.parallel.none_of(seq, [], lambda x: True) is True
    assert hpyx.parallel.none_of(par, [], lambda x: True) is True


def test_none_of_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.none_of(seq(task), [1], lambda x: True)


# ===========================================================================
# sort / stable_sort
# ===========================================================================

def test_sort_seq():
    assert hpyx.parallel.sort(seq, [3, 1, 2]) == [1, 2, 3]


def test_sort_par():
    assert hpyx.parallel.sort(par, [3, 1, 2]) == [1, 2, 3]


def test_sort_with_key():
    result = hpyx.parallel.sort(seq, ["bb", "a", "ccc"], key=len)
    assert result == ["a", "bb", "ccc"]


def test_sort_reverse():
    assert hpyx.parallel.sort(seq, [1, 3, 2], reverse=True) == [3, 2, 1]


def test_sort_empty():
    assert hpyx.parallel.sort(seq, []) == []
    assert hpyx.parallel.sort(par, []) == []


def test_sort_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.sort(seq(task), [1])


def test_stable_sort_seq():
    assert hpyx.parallel.stable_sort(seq, [3, 1, 2]) == [1, 2, 3]


def test_stable_sort_par():
    assert hpyx.parallel.stable_sort(par, [3, 1, 2]) == [1, 2, 3]


def test_stable_sort_preserves_order():
    data = [(1, "b"), (2, "a"), (1, "a")]
    result = hpyx.parallel.stable_sort(seq, data, key=lambda x: x[0])
    assert result == [(1, "b"), (1, "a"), (2, "a")]


def test_stable_sort_empty():
    assert hpyx.parallel.stable_sort(seq, []) == []


def test_stable_sort_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.stable_sort(seq(task), [1])


# ===========================================================================
# fill / fill_n / copy / copy_if / iota
# ===========================================================================

def test_fill_seq():
    assert hpyx.parallel.fill(seq, 5, 42) == [42, 42, 42, 42, 42]


def test_fill_par():
    assert hpyx.parallel.fill(par, 3, "x") == ["x", "x", "x"]


def test_fill_zero():
    assert hpyx.parallel.fill(seq, 0, 1) == []
    assert hpyx.parallel.fill(par, 0, 1) == []


def test_fill_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.fill(seq(task), 1, 0)


def test_fill_n_is_alias():
    assert hpyx.parallel.fill_n(seq, 3, 7) == hpyx.parallel.fill(seq, 3, 7)


def test_copy_seq():
    original = [1, 2, 3]
    result = hpyx.parallel.copy(seq, original)
    assert result == [1, 2, 3]
    assert result is not original


def test_copy_par():
    result = hpyx.parallel.copy(par, [4, 5, 6])
    assert result == [4, 5, 6]


def test_copy_empty():
    assert hpyx.parallel.copy(seq, []) == []
    assert hpyx.parallel.copy(par, []) == []


def test_copy_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.copy(seq(task), [1])


def test_copy_if_seq():
    result = hpyx.parallel.copy_if(seq, [1, 2, 3, 4, 5], lambda x: x % 2 == 0)
    assert result == [2, 4]


def test_copy_if_par():
    result = hpyx.parallel.copy_if(par, [1, 2, 3, 4, 5], lambda x: x % 2 == 0)
    assert result == [2, 4]


def test_copy_if_empty():
    assert hpyx.parallel.copy_if(seq, [], lambda x: True) == []
    assert hpyx.parallel.copy_if(par, [], lambda x: True) == []


def test_copy_if_none_match():
    assert hpyx.parallel.copy_if(seq, [1, 2, 3], lambda x: x > 10) == []


def test_copy_if_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.copy_if(seq(task), [1], lambda x: True)


def test_iota_seq():
    assert hpyx.parallel.iota(seq, 5) == [0, 1, 2, 3, 4]


def test_iota_par():
    assert hpyx.parallel.iota(par, 5) == [0, 1, 2, 3, 4]


def test_iota_with_start():
    assert hpyx.parallel.iota(seq, 3, start=10) == [10, 11, 12]


def test_iota_zero():
    assert hpyx.parallel.iota(seq, 0) == []
    assert hpyx.parallel.iota(par, 0) == []


def test_iota_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.iota(seq(task), 5)


# ===========================================================================
# inclusive_scan / exclusive_scan
# ===========================================================================

def test_inclusive_scan_seq():
    result = hpyx.parallel.inclusive_scan(seq, [1, 2, 3, 4], op=operator.add)
    assert result == [1, 3, 6, 10]


def test_inclusive_scan_par():
    result = hpyx.parallel.inclusive_scan(par, [1, 2, 3, 4], op=operator.add)
    assert result == [1, 3, 6, 10]


def test_inclusive_scan_product():
    result = hpyx.parallel.inclusive_scan(seq, [1, 2, 3, 4], op=operator.mul)
    assert result == [1, 2, 6, 24]


def test_inclusive_scan_empty():
    assert hpyx.parallel.inclusive_scan(seq, [], op=operator.add) == []
    assert hpyx.parallel.inclusive_scan(par, [], op=operator.add) == []


def test_inclusive_scan_single():
    assert hpyx.parallel.inclusive_scan(seq, [42], op=operator.add) == [42]


def test_inclusive_scan_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.inclusive_scan(seq(task), [1], op=operator.add)


def test_exclusive_scan_seq():
    result = hpyx.parallel.exclusive_scan(seq, [1, 2, 3, 4], init=0, op=operator.add)
    assert result == [0, 1, 3, 6]


def test_exclusive_scan_par():
    result = hpyx.parallel.exclusive_scan(par, [1, 2, 3, 4], init=0, op=operator.add)
    assert result == [0, 1, 3, 6]


def test_exclusive_scan_product():
    result = hpyx.parallel.exclusive_scan(seq, [1, 2, 3, 4], init=1, op=operator.mul)
    assert result == [1, 1, 2, 6]


def test_exclusive_scan_empty():
    assert hpyx.parallel.exclusive_scan(seq, [], init=0, op=operator.add) == []
    assert hpyx.parallel.exclusive_scan(par, [], init=0, op=operator.add) == []


def test_exclusive_scan_single():
    result = hpyx.parallel.exclusive_scan(seq, [5], init=0, op=operator.add)
    assert result == [0]


def test_exclusive_scan_task_raises():
    with pytest.raises(NotImplementedError):
        hpyx.parallel.exclusive_scan(seq(task), [1], init=0, op=operator.add)


def test_exclusive_scan_keyword_only_enforcement():
    with pytest.raises(TypeError):
        hpyx.parallel.exclusive_scan(seq, [1, 2], 0, operator.add)
