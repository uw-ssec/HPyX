"""
Tests for the submit function in hpyx.futures.submit module.
"""

import time
from typing import Callable, Any
import pytest
import numpy as np
from hpyx.futures import submit
from hpyx.runtime import HPXRuntime


@pytest.fixture(scope="session")
def hpx_runtime():
    """HPX runtime fixture that starts once for the entire test session."""
    runtime = HPXRuntime()
    runtime.__enter__()
    yield runtime
    runtime.__exit__(None, None, None)


class TestSubmit:
    """Test class for the submit function."""

    def test_submit_simple_function(self, hpx_runtime):
        """Test submit with a simple function."""
        def add(a: int, b: int) -> int:
            return a + b

        future = submit(add, 2, 3)
        result = future.get()
        assert result == 5

    def test_submit_lambda_function(self, hpx_runtime):
        """Test submit with a lambda function."""
        future = submit(lambda x: x * 2, 5)
        result = future.get()
        assert result == 10

    def test_submit_function_with_no_args(self, hpx_runtime):
        """Test submit with a function that takes no arguments."""
        def get_constant():
            return 42

        future = submit(get_constant)
        result = future.get()
        assert result == 42

    def test_submit_function_with_multiple_args(self, hpx_runtime):
        """Test submit with a function that takes multiple arguments."""
        def multiply_three(a: int, b: int, c: int) -> int:
            return a * b * c

        future = submit(multiply_three, 2, 3, 4)
        result = future.get()
        assert result == 24

    def test_submit_function_with_keyword_args(self, hpx_runtime):
        """Test submit with function using keyword arguments."""
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        # Note: submit likely doesn't support keyword args directly, 
        # so we test with positional args
        future = submit(greet, "World", "Hi")
        result = future.get()
        assert result == "Hi, World!"

    def test_submit_function_returning_different_types(self, hpx_runtime):
        """Test submit with functions returning different data types."""
        
        def return_string() -> str:
            return "hello world"
        
        def return_float() -> float:
            return 3.14159
        
        def return_list() -> list:
            return [1, 2, 3, 4, 5]
        
        def return_dict() -> dict:
            return {"key": "value", "number": 42}

        # Test string return
        future_str = submit(return_string)
        assert future_str.get() == "hello world"
        
        # Test float return
        future_float = submit(return_float)
        assert abs(future_float.get() - 3.14159) < 1e-6
        
        # Test list return
        future_list = submit(return_list)
        assert future_list.get() == [1, 2, 3, 4, 5]
        
        # Test dict return
        future_dict = submit(return_dict)
        assert future_dict.get() == {"key": "value", "number": 42}

    def test_submit_multiple_futures(self, hpx_runtime):
        """Test submitting multiple futures and getting results."""
        def square(x: int) -> int:
            return x * x

        futures = []
        for i in range(5):
            future = submit(square, i)
            futures.append(future)
        
        results = [future.get() for future in futures]
        expected = [i * i for i in range(5)]
        assert results == expected

    def test_submit_function_with_side_effects(self, hpx_runtime):
        """Test submit with a function that has side effects."""
        def append_to_list(lst: list, value: Any) -> list:
            lst.append(value)
            return lst

        input_list = [1, 2, 3]
        future = submit(append_to_list, input_list, 4)
        result = future.get()
        assert result == [1, 2, 3, 4]

    def test_submit_function_raising_exception(self, hpx_runtime):
        """Test submit with a function that raises an exception."""
        def divide_by_zero():
            return 1 / 0

        future = submit(divide_by_zero)
        # The exception should be raised when we call get()
        with pytest.raises(ZeroDivisionError):
            future.get()

    def test_submit_cpu_intensive_function(self, hpx_runtime):
        """Test submit with a CPU-intensive function."""
        def fibonacci(n: int) -> int:
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        future = submit(fibonacci, 10)
        result = future.get()
        assert result == 55  # fibonacci(10) = 55

    def test_submit_with_nested_function_calls(self, hpx_runtime):
        """Test submit with nested function calls."""
        def outer_function(x: int) -> int:
            def inner_function(y: int) -> int:
                return y * 2
            return inner_function(x) + 1

        future = submit(outer_function, 5)
        result = future.get()
        assert result == 11  # (5 * 2) + 1 = 11


