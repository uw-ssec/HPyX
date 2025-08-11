from typing import Callable
from .._core import hpx_async, future

def submit(function: Callable, *args) -> future:
    """
    Submit a function to be executed asynchronously using HPX.
    Under the hood, this uses `hpx::async` to run the function
    with `hpx::launch::deferred` policy.

    :param function: The function to execute.
    :param args: Arguments to pass to the function.
    :return: A future representing the result of the asynchronous execution.
    """
    return hpx_async(function, *args)
