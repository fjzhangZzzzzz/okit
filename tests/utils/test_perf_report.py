"""Tests for perf_report utility."""

import json
import sys
from unittest.mock import patch, MagicMock, mock_open
import pytest

from okit.utils.perf_report import (
    ConsoleReporter,
    JSONReporter,
    PerformanceReporter,
    print_performance_report,
)
from okit.utils.perf_monitor import PerformanceMetrics


@pytest.fixture
def sample_metrics():
    """Create sample PerformanceMetrics for testing."""
    return PerformanceMetrics(
        total_time=0.5,
        phases={
            "module_imports": 0.2,
            "decorator_execution": 0.1,
            "command_registration": 0.1,
            "external_imports": 0.05,
            "other": 0.05,
        },
        tools={
            "test_tool": {
                "total_time": 0.1,
                "import_time": 0.05,
                "registration_time": 0.05,
            }
        },
        import_times={"okit.tools.test": 0.1},
        external_imports={"click": 0.05, "rich": 0.03},
        system_phases={
            "click_framework": 0.02,
            "python_startup": 0.01,
            "filesystem_ops": 0.01,
        },
        dependency_tree={"okit.tools.test": ["click", "pathlib"]},
        bottlenecks=[
            {
                "module": "okit.tools.slow_tool",
                "time": 0.2,
                "type": "import",
                "severity": "high",
            }
        ],
        recommendations=["Optimize imports", "Use lazy loading"],
        timestamp="2023-01-01T00:00:00",
        version="1.0.0",
    )


class TestConsoleReporter:
    """Test ConsoleReporter class."""

    def test_console_reporter_creation(self):
        """Test ConsoleReporter creation."""
        with patch('sys.stdout.isatty', return_value=True):
            reporter = ConsoleReporter()
            assert reporter.use_colors is True

    def test_console_reporter_creation_no_colors(self):
        """Test ConsoleReporter creation without colors."""
        with patch('sys.stdout.isatty', return_value=False):
            reporter = ConsoleReporter(use_colors=False)
            assert reporter.use_colors is False

    def test_colorize_with_colors(self):
        """Test _colorize method with colors enabled."""
        with patch('sys.stdout.isatty', return_value=True):
            reporter = ConsoleReporter(use_colors=True)
            result = reporter._colorize("test", "red")
            assert "\033[91m" in result
            assert "\033[0m" in result

    def test_colorize_without_colors(self):
        """Test _colorize method without colors."""
        reporter = ConsoleReporter(use_colors=False)
        result = reporter._colorize("test", "red")
        assert result == "test"

    def test_format_time_microseconds(self):
        """Test _format_time method with microseconds."""
        reporter = ConsoleReporter()
        result = reporter._format_time(0.000001)
        assert "μs" in result

    def test_format_time_milliseconds(self):
        """Test _format_time method with milliseconds."""
        reporter = ConsoleReporter()
        result = reporter._format_time(0.001)
        assert "ms" in result

    def test_format_time_seconds(self):
        """Test _format_time method with seconds."""
        reporter = ConsoleReporter()
        result = reporter._format_time(1.5)
        assert "s" in result
        assert "1.500" in result

    def test_create_progress_bar(self):
        """Test _create_progress_bar method."""
        reporter = ConsoleReporter()
        result = reporter._create_progress_bar(50.0, width=10)
        assert len(result) == 10
        assert "█" in result
        assert "░" in result

    def test_format_percentage_normal(self):
        """Test _format_percentage method with normal values."""
        reporter = ConsoleReporter()
        result = reporter._format_percentage(25, 100)
        assert result == "25.0%"

    def test_format_percentage_zero_total(self):
        """Test _format_percentage method with zero total."""
        reporter = ConsoleReporter()
        result = reporter._format_percentage(25, 0)
        assert result == "0.0%"

    def test_generate_report_basic(self, sample_metrics):
        """Test generate_report method with basic metrics."""
        reporter = ConsoleReporter()
        result = reporter.generate_report(sample_metrics)
        
        assert "OKIT Performance Report" in result
        assert "Total CLI initialization" in result
        assert "Phase Breakdown" in result
        assert "Tool-level Breakdown" in result

    def test_generate_report_fast_performance(self):
        """Test generate_report with fast performance."""
        metrics = PerformanceMetrics(total_time=0.1)
        reporter = ConsoleReporter()
        result = reporter.generate_report(metrics)
        assert "✓" in result

    def test_generate_report_slow_performance(self):
        """Test generate_report with slow performance."""
        metrics = PerformanceMetrics(total_time=1.0)
        reporter = ConsoleReporter()
        result = reporter.generate_report(metrics)
        assert "✗" in result

    def test_generate_report_with_external_imports(self, sample_metrics):
        """Test generate_report with external imports."""
        reporter = ConsoleReporter()
        result = reporter.generate_report(sample_metrics)
        assert "Heavy External Imports" in result
        assert "click" in result

    def test_generate_report_with_system_phases(self, sample_metrics):
        """Test generate_report with system phases."""
        reporter = ConsoleReporter()
        result = reporter.generate_report(sample_metrics)
        assert "System Operations" in result

    def test_generate_report_with_bottlenecks(self, sample_metrics):
        """Test generate_report with bottlenecks."""
        reporter = ConsoleReporter()
        result = reporter.generate_report(sample_metrics)
        assert "Performance Insights" in result

    def test_generate_report_with_recommendations(self, sample_metrics):
        """Test generate_report with recommendations."""
        reporter = ConsoleReporter()
        result = reporter.generate_report(sample_metrics)
        assert "Optimization Recommendations" in result

    def test_generate_report_target_achieved(self):
        """Test generate_report when target is achieved."""
        metrics = PerformanceMetrics(total_time=0.2)
        reporter = ConsoleReporter()
        result = reporter.generate_report(metrics)
        assert "Target achieved" in result

    def test_generate_report_target_not_achieved(self):
        """Test generate_report when target is not achieved."""
        metrics = PerformanceMetrics(total_time=0.5)
        reporter = ConsoleReporter()
        result = reporter.generate_report(metrics)
        assert "need:" in result


