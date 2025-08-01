"""Tests for minimal example tool."""

import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import click
from click.testing import CliRunner

from okit.tools.minimal_example import MinimalExample


@pytest.fixture
def minimal_tool():
    """Create a MinimalExample instance."""
    return MinimalExample("minimal", "Minimal Example Tool")


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_output():
    """Mock output module."""
    with patch("okit.tools.minimal_example.output") as mock_out:
        yield mock_out


def test_tool_initialization(minimal_tool):
    """Test tool initialization."""
    assert minimal_tool.tool_name == "minimal"
    assert minimal_tool.description == "Minimal Example Tool"
    assert isinstance(minimal_tool.create_cli_group(), click.Group)


def test_cli_help(minimal_tool):
    """Test CLI help information."""
    assert "Minimal Example Tool" in minimal_tool._get_cli_help()
    assert "Minimal example tool" == minimal_tool._get_cli_short_help()


def test_hello_command(minimal_tool, cli_runner, mock_output):
    """Test hello command."""
    cli = minimal_tool.create_cli_group()
    result = cli_runner.invoke(cli, ["hello"])
    
    assert result.exit_code == 0
    mock_output.success.assert_called_with("Hello from Minimal Example Tool!")
    
    # Verify tool info output
    mock_output.info.assert_called_with("Tool Information:")
    mock_output.result.assert_any_call("  Name: minimal")
    mock_output.result.assert_any_call("  Description: Minimal Example Tool")


def test_config_command_get(minimal_tool, cli_runner, mock_output):
    """Test config command - get value."""
    with patch.object(minimal_tool, "get_config_value", return_value="test_value"):
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["config", "--key", "test_key"])
        
        assert result.exit_code == 0
        mock_output.result.assert_called_with("test_key: test_value")


def test_config_command_get_not_found(minimal_tool, cli_runner, mock_output):
    """Test config command - get non-existent value."""
    with patch.object(minimal_tool, "get_config_value", return_value=None):
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["config", "--key", "test_key"])
        
        assert result.exit_code == 0
        mock_output.warning.assert_called_with("Configuration key 'test_key' not found")


def test_config_command_set(minimal_tool, cli_runner, mock_output):
    """Test config command - set value."""
    with patch.object(minimal_tool, "set_config_value") as mock_set:
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["config", "--key", "test_key", "--value", "test_value"])
        
        assert result.exit_code == 0
        mock_set.assert_called_with("test_key", "test_value")
        mock_output.success.assert_called_with("Set test_key = test_value")


def test_status_command_with_config(minimal_tool, cli_runner, mock_output):
    """Test status command with configuration."""
    config_data = {"key1": "value1", "key2": "value2"}
    with patch.object(minimal_tool, "load_config", return_value=config_data):
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["status"])
        
        assert result.exit_code == 0
        mock_output.info.assert_any_call("Tool Status:")
        mock_output.info.assert_any_call("Configuration:")
        mock_output.result.assert_any_call("  key1: value1")
        mock_output.result.assert_any_call("  key2: value2")


def test_status_command_no_config(minimal_tool, cli_runner, mock_output):
    """Test status command without configuration."""
    with patch.object(minimal_tool, "load_config", return_value={}):
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["status"])
        
        assert result.exit_code == 0
        mock_output.warning.assert_called_with("No configuration found")


def test_test_command_basic(minimal_tool, cli_runner, mock_output):
    """Test test command - basic usage."""
    with patch("time.sleep"):  # Mock sleep to speed up test
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["test", "--count", "1"])
        
        assert result.exit_code == 0
        mock_output.info.assert_called_with("Running test with 1 iterations")
        mock_output.success.assert_any_call("Completed item 1")
        mock_output.success.assert_called_with("Test completed successfully!")
        mock_output.result.assert_called_with("Total items processed: 1")


def test_test_command_with_progress(minimal_tool, cli_runner, mock_output):
    """Test test command with progress output."""
    with patch("time.sleep"):  # Mock sleep to speed up test
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["test", "--count", "2", "--with-progress"])
        
        assert result.exit_code == 0
        mock_output.progress.assert_any_call("Processing item 1/2")
        mock_output.progress.assert_any_call("Processing item 2/2")


def test_test_command_output_types(minimal_tool, cli_runner, mock_output):
    """Test test command - different output types."""
    with patch("time.sleep"):  # Mock sleep to speed up test
        cli = minimal_tool.create_cli_group()
        result = cli_runner.invoke(cli, ["test", "--count", "6"])
        
        assert result.exit_code == 0
        # Item 1 (i=0): success
        mock_output.success.assert_any_call("Completed item 1")
        # Item 4 (i=3): warning
        mock_output.warning.assert_any_call("Warning for item 4")
        # Item 5 (i=4): debug
        mock_output.debug.assert_any_call("Processed item 5", category="processing")
        # Item 6 (i=5): success
        mock_output.success.assert_any_call("Completed item 6")


def test_cleanup(minimal_tool, mock_output):
    """Test cleanup implementation."""
    minimal_tool.cleanup()
    mock_output.debug.assert_called_with("Executing custom cleanup logic")
    mock_output.info.assert_called_with("Minimal Example Tool cleanup completed")