"""Tests for tool decorator module."""

import os
import sys
import click
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import LazyCommand, LazyGroup, okit_tool


class MockTool(BaseTool):
    """Test tool class."""

    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            """Test command."""
            pass


class MockToolWithCallback(BaseTool):
    """Test tool class with callback."""

    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            """Test command."""
            pass

        @cli_group.callback()
        def callback():
            """Group callback."""
            pass


def test_lazy_command_basic():
    """Test basic LazyCommand functionality."""
    cmd = LazyCommand("test", MockTool, "Test tool", use_subcommands=False)

    # Test basic attributes
    assert cmd.name == "test"
    assert cmd.help == "Test tool"
    assert cmd.short_help == "Test tool"
    assert cmd.tool_class == MockTool
    assert cmd.tool_name == "test"
    assert cmd.tool_description == "Test tool"
    assert not cmd.use_subcommands
    # 对于简单命令模式，工具实例会在构造函数中创建以确保帮助信息正确显示
    assert cmd._tool_instance is not None
    assert cmd._real_command is not None


def test_lazy_command_ensure_real_command():
    """Test LazyCommand real command creation."""
    cmd = LazyCommand("test", MockTool, "Test tool", use_subcommands=False)

    # Test real command creation
    cmd._ensure_real_command()
    assert isinstance(cmd._tool_instance, MockTool)
    assert isinstance(cmd._real_command, click.Command)
    assert cmd._real_command.name == "test"


def test_lazy_command_invoke():
    """Test LazyCommand invoke."""
    cmd = LazyCommand("test", MockTool, "Test tool", use_subcommands=False)
    ctx = click.Context(cmd)

    # Mock real command invoke
    with patch.object(cmd, "_ensure_real_command") as mock_ensure:
        cmd._real_command = MagicMock()
        cmd.invoke(ctx)
        mock_ensure.assert_called_once()
        cmd._real_command.invoke.assert_called_once_with(ctx)


def test_lazy_command_get_help():
    """Test LazyCommand help text."""
    # Test simple command mode (use_subcommands=False)
    cmd = LazyCommand("test", MockTool, "Test tool", use_subcommands=False)
    ctx = click.Context(cmd)

    # Test help text - for simple commands, should return full help info
    help_text = cmd.get_help(ctx)
    assert "Usage:" in help_text
    assert "Test tool" in help_text
    assert "Options:" in help_text

    # Test default help text for simple commands
    cmd = LazyCommand("test", MockTool, "", use_subcommands=False)
    help_text = cmd.get_help(ctx)
    assert "Usage:" in help_text
    assert "test tool" in help_text
    assert "Options:" in help_text

    # Test complex command mode (use_subcommands=True)
    cmd = LazyCommand("test", MockTool, "Test tool", use_subcommands=True)
    ctx = click.Context(cmd)

    # Test help text - for complex commands, should return basic description
    help_text = cmd.get_help(ctx)
    assert help_text == "Test tool"

    # Test default help text for complex commands
    cmd = LazyCommand("test", MockTool, "", use_subcommands=True)
    help_text = cmd.get_help(ctx)
    assert help_text == "test tool"


def test_lazy_group_basic():
    """Test basic LazyGroup functionality."""
    group = LazyGroup("test", MockTool, "Test tool")

    # Test basic attributes
    assert group.name == "test"
    assert group.help == "Test tool"
    assert group.short_help == "Test tool"
    assert group.tool_class == MockTool
    assert group.tool_name == "test"
    assert group.tool_description == "Test tool"
    assert group._tool_instance is None
    assert group._real_group is None
    assert not group._commands_loaded


def test_lazy_group_ensure_real_group():
    """Test LazyGroup real group creation."""
    group = LazyGroup("test", MockTool, "Test tool")

    # Test real group creation
    group._ensure_real_group()
    assert isinstance(group._tool_instance, MockTool)
    assert isinstance(group._real_group, click.Group)
    assert group._real_group.name == "cli"


def test_lazy_group_load_commands():
    """Test LazyGroup command loading."""
    group = LazyGroup("test", MockTool, "Test tool")

    # Test command loading
    group._load_commands()
    assert group._commands_loaded
    assert "test" in group.commands


def test_lazy_group_invoke():
    """Test LazyGroup invoke."""
    group = LazyGroup("test", MockToolWithCallback, "Test tool")
    ctx = click.Context(group)

    # Mock real group invoke
    with patch.object(group, "_ensure_real_group") as mock_ensure:
        group.callback = MagicMock()
        group.invoke(ctx)
        mock_ensure.assert_called_once()
        group.callback.assert_called_once()


def test_lazy_group_get_command():
    """Test LazyGroup command retrieval."""
    group = LazyGroup("test", MockTool, "Test tool")
    ctx = click.Context(group)

    # Test command retrieval
    with patch.object(group, "_load_commands") as mock_load:
        group.get_command(ctx, "test")
        mock_load.assert_called_once()


def test_lazy_group_list_commands():
    """Test LazyGroup command listing."""
    group = LazyGroup("test", MockTool, "Test tool")
    ctx = click.Context(group)

    # Test command listing
    with patch.object(group, "_load_commands") as mock_load:
        group.list_commands(ctx)
        mock_load.assert_called_once()


def test_okit_tool_decorator():
    """Test okit_tool decorator."""

    # Test with subcommands
    @okit_tool("test", "Test tool")
    class TestToolWithDecorator(MockTool):
        pass

    assert TestToolWithDecorator.tool_name == "test"
    assert TestToolWithDecorator.description == "Test tool"
    assert TestToolWithDecorator.use_subcommands is True

    # Test without subcommands
    @okit_tool("test2", "Test tool 2", use_subcommands=False)
    class TestToolWithoutSubcommands(MockTool):
        pass

    assert TestToolWithoutSubcommands.tool_name == "test2"
    assert TestToolWithoutSubcommands.description == "Test tool 2"
    assert TestToolWithoutSubcommands.use_subcommands is False

    # Test CLI registration
    with patch("sys.modules") as mock_modules:
        mock_module = MagicMock()
        mock_modules.__getitem__.return_value = mock_module

        @okit_tool("test3", "Test tool 3")
        class TestToolWithCLI(MockTool):
            pass

        mock_modules.__getitem__.assert_called_with(TestToolWithCLI.__module__)