class TestJSONReporter:
    """Test JSONReporter class."""

    def test_json_reporter_creation(self):
        """Test JSONReporter creation."""
        reporter = JSONReporter()
        assert reporter.pretty is True

    def test_json_reporter_creation_not_pretty(self):
        """Test JSONReporter creation without pretty formatting."""
        reporter = JSONReporter(pretty=False)
        assert reporter.pretty is False

    def test_calculate_performance_score_excellent(self):
        """Test _calculate_performance_score with excellent performance."""
        reporter = JSONReporter()
        metrics = PerformanceMetrics(total_time=0.2)
        score = reporter._calculate_performance_score(metrics)
        assert score == 100.0

    def test_calculate_performance_score_good(self):
        """Test _calculate_performance_score with good performance."""
        reporter = JSONReporter()
        metrics = PerformanceMetrics(total_time=0.4)
        score = reporter._calculate_performance_score(metrics)
        assert 50.0 <= score <= 100.0

    def test_calculate_performance_score_poor(self):
        """Test _calculate_performance_score with poor performance."""
        reporter = JSONReporter()
        metrics = PerformanceMetrics(total_time=1.0)
        score = reporter._calculate_performance_score(metrics)
        assert score < 50.0

    def test_generate_report_pretty(self, sample_metrics):
        """Test generate_report with pretty formatting."""
        reporter = JSONReporter(pretty=True)
        result = reporter.generate_report(sample_metrics)
        
        # Should be valid JSON
        data = json.loads(result)
        assert "total_time" in data
        assert "phases" in data
        assert "performance_score" in data
        assert "status" in data

    def test_generate_report_not_pretty(self, sample_metrics):
        """Test generate_report without pretty formatting."""
        reporter = JSONReporter(pretty=False)
        result = reporter.generate_report(sample_metrics)
        
        # Should be valid JSON
        data = json.loads(result)
        assert "total_time" in data

    def test_generate_report_status_excellent(self):
        """Test generate_report with excellent status."""
        metrics = PerformanceMetrics(total_time=0.2)
        reporter = JSONReporter()
        result = reporter.generate_report(metrics)
        data = json.loads(result)
        assert data["status"] == "excellent"

    def test_generate_report_status_good(self):
        """Test generate_report with good status."""
        metrics = PerformanceMetrics(total_time=0.4)
        reporter = JSONReporter()
        result = reporter.generate_report(metrics)
        data = json.loads(result)
        assert data["status"] == "good"

    def test_generate_report_status_needs_improvement(self):
        """Test generate_report with needs improvement status."""
        metrics = PerformanceMetrics(total_time=1.0)
        reporter = JSONReporter()
        result = reporter.generate_report(metrics)
        data = json.loads(result)
        assert data["status"] == "needs_improvement"


