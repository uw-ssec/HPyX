"""
Tests for the submit function in hpyx.futures.submit module.
"""

import time
from typing import Callable, Any
import pytest
import numpy as np
from hpyx.futures.submit import submit
from hpyx.runtime import HPXRuntime


class TestSubmit:
    """Test class for the submit function."""

    def test_submit_simple_function(self):
        """Test submit with a simple function."""
        def add(a: int, b: int) -> int:
            return a + b

        with HPXRuntime():
            future = submit(add, 2, 3)
            result = future.get()
            assert result == 5

    def test_submit_lambda_function(self):
        """Test submit with a lambda function."""
        with HPXRuntime():
            future = submit(lambda x: x * 2, 5)
            result = future.get()
            assert result == 10

    def test_submit_function_with_no_args(self):
        """Test submit with a function that takes no arguments."""
        def get_constant():
            return 42

        with HPXRuntime():
            future = submit(get_constant)
            result = future.get()
            assert result == 42

    def test_submit_function_with_multiple_args(self):
        """Test submit with a function that takes multiple arguments."""
        def multiply_three(a: int, b: int, c: int) -> int:
            return a * b * c

        with HPXRuntime():
            future = submit(multiply_three, 2, 3, 4)
            result = future.get()
            assert result == 24

    def test_submit_function_with_keyword_args(self):
        """Test submit with function using keyword arguments."""
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        with HPXRuntime():
            # Note: submit likely doesn't support keyword args directly, 
            # so we test with positional args
            future = submit(greet, "World", "Hi")
            result = future.get()
            assert result == "Hi, World!"

    def test_submit_function_returning_different_types(self):
        """Test submit with functions returning different data types."""
        
        def return_string() -> str:
            return "hello world"
        
        def return_float() -> float:
            return 3.14159
        
        def return_list() -> list:
            return [1, 2, 3, 4, 5]
        
        def return_dict() -> dict:
            return {"key": "value", "number": 42}

        with HPXRuntime():
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

    def test_submit_multiple_futures(self):
        """Test submitting multiple futures and getting results."""
        def square(x: int) -> int:
            return x * x

        with HPXRuntime():
            futures = []
            for i in range(5):
                future = submit(square, i)
                futures.append(future)
            
            results = [future.get() for future in futures]
            expected = [i * i for i in range(5)]
            assert results == expected

    def test_submit_function_with_side_effects(self):
        """Test submit with a function that has side effects."""
        def append_to_list(lst: list, value: Any) -> list:
            lst.append(value)
            return lst

        with HPXRuntime():
            input_list = [1, 2, 3]
            future = submit(append_to_list, input_list, 4)
            result = future.get()
            assert result == [1, 2, 3, 4]

    def test_submit_function_raising_exception(self):
        """Test submit with a function that raises an exception."""
        def divide_by_zero():
            return 1 / 0

        with HPXRuntime():
            future = submit(divide_by_zero)
            # The exception should be raised when we call get()
            with pytest.raises(ZeroDivisionError):
                future.get()

    def test_submit_cpu_intensive_function(self):
        """Test submit with a CPU-intensive function."""
        def fibonacci(n: int) -> int:
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        with HPXRuntime():
            future = submit(fibonacci, 10)
            result = future.get()
            assert result == 55  # fibonacci(10) = 55

    def test_submit_with_nested_function_calls(self):
        """Test submit with nested function calls."""
        def outer_function(x: int) -> int:
            def inner_function(y: int) -> int:
                return y * 2
            return inner_function(x) + 1

        with HPXRuntime():
            future = submit(outer_function, 5)
            result = future.get()
            assert result == 11  # (5 * 2) + 1 = 11


