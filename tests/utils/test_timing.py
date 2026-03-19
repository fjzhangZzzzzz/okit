"""Tests for timing utility."""

import time
import threading
from unittest.mock import patch
import pytest

from okit.utils.timing import (
    with_timing,
    timing_context,
)


@pytest.fixture
def sample_function():
    """Create a sample function for testing."""
    def test_func():
        time.sleep(0.01)
        return "test"
    return test_func


def test_with_timing_decorator(sample_function) -> None:
    """Test with_timing decorator."""
    decorated_func = with_timing(sample_function)
    result = decorated_func()
    assert result == "test"


def test_with_timing_decorator_with_args() -> None:
    """Test with_timing decorator with arguments."""
    def test_func_with_args(arg1, arg2):
        time.sleep(0.01)
        return arg1 + arg2

    decorated_func = with_timing(test_func_with_args)
    result = decorated_func("hello", "world")
    assert result == "helloworld"


def test_timing_context_enabled() -> None:
    """Test timing_context when enabled."""
    with timing_context("test_operation", enabled=True):
        time.sleep(0.01)


def test_timing_context_disabled() -> None:
    """Test timing_context when disabled."""
    with timing_context("test_operation", enabled=False):
        time.sleep(0.01)


def test_timing_context_with_exception() -> None:
    """Test timing_context with exception."""
    with pytest.raises(ValueError):
        with timing_context("test_operation", enabled=True):
            raise ValueError("Test exception")


def test_timing_context_performance() -> None:
    """Test timing_context performance."""
    with timing_context("fast_operation", enabled=True):
        pass


def test_with_timing_decorator_performance() -> None:
    """Test with_timing decorator performance."""
    def fast_func():
        return "fast"

    decorated_func = with_timing(fast_func)
    result = decorated_func()
    assert result == "fast"


def test_timing_context_nested() -> None:
    """Test nested timing_context."""
    with timing_context("outer_operation", enabled=True):
        with timing_context("inner_operation", enabled=True):
            time.sleep(0.01)


def test_with_timing_decorator_exception_handling() -> None:
    """Test with_timing decorator exception handling."""
    def func_with_exception():
        raise ValueError("Test exception")

    decorated_func = with_timing(func_with_exception)

    with pytest.raises(ValueError):
        decorated_func()


def test_timing_context_with_logging() -> None:
    """Test timing_context with logging integration."""
    with patch("okit.utils.log.output") as mock_output:
        with timing_context("test_operation", enabled=True):
            time.sleep(0.01)

        mock_output.result.assert_called()


def test_with_timing_decorator_with_logging() -> None:
    """Test with_timing decorator with logging integration."""
    with patch("okit.utils.log.output") as mock_output:
        def test_func():
            time.sleep(0.01)
            return "test"

        decorated_func = with_timing(test_func)
        result = decorated_func()

        assert result == "test"
        mock_output.result.assert_called()


def test_timing_context_thread_safety() -> None:
    """Test timing_context thread safety."""
    def timing_worker():
        with timing_context("worker_operation", enabled=True):
            time.sleep(0.01)

    threads = []
    for _ in range(5):
        thread = threading.Thread(target=timing_worker)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def test_with_timing_decorator_thread_safety() -> None:
    """Test with_timing decorator thread safety."""
    def test_func():
        time.sleep(0.01)
        return "test"

    decorated_func = with_timing(test_func)

    def worker():
        result = decorated_func()
        assert result == "test"

    threads = []
    for _ in range(5):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


def test_timing_context_with_custom_operation_name() -> None:
    """Test timing_context with custom operation names."""
    for name in ["import_modules", "register_tools", "setup_cli"]:
        with timing_context(name, enabled=True):
            time.sleep(0.001)


def test_with_timing_decorator_with_different_function_types() -> None:
    """Test with_timing decorator with different function types."""
    for func, expected in [
        (lambda: "string", "string"),
        (lambda: 42, 42),
        (lambda: [1, 2, 3], [1, 2, 3]),
    ]:
        result = with_timing(func)()
        assert result == expected


def test_timing_context_disabled_with_exception() -> None:
    """Test timing_context disabled with exception."""
    with pytest.raises(ValueError):
        with timing_context("test_operation", enabled=False):
            raise ValueError("Test exception")


def test_with_timing_decorator_with_kwargs() -> None:
    """Test with_timing decorator with keyword arguments."""
    def test_func_with_kwargs(**kwargs):
        time.sleep(0.01)
        return kwargs

    decorated_func = with_timing(test_func_with_kwargs)
    result = decorated_func(key1="value1", key2="value2")
    assert result == {"key1": "value1", "key2": "value2"}


def test_with_timing_preserves_metadata() -> None:
    """Test that with_timing preserves __name__ and __doc__ via functools.wraps."""
    def my_function():
        """My docstring."""
        return "result"

    decorated = with_timing(my_function)
    assert decorated.__name__ == "my_function"
    assert decorated.__doc__ == "My docstring."


def test_timing_context_disabled_no_output() -> None:
    """Test that timing_context with enabled=False never calls output.result."""
    with patch("okit.utils.log.output") as mock_output:
        with timing_context("test_op", enabled=False):
            pass
        mock_output.result.assert_not_called()