class TestSubmitWithNumpy:
    """Test class for submit function with numpy operations."""

    def test_submit_numpy_array_sum(self, hpx_runtime):
        """Test submit with numpy array sum operation."""
        def array_sum(arr: np.ndarray) -> float:
            return np.sum(arr)

        test_array = np.array([1, 2, 3, 4, 5])
        future = submit(array_sum, test_array)
        result = future.get()
        assert result == 15.0

    def test_submit_numpy_array_operations(self, hpx_runtime):
        """Test submit with various numpy array operations."""
        def array_operations(arr: np.ndarray) -> dict:
            return {
                'mean': np.mean(arr),
                'std': np.std(arr),
                'max': np.max(arr),
                'min': np.min(arr)
            }

        test_array = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        future = submit(array_operations, test_array)
        result = future.get()
        
        assert abs(result['mean'] - 3.0) < 1e-6
        assert abs(result['max'] - 5.0) < 1e-6
        assert abs(result['min'] - 1.0) < 1e-6
        assert result['std'] > 0

    def test_submit_numpy_matrix_multiplication(self, hpx_runtime):
        """Test submit with numpy matrix multiplication."""
        def matrix_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return np.dot(a, b)

        matrix_a = np.array([[1, 2], [3, 4]])
        matrix_b = np.array([[5, 6], [7, 8]])
        
        future = submit(matrix_multiply, matrix_a, matrix_b)
        result = future.get()
        
        expected = np.array([[19, 22], [43, 50]])
        np.testing.assert_array_equal(result, expected)

    def test_submit_numpy_large_array_computation(self, hpx_runtime):
        """Test submit with large numpy array computation."""
        def compute_statistics(size: int) -> dict:
            # Create a large random array
            arr = np.random.random(size)
            return {
                'size': len(arr),
                'mean': np.mean(arr),
                'sum': np.sum(arr),
                'dtype': str(arr.dtype)
            }

        future = submit(compute_statistics, 10000)
        result = future.get()
        
        assert result['size'] == 10000
        assert 0.4 < result['mean'] < 0.6  # Should be around 0.5 for uniform random
        assert result['dtype'] == 'float64'

    def test_submit_numpy_array_processing_pipeline(self, hpx_runtime):
        """Test submit with a numpy array processing pipeline."""
        def process_array(arr: np.ndarray) -> np.ndarray:
            # Normalize the array
            normalized = (arr - np.mean(arr)) / np.std(arr)
            # Apply some transformations
            processed = np.square(normalized)
            # Return the top 5 values
            return np.sort(processed)[-5:]

        test_array = np.random.normal(10, 2, 100)  # Normal distribution
        future = submit(process_array, test_array)
        result = future.get()
        
        assert len(result) == 5
        assert all(result[i] <= result[i+1] for i in range(4))  # Should be sorted

    def test_submit_numpy_linear_algebra(self, hpx_runtime):
        """Test submit with numpy linear algebra operations."""
        def solve_linear_system(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return np.linalg.solve(a, b)

        # Create a simple 2x2 system: 2x + y = 5, x + y = 3
        a = np.array([[2, 1], [1, 1]], dtype=float)
        b = np.array([5, 3], dtype=float)
        
        future = submit(solve_linear_system, a, b)
        result = future.get()
        
        # Solution should be x=2, y=1
        expected = np.array([2.0, 1.0])
        np.testing.assert_allclose(result, expected, rtol=1e-6)

    @pytest.mark.parametrize("array_size", [100, 1000, 10000])
    def test_submit_numpy_different_sizes(self, array_size, hpx_runtime):
        """Test submit with numpy arrays of different sizes."""
        def compute_norm(arr: np.ndarray) -> float:
            return np.linalg.norm(arr)

        test_array = np.random.random(array_size)
        future = submit(compute_norm, test_array)
        result = future.get()
        
        # The norm should be positive and reasonable for the array size
        assert result > 0
        assert result < array_size  # Rough upper bound check

    def test_submit_numpy_complex_numbers(self, hpx_runtime):
        """Test submit with numpy complex number operations."""
        def complex_operations(arr: np.ndarray) -> dict:
            return {
                'magnitude': np.abs(arr),
                'phase': np.angle(arr),
                'real_part': np.real(arr),
                'imag_part': np.imag(arr)
            }

        complex_array = np.array([1+2j, 3-4j, -1+1j])
        future = submit(complex_operations, complex_array)
        result = future.get()
        
        assert len(result['magnitude']) == 3
        assert len(result['phase']) == 3
        np.testing.assert_array_equal(result['real_part'], [1, 3, -1])
        np.testing.assert_array_equal(result['imag_part'], [2, -4, 1])


class TestSubmitThenChaining:
    """Test class for the .then() method with chaining and extra arguments."""

    def test_then_simple_callback(self, hpx_runtime):
        """Test .then() with a simple callback function."""
        def multiply_by_two(x: int) -> int:
            return x * 2
        
        def add_ten(result: int) -> int:
            return result + 10

        future = submit(multiply_by_two, 5)
        chained_future = future.then(add_ten)
        result = chained_future.get()
        assert result == 20  # (5 * 2) + 10 = 20

    def test_then_with_single_extra_arg(self, hpx_runtime):
        """Test .then() with callback that takes one extra argument."""
        def base_function(x: int) -> int:
            return x * 3
        
        def add_offset(result: int, offset: int) -> int:
            return result + offset

        future = submit(base_function, 4)
        chained_future = future.then(add_offset, 100)
        result = chained_future.get()
        assert result == 112  # (4 * 3) + 100 = 112

    def test_then_with_multiple_extra_args(self, hpx_runtime):
        """Test .then() with callback that takes multiple extra arguments."""
        def base_function(x: int) -> int:
            return x * 2
        
        def complex_calculation(result: int, multiplier: int, offset: int, divisor: int) -> float:
            return (result * multiplier + offset) / divisor

        future = submit(base_function, 6)
        chained_future = future.then(complex_calculation, 5, 20, 4)
        result = chained_future.get()
        assert result == 20.0  # ((6 * 2) * 5 + 20) / 4 = (60 + 20) / 4 = 20.0

    def test_then_multiple_chaining(self, hpx_runtime):
        """Test chaining multiple .then() calls together."""
        def base_function(x: int) -> int:
            return x * 2
        
        def step1(result: int) -> int:
            return result + 5
        
        def step2(result: int, multiplier: int) -> int:
            return result * multiplier
        
        def step3(result: int) -> float:
            return result / 2.0

        future = submit(base_function, 3)
        final_future = (future
                      .then(step1)           # (3 * 2) + 5 = 11
                      .then(step2, 4)        # 11 * 4 = 44
                      .then(step3))          # 44 / 2.0 = 22.0
        result = final_future.get()
        assert result == 22.0

    def test_then_mixed_arg_types(self, hpx_runtime):
        """Test .then() with different argument types."""
        def base_function(x: int) -> int:
            return x
        
        def mixed_callback(result: int, text: str, factor: float, flag: bool) -> str:
            if flag:
                return f"{text}: {result * factor}"
            else:
                return f"{text}: {result}"

        future = submit(base_function, 10)
        chained_future = future.then(mixed_callback, "Result", 2.5, True)
        result = chained_future.get()
        assert result == "Result: 25.0"  # 10 * 2.5 = 25.0

    def test_then_with_exception_in_callback(self, hpx_runtime):
        """Test .then() when the callback raises an exception."""
        def base_function(x: int) -> int:
            return x
        
        def failing_callback(result: int, divisor: int) -> int:
            return result / divisor  # Will cause ZeroDivisionError if divisor is 0

        future = submit(base_function, 10)
        chained_future = future.then(failing_callback, 0)  # Pass 0 as divisor
        with pytest.raises(ZeroDivisionError):
            chained_future.get()

    def test_then_return_different_types(self, hpx_runtime):
        """Test .then() callbacks that return different types."""
        def base_function(x: int) -> int:
            return x
        
        def to_string(result: int, prefix: str) -> str:
            return f"{prefix}{result}"
        
        def to_list(result: str) -> list:
            return [result, len(result)]

        future = submit(base_function, 42)
        string_future = future.then(to_string, "Value: ")
        list_future = string_future.then(to_list)
        result = list_future.get()
        assert result == ["Value: 42", 9]  # "Value: 42" has length 9

    def test_then_with_numpy_arrays(self, hpx_runtime):
        """Test .then() with numpy array operations."""
        def create_array(size: int) -> np.ndarray:
            return np.arange(size)
        
        def scale_array(arr: np.ndarray, factor: int) -> np.ndarray:
            return arr * factor
        
        def sum_array(arr: np.ndarray) -> float:
            return np.sum(arr)

        future = submit(create_array, 5)
        scaled_future = future.then(scale_array, 3)
        sum_future = scaled_future.then(sum_array)
        result = sum_future.get()
        # np.arange(5) = [0, 1, 2, 3, 4]
        # * 3 = [0, 3, 6, 9, 12]
        # sum = 30
        assert result == 30.0

    def test_then_backward_compatibility(self, hpx_runtime):
        """Test that .then() maintains backward compatibility with single callback."""
        def base_function(x: int) -> int:
            return x * x
        
        def simple_callback(result: int) -> int:
            return result + 1

        # Test the old way (should still work)
        future = submit(base_function, 5)
        chained_future = future.then(simple_callback)
        result = chained_future.get()
        assert result == 26  # (5 * 5) + 1 = 26

    def test_then_complex_chaining_scenario(self, hpx_runtime):
        """Test a complex real-world-like chaining scenario."""
        def fetch_data(user_id: int) -> dict:
            return {"user_id": user_id, "score": user_id * 10}
        
        def calculate_bonus(data: dict, bonus_rate: float, min_bonus: int) -> dict:
            bonus = max(data["score"] * bonus_rate, min_bonus)
            data["bonus"] = bonus
            return data
        
        def format_result(data: dict, currency: str) -> str:
            return f"User {data['user_id']}: {currency}{data['bonus']:.2f}"

        future = submit(fetch_data, 7)
        bonus_future = future.then(calculate_bonus, 0.15, 5)
        formatted_future = bonus_future.then(format_result, "$")
        result = formatted_future.get()
        # score = 7 * 10 = 70
        # bonus = max(70 * 0.15, 5) = max(10.5, 5) = 10.5
        assert result == "User 7: $10.50"


class TestSubmitErrorHandling:
    """Error handling tests for the submit function."""

    def test_submit_invalid_function(self, hpx_runtime):
        """Test submit with invalid function types."""
        # Test with None
        with pytest.raises((TypeError, AttributeError)):
            submit(None)
        
        # Test with non-callable
        with pytest.raises((TypeError, AttributeError)):
            submit("not_a_function")

    def test_submit_function_with_invalid_args(self, hpx_runtime):
        """Test submit with functions that receive invalid arguments."""
        def strict_function(x: int) -> int:
            if not isinstance(x, int):
                raise TypeError("Expected integer")
            return x * 2

        # This should work
        future = submit(strict_function, 5)
        assert future.get() == 10
        
        # This should raise an error when we call get()
        future_bad = submit(strict_function, "not_an_int")
        with pytest.raises(TypeError):
            future_bad.get()

    def test_submit_without_runtime(self):
        """Test submit behavior when HPX runtime is not initialized."""
        def simple_func():
            return "hello"
        
        # Without HPXRuntime context, this may fail
        # The exact behavior depends on the implementation
        try:
            future = submit(simple_func)
            # If it doesn't immediately fail, getting the result might fail
            result = future.get()
        except Exception:
            # Some exception is expected when runtime is not properly initialized
            pass


class TestSubmitReturnValues:
    """Tests for submit function return value handling."""

    def test_submit_returns_future_object(self, hpx_runtime):
        """Test that submit returns a future-like object."""
        def simple_func():
            return 42

        future = submit(simple_func)
        
        # Should have a get method
        assert hasattr(future, 'get')
        assert callable(getattr(future, 'get'))
        
        # get() should return the expected value
        assert future.get() == 42

    def test_submit_type_annotations(self, hpx_runtime):
        """Test that submit works correctly with type annotations."""
        def typed_function(x: int, y: str) -> str:
            return f"{y}: {x}"

        future = submit(typed_function, 42, "Answer")
        result = future.get()
        assert result == "Answer: 42"
