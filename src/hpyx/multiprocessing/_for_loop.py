from typing import Callable, Iterable
from .._core import hpx_for_loop

def for_loop(function: Callable, iterable: Iterable, policy: str = "seq") -> None:
    """
    Execute a function over an iterable using HPX's for_loop.
    Note that this method will modify the iterable in place.

    :param function: The function to apply to each element in the iterable.
    :param iterable: The iterable to process.
    :param policy: Execution policy, either "seq" for sequential or "par" for parallel.
    """
    hpx_for_loop(function, iterable, policy)