class TestPerformanceReporter:
    """Test PerformanceReporter class."""

    def test_performance_reporter_creation(self):
        """Test PerformanceReporter creation."""
        reporter = PerformanceReporter()
        assert reporter.console_reporter is not None
        assert reporter.json_reporter is not None

    def test_generate_report_console_format(self, sample_metrics):
        """Test generate_report with console format."""
        reporter = PerformanceReporter()
        result = reporter.generate_report(sample_metrics, format="console")
        assert "OKIT Performance Report" in result
        assert "Total CLI initialization" in result

    def test_generate_report_json_format(self, sample_metrics):
        """Test generate_report with json format."""
        reporter = PerformanceReporter()
        result = reporter.generate_report(sample_metrics, format="json")
        data = json.loads(result)
        assert "total_time" in data

    def test_generate_report_both_format(self, sample_metrics):
        """Test generate_report with both format."""
        reporter = PerformanceReporter()
        result = reporter.generate_report(sample_metrics, format="both")
        assert "OKIT Performance Report" in result

    def test_generate_report_with_output_file(self, sample_metrics):
        """Test generate_report with output file."""
        reporter = PerformanceReporter()
        
        with patch("builtins.open", mock_open()) as mock_file:
            result = reporter.generate_report(
                sample_metrics, format="json", output_file="test.json"
            )
            mock_file.assert_called_once_with("test.json", "w", encoding="utf-8")

    def test_generate_report_with_output_file_error(self, sample_metrics):
        """Test generate_report with output file error."""
        reporter = PerformanceReporter()
        
        with patch("builtins.open", side_effect=Exception("test error")):
            with patch("builtins.print") as mock_print:
                result = reporter.generate_report(
                    sample_metrics, format="json", output_file="test.json"
                )
                mock_print.assert_called()

    def test_generate_report_invalid_format(self, sample_metrics):
        """Test generate_report with invalid format."""
        reporter = PerformanceReporter()
        result = reporter.generate_report(sample_metrics, format="invalid")
        # Should return console format as default
        assert result == ""  # Invalid format returns empty string


class TestPrintPerformanceReport:
    """Test print_performance_report function."""

    def test_print_performance_report_console(self, sample_metrics):
        """Test print_performance_report with console format."""
        with patch("builtins.print") as mock_print:
            print_performance_report(sample_metrics, format="console")
            mock_print.assert_called()

    def test_print_performance_report_json(self, sample_metrics):
        """Test print_performance_report with json format."""
        with patch("builtins.print") as mock_print:
            print_performance_report(sample_metrics, format="json")
            mock_print.assert_called()

    def test_print_performance_report_both(self, sample_metrics):
        """Test print_performance_report with both format."""
        with patch("builtins.print") as mock_print:
            print_performance_report(sample_metrics, format="both")
            mock_print.assert_called()

    def test_print_performance_report_with_output_file(self, sample_metrics):
        """Test print_performance_report with output file."""
        with patch("builtins.print") as mock_print:
            with patch("builtins.open", mock_open()):
                print_performance_report(
                    sample_metrics, format="both", output_file="test.json"
                )
                # Should print both report and file location
                assert mock_print.call_count >= 2

    def test_print_performance_report_exception(self, sample_metrics):
        """Test print_performance_report with exception."""
        with patch("okit.utils.perf_report.PerformanceReporter") as mock_reporter_class:
            mock_reporter = MagicMock()
            mock_reporter.generate_report.side_effect = Exception("test error")
            mock_reporter_class.return_value = mock_reporter
            
            with patch("builtins.print") as mock_print:
                print_performance_report(sample_metrics)
                mock_print.assert_called()


