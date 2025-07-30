"""
Performance report generation utilities.

Provides formatted console and JSON output for performance monitoring data.
"""

import json
import sys
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from .perf_monitor import PerformanceMetrics


class ConsoleReporter:
    """Console-based performance reporter with rich formatting"""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors and sys.stdout.isatty()

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled"""
        if not self.use_colors:
            return text

        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

        return f"{colors.get(color, '')}{text}{colors.get('reset', '')}"

    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format"""
        if seconds < 0.001:
            return f"{seconds*1000000:.0f}μs"
        elif seconds < 1:
            return f"{seconds*1000:.0f}ms"
        else:
            return f"{seconds:.3f}s"

    def _create_progress_bar(self, percentage: float, width: int = 20) -> str:
        """Create ASCII progress bar"""
        filled = int(percentage * width / 100)
        bar = "█" * filled + "░" * (width - filled)
        return bar

    def _format_percentage(self, value: float, total: float) -> str:
        """Format percentage with proper handling of zero division"""
        if total == 0:
            return "0.0%"
        return f"{(value/total)*100:.1f}%"

    def generate_report(self, metrics: PerformanceMetrics) -> str:
        """Generate formatted console report"""
        lines = []

        # Header
        lines.append(self._colorize("🚀 OKIT Performance Report", "bold"))
        lines.append("=" * 50)

        # Total time
        total_time_str = self._format_time(metrics.total_time)
        target_time = 0.3  # 300ms target

        if metrics.total_time <= target_time:
            time_status = self._colorize(f"{total_time_str} ✓", "green")
        elif metrics.total_time <= target_time * 2:
            time_status = self._colorize(f"{total_time_str} ⚠", "yellow")
        else:
            time_status = self._colorize(f"{total_time_str} ✗", "red")

        lines.append(f"Total CLI initialization: {time_status}")
        lines.append("")

        # Phase breakdown
        if metrics.phases:
            lines.append(self._colorize("📊 Phase Breakdown:", "bold"))
            phase_items = [
                ("Module Imports", metrics.phases.get("module_imports", 0)),
                ("Decorator Execution", metrics.phases.get("decorator_execution", 0)),
                ("Command Registration", metrics.phases.get("command_registration", 0)),
                ("External Imports", metrics.phases.get("external_imports", 0)),
                ("Other", metrics.phases.get("other", 0)),
            ]

            for phase_name, phase_time in phase_items:
                if phase_time > 0:
                    percentage = self._format_percentage(phase_time, metrics.total_time)
                    time_str = self._format_time(phase_time)
                    bar = self._create_progress_bar(
                        (phase_time / metrics.total_time) * 100, 15
                    )
                    lines.append(
                        f"   ├─ {phase_name:<20} {time_str:>8} ({percentage:>5}) {bar}"
                    )
            lines.append("")

        # External imports breakdown (if significant)
        if metrics.external_imports:
            total_external = sum(metrics.external_imports.values())
            if total_external > 0.01:  # Show if >10ms
                lines.append(self._colorize("📦 Heavy External Imports:", "bold"))

                sorted_externals = sorted(
                    metrics.external_imports.items(), key=lambda x: x[1], reverse=True
                )

                for module, import_time in sorted_externals[:5]:
                    if import_time > 0.005:  # Show imports >5ms
                        time_str = self._format_time(import_time)
                        percentage = self._format_percentage(
                            import_time, metrics.total_time
                        )
                        lines.append(
                            f"   • {module:<15} {time_str:>8} ({percentage:>5})"
                        )
                lines.append("")

        # System operations breakdown (estimated)
        if metrics.system_phases:
            lines.append(self._colorize("⚙️ System Operations (estimated):", "bold"))
            system_items = [
                ("Click Framework", metrics.system_phases.get("click_framework", 0)),
                ("Python Startup", metrics.system_phases.get("python_startup", 0)),
                ("Filesystem Ops", metrics.system_phases.get("filesystem_ops", 0)),
            ]

            for sys_name, sys_time in system_items:
                if sys_time > 0:
                    time_str = self._format_time(sys_time)
                    percentage = self._format_percentage(sys_time, metrics.total_time)
                    lines.append(f"   • {sys_name:<15} {time_str:>8} ({percentage:>5})")
            lines.append("")

        # Tool-level breakdown
        if metrics.tools:
            lines.append(self._colorize("🔍 Tool-level Breakdown:", "bold"))

            # Sort tools by total time
            sorted_tools = sorted(
                metrics.tools.items(),
                key=lambda x: x[1].get("total_time", 0),
                reverse=True,
            )

            for i, (tool_name, tool_data) in enumerate(sorted_tools[:6], 1):
                total_time = tool_data.get("total_time", 0)
                import_time = tool_data.get("import_time", 0)

                if total_time > 0:
                    percentage = self._format_percentage(total_time, metrics.total_time)
                    time_str = self._format_time(total_time)

                    # Status indicator
                    if total_time > 0.2:
                        status = self._colorize("[SLOW]", "red")
                    elif total_time > 0.1:
                        status = self._colorize("[MEDIUM]", "yellow")
                    elif total_time > 0.05:
                        status = self._colorize("[OK]", "cyan")
                    else:
                        status = self._colorize("[FAST]", "green")

                    lines.append(
                        f"   {i}. {tool_name:<18} {time_str:>8} ({percentage:>5}) {status}"
                    )
            lines.append("")

        # Performance insights
        if metrics.bottlenecks:
            lines.append(self._colorize("⚡ Performance Insights:", "bold"))

            # Show top bottlenecks
            for bottleneck in metrics.bottlenecks[:3]:
                module = bottleneck["module"].split(".")[-1]
                time_str = self._format_time(bottleneck["time"])
                severity = bottleneck.get("severity", "medium")

                severity_color = {"high": "red", "medium": "yellow", "low": "cyan"}.get(
                    severity, "white"
                )

                lines.append(
                    f"   • {module} is slow ({time_str}) - {bottleneck.get('type', 'unknown')}"
                )

            # Show summary stats
            slow_count = len(
                [b for b in metrics.bottlenecks if b.get("severity") == "high"]
            )
            medium_count = len(
                [b for b in metrics.bottlenecks if b.get("severity") == "medium"]
            )
            fast_count = len(metrics.tools) - slow_count - medium_count

            if fast_count > 0:
                lines.append(f"   • {fast_count} tools are below 100ms threshold ✓")

            lines.append("")

        # Recommendations
        if metrics.recommendations:
            lines.append(self._colorize("💡 Optimization Recommendations:", "bold"))
            for i, rec in enumerate(metrics.recommendations[:5], 1):
                lines.append(f"   {i}. {rec}")
            lines.append("")

        # Performance target
        target_str = self._format_time(target_time)
        current_str = self._format_time(metrics.total_time)

        if metrics.total_time > target_time:
            improvement = metrics.total_time - target_time
            improvement_str = self._format_time(improvement)
            lines.append(
                self._colorize(
                    f"🎯 Target: Reduce to <{target_str} (current: {current_str}, need: -{improvement_str})",
                    "yellow",
                )
            )
        else:
            lines.append(
                self._colorize(f"🎯 Target achieved: <{target_str} ✓", "green")
            )

        return "\n".join(lines)


