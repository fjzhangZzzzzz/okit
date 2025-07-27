import click
from pathlib import Path
from typing import Dict, List
from okit.utils.log import console
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool


@okit_tool("minimal", "Minimal Example Tool")
class MinimalExample(BaseTool):
    """Minimal Example Tool - Demonstrates BaseTool's basic functionality"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

        # 工具特定的初始化
        self.example_data = {"message": "Hello from MinimalExample!"}

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
Minimal Example Tool - A comprehensive demonstration of BaseTool functionality.

This tool showcases various features of the BaseTool framework:
• Basic command structure and parameter handling
• Rich console output with colors and formatting
• Configuration validation
• Nested command groups
• File operations and data processing
• Error handling and logging

Use 'minimal-example --help' to see available commands.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Minimal example tool demonstrating BaseTool features"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""

        # 命令1: 显示信息
        @cli_group.command()
        @click.option("--name", "-n", default="World", help="要问候的名字")
        def hello(name: str) -> None:
            """Display greeting message"""
            try:
                self.logger.info(f"Executing hello command with parameter: name={name}")
                console.print(f"[green]Hello, {name}![/green]")
                console.print(f"[blue]From tool: {self.tool_name}[/blue]")
            except Exception as e:
                self.logger.error(f"hello command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        # 命令2: 显示工具信息
        @cli_group.command()
        def info() -> None:
            """Display tool information"""
            try:
                self.logger.info("Executing info command")
                info = self.get_tool_info()

                from rich.table import Table

                table = Table(title="Tool Information")
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")

                for key, value in info.items():
                    table.add_row(key, str(value))
                console.print(table)

            except Exception as e:
                self.logger.error(f"info command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        # 命令3: 测试配置验证
        @cli_group.command()
        def test_config() -> None:
            """Test configuration validation"""
            try:
                self.logger.info("Executing test_config command")
                is_valid = self.validate_config()

                if is_valid:
                    console.print("[green]Configuration validation passed![/green]")
                else:
                    console.print("[yellow]Configuration validation failed![/yellow]")

            except Exception as e:
                self.logger.error(f"test_config command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        # 命令4: 带参数的命令
        @cli_group.command()
        @click.argument("message", required=False, default="默认消息")
        @click.option("--repeat", "-r", type=int, default=1, help="重复次数")
        @click.option("--uppercase", "-u", is_flag=True, help="转换为大写")
        def echo(message: str, repeat: int, uppercase: bool) -> None:
            """Echo message"""
            try:
                self.logger.info(
                    f"Executing echo command with parameters: message={message}, repeat={repeat}, uppercase={uppercase}"
                )

                if uppercase:
                    message = message.upper()

                for i in range(repeat):
                    console.print(f"[cyan]{i+1}: {message}[/cyan]")

            except Exception as e:
                self.logger.error(f"echo command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        # 命令5: 子命令组示例
        @cli_group.group()
        def advanced() -> None:
            """Advanced functionality command group"""
            pass

        @advanced.command()
        @click.argument("file_path", type=click.Path(exists=True, path_type=Path))
        def read_file(file_path: Path) -> None:
            """Read file content"""
            try:
                self.logger.info(f"Executing read_file command, file: {file_path}")

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                console.print(f"[green]File {file_path} content:[/green]")
                console.print(f"[white]{content}[/white]")

            except Exception as e:
                self.logger.error(f"read_file command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @advanced.command()
        @click.argument("numbers", nargs=-1, type=int)
        def sum_numbers(numbers: tuple) -> None:
            """Calculate sum of numbers"""
            try:
                self.logger.info(f"Executing sum_numbers command, numbers: {numbers}")

                if not numbers:
                    console.print("[yellow]No numbers provided[/yellow]")
                    return

                total = sum(numbers)
                console.print(f"[green]Sum: {total}[/green]")
                console.print(f"[blue]Numbers: {numbers}[/blue]")

            except Exception as e:
                self.logger.error(f"sum_numbers command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

    def validate_config(self) -> bool:
        """Validate configuration"""
        # Simple configuration validation logic
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        if not self.example_data:
            self.logger.warning("Example data is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """Custom cleanup logic"""
        self.logger.info("Executing custom cleanup logic")
        # Tool-specific cleanup code can be added here
        pass
