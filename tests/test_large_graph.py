"""Stress tests for large future DAGs."""

import pytest

import hpyx


def test_10k_independent_futures():
    futs = [hpyx.async_(lambda i=i: i) for i in range(10_000)]
    results = hpyx.when_all(*futs).result()
    assert len(results) == 10_000
    assert results[0] == 0
    assert results[9_999] == 9_999


def test_1k_then_depth():
    """Build a chain of 1000 .then() continuations."""
    fut = hpyx.async_(lambda: 0)
    for _ in range(1000):
        fut = fut.then(lambda f: f.result() + 1)
    assert fut.result() == 1000


@pytest.mark.parametrize("width", [100, 1000])
def test_wide_dataflow(width):
    """Fan-in: sum of `width` async results via dataflow."""
    futs = [hpyx.async_(lambda i=i: i) for i in range(width)]
    combined = hpyx.dataflow(lambda *xs: sum(xs), *futs)
    assert combined.result() == sum(range(width))
