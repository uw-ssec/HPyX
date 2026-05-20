"""Executes the worked example from docs/adding-a-binding.md.

Keeps the docs in sync with reality. If this test fails, the guide's
code blocks are wrong.
"""

import numpy as np
import pytest

try:
    from hpyx._core import contributor_example as contrib

    HAS_CONTRIB = True
except ImportError:
    HAS_CONTRIB = False

pytestmark = pytest.mark.skipif(
    not HAS_CONTRIB,
    reason="Contributor example binding not built "
    "(set HPYX_BUILD_CONTRIBUTOR_EXAMPLE=ON)",
)

# Policy constants matching hpyx.execution._KIND_* and _CHUNK_NONE
_KIND_PAR = 1
_CHUNK_NONE = 0


def test_sum_of_squares_matches_reference():
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    expected = sum(x * x for x in data)
    # Call with par policy (kind=1, task=False, chunk=0, chunk_size=0)
    result = contrib.sum_of_squares(_KIND_PAR, False, _CHUNK_NONE, 0, data)
    assert result == pytest.approx(expected)


def test_sum_of_squares_seq_policy():
    data = list(range(1, 11))
    expected = sum(x * x for x in data)
    result = contrib.sum_of_squares(0, False, _CHUNK_NONE, 0, data)  # seq
    assert result == pytest.approx(expected)


def test_l2_norm_squared_matches_numpy_float64():
    rng = np.random.default_rng(0)
    a = rng.random(10_000).astype(np.float64)
    result = contrib.l2_norm_squared(a)
    expected = np.sum(a * a)
    assert result == pytest.approx(expected, rel=1e-10)


def test_l2_norm_squared_float32():
    rng = np.random.default_rng(1)
    a = rng.random(1000).astype(np.float32)
    result = contrib.l2_norm_squared(a)
    expected = np.sum(a * a, dtype=np.float64)
    assert result == pytest.approx(expected, rel=1e-5)
