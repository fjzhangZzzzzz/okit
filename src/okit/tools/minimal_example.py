import click
from pathlib import Path
from typing import Dict, Any, Optional
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool
from okit.utils.log import output


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
                output.debug("Executing hello command")
                output.success("Hello from Minimal Example Tool!")

                # Show tool information
                tool_info = self.get_tool_info()
                output.info("Tool Information:")
                output.result(f"  Name: {tool_info['name']}")
                output.result(f"  Description: {tool_info['description']}")
                output.result(f"  Config Path: {tool_info['config_path']}")
                output.result(f"  Data Path: {tool_info['data_path']}")

            except Exception as e:
                output.error(f"hello command execution failed: {e}")

        @cli_group.command()
        @click.option("--key", "-k", required=True, help="Configuration key")
        @click.option("--value", "-v", default=None, help="Configuration value")
        def config(key: str, value: Optional[str]) -> None:
            """Manage tool configuration"""
            try:
                output.debug(f"Executing config command, key: {key}, value: {value}")

                if value is None:
                    # Get configuration value
                    config_value = self.get_config(key)
                    if config_value is not None:
                        output.result(f"{key}: {config_value}")
                    else:
                        output.warning(f"Configuration key '{key}' not found")
                else:
                    # Set configuration value
                    self.set_config(key, value)
                    output.success(f"Set {key} = {value}")

            except Exception as e:
                output.error(f"config command execution failed: {e}")

        @cli_group.command()
        def status() -> None:
            """Show tool status and configuration"""
            try:
                output.debug("Executing status command")

                # Show tool status
                output.info("Tool Status:")
                
                # Get all configuration
                config_data = self.get_all_config()
                if config_data:
                    output.info("Configuration:")
                    for key, value in config_data.items():
                        output.result(f"  {key}: {value}")
                else:
                    output.warning("No configuration found")

                # Check if tool is properly initialized
                config_path = self.get_config_path()
                data_path = self.get_data_path()
                
                output.info("Paths:")
                output.result(f"  Config: {config_path}")
                output.result(f"  Data: {data_path}")
                
                if config_path.exists():
                    output.success(f"✓ Config directory exists")
                else:
                    output.warning(f"⚠ Config directory does not exist")
                    
                if data_path.exists():
                    output.success(f"✓ Data directory exists")
                else:
                    output.warning(f"⚠ Data directory does not exist")

            except Exception as e:
                output.error(f"status command execution failed: {e}")

        @cli_group.command()
        @click.option("--count", "-c", default=1, help="Number of test messages")
        @click.option("--with-progress", is_flag=True, help="Show progress messages")
        def test(count: int, with_progress: bool) -> None:
            """Test different output types"""
            try:
                output.debug(f"Executing test command, count: {count}, with_progress: {with_progress}")
                
                output.info(f"Running test with {count} iterations")
                
                for i in range(count):
                    if with_progress:
                        output.progress(f"Processing item {i+1}/{count}")
                    
                    # Simulate some work
                    import time
                    time.sleep(0.1)
                    
                    # Test different output levels
                    if i % 5 == 0:
                        output.success(f"Completed item {i+1}")
                    elif i % 3 == 0:
                        output.warning(f"Warning for item {i+1}")
                    else:
                        output.debug(f"Processed item {i+1}", category="processing")
                
                output.success("Test completed successfully!")
                output.result(f"Total items processed: {count}")

            except Exception as e:
                output.error(f"test command execution failed: {e}")

    def cleanup(self) -> None:
        """Custom cleanup logic"""
        output.debug("Executing custom cleanup logic")
        output.info("Minimal Example Tool cleanup completed")
