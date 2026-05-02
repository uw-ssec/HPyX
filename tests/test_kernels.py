"""Tests for hpyx.kernels — pure C++ parallel kernels on ndarray data."""

from __future__ import annotations

import numpy as np
import pytest

import hpyx  # noqa: F401

DTYPES = [np.float32, np.float64, np.int32, np.int64]


class TestDot:
    @pytest.mark.parametrize("dtype", DTYPES)
    def test_basic(self, dtype):
        a = np.array([1, 2, 3], dtype=dtype)
        b = np.array([4, 5, 6], dtype=dtype)
        result = hpyx.kernels.dot(a, b)
        assert result == pytest.approx(32.0)

    @pytest.mark.parametrize("dtype", DTYPES)
    def test_zeros(self, dtype):
        a = np.zeros(10, dtype=dtype)
        b = np.ones(10, dtype=dtype)
        assert hpyx.kernels.dot(a, b) == pytest.approx(0.0)

    def test_large_array(self):
        a = np.ones(100_000, dtype=np.float64)
        b = np.ones(100_000, dtype=np.float64)
        assert hpyx.kernels.dot(a, b) == pytest.approx(100_000.0)

    def test_size_mismatch(self):
        a = np.array([1.0, 2.0])
        b = np.array([1.0, 2.0, 3.0])
        with pytest.raises(Exception):
            hpyx.kernels.dot(a, b)

    def test_rejects_non_1d(self):
        a = np.array([[1.0, 2.0], [3.0, 4.0]])
        b = np.array([[5.0, 6.0], [7.0, 8.0]])
        with pytest.raises(ValueError, match="1-dimensional"):
            hpyx.kernels.dot(a, b)

    def test_rejects_mixed_ndim(self):
        a = np.array([1.0, 2.0, 3.0, 4.0])
        b = np.array([[1.0, 2.0], [3.0, 4.0]])
        with pytest.raises(ValueError, match="1-dimensional"):
            hpyx.kernels.dot(a, b)

    def test_unsupported_dtype(self):
        a = np.array([1, 2], dtype=np.float16)
        b = np.array([3, 4], dtype=np.float16)
        with pytest.raises(TypeError):
            hpyx.kernels.dot(a, b)


class TestSum:
    @pytest.mark.parametrize("dtype", DTYPES)
    def test_basic(self, dtype):
        a = np.array([1, 2, 3, 4], dtype=dtype)
        result = hpyx.kernels.sum(a)
        assert result == pytest.approx(10)

    @pytest.mark.parametrize("dtype", DTYPES)
    def test_empty(self, dtype):
        a = np.array([], dtype=dtype)
        assert hpyx.kernels.sum(a) == pytest.approx(0)

    def test_large_array(self):
        a = np.ones(100_000, dtype=np.float64)
        assert hpyx.kernels.sum(a) == pytest.approx(100_000.0)

    def test_negative(self):
        a = np.array([-1.0, -2.0, 3.0])
        assert hpyx.kernels.sum(a) == pytest.approx(0.0)


class TestMax:
    @pytest.mark.parametrize("dtype", DTYPES)
    def test_basic(self, dtype):
        a = np.array([3, 1, 4, 1, 5], dtype=dtype)
        assert hpyx.kernels.max(a) == pytest.approx(5)

    def test_negative(self):
        a = np.array([-5.0, -1.0, -3.0])
        assert hpyx.kernels.max(a) == pytest.approx(-1.0)

    def test_single_element(self):
        a = np.array([42.0])
        assert hpyx.kernels.max(a) == pytest.approx(42.0)

    def test_empty_raises(self):
        a = np.array([], dtype=np.float64)
        with pytest.raises(Exception):
            hpyx.kernels.max(a)


class TestMin:
    @pytest.mark.parametrize("dtype", DTYPES)
    def test_basic(self, dtype):
        a = np.array([3, 1, 4, 1, 5], dtype=dtype)
        assert hpyx.kernels.min(a) == pytest.approx(1)

    def test_negative(self):
        a = np.array([-5.0, -1.0, -3.0])
        assert hpyx.kernels.min(a) == pytest.approx(-5.0)

    def test_single_element(self):
        a = np.array([42.0])
        assert hpyx.kernels.min(a) == pytest.approx(42.0)

    def test_empty_raises(self):
        a = np.array([], dtype=np.float64)
        with pytest.raises(Exception):
            hpyx.kernels.min(a)


class TestMatmul:
    def test_basic(self):
        A = np.array([[1.0, 2.0], [3.0, 4.0]])
        B = np.array([[5.0, 6.0], [7.0, 8.0]])
        C = hpyx.kernels.matmul(A, B)
        expected = np.array([[19.0, 22.0], [43.0, 50.0]])
        np.testing.assert_allclose(C, expected)

    def test_identity(self):
        A = np.eye(3, dtype=np.float64)
        B = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
        np.testing.assert_allclose(hpyx.kernels.matmul(A, B), B)

    def test_rectangular(self):
        A = np.ones((2, 3), dtype=np.float64)
        B = np.ones((3, 4), dtype=np.float64)
        C = hpyx.kernels.matmul(A, B)
        assert C.shape == (2, 4)
        np.testing.assert_allclose(C, np.full((2, 4), 3.0))

    def test_not_2d_raises(self):
        A = np.array([1.0, 2.0])
        B = np.array([[1.0], [2.0]])
        with pytest.raises(ValueError, match="2-dimensional"):
            hpyx.kernels.matmul(A, B)

    def test_shape_mismatch_raises(self):
        A = np.ones((2, 3), dtype=np.float64)
        B = np.ones((4, 2), dtype=np.float64)
        with pytest.raises(ValueError, match="A.shape"):
            hpyx.kernels.matmul(A, B)

    def test_not_contiguous_raises(self):
        A = np.ones((4, 4), dtype=np.float64)[::2, :]
        B = np.ones((2, 4), dtype=np.float64)
        with pytest.raises(TypeError, match="C-contiguous"):
            hpyx.kernels.matmul(A, B)


class TestContiguityCheck:
    def test_non_contiguous_dot_raises(self):
        a = np.ones(10, dtype=np.float64)[::2]
        b = np.ones(5, dtype=np.float64)
        with pytest.raises(TypeError, match="C-contiguous"):
            hpyx.kernels.dot(a, b)
