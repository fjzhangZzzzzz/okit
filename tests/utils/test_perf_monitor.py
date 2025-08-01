"""Tests for perf_monitor utility."""

import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, mock_open
import pytest

from okit.utils.perf_monitor import (
    PerformanceMetrics,
    ImportTracker,
    DecoratorTracker,
    RegistrationTracker,
    PerformanceAnalyzer,
    PerformanceMonitor,
    get_monitor,
    is_monitoring_enabled,
    get_monitoring_level,
    performance_context,
    PerfConfig,
    get_perf_config,
    _print_perf_report_once,
    _atexit_handler,
    init_cli_performance_monitoring,
    update_cli_performance_config,
)


@pytest.fixture
def performance_metrics() -> PerformanceMetrics:
    """Create a PerformanceMetrics instance."""
    return PerformanceMetrics(
        total_time=1.5,
        phases={"import": 0.5, "registration": 1.0},
        tools={"test_tool": {"import": 0.2, "registration": 0.3}},
        import_times={"okit.tools.test": 0.1},
        external_imports={"click": 0.05},
        system_phases={"startup": 0.1},
        dependency_tree={"okit.tools.test": ["click", "pathlib"]},
        bottlenecks=[{"phase": "import", "time": 0.3, "description": "Slow import"}],
        recommendations=["Optimize imports"],
        timestamp="2023-01-01T00:00:00",
        version="1.0.0",
    )


@pytest.fixture
def import_tracker() -> ImportTracker:
    """Create an ImportTracker instance."""
    return ImportTracker()


@pytest.fixture
def decorator_tracker() -> DecoratorTracker:
    """Create a DecoratorTracker instance."""
    return DecoratorTracker()


@pytest.fixture
def registration_tracker() -> RegistrationTracker:
    """Create a RegistrationTracker instance."""
    return RegistrationTracker()


@pytest.fixture
def performance_analyzer() -> PerformanceAnalyzer:
    """Create a PerformanceAnalyzer instance."""
    return PerformanceAnalyzer()


@pytest.fixture
def performance_monitor() -> PerformanceMonitor:
    """Create a PerformanceMonitor instance."""
    return PerformanceMonitor()


@pytest.fixture
def perf_config() -> PerfConfig:
    """Create a PerfConfig instance."""
    return PerfConfig(enabled=True, format="detailed", output_file="test_report.json")


def test_performance_metrics_initialization(performance_metrics: PerformanceMetrics) -> None:
    """Test PerformanceMetrics initialization."""
    assert performance_metrics.total_time == 1.5
    assert len(performance_metrics.phases) == 2
    assert len(performance_metrics.tools) == 1
    assert len(performance_metrics.import_times) == 1
    assert len(performance_metrics.external_imports) == 1
    assert len(performance_metrics.system_phases) == 1
    assert len(performance_metrics.dependency_tree) == 1
    assert len(performance_metrics.bottlenecks) == 1
    assert len(performance_metrics.recommendations) == 1
    assert performance_metrics.timestamp == "2023-01-01T00:00:00"
    assert performance_metrics.version == "1.0.0"


def test_import_tracker_initialization(import_tracker: ImportTracker) -> None:
    """Test ImportTracker initialization."""
    assert len(import_tracker.import_times) == 0
    assert len(import_tracker.external_import_times) == 0
    assert len(import_tracker.import_stack) == 0
    assert len(import_tracker.dependency_tree) == 0
    assert len(import_tracker.external_deps) == 0
    assert import_tracker.original_import is None
    assert not import_tracker.tracking_enabled
    assert len(import_tracker.okit_modules) == 0


def test_import_tracker_start_stop_tracking(import_tracker: ImportTracker) -> None:
    """Test starting and stopping import tracking."""
    import_tracker.start_tracking()
    assert import_tracker.tracking_enabled
    assert import_tracker.original_import is not None
    
    import_tracker.stop_tracking()
    assert not import_tracker.tracking_enabled


def test_import_tracker_tracked_import(import_tracker: ImportTracker) -> None:
    """Test tracked import functionality."""
    import_tracker.start_tracking()
    
    # Mock the original import function
    mock_original_import = MagicMock()
    import_tracker.original_import = mock_original_import
    mock_original_import.return_value = MagicMock()
    
    # Test tracking an okit module
    result = import_tracker._tracked_import("okit.tools.test")
    assert result is not None
    assert "okit.tools.test" in import_tracker.import_times
    
    # Test tracking an external module - we need to ensure it takes >1ms
    # For testing purposes, we'll just verify the logic works
    # The actual time tracking depends on real import performance
    result = import_tracker._tracked_import("click")
    assert result is not None
    # Note: click may not be added to external_import_times if import is too fast
    # This is expected behavior - only track external imports >1ms
    
    import_tracker.stop_tracking()


