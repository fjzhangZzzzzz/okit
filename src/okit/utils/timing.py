"""
Timing utilities for debug timing statistics

Provides functionality to track and display timing statistics for CLI startup
and tool registration processes.
"""

from typing import TypeVar, Callable, Any

T = TypeVar("T")


def with_timing(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to time function execution (only active in debug mode)"""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.time() - start
            from okit.utils.log import console

            console.print(f"'{func.__name__}' execution time: {elapsed:.2f} seconds")

    return wrapper