class JSONReporter:
    """JSON-based performance reporter"""

    def __init__(self, pretty: bool = True):
        self.pretty = pretty

    def generate_report(self, metrics: PerformanceMetrics) -> str:
        """Generate JSON report"""
        data = asdict(metrics)

        # Add computed fields
        data["performance_score"] = self._calculate_performance_score(metrics)
        data["target_time"] = 0.3
        data["status"] = (
            "excellent"
            if metrics.total_time <= 0.3
            else "good" if metrics.total_time <= 0.6 else "needs_improvement"
        )

        if self.pretty:
            return json.dumps(data, indent=2, default=str)
        else:
            return json.dumps(data, default=str)

    def _calculate_performance_score(self, metrics: PerformanceMetrics) -> float:
        """Calculate performance score (0-100)"""
        target_time = 0.3
        if metrics.total_time <= target_time:
            return 100.0
        elif metrics.total_time <= target_time * 2:
            # Linear decrease from 100 to 50
            return 100 - ((metrics.total_time - target_time) / target_time) * 50
        else:
            # Further decrease for very slow performance
            return max(0, 50 - (metrics.total_time - target_time * 2) * 10)


class PerformanceReporter:
    """Main performance reporter that supports multiple output formats"""

    def __init__(self) -> None:
        self.console_reporter = ConsoleReporter()
        self.json_reporter = JSONReporter()

    def generate_report(
        self,
        metrics: PerformanceMetrics,
        format: str = "console",
        output_file: Optional[str] = None,
    ) -> str:
        """
        Generate performance report in specified format

        Args:
            metrics: Performance metrics to report
            format: Output format ("console", "json", or "both")
            output_file: Optional file path to save JSON output

        Returns:
            Report string (console format if both requested)
        """
        console_report = ""
        json_report = ""

        if format in ["console", "both"]:
            console_report = self.console_reporter.generate_report(metrics)

        if format in ["json", "both"]:
            json_report = self.json_reporter.generate_report(metrics)

        # Save JSON to file if requested
        if output_file and json_report:
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(json_report)
            except Exception as e:
                # Don't fail the whole operation if file write fails
                print(
                    f"Warning: Could not save JSON report to {output_file}: {e}",
                    file=sys.stderr,
                )

        # Return appropriate report
        if format == "json":
            return json_report
        else:
            return console_report


def print_performance_report(
    metrics: PerformanceMetrics,
    format: str = "console",
    output_file: Optional[str] = None,
) -> None:
    """
    Print performance report to console and optionally save to file

    Args:
        metrics: Performance metrics to report
        format: Output format ("console", "json", or "both")
        output_file: Optional file path to save JSON output
    """
    reporter = PerformanceReporter()

    try:
        report = reporter.generate_report(metrics, format, output_file)
        if report:
            print(report)

        if format == "both" and output_file:
            print(f"\nJSON report saved to: {output_file}")

    except Exception as e:
        print(f"Error generating performance report: {e}", file=sys.stderr)
