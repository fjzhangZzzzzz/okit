"""
Timing utilities for debug timing statistics

Provides functionality to track and display timing statistics for CLI startup
and tool registration processes.
"""

from typing import TypeVar, Callable, Any, Generator
from contextlib import contextmanager

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
            from okit.utils.log import output

            output.result(f"'{func.__name__}' execution time: {elapsed:.2f} seconds")

    return wrapper


@contextmanager
def timing_context(
    operation_name: str, enabled: bool = True
) -> Generator[None, None, None]:
    """Context manager for timing operations"""
    if not enabled:
        yield
        return

    import time

    start_time = time.perf_counter()

    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        from okit.utils.log import output

        output.result(f"'{operation_name}' completed in {elapsed:.3f} seconds")
