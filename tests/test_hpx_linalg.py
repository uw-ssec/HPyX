import numpy as np
import pytest

import hpyx
from hpyx.runtime import HPXRuntime

@pytest.mark.parametrize("v_len", [int(x) for x in [10e1, 10e2, 10e3, 10e4, 10e5, 10e6]])
def test_hpx_dot1d(v_len):
    rng = np.random.default_rng()
    a = rng.random(int(v_len))
    b = rng.random(int(v_len))
    with HPXRuntime():
        result = hpyx._core.dot1d(a, b)
    assert isinstance(result, float), "Result should be a float"
    assert np.allclose(result, np.dot(a, b)), "HPX dot1d result does not match numpy dot product"
