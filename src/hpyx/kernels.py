"""hpyx.kernels -- Pure C++ parallel kernels on ndarray data.

Note: ``sum``, ``max``, and ``min`` shadow Python builtins.  Import them
explicitly (e.g. ``from hpyx.kernels import sum as hsum``) or access via the
module (``hpyx.kernels.sum``) to avoid masking the built-in names in calling
code.
"""

from __future__ import annotations

import numpy as np

from hpyx import _core, _runtime

_DTYPE_SUFFIX = {
    np.dtype("float32"): "f32",
    np.dtype("float64"): "f64",
    np.dtype("int32"): "i32",
    np.dtype("int64"): "i64",
}


def _suffix(arr: np.ndarray) -> str:
    dt = np.dtype(arr.dtype)
    s = _DTYPE_SUFFIX.get(dt)
    if s is None:
        raise TypeError(
            f"Unsupported dtype {dt}; use float32/float64/int32/int64 or hpyx.parallel.*"
        )
    return s


def _ensure_contiguous(arr: np.ndarray, name: str = "array") -> None:
    if not arr.flags["C_CONTIGUOUS"]:
        raise TypeError(
            f"{name} must be C-contiguous; call np.ascontiguousarray() first"
        )


def dot(a: np.ndarray, b: np.ndarray) -> float:
    """Parallel dot product of two 1-D arrays. Always returns float64."""
    _runtime.ensure_started()
    if a.ndim != 1 or b.ndim != 1:
        raise ValueError(
            f"dot: both arrays must be 1-dimensional, got a.ndim={a.ndim} b.ndim={b.ndim}"
        )
    _ensure_contiguous(a, "a")
    _ensure_contiguous(b, "b")
    fn = getattr(_core.kernels, f"dot_{_suffix(a)}")
    return fn(a, b)


def sum(a: np.ndarray):
    """Parallel sum of array elements."""
    _runtime.ensure_started()
    _ensure_contiguous(a)
    fn = getattr(_core.kernels, f"sum_{_suffix(a)}")
    return fn(a)


def max(a: np.ndarray):
    """Parallel maximum of array elements. Raises on empty array."""
    _runtime.ensure_started()
    _ensure_contiguous(a)
    fn = getattr(_core.kernels, f"max_val_{_suffix(a)}")
    return fn(a)


def min(a: np.ndarray):
    """Parallel minimum of array elements. Raises on empty array."""
    _runtime.ensure_started()
    _ensure_contiguous(a)
    fn = getattr(_core.kernels, f"min_val_{_suffix(a)}")
    return fn(a)


def matmul(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Matrix multiplication. Both inputs must be 2-D.

    Currently delegates to NumPy's ``@`` operator rather than an HPX C++
    kernel.  A native HPX implementation is a candidate for a future release.
    """
    _runtime.ensure_started()
    _ensure_contiguous(A, "A")
    _ensure_contiguous(B, "B")
    if A.ndim != 2 or B.ndim != 2:
        raise ValueError("matmul: both arrays must be 2-dimensional")
    if A.shape[1] != B.shape[0]:
        raise ValueError("matmul: A.shape[1] must equal B.shape[0]")
    return A @ B


__all__ = ["dot", "matmul", "max", "min", "sum"]
