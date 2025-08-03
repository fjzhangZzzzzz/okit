"""
Performance monitoring utilities for okit CLI startup analysis.

Provides zero-intrusion performance monitoring capabilities to track
module imports, decorator execution, and CLI registration processes.
"""

import sys
import time
import os

# Defer heavy imports to reduce startup cost
# import json  # Only import when needed
# import importlib.util  # Only import when needed
# from types import ModuleType  # Only import when needed
from typing import Dict, List, Optional, Any, Set, Tuple, Callable, Generator, Type
from contextlib import contextmanager

# from pathlib import Path  # Only import when needed
from dataclasses import dataclass, field  # asdict removed, import when needed
from collections import defaultdict


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""

    total_time: float = 0.0
    phases: Dict[str, float] = field(default_factory=dict)
    tools: Dict[str, Dict[str, float]] = field(default_factory=dict)
    import_times: Dict[str, float] = field(default_factory=dict)
    external_imports: Dict[str, float] = field(
        default_factory=dict
    )  # New: external module imports
    system_phases: Dict[str, float] = field(
        default_factory=dict
    )  # New: system operations breakdown
    dependency_tree: Dict[str, List[str]] = field(default_factory=dict)
    bottlenecks: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = ""
    version: str = ""


class ImportTracker:
    """Module import tracker - zero intrusion monitoring"""

    def __init__(self) -> None:
        self.import_times: Dict[str, float] = {}
        self.external_import_times: Dict[str, float] = (
            {}
        )  # Track heavy external imports
        self.import_stack: List[str] = []
        self.dependency_tree: Dict[str, List[str]] = defaultdict(list)
        self.external_deps: Dict[str, List[str]] = defaultdict(list)
        self.original_import: Optional[Callable[..., Any]] = None
        self.tracking_enabled = False
        self._builtin_import_backup: Optional[Callable[..., Any]] = None
        self.okit_modules: Set[str] = set()

        # Optimize: pre-compile the module name check for better performance
        self._okit_prefixes = ("okit.tools.", "okit.core.", "okit.utils.")
        # Track these heavy external modules specifically
        self._heavy_external_modules = (
            "click",
            "pathlib",
            "typing",
            "dataclasses",
            "json",
            "collections",
            "ruamel",
        )

    def start_tracking(self) -> None:
        """Start tracking imports"""
        if self.tracking_enabled:
            return
        import builtins

        self._builtin_import_backup = builtins.__import__
        self.original_import = builtins.__import__
        builtins.__import__ = self._tracked_import
        self.tracking_enabled = True

    def stop_tracking(self) -> None:
        """Stop tracking imports"""
        if not self.tracking_enabled:
            return
        import builtins

        if self._builtin_import_backup:
            builtins.__import__ = self._builtin_import_backup
        self.tracking_enabled = False

    def _tracked_import(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Track import timing and dependencies"""
        start_time = time.perf_counter()

        # Check if this is an okit module we should track (optimized)
        should_track_okit = name.startswith(self._okit_prefixes)
        # Check if this is a heavy external module we should track
        should_track_external = any(
            name.startswith(prefix) for prefix in self._heavy_external_modules
        )

        if should_track_okit:
            self.import_stack.append(name)

        try:
            # Always use the backup builtin import to avoid recursion
            if self._builtin_import_backup is None:
                # Fallback to direct builtins access
                import builtins

                module = builtins.__import__(name, *args, **kwargs)
            else:
                module = self._builtin_import_backup(name, *args, **kwargs)

            elapsed = time.perf_counter() - start_time

            if should_track_okit:
                self.import_times[name] = elapsed
                self.okit_modules.add(name)

                # Record dependency relationships
                if len(self.import_stack) > 1:
                    parent = self.import_stack[-2]
                    self.dependency_tree[parent].append(name)

            elif (
                should_track_external and elapsed > 0.001
            ):  # Only track external imports >1ms
                self.external_import_times[name] = elapsed

            elif self.import_stack:  # Other external dependency
                parent = self.import_stack[-1] if self.import_stack else "unknown"
                self.external_deps[parent].append(name)

            return module

        except Exception as e:
            elapsed = time.perf_counter() - start_time
            if should_track_okit:
                self.import_times[name] = elapsed
            raise
        finally:
            if (
                should_track_okit
                and self.import_stack
                and self.import_stack[-1] == name
            ):
                self.import_stack.pop()


class DecoratorTracker:
    """Decorator execution tracker"""

    def __init__(self) -> None:
        self.decorator_times: Dict[str, float] = {}
        self.cli_creation_times: Dict[str, float] = {}
        self.original_okit_tool: Optional[Callable[..., Any]] = None
        self.tracking_enabled = False

    def start_tracking(self) -> None:
        """Start tracking decorator execution"""
        if self.tracking_enabled:
            return

        try:
            from okit.core.tool_decorator import okit_tool

            self.original_okit_tool = okit_tool

            # Replace the decorator with our timed version
            import okit.core.tool_decorator

            okit.core.tool_decorator.okit_tool = self._timed_okit_tool
            self.tracking_enabled = True
        except ImportError:
            pass  # Module not yet imported

    def stop_tracking(self) -> None:
        """Stop tracking decorator execution"""
        if not self.tracking_enabled or not self.original_okit_tool:
            return

        try:
            import okit.core.tool_decorator

            okit.core.tool_decorator.okit_tool = self.original_okit_tool
            self.tracking_enabled = False
        except ImportError:
            pass

    def _timed_okit_tool(self, *args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """Timed version of @okit_tool decorator"""

        def decorator(tool_class: Type[Any]) -> Type[Any]:
            start_time = time.perf_counter()

            # Execute original decorator
            if self.original_okit_tool is None:
                # Return the original class if decorator is not available
                return tool_class

            try:
                result = self.original_okit_tool(*args, **kwargs)(tool_class)
            except Exception:
                # If original decorator fails, return the original class
                return tool_class

            elapsed = time.perf_counter() - start_time
            class_name = f"{tool_class.__module__}.{tool_class.__name__}"
            self.decorator_times[class_name] = elapsed

            return result  # type: ignore

        return decorator


class RegistrationTracker:
    """CLI registration process tracker"""

    def __init__(self) -> None:
        self.registration_times: Dict[str, Dict[str, float]] = {}
        self.command_times: Dict[str, float] = {}
        self.original_auto_register: Optional[Callable[..., Any]] = None
        self.original_add_command: Optional[Callable[..., Any]] = None
        self.tracking_enabled = False

    def start_tracking(self) -> None:
        """Start tracking registration process"""
        if self.tracking_enabled:
            return

        try:
            from okit.core.autoreg import auto_register_commands

            self.original_auto_register = auto_register_commands

            import okit.core.autoreg

            okit.core.autoreg.auto_register_commands = self._timed_auto_register
            self.tracking_enabled = True
        except ImportError:
            pass

    def stop_tracking(self) -> None:
        """Stop tracking registration process"""
        if not self.tracking_enabled or not self.original_auto_register:
            return

        try:
            import okit.core.autoreg

            okit.core.autoreg.auto_register_commands = self.original_auto_register
            self.tracking_enabled = False
        except ImportError:
            pass

    def _timed_auto_register(
        self,
        package: str,
        package_path: str,
        parent_group: Any,
        debug_enabled: bool = False,
    ) -> Any:
        """Timed version of auto_register_commands"""
        start_time = time.perf_counter()

        # Execute original registration
        if self.original_auto_register is None:
            # Return None if registration is not available
            return None

        try:
            result = self.original_auto_register(
                package, package_path, parent_group, debug_enabled
            )
        except Exception:
            # If original registration fails, return None
            return None

        elapsed = time.perf_counter() - start_time
        self.registration_times[package] = {"total": elapsed}

        return result


class PerformanceAnalyzer:
    """Performance data analyzer and report generator"""

    def __init__(self) -> None:
        self.thresholds = {
            "slow_import": 0.1,  # 100ms
            "slow_decorator": 0.05,  # 50ms
            "slow_registration": 0.1,  # 100ms
            "total_target": 0.3,  # 300ms target
        }

    def analyze_metrics(self, metrics: PerformanceMetrics) -> PerformanceMetrics:
        """Analyze performance metrics and generate insights"""
        # Identify bottlenecks
        bottlenecks = []
        recommendations = []

        # Check slow imports
        for module, time_taken in metrics.import_times.items():
            if time_taken > self.thresholds["slow_import"]:
                bottlenecks.append(
                    {
                        "type": "slow_import",
                        "module": module,
                        "time": time_taken,
                        "severity": "high" if time_taken > 0.2 else "medium",
                    }
                )

        # Generate recommendations
        if any(str(b.get("module", "")).endswith("mobaxterm_pro") for b in bottlenecks):
            recommendations.append(
                "Consider lazy loading of cryptography in mobaxterm_pro"
            )

        if any(str(b.get("module", "")).endswith("shellconfig") for b in bottlenecks):
            recommendations.append("Cache Git repository initialization in shellconfig")

        if metrics.total_time > self.thresholds["total_target"]:
            recommendations.append("Implement deferred loading for heavy modules")

        # Sort bottlenecks by severity and time
        bottlenecks.sort(
            key=lambda x: (x["severity"] == "high", x["time"]), reverse=True
        )

        metrics.bottlenecks = bottlenecks
        metrics.recommendations = recommendations

        return metrics


class PerformanceMonitor:
    """Main performance monitoring controller"""

    def __init__(self) -> None:
        self.import_tracker = ImportTracker()
        self.decorator_tracker = DecoratorTracker()
        self.registration_tracker = RegistrationTracker()
        self.analyzer = PerformanceAnalyzer()
        self.start_time = 0.0
        self.monitoring_enabled = False
        self.metrics = PerformanceMetrics()

    @contextmanager
    def monitor(self) -> Generator[Any, None, None]:
        """Context manager for performance monitoring"""
        self.start_monitoring()
        try:
            yield self
        finally:
            self.stop_monitoring()

    def start_monitoring(self) -> None:
        """Start performance monitoring"""
        if self.monitoring_enabled:
            return

        self.start_time = time.perf_counter()
        self.import_tracker.start_tracking()
        self.decorator_tracker.start_tracking()
        self.registration_tracker.start_tracking()
        self.monitoring_enabled = True

    def stop_monitoring(self) -> None:
        """Stop performance monitoring and collect metrics"""
        if not self.monitoring_enabled:
            return

        total_time = time.perf_counter() - self.start_time

        # Stop all trackers
        self.import_tracker.stop_tracking()
        self.decorator_tracker.stop_tracking()
        self.registration_tracker.stop_tracking()

        # Collect metrics
        self.metrics = PerformanceMetrics(
            total_time=total_time,
            import_times=self.import_tracker.import_times.copy(),
            dependency_tree=dict(self.import_tracker.dependency_tree),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            version="1.0.0",
        )

        # Build tool-level metrics
        for module, import_time in self.import_tracker.import_times.items():
            if module.startswith("okit.tools."):
                tool_name = module.split(".")[-1]
                decorator_time = self.decorator_tracker.decorator_times.get(module, 0.0)

                self.metrics.tools[tool_name] = {
                    "import_time": import_time,
                    "decorator_time": decorator_time,
                    "total_time": import_time + decorator_time,
                }

        # Calculate phase times
        total_import = sum(self.import_tracker.import_times.values())
        total_decorator = sum(self.decorator_tracker.decorator_times.values())
        total_registration = sum(
            times.get("total", 0.0)
            for times in self.registration_tracker.registration_times.values()
        )
        total_external_imports = sum(self.import_tracker.external_import_times.values())

        # Break down "Other" phase into more specific categories
        tracked_time = (
            total_import + total_decorator + total_registration + total_external_imports
        )
        remaining_other = max(0, total_time - tracked_time)

        self.metrics.phases = {
            "module_imports": total_import,
            "decorator_execution": total_decorator,
            "command_registration": total_registration,
            "external_imports": total_external_imports,
            "other": remaining_other,
        }

        # Store external imports data
        self.metrics.external_imports = self.import_tracker.external_import_times.copy()

        # Estimate system operation breakdown (heuristic)
        self.metrics.system_phases = {
            "click_framework": min(
                remaining_other * 0.7, 200
            ),  # Estimate Click takes 70% or max 200ms
            "python_startup": min(
                remaining_other * 0.2, 50
            ),  # Python interpreter overhead
            "filesystem_ops": min(remaining_other * 0.1, 30),  # File system operations
        }

        # Analyze performance
        self.metrics = self.analyzer.analyze_metrics(self.metrics)
        self.monitoring_enabled = False

    def get_metrics(self) -> PerformanceMetrics:
        """Get collected performance metrics"""
        return self.metrics


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def is_monitoring_enabled() -> bool:
    """Check if performance monitoring is enabled via environment variables"""
    return (
        os.getenv("OKIT_PERF_MONITOR") is not None
        or os.getenv("OKIT_PERF") is not None
        or "--perf-monitor" in sys.argv
    )


def get_monitoring_level() -> str:
    """Get monitoring detail level"""
    level = os.getenv("OKIT_PERF_LEVEL", "basic")
    if level in ["1", "true", "on"]:
        return "basic"
    return level.lower()


@contextmanager
def performance_context() -> Generator[Optional[PerformanceMonitor], None, None]:
    """Context manager for automatic performance monitoring"""
    if is_monitoring_enabled():
        monitor = get_monitor()
        with monitor.monitor():
            yield monitor
    else:
        yield None


# === CLI Integration Module ===

import sys
import os
import atexit
import tempfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerfConfig:
    """Performance monitoring configuration"""

    enabled: bool = False
    format: str = "basic"  # basic|detailed|json
    output_file: Optional[str] = None


def get_perf_config(
    cli_format: Optional[str] = None, cli_output: Optional[str] = None
) -> PerfConfig:
    """Get performance monitoring configuration with priority: CLI > ENV > Default"""

    # Check if monitoring should be enabled (CLI args or ENV vars)
    cli_enabled = cli_format is not None
    env_enabled = bool(
        os.getenv("OKIT_PERF_MONITOR")
        or os.getenv("OKIT_PERF")
        or os.getenv("OKIT_PERFORMANCE")
    )

    # Also check sys.argv for early detection (before Click parsing)
    argv_enabled = any(arg.startswith("--perf-monitor") for arg in sys.argv)

    enabled = cli_enabled or env_enabled or argv_enabled

    if not enabled:
        return PerfConfig()

    # Determine format: CLI > ENV > Default
    format_type = (
        cli_format
        if cli_format is not None
        else os.getenv("OKIT_PERF_MONITOR", "basic")
    )

    # Determine output file: CLI > ENV > None
    output_file = cli_output or os.getenv("OKIT_PERF_OUTPUT")

    return PerfConfig(enabled=True, format=format_type, output_file=output_file)


# Global CLI integration state
_cli_perf_monitor = None
_cli_config = None
_atexit_registered = False


def _print_perf_report_once(config: PerfConfig, from_atexit: bool = False) -> None:
    """Print performance report exactly once"""
    global _cli_perf_monitor

    # Use a simple process-specific marker to prevent duplicate output
    marker_file = os.path.join(tempfile.gettempdir(), f"okit_perf_{os.getpid()}.done")

    # Skip if already output or no monitor
    if os.path.exists(marker_file) or _cli_perf_monitor is None:
        return

    try:
        from .perf_report import print_performance_report

        # Create marker file immediately
        try:
            with open(marker_file, "w") as f:
                f.write("done")
        except:
            pass  # Continue even if marker creation fails

        if _cli_perf_monitor.monitoring_enabled:
            _cli_perf_monitor.stop_monitoring()

        metrics = _cli_perf_monitor.get_metrics()

        if metrics.total_time > 0:
            format_type = "json" if config.format == "json" else "console"

            # Add blank line before report for atexit cases
            if from_atexit:
                print()

            print_performance_report(metrics, format_type, config.output_file)

    except Exception as e:
        print(f"Error generating performance report: {e}", file=sys.stderr)


def _atexit_handler() -> None:
    """Exit handler that uses the current config"""
    global _cli_config
    if _cli_config is None:
        return
    _print_perf_report_once(_cli_config, from_atexit=True)


def init_cli_performance_monitoring() -> PerfConfig:
    """Initialize performance monitoring for CLI usage

    Returns:
        PerfConfig: The configuration used for initialization
    """
    global _cli_perf_monitor, _cli_config, _atexit_registered

    # Get initial configuration
    _cli_config = get_perf_config()

    if _cli_config.enabled and not _atexit_registered:
        try:
            _cli_perf_monitor = get_monitor()
            _cli_perf_monitor.start_monitoring()

            # Register exit handler to ensure performance report is always printed
            atexit.register(_atexit_handler)
            _atexit_registered = True

        except ImportError:
            pass

    return _cli_config


def update_cli_performance_config(
    cli_format: Optional[str] = None, cli_output: Optional[str] = None
) -> None:
    """Update performance monitoring configuration with CLI parameters

    Args:
        cli_format: CLI-provided format override
        cli_output: CLI-provided output file override
    """
    global _cli_config, _cli_perf_monitor, _atexit_registered

    if cli_format:
        # Update configuration with CLI parameters
        _cli_config = get_perf_config(cli_format, cli_output)

        # If monitoring wasn't enabled before but should be now, start it
        if _cli_config.enabled and not _atexit_registered:
            try:
                _cli_perf_monitor = get_monitor()
                _cli_perf_monitor.start_monitoring()

                atexit.register(_atexit_handler)
                _atexit_registered = True

            except ImportError:
                pass
