"""
okit CLI main entry module

Responsible for initializing the CLI application and registering commands.
"""

import click
import sys
from pathlib import Path
from rich.console import Console

from ..utils.version import get_version

console = Console()

@click.group()
@click.version_option(version=get_version(), prog_name="okit")
@click.pass_context
def main(ctx: click.Context) -> None:
    """okit - Python tool management platform"""
    # Ensure context object exists
    if ctx.obj is None:
        ctx.obj = {}

    try:
        print("Hello from okit!")

    except Exception as e:
        console.print(f"[red]Failed to initialize okit: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