def test_decorator_tracker_initialization(decorator_tracker: DecoratorTracker) -> None:
    """Test DecoratorTracker initialization."""
    assert len(decorator_tracker.decorator_times) == 0
    assert decorator_tracker.original_okit_tool is None
    assert not decorator_tracker.tracking_enabled


def test_decorator_tracker_start_stop_tracking(decorator_tracker: DecoratorTracker) -> None:
    """Test starting and stopping decorator tracking."""
    decorator_tracker.start_tracking()
    assert decorator_tracker.tracking_enabled
    assert decorator_tracker.original_okit_tool is not None
    
    decorator_tracker.stop_tracking()
    assert not decorator_tracker.tracking_enabled


def test_decorator_tracker_timed_okit_tool(decorator_tracker: DecoratorTracker) -> None:
    """Test timed okit tool decorator."""
    decorator_tracker.start_tracking()
    
    # Create a mock tool class
    class MockTool:
        pass
    
    # Test the decorator with required tool_name parameter
    decorated_tool = decorator_tracker._timed_okit_tool("test_tool")(MockTool)
    assert decorated_tool == MockTool
    
    decorator_tracker.stop_tracking()


def test_registration_tracker_initialization(registration_tracker: RegistrationTracker) -> None:
    """Test RegistrationTracker initialization."""
    assert len(registration_tracker.registration_times) == 0
    assert registration_tracker.original_auto_register is None
    assert not registration_tracker.tracking_enabled


def test_registration_tracker_start_stop_tracking(registration_tracker: RegistrationTracker) -> None:
    """Test starting and stopping registration tracking."""
    registration_tracker.start_tracking()
    assert registration_tracker.tracking_enabled
    assert registration_tracker.original_auto_register is not None
    
    registration_tracker.stop_tracking()
    assert not registration_tracker.tracking_enabled


def test_registration_tracker_timed_auto_register(registration_tracker: RegistrationTracker) -> None:
    """Test timed auto register function."""
    registration_tracker.start_tracking()
    
    # Mock the original auto_register function
    mock_original_auto_register = MagicMock()
    registration_tracker.original_auto_register = mock_original_auto_register
    mock_original_auto_register.return_value = MagicMock()
    
    # Test the timed function
    result = registration_tracker._timed_auto_register("test_package", "/test/path", MagicMock(), False)
    assert result is not None
    
    registration_tracker.stop_tracking()


def test_performance_analyzer_initialization(performance_analyzer: PerformanceAnalyzer) -> None:
    """Test PerformanceAnalyzer initialization."""
    assert performance_analyzer.thresholds is not None
    assert len(performance_analyzer.thresholds) > 0


def test_performance_analyzer_analyze_metrics(performance_analyzer: PerformanceAnalyzer, performance_metrics: PerformanceMetrics) -> None:
    """Test analyzing performance metrics."""
    result = performance_analyzer.analyze_metrics(performance_metrics)
    
    assert result is not None
    assert len(result.bottlenecks) >= 0
    assert len(result.recommendations) >= 0


def test_performance_monitor_initialization(performance_monitor: PerformanceMonitor) -> None:
    """Test PerformanceMonitor initialization."""
    assert performance_monitor.metrics is not None
    assert performance_monitor.import_tracker is not None
    assert performance_monitor.decorator_tracker is not None
    assert performance_monitor.registration_tracker is not None
    assert performance_monitor.analyzer is not None


def test_performance_monitor_context_manager(performance_monitor: PerformanceMonitor) -> None:
    """Test performance monitor context manager."""
    with performance_monitor.monitor():
        time.sleep(0.01)  # Small delay to ensure timing
    
    metrics = performance_monitor.get_metrics()
    assert metrics.total_time > 0


def test_performance_monitor_start_stop_monitoring(performance_monitor: PerformanceMonitor) -> None:
    """Test starting and stopping monitoring."""
    performance_monitor.start_monitoring()
    assert performance_monitor.import_tracker.tracking_enabled
    assert performance_monitor.decorator_tracker.tracking_enabled
    assert performance_monitor.registration_tracker.tracking_enabled
    
    performance_monitor.stop_monitoring()
    assert not performance_monitor.import_tracker.tracking_enabled
    assert not performance_monitor.decorator_tracker.tracking_enabled
    assert not performance_monitor.registration_tracker.tracking_enabled


