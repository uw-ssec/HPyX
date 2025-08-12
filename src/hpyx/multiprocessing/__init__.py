"""
HPyX multiprocessing subpackage for parallel execution utilities.

This subpackage provides support for parallel and multiprocessing-style
computation in HPyX. It includes utilities that leverage HPX's parallel
algorithms to provide efficient execution across multiple cores.

The multiprocessing module offers familiar interfaces for parallel computation
while utilizing HPX's advanced runtime system for optimal performance.

Important
---------
All functions in this module require an active HPX runtime. Use the
HPXRuntime context manager to ensure proper initialization and cleanup
of the HPX runtime system before calling any functions from this module.
"""

from __future__ import annotations

from ._for_loop import for_loop

__all__ = ["for_loop"]
