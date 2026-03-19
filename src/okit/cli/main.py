"""
okit CLI main entry module

Responsible for initializing the CLI application and registering commands.
"""

import click


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
@click.pass_context
def main(ctx: click.Context, log_level: str, verbose: bool, quiet: bool) -> None:
    """okit - Tool scripts manager"""

    if verbose:
        log_level = "DEBUG"
    elif quiet:
        log_level = "QUIET"

    _configure_output_level(log_level)

    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level

main.add_command(_get_completion_command())
_register_all_tools(main)

if __name__ == "__main__":
    main()