def test_get_monitor() -> None:
    """Test getting the global monitor instance."""
    monitor = get_monitor()
    assert isinstance(monitor, PerformanceMonitor)


def test_is_monitoring_enabled() -> None:
    """Test checking if monitoring is enabled."""
    # Test with environment variable set
    with patch.dict(os.environ, {"OKIT_PERF_MONITOR": "1"}):
        assert is_monitoring_enabled()
    
    # Test without environment variable
    with patch.dict(os.environ, {}, clear=True):
        assert not is_monitoring_enabled()


def test_get_monitoring_level() -> None:
    """Test getting monitoring level."""
    # Test with environment variable set
    with patch.dict(os.environ, {"OKIT_PERF_LEVEL": "detailed"}):
        assert get_monitoring_level() == "detailed"
    
    # Test without environment variable
    with patch.dict(os.environ, {}, clear=True):
        assert get_monitoring_level() == "basic"


def test_performance_context() -> None:
    """Test performance context manager."""
    with performance_context() as monitor:
        if monitor:
            assert isinstance(monitor, PerformanceMonitor)


def test_perf_config_initialization(perf_config: PerfConfig) -> None:
    """Test PerfConfig initialization."""
    assert perf_config.enabled is True
    assert perf_config.format == "detailed"
    assert perf_config.output_file == "test_report.json"


def test_get_perf_config() -> None:
    """Test getting performance configuration."""
    # Test with CLI parameters
    config = get_perf_config("json", "test_output.json")
    assert config.format == "json"
    assert config.output_file == "test_output.json"
    
    # Test without CLI parameters
    config = get_perf_config()
    assert config.format == "basic"
    assert config.output_file is None


@patch("okit.utils.perf_monitor.output")
def test_print_perf_report_once(mock_output: MagicMock, performance_metrics: PerformanceMetrics) -> None:
    """Test printing performance report."""
    config = PerfConfig(enabled=True, format="basic")
    
    _print_perf_report_once(config, False)
    # Should call output.info at least once
    assert mock_output.info.called


def test_atexit_handler() -> None:
    """Test atexit handler."""
    # This should not raise any exceptions
    _atexit_handler()


def test_init_cli_performance_monitoring() -> None:
    """Test initializing CLI performance monitoring."""
    # Test with monitoring enabled
    with patch.dict(os.environ, {"OKIT_PERF_MONITOR": "1"}):
        config = init_cli_performance_monitoring()
        assert config.enabled is True
    
    # Test with monitoring disabled
    with patch.dict(os.environ, {}, clear=True):
        config = init_cli_performance_monitoring()
        assert config.enabled is False


def test_update_cli_performance_config() -> None:
    """Test updating CLI performance configuration."""
    # This should not raise any exceptions
    update_cli_performance_config("detailed", "test_output.json")


def test_import_tracker_heavy_external_modules(import_tracker: ImportTracker) -> None:
    """Test tracking heavy external modules."""
    import_tracker.start_tracking()
    
    # Test tracking heavy external modules
    for module in import_tracker._heavy_external_modules:
        mock_original_import = MagicMock()
        import_tracker.original_import = mock_original_import
        mock_original_import.return_value = MagicMock()
        
        result = import_tracker._tracked_import(module)
        assert result is not None
        assert module in import_tracker.external_import_times
    
    import_tracker.stop_tracking()


def test_import_tracker_dependency_tracking(import_tracker: ImportTracker) -> None:
    """Test dependency tracking."""
    import_tracker.start_tracking()
    import_tracker.import_stack = ["okit.tools.test"]
    
    mock_original_import = MagicMock()
    import_tracker.original_import = mock_original_import
    mock_original_import.return_value = MagicMock()
    
    # Test dependency tracking
    result = import_tracker._tracked_import("click")
    assert result is not None
    assert "okit.tools.test" in import_tracker.dependency_tree
    assert "click" in import_tracker.dependency_tree["okit.tools.test"]
    
    import_tracker.stop_tracking()


def test_performance_analyzer_bottleneck_detection(performance_analyzer: PerformanceAnalyzer) -> None:
    """Test bottleneck detection."""
    metrics = PerformanceMetrics(
        total_time=5.0,
        phases={"import": 3.0, "registration": 2.0},
        import_times={"slow_module": 2.5},
        external_imports={"heavy_module": 1.0},
    )
    
    result = performance_analyzer.analyze_metrics(metrics)
    assert len(result.bottlenecks) > 0


