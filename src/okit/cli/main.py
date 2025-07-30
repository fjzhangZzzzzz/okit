"""
okit CLI main entry module

Responsible for initializing the CLI application and registering commands.
"""

import click

from okit.utils.version import get_version
from okit.utils.log import configure_output_level, output
from okit.core.autoreg import register_all_tools
from okit.core.completion import completion


@click.group()
@click.version_option(version=get_version(), prog_name="okit", message="%(version)s")
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
@click.pass_context
def main(ctx: click.Context, log_level: str, verbose: bool, quiet: bool) -> None:
    """okit - Tool scripts manager"""
    
    # 处理快捷选项
    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "QUIET"
    
    # 使用新的统一输出系统
    configure_output_level(log_level)
    
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level


main.add_command(completion)
register_all_tools(main)

if __name__ == "__main__":
    main()