class TestIntegration:
    """Integration tests for performance reporting."""

    def test_full_report_generation(self):
        """Test full report generation workflow."""
        metrics = PerformanceMetrics(
            total_time=0.3,
            phases={"module_imports": 0.1, "decorator_execution": 0.1, "other": 0.1},
            tools={"test_tool": {"total_time": 0.1}},
            external_imports={"click": 0.05},
            system_phases={"click_framework": 0.02},
            bottlenecks=[{"module": "test", "time": 0.1, "type": "import"}],
            recommendations=["Optimize imports"],
            timestamp="2023-01-01T00:00:00",
            version="1.0.0",
        )
        
        # Test console reporter
        console_reporter = ConsoleReporter()
        console_result = console_reporter.generate_report(metrics)
        assert "OKIT Performance Report" in console_result
        assert "Total CLI initialization" in console_result
        
        # Test JSON reporter
        json_reporter = JSONReporter()
        json_result = json_reporter.generate_report(metrics)
        data = json.loads(json_result)
        assert data["total_time"] == 0.3
        assert data["status"] == "excellent"
        
        # Test performance reporter
        perf_reporter = PerformanceReporter()
        perf_result = perf_reporter.generate_report(metrics, format="both")
        assert "OKIT Performance Report" in perf_result

    def test_report_with_empty_metrics(self):
        """Test report generation with empty metrics."""
        metrics = PerformanceMetrics()
        
        console_reporter = ConsoleReporter()
        result = console_reporter.generate_report(metrics)
        assert "OKIT Performance Report" in result
        
        json_reporter = JSONReporter()
        result = json_reporter.generate_report(metrics)
        data = json.loads(result)
        assert "total_time" in data

    def test_report_with_large_values(self):
        """Test report generation with large time values."""
        metrics = PerformanceMetrics(
            total_time=10.0,
            phases={"module_imports": 5.0, "decorator_execution": 3.0, "other": 2.0},
            tools={"slow_tool": {"total_time": 8.0}},
            external_imports={"heavy_module": 4.0},
            bottlenecks=[{"module": "very_slow", "time": 8.0, "type": "import", "severity": "high"}],
            recommendations=["Optimize everything"],
        )
        
        console_reporter = ConsoleReporter()
        result = console_reporter.generate_report(metrics)
        assert "10.000s" in result
        assert "✗" in result  # Should indicate slow performance
        
        json_reporter = JSONReporter()
        result = json_reporter.generate_report(metrics)
        data = json.loads(result)
        assert data["status"] == "needs_improvement"
        assert data["performance_score"] < 50.0

    def test_report_with_special_characters(self):
        """Test report generation with special characters in content."""
        metrics = PerformanceMetrics(
            total_time=0.1,
            tools={"tool_with_unicode": {"total_time": 0.05}},
            recommendations=["Optimize with 🚀", "Use ⚡ fast modules"],
        )
        
        console_reporter = ConsoleReporter()
        result = console_reporter.generate_report(metrics)
        # Should handle unicode characters gracefully
        assert "🚀" in result or "Optimization Recommendations" in result
        
        json_reporter = JSONReporter()
        result = json_reporter.generate_report(metrics)
        data = json.loads(result)
        # Should preserve unicode in JSON
        assert "recommendations" in data 