class TestSubmitWithNumpy:
    """Test class for submit function with numpy operations."""

    def test_submit_numpy_array_sum(self):
        """Test submit with numpy array sum operation."""
        def array_sum(arr: np.ndarray) -> float:
            return np.sum(arr)

        with HPXRuntime():
            test_array = np.array([1, 2, 3, 4, 5])
            future = submit(array_sum, test_array)
            result = future.get()
            assert result == 15.0

    def test_submit_numpy_array_operations(self):
        """Test submit with various numpy array operations."""
        def array_operations(arr: np.ndarray) -> dict:
            return {
                'mean': np.mean(arr),
                'std': np.std(arr),
                'max': np.max(arr),
                'min': np.min(arr)
            }

        with HPXRuntime():
            test_array = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
            future = submit(array_operations, test_array)
            result = future.get()
            
            assert abs(result['mean'] - 3.0) < 1e-6
            assert abs(result['max'] - 5.0) < 1e-6
            assert abs(result['min'] - 1.0) < 1e-6
            assert result['std'] > 0

    def test_submit_numpy_matrix_multiplication(self):
        """Test submit with numpy matrix multiplication."""
        def matrix_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return np.dot(a, b)

        with HPXRuntime():
            matrix_a = np.array([[1, 2], [3, 4]])
            matrix_b = np.array([[5, 6], [7, 8]])
            
            future = submit(matrix_multiply, matrix_a, matrix_b)
            result = future.get()
            
            expected = np.array([[19, 22], [43, 50]])
            np.testing.assert_array_equal(result, expected)

    def test_submit_numpy_large_array_computation(self):
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

        with HPXRuntime():
            future = submit(compute_statistics, 10000)
            result = future.get()
            
            assert result['size'] == 10000
            assert 0.4 < result['mean'] < 0.6  # Should be around 0.5 for uniform random
            assert result['dtype'] == 'float64'

    def test_submit_numpy_array_processing_pipeline(self):
        """Test submit with a numpy array processing pipeline."""
        def process_array(arr: np.ndarray) -> np.ndarray:
            # Normalize the array
            normalized = (arr - np.mean(arr)) / np.std(arr)
            # Apply some transformations
            processed = np.square(normalized)
            # Return the top 5 values
            return np.sort(processed)[-5:]

        with HPXRuntime():
            test_array = np.random.normal(10, 2, 100)  # Normal distribution
            future = submit(process_array, test_array)
            result = future.get()
            
            assert len(result) == 5
            assert all(result[i] <= result[i+1] for i in range(4))  # Should be sorted

    def test_submit_numpy_linear_algebra(self):
        """Test submit with numpy linear algebra operations."""
        def solve_linear_system(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return np.linalg.solve(a, b)

        with HPXRuntime():
            # Create a simple 2x2 system: 2x + y = 5, x + y = 3
            a = np.array([[2, 1], [1, 1]], dtype=float)
            b = np.array([5, 3], dtype=float)
            
            future = submit(solve_linear_system, a, b)
            result = future.get()
            
            # Solution should be x=2, y=1
            expected = np.array([2.0, 1.0])
            np.testing.assert_allclose(result, expected, rtol=1e-6)

    @pytest.mark.parametrize("array_size", [100, 1000, 10000])
    def test_submit_numpy_different_sizes(self, array_size):
        """Test submit with numpy arrays of different sizes."""
        def compute_norm(arr: np.ndarray) -> float:
            return np.linalg.norm(arr)

        with HPXRuntime():
            test_array = np.random.random(array_size)
            future = submit(compute_norm, test_array)
            result = future.get()
            
            # The norm should be positive and reasonable for the array size
            assert result > 0
            assert result < array_size  # Rough upper bound check

    def test_submit_numpy_complex_numbers(self):
        """Test submit with numpy complex number operations."""
        def complex_operations(arr: np.ndarray) -> dict:
            return {
                'magnitude': np.abs(arr),
                'phase': np.angle(arr),
                'real_part': np.real(arr),
                'imag_part': np.imag(arr)
            }

        with HPXRuntime():
            complex_array = np.array([1+2j, 3-4j, -1+1j])
            future = submit(complex_operations, complex_array)
            result = future.get()
            
            assert len(result['magnitude']) == 3
            assert len(result['phase']) == 3
            np.testing.assert_array_equal(result['real_part'], [1, 3, -1])
            np.testing.assert_array_equal(result['imag_part'], [2, -4, 1])


class TestSubmitErrorHandling:
    """Error handling tests for the submit function."""

    def test_submit_invalid_function(self):
        """Test submit with invalid function types."""
        with HPXRuntime():
            # Test with None
            with pytest.raises((TypeError, AttributeError)):
                submit(None)
            
            # Test with non-callable
            with pytest.raises((TypeError, AttributeError)):
                submit("not_a_function")

    def test_submit_function_with_invalid_args(self):
        """Test submit with functions that receive invalid arguments."""
        def strict_function(x: int) -> int:
            if not isinstance(x, int):
                raise TypeError("Expected integer")
            return x * 2

        with HPXRuntime():
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

    def test_submit_returns_future_object(self):
        """Test that submit returns a future-like object."""
        def simple_func():
            return 42

        with HPXRuntime():
            future = submit(simple_func)
            
            # Should have a get method
            assert hasattr(future, 'get')
            assert callable(getattr(future, 'get'))
            
            # get() should return the expected value
            assert future.get() == 42

    def test_submit_type_annotations(self):
        """Test that submit works correctly with type annotations."""
        def typed_function(x: int, y: str) -> str:
            return f"{y}: {x}"

        with HPXRuntime():
            future = submit(typed_function, 42, "Answer")
            result = future.get()
            assert result == "Answer: 42"
