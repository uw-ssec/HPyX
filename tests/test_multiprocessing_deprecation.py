"""Test that hpyx.multiprocessing emits DeprecationWarning."""

from __future__ import annotations

import importlib
import sys
import warnings

import numpy as np
import pytest


def test_multiprocessing_import_warns():
    sys.modules.pop("hpyx.multiprocessing", None)
    sys.modules.pop("hpyx.multiprocessing._for_loop", None)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        importlib.import_module("hpyx.multiprocessing")
        assert any(
            issubclass(item.category, DeprecationWarning)
            and "hpyx.multiprocessing is deprecated" in str(item.message)
            for item in w
        ), f"Expected deprecation warning; got: {[str(x.message) for x in w]}"


def test_multiprocessing_for_loop_warns():
    import hpyx
    import hpyx.multiprocessing as mp

    hpyx.init()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        mp.for_loop(lambda x: None, [1, 2, 3], policy="seq")
        assert any(
            issubclass(item.category, DeprecationWarning)
            and "hpyx.multiprocessing.for_loop is deprecated" in str(item.message)
            for item in w
        ), f"Expected deprecation warning; got: {[str(x.message) for x in w]}"


def test_multiprocessing_for_loop_list_transform_and_store():
    """Regression: list input must have function return values written back."""
    import hpyx
    import hpyx.multiprocessing as mp

    hpyx.init()
    data = [1, 2, 3, 4, 5]
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        mp.for_loop(lambda x: x * 2, data, policy="seq")
    assert data == [2, 4, 6, 8, 10]


def test_multiprocessing_for_loop_ndarray_transform_and_store():
    """Regression: numpy array input must have function return values written back."""
    import hpyx
    import hpyx.multiprocessing as mp

    hpyx.init()
    arr = np.array([1, 2, 3, 4, 5])
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        mp.for_loop(lambda x: x * 2, arr, policy="seq")
    np.testing.assert_array_equal(arr, np.array([2, 4, 6, 8, 10]))


def test_multiprocessing_for_loop_invalid_policy():
    """Invalid policy must raise ValueError, not silently fall back to seq."""
    import hpyx
    import hpyx.multiprocessing as mp

    hpyx.init()
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match="policy must be 'seq' or 'par'"):
            mp.for_loop(lambda x: x, [1, 2, 3], policy="invalid")


def test_for_loop_docstring_preserved():
    """for_loop.__doc__ must not be None (docstring must precede warnings.warn)."""
    import hpyx.multiprocessing as mp

    assert mp.for_loop.__doc__ is not None
