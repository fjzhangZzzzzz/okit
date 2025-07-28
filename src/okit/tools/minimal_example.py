import click
from pathlib import Path
from typing import Dict, Any, Optional
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool
from okit.utils.log import console


@okit_tool("minimal", "Minimal Example Tool")
class MinimalExample(BaseTool):
    """Minimal Example Tool - Demonstrates BaseTool and configuration management features"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

    def _get_cli_help(self) -> str:
        """Custom CLI help information"""
        return """
Minimal Example Tool - Demonstrates BaseTool and configuration management features
        """.strip()

    def _get_cli_short_help(self) -> str:
        """Custom CLI short help information"""
        return "Minimal example tool"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """Add tool-specific CLI commands"""

        @cli_group.command()
        def hello() -> None:
            """Simple greeting command"""
            try:
                self.logger.info("Executing hello command")
                console.print("[green]Hello from Minimal Example Tool![/green]")

                # Show tool information
                tool_info = self.get_tool_info()
                console.print(f"[blue]Tool Information:[/blue]")
                console.print(f"  Name: {tool_info['name']}")
                console.print(f"  Description: {tool_info['description']}")
                console.print(f"  Config Path: {tool_info['config_path']}")
                console.print(f"  Data Path: {tool_info['data_path']}")

            except Exception as e:
                self.logger.error(f"hello command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.option("--key", "-k", required=True, help="Configuration key")
        @click.option("--value", "-v", default=None, help="Configuration value")
        def config(key: str, value: Optional[str]) -> None:
            """Configuration management demonstration"""
            try:
                self.logger.info(
                    f"Executing config command, key: {key}, value: {value}"
                )

                if value is None:
                    # Read configuration
                    config_value = self.get_config_value(key, "Not set")
                    console.print(f"[blue]Config {key}:[/blue] {config_value}")
                else:
                    # Set configuration
                    if self.set_config_value(key, value):
                        console.print(
                            f"[green]Successfully set config {key} = {value}[/green]"
                        )
                    else:
                        console.print(f"[red]Failed to set config[/red]")

            except Exception as e:
                self.logger.error(f"config command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.option("--path", "-p", default="", help="Data path")
        def data(path: str) -> None:
            """Data directory management demonstration"""
            try:
                self.logger.info(f"Executing data command, path: {path}")

                if path:
                    # Ensure data directory exists
                    data_dir = self.ensure_data_dir(path)
                    console.print(f"[green]Data directory created: {data_dir}[/green]")

                    # List files
                    files = self.list_data_files(path)
                    if files:
                        console.print(f"[blue]Directory contents:[/blue]")
                        for file in files:
                            console.print(f"  {file.name}")
                    else:
                        console.print("[yellow]Directory is empty[/yellow]")
                else:
                    # Show data directory information
                    data_path = self.get_data_path()
                    console.print(f"[blue]Data root directory:[/blue] {data_path}")

                    # List all data files
                    all_files = self.list_data_files()
                    if all_files:
                        console.print(f"[blue]All data files:[/blue]")
                        for file in all_files:
                            console.print(f"  {file.name}")
                    else:
                        console.print("[yellow]No data files[/yellow]")

            except Exception as e:
                self.logger.error(f"data command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        def backup() -> None:
            """Configuration backup demonstration"""
            try:
                self.logger.info("Executing backup command")

                backup_path = self.backup_config()
                if backup_path:
                    console.print(
                        f"[green]Configuration backed up: {backup_path}[/green]"
                    )
                else:
                    console.print(
                        "[yellow]No backup needed (config file doesn't exist)[/yellow]"
                    )

            except Exception as e:
                self.logger.error(f"backup command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        def info() -> None:
            """Display detailed tool information"""
            try:
                self.logger.info("Executing info command")

                # Tool information
                tool_info = self.get_tool_info()
                console.print("[bold blue]Tool Information[/bold blue]")
                for key, value in tool_info.items():
                    console.print(f"  {key}: {value}")

                # Configuration information
                console.print("\n[bold blue]Configuration Information[/bold blue]")
                config_path = self.get_config_path()
                config_file = self.get_config_file()
                console.print(f"  Config directory: {config_path}")
                console.print(f"  Config file: {config_file}")
                console.print(f"  Config file exists: {config_file.exists()}")

                # Data information
                console.print("\n[bold blue]Data Information[/bold blue]")
                data_path = self.get_data_path()
                console.print(f"  Data directory: {data_path}")
                console.print(f"  Data directory exists: {data_path.exists()}")

                # List configuration files
                config_files = list(config_path.glob("*.yaml")) + list(
                    config_path.glob("*.yml")
                )
                if config_files:
                    console.print(
                        f"  Configuration files: {[f.name for f in config_files]}"
                    )
                else:
                    console.print("  Configuration files: None")

            except Exception as e:
                self.logger.error(f"info command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

    def validate_config(self) -> bool:
        """Validate configuration"""
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """Custom cleanup logic"""
        self.logger.info("Executing custom cleanup logic")
        pass
