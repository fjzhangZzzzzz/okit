"""Tests for tool decorator module."""

import os
import sys
import click
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import LazyCommand, LazyGroup, okit_tool


class TestTool(BaseTool):
    """Test tool class."""
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            """Test command."""
            pass


class TestToolWithCallback(BaseTool):
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
    cmd = LazyCommand("test", TestTool, "Test tool", use_subcommands=False)
    
    # Test basic attributes
    assert cmd.name == "test"
    assert cmd.help == "Test tool"
    assert cmd.short_help == "Test tool"
    assert cmd.tool_class == TestTool
    assert cmd.tool_name == "test"
    assert cmd.tool_description == "Test tool"
    assert not cmd.use_subcommands
    assert cmd._tool_instance is None
    assert cmd._real_command is None


def test_lazy_command_ensure_real_command():
    """Test LazyCommand real command creation."""
    cmd = LazyCommand("test", TestTool, "Test tool", use_subcommands=False)
    
    # Test real command creation
    cmd._ensure_real_command()
    assert isinstance(cmd._tool_instance, TestTool)
    assert isinstance(cmd._real_command, click.Command)
    assert cmd._real_command.name == "test"


def test_lazy_command_invoke():
    """Test LazyCommand invoke."""
    cmd = LazyCommand("test", TestTool, "Test tool", use_subcommands=False)
    ctx = click.Context(cmd)
    
    # Mock real command invoke
    with patch.object(cmd, "_ensure_real_command") as mock_ensure:
        cmd._real_command = MagicMock()
        cmd.invoke(ctx)
        mock_ensure.assert_called_once()
        cmd._real_command.invoke.assert_called_once_with(ctx)


def test_lazy_command_get_help():
    """Test LazyCommand help text."""
    cmd = LazyCommand("test", TestTool, "Test tool", use_subcommands=False)
    ctx = click.Context(cmd)
    
    # Test help text
    assert cmd.get_help(ctx) == "Test tool"
    
    # Test default help text
    cmd = LazyCommand("test", TestTool, "", use_subcommands=False)
    assert cmd.get_help(ctx) == "test tool"


def test_lazy_group_basic():
    """Test basic LazyGroup functionality."""
    group = LazyGroup("test", TestTool, "Test tool")
    
    # Test basic attributes
    assert group.name == "test"
    assert group.help == "Test tool"
    assert group.short_help == "Test tool"
    assert group.tool_class == TestTool
    assert group.tool_name == "test"
    assert group.tool_description == "Test tool"
    assert group._tool_instance is None
    assert group._real_group is None
    assert not group._commands_loaded


def test_lazy_group_ensure_real_group():
    """Test LazyGroup real group creation."""
    group = LazyGroup("test", TestTool, "Test tool")
    
    # Test real group creation
    group._ensure_real_group()
    assert isinstance(group._tool_instance, TestTool)
    assert isinstance(group._real_group, click.Group)
    assert group._real_group.name == "cli"


def test_lazy_group_load_commands():
    """Test LazyGroup command loading."""
    group = LazyGroup("test", TestTool, "Test tool")
    
    # Test command loading
    group._load_commands()
    assert group._commands_loaded
    assert "test" in group.commands


def test_lazy_group_invoke():
    """Test LazyGroup invoke."""
    group = LazyGroup("test", TestToolWithCallback, "Test tool")
    ctx = click.Context(group)
    
    # Mock real group invoke
    with patch.object(group, "_ensure_real_group") as mock_ensure:
        group.callback = MagicMock()
        group.invoke(ctx)
        mock_ensure.assert_called_once()
        group.callback.assert_called_once()


def test_lazy_group_get_command():
    """Test LazyGroup command retrieval."""
    group = LazyGroup("test", TestTool, "Test tool")
    ctx = click.Context(group)
    
    # Test command retrieval
    with patch.object(group, "_load_commands") as mock_load:
        group.get_command(ctx, "test")
        mock_load.assert_called_once()


def test_lazy_group_list_commands():
    """Test LazyGroup command listing."""
    group = LazyGroup("test", TestTool, "Test tool")
    ctx = click.Context(group)
    
    # Test command listing
    with patch.object(group, "_load_commands") as mock_load:
        group.list_commands(ctx)
        mock_load.assert_called_once()


def test_okit_tool_decorator():
    """Test okit_tool decorator."""
    # Test with subcommands
    @okit_tool("test", "Test tool")
    class TestToolWithDecorator(TestTool):
        pass
    
    assert TestToolWithDecorator.tool_name == "test"
    assert TestToolWithDecorator.description == "Test tool"
    assert TestToolWithDecorator.use_subcommands is True
    
    # Test without subcommands
    @okit_tool("test2", "Test tool 2", use_subcommands=False)
    class TestToolWithoutSubcommands(TestTool):
        pass
    
    assert TestToolWithoutSubcommands.tool_name == "test2"
    assert TestToolWithoutSubcommands.description == "Test tool 2"
    assert TestToolWithoutSubcommands.use_subcommands is False
    
    # Test CLI registration
    with patch("sys.modules") as mock_modules:
        mock_module = MagicMock()
        mock_modules.__getitem__.return_value = mock_module
        
        @okit_tool("test3", "Test tool 3")
        class TestToolWithCLI(TestTool):
            pass
        
        mock_modules.__getitem__.assert_called_with(TestToolWithCLI.__module__)