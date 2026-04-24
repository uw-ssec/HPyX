"""Pytest configuration for HPyX tests."""

from __future__ import annotations

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "skip_after_shutdown: skip this test if the HPX runtime has been stopped",
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests marked skip_after_shutdown unless run in isolation."""
    try:
        marker_expr = config.getoption("-m")
    except ValueError:
        marker_expr = ""
    if marker_expr == "skip_after_shutdown":
        return
    skip = pytest.mark.skip(reason="Leaves runtime stopped; run in isolation")
    for item in items:
        if "skip_after_shutdown" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def hpx_runtime():
    """Start the HPX runtime once per pytest session with os_threads=4."""
    import hpyx
    hpyx.init(os_threads=4)
    yield
