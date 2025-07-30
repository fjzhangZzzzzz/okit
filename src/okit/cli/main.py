"""
okit CLI main entry module

Responsible for initializing the CLI application and registering commands.
"""

import click

# Initialize performance monitoring as early as possible
from okit.utils.perf_monitor import init_cli_performance_monitoring, update_cli_performance_config
init_cli_performance_monitoring()

# Lazy import optimization: only import what we need when we need it
def _get_version():
    from okit.utils.version import get_version
    return get_version()

def _configure_output_level(level):
    from okit.utils.log import configure_output_level
    return configure_output_level(level)

def _register_all_tools(main_group):
    from okit.core.autoreg import register_all_tools
    return register_all_tools(main_group)

def _get_completion_command():
    from okit.core.completion import completion
    return completion


@click.group()
@click.version_option(version=_get_version(), prog_name="okit", message="%(version)s")
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    type=click.Choice(["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "QUIET"]),
    help="Set the output level. Use DEBUG for troubleshooting, QUIET for minimal output.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output (equivalent to --log-level DEBUG)."
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Enable quiet mode (equivalent to --log-level QUIET)."
)
@click.option(
    "--perf-monitor",
    type=click.Choice(["basic", "detailed", "json"]),
    help="Enable performance monitoring. Use 'basic' for console output, 'detailed' for verbose analysis, 'json' for machine-readable output.",
)
@click.option(
    "--perf-output",
    type=click.Path(),
    help="File path to save performance monitoring results in JSON format.",
)
@click.pass_context
def main(ctx: click.Context, log_level: str, verbose: bool, quiet: bool, perf_monitor: str, perf_output: str) -> None:
    """okit - Tool scripts manager"""
    
    # 处理快捷选项
    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "QUIET"
    
    # 使用新的统一输出系统
    _configure_output_level(log_level)
    
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    
    # 如果通过CLI参数指定了性能监控，更新配置
    if perf_monitor:
        update_cli_performance_config(perf_monitor, perf_output)

main.add_command(_get_completion_command())
_register_all_tools(main)

if __name__ == "__main__":
    main()
