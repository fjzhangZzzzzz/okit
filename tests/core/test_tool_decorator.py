"""Tests for tool decorator module."""

import os
import sys
import click
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import LazyGroup, okit_tool


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
    assert group._real_group.name == "test"


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

    # Mock both _ensure_real_group and _load_commands to avoid real tool instantiation
    with patch.object(group, "_ensure_real_group") as mock_ensure, \
         patch.object(group, "_load_commands") as mock_load:
        group.callback = MagicMock()
        # Mock super().invoke() to avoid Click's command validation
        with patch.object(click.Group, "invoke") as mock_super_invoke:
            group.invoke(ctx)
            mock_ensure.assert_called_once()
            mock_load.assert_called_once()
            mock_super_invoke.assert_called_once_with(ctx)


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


def test_okit_tool_decorator_with_subcommands():
    """Test okit_tool decorator with subcommands (uses LazyGroup)."""

    @okit_tool("test", "Test tool")
    class TestToolWithDecorator(MockTool):
        pass

    assert TestToolWithDecorator.tool_name == "test"
    assert TestToolWithDecorator.description == "Test tool"
    assert TestToolWithDecorator.use_subcommands is True


def test_okit_tool_decorator_without_subcommands():
    """Test okit_tool decorator without subcommands (creates Command directly)."""

    @okit_tool("test2", "Test tool 2", use_subcommands=False)
    class TestToolWithoutSubcommands(MockTool):
        pass

    assert TestToolWithoutSubcommands.tool_name == "test2"
    assert TestToolWithoutSubcommands.description == "Test tool 2"
    assert TestToolWithoutSubcommands.use_subcommands is False


def test_okit_tool_decorator_registers_cli():
    """Test that okit_tool sets a LazyGroup as 'cli' on the module for subcommands mode."""
    @okit_tool("test3", "Test tool 3")
    class TestToolWithCLI(MockTool):
        pass

    module = sys.modules[TestToolWithCLI.__module__]
    cli = getattr(module, "cli", None)
    assert cli is not None
    assert isinstance(cli, LazyGroup)
    assert cli.name == "test3"


def test_okit_tool_non_subcommand_creates_click_command():
    """Test that non-subcommand mode creates a click.Command directly."""

    @okit_tool("direct_tool", "Direct tool", use_subcommands=False)
    class DirectTool(MockTool):
        pass

    # The cli should be a click.Command (not LazyGroup)
    module = sys.modules[DirectTool.__module__]
    cli = getattr(module, "cli", None)
    assert cli is not None
    assert isinstance(cli, click.Command)
    assert cli.name == "direct_tool"


def test_lazy_group_empty_description():
    """Test LazyGroup with empty description falls back to '{name} tool'."""
    group = LazyGroup("mytool", MockTool, "")
    assert group.help == "mytool tool"
    assert group.short_help == "mytool tool"


def test_lazy_group_load_commands_idempotent():
    """Test that calling _load_commands twice does not duplicate commands."""
    group = LazyGroup("test", MockTool, "Test tool")
    group._load_commands()
    group._load_commands()  # second call should be a no-op
    assert list(group.commands.keys()).count("test") == 1