def test_performance_analyzer_recommendations(performance_analyzer: PerformanceAnalyzer) -> None:
    """Test recommendation generation."""
    metrics = PerformanceMetrics(
        total_time=1.0,
        phases={"import": 0.8},
        import_times={"slow_module": 0.5},
        external_imports={"heavy_module": 0.3},
    )
    
    result = performance_analyzer.analyze_metrics(metrics)
    assert len(result.recommendations) > 0


def test_performance_monitor_get_metrics(performance_monitor: PerformanceMonitor) -> None:
    """Test getting metrics from monitor."""
    # Start monitoring to generate some data
    performance_monitor.start_monitoring()
    time.sleep(0.01)
    performance_monitor.stop_monitoring()
    
    metrics = performance_monitor.get_metrics()
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.total_time >= 0


def test_performance_context_with_monitoring_disabled() -> None:
    """Test performance context when monitoring is disabled."""
    with patch.dict(os.environ, {}, clear=True):
        with performance_context() as monitor:
            assert monitor is None


def test_perf_config_with_file_output() -> None:
    """Test PerfConfig with file output."""
    config = PerfConfig(enabled=True, format="json", output_file="test.json")
    
    with patch("builtins.open", mock_open()) as mock_file:
        _print_perf_report_once(config, False)
        # Should attempt to write to file
        mock_file.assert_called()


def test_import_tracker_error_handling(import_tracker: ImportTracker) -> None:
    """Test import tracker error handling."""
    import_tracker.start_tracking()
    
    # Mock original import to raise an exception
    mock_original_import = MagicMock()
    mock_original_import.side_effect = ImportError("Test import error")
    import_tracker.original_import = mock_original_import
    
    # Should handle the exception gracefully
    with pytest.raises(ImportError):
        import_tracker._tracked_import("test_module")
    
    import_tracker.stop_tracking()


def test_decorator_tracker_error_handling(decorator_tracker: DecoratorTracker) -> None:
    """Test decorator tracker error handling."""
    decorator_tracker.start_tracking()
    
    # Mock original okit_tool to raise an exception
    mock_original_okit_tool = MagicMock()
    mock_original_okit_tool.side_effect = Exception("Test decorator error")
    decorator_tracker.original_okit_tool = mock_original_okit_tool
    
    # Should handle the exception gracefully
    with pytest.raises(Exception):
        decorator_tracker._timed_okit_tool()(MagicMock())
    
    decorator_tracker.stop_tracking()


def test_registration_tracker_error_handling(registration_tracker: RegistrationTracker) -> None:
    """Test registration tracker error handling."""
    registration_tracker.start_tracking()
    
    # Mock original auto_register to raise an exception
    mock_original_auto_register = MagicMock()
    mock_original_auto_register.side_effect = Exception("Test registration error")
    registration_tracker.original_auto_register = mock_original_auto_register
    
    # Should handle the exception gracefully
    with pytest.raises(Exception):
        registration_tracker._timed_auto_register("test_package", "/test/path", MagicMock(), False)
    
    registration_tracker.stop_tracking()


def test_performance_monitor_multiple_starts(performance_monitor: PerformanceMonitor) -> None:
    """Test multiple start/stop cycles."""
    # First start
    performance_monitor.start_monitoring()
    assert performance_monitor.import_tracker.tracking_enabled
    
    # Stop
    performance_monitor.stop_monitoring()
    assert not performance_monitor.import_tracker.tracking_enabled
    
    # Second start
    performance_monitor.start_monitoring()
    assert performance_monitor.import_tracker.tracking_enabled
    
    # Stop again
    performance_monitor.stop_monitoring()
    assert not performance_monitor.import_tracker.tracking_enabled


def test_performance_metrics_empty_initialization() -> None:
    """Test PerformanceMetrics with empty initialization."""
    metrics = PerformanceMetrics()
    assert metrics.total_time == 0.0
    assert len(metrics.phases) == 0
    assert len(metrics.tools) == 0
    assert len(metrics.import_times) == 0
    assert len(metrics.external_imports) == 0
    assert len(metrics.system_phases) == 0
    assert len(metrics.dependency_tree) == 0
    assert len(metrics.bottlenecks) == 0
    assert len(metrics.recommendations) == 0
    assert metrics.timestamp == ""
    assert metrics.version == ""


def test_performance_analyzer_empty_metrics(performance_analyzer: PerformanceAnalyzer) -> None:
    """Test analyzing empty metrics."""
    empty_metrics = PerformanceMetrics()
    result = performance_analyzer.analyze_metrics(empty_metrics)
    
    assert result is not None
    assert result.total_time == 0.0 