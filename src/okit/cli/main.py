"""
okit CLI main entry module

Responsible for initializing the CLI application and registering commands.
"""

import logging
import click

from okit.utils.version import get_version
from okit.utils.log import logger
from okit.core.autoreg import register_all_tools
from okit.core.completion import completion


@click.group()
@click.version_option(version=get_version(), prog_name="okit", message="%(version)s")
@click.option(
    "--log-level",
    default="INFO",
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Set the logging level. Use DEBUG for troubleshooting.",
)
@click.pass_context
def main(ctx: click.Context, log_level: str) -> None:
    """okit - Tool scripts manager"""
    logger.setLevel(getattr(logging, log_level.upper()))
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level


main.add_command(completion)
register_all_tools(main)

if __name__ == "__main__":
    main()
