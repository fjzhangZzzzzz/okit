"""
Timing utilities for debug timing statistics

Provides functionality to track and display timing statistics for CLI startup
and tool registration processes. Now integrated with the performance monitoring system.
"""

import os
import sys
from typing import TypeVar, Callable, Any, Optional, Generator
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
    """Context manager for timing operations with optional performance monitoring integration"""
    if not enabled:
        yield
        return

    import time

    start_time = time.perf_counter()

    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time

        # If performance monitoring is active, don't duplicate output
        if not _is_perf_monitoring_active():
            from okit.utils.log import output

            output.result(f"'{operation_name}' completed in {elapsed:.3f} seconds")


def _is_perf_monitoring_active() -> bool:
    """Check if performance monitoring is currently active"""
    try:
        from .perf_monitor import is_monitoring_enabled

        return is_monitoring_enabled()
    except ImportError:
        return False


# Performance monitoring integration functions
def enable_performance_monitoring() -> Optional[Any]:
    """
    Enable performance monitoring for CLI startup analysis.

    Returns monitor instance if successful, None otherwise.
    """
    try:
        from .perf_monitor import get_monitor

        monitor = get_monitor()
        monitor.start_monitoring()
        return monitor
    except ImportError:
        return None


def disable_performance_monitoring(monitor: Optional[Any] = None) -> Optional[Any]:
    """
    Disable performance monitoring and return collected metrics.

    Args:
        monitor: Monitor instance to stop, or None to use global monitor

    Returns:
        PerformanceMetrics if successful, None otherwise
    """
    try:
        from .perf_monitor import get_monitor

        if monitor is None:
            monitor = get_monitor()

        monitor.stop_monitoring()
        return monitor.get_metrics()
    except ImportError:
        return None


def print_performance_summary(
    format: str = "console", output_file: Optional[str] = None
) -> None:
    """
    Print performance monitoring summary if monitoring was enabled.

    Args:
        format: Output format ("console", "json", or "both")
        output_file: Optional file to save JSON output
    """
    try:
        from .perf_monitor import get_monitor
        from .perf_report import print_performance_report

        monitor = get_monitor()
        if monitor.monitoring_enabled:
            # Stop monitoring if still active
            monitor.stop_monitoring()

        metrics = monitor.get_metrics()
        if metrics.total_time > 0:  # Only print if we have actual data
            print_performance_report(metrics, format, output_file)

    except ImportError:
        pass  # Performance monitoring not available
    except Exception as e:
        print(f"Error generating performance summary: {e}", file=sys.stderr)
