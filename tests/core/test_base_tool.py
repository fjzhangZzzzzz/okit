"""Tests for base tool module."""

import os
import sys
import platform
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import click
from datetime import datetime

from okit.core.base_tool import BaseTool
from okit.utils.log import output


class MockBaseTool(BaseTool):
    """Mock base tool for testing."""

    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            pass


@pytest.fixture
def test_tool():
    """Create a test base tool instance."""
    return MockBaseTool("test_tool", "Test Tool")


@pytest.fixture
def test_home(tmp_path):
    """Create a temporary home directory."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_base_tool_init(test_tool):
    """Test base tool initialization."""
    assert test_tool.tool_name == "test_tool"
    assert test_tool.description == "Test Tool"
    assert test_tool._yaml is None
    assert isinstance(test_tool._start_time, datetime)


def test_base_tool_init_config_data(test_tool, test_home):
    """Test config and data directory initialization."""
    test_tool._init_config_data()

    # Check directories were created
    assert (test_home / ".okit").exists()
    assert (test_home / ".okit" / "config" / "test_tool").exists()
    assert (test_home / ".okit" / "data" / "test_tool").exists()


def test_base_tool_git_bash_detection(test_tool):
    """Test git bash environment detection."""
    # Test non-git bash environment
    with patch.dict(os.environ, {}, clear=True):
        assert not test_tool.is_git_bash()

    # Test git bash environment
    with patch.dict(
        os.environ,
        {
            "MSYSTEM": "MINGW64",
            "SHELL": "/usr/bin/bash",
            "HOME": "C:\\Users\\test",
            "OSTYPE": "msys",
        },
    ):
        assert test_tool.is_git_bash()


def test_base_tool_path_conversion(test_tool):
    """Test Windows path to git bash path conversion."""
    # Test Windows path
    with patch.object(test_tool, "_is_git_bash", return_value=True):
        path = Path("C:\\Users\\test\\file.txt")
        assert test_tool.convert_to_git_bash_path(path) == "/c/Users/test/file.txt"

    # Test non-Windows path
    with patch.object(test_tool, "_is_git_bash", return_value=True):
        path = Path("/usr/local/bin")
        assert test_tool.convert_to_git_bash_path(path) == "/usr/local/bin"

    # Test when not in git bash
    with patch.object(test_tool, "_is_git_bash", return_value=False):
        path = Path("C:\\Users\\test\\file.txt")
        assert test_tool.convert_to_git_bash_path(path) == str(path)


def test_base_tool_yaml_instance(test_tool):
    """Test YAML instance creation."""
    yaml = test_tool._get_yaml()
    assert yaml is not None
    assert yaml.preserve_quotes is True
    assert test_tool._yaml is yaml  # Test caching


def test_base_tool_config_management(test_tool, test_home):
    """Test configuration management."""
    # Test default config
    config = test_tool.load_config({"test": "value"})
    assert config == {"test": "value"}

    # Test saving and loading config
    test_tool.save_config({"key": "value"})
    config = test_tool.load_config()
    assert config == {"key": "value"}

    # Test nested config values
    test_tool.set_config_value("nested.key", "value")
    assert test_tool.get_config_value("nested.key") == "value"

    # Test config existence
    assert test_tool.has_config()


def test_base_tool_data_management(test_tool, test_home):
    """Test data management."""
    # Test data paths
    data_path = test_tool.get_data_path()
    assert data_path == test_home / ".okit" / "data" / "test_tool"

    # Test data file paths
    data_file = test_tool.get_data_file("test", "file.txt")
    assert data_file == data_path / "test" / "file.txt"

    # Test directory creation
    test_dir = test_tool.ensure_data_dir("test_dir")
    assert test_dir.exists()
    assert test_dir.is_dir()

    # Test file listing
    test_file = test_dir / "test.txt"
    test_file.write_text("test")
    files = test_tool.list_data_files("test_dir")
    assert test_file in files

    # Test cleanup
    assert test_tool.cleanup_data("test_dir")
    assert not test_dir.exists()


def test_base_tool_config_backup_restore(test_tool, test_home):
    """Test configuration backup and restore."""
    # Create initial config
    test_tool.save_config({"original": "value"})

    # Backup config
    backup_path = test_tool.backup_config()
    assert backup_path is not None
    assert backup_path.exists()

    # Modify config
    test_tool.save_config({"modified": "value"})

    # Restore config
    assert test_tool.restore_config(backup_path)
    config = test_tool.load_config()
    assert config == {"original": "value"}


def test_base_tool_cli_creation(test_tool):
    """Test CLI creation."""
    # Test with subcommands
    cli = test_tool.create_cli_group()
    assert isinstance(cli, click.Group)
    assert "test" in cli.commands

    # Test without subcommands
    test_tool.use_subcommands = False
    cli = test_tool.create_cli_group()
    assert isinstance(cli, click.Command)
    assert cli.name == "test_tool"


def test_base_tool_tool_info(test_tool):
    """Test tool information retrieval."""
    info = test_tool.get_tool_info()
    assert info["name"] == "test_tool"
    assert info["description"] == "Test Tool"
    assert "start_time" in info
    assert "config_path" in info
    assert "data_path" in info


def test_base_tool_cleanup(test_tool):
    """Test tool cleanup."""
    mock_cleanup = MagicMock()
    test_tool._cleanup_impl = mock_cleanup
    test_tool.cleanup()
    mock_cleanup.assert_called_once()


def test_base_tool_cli_help(test_tool):
    """Test CLI help text generation."""
    assert test_tool._get_cli_help() == "Test Tool"
    assert test_tool._get_cli_short_help() == "Test Tool"

    # Test without description
    test_tool.description = ""
    assert test_tool._get_cli_help() == "test_tool tool"
    assert test_tool._get_cli_short_help() == "test_tool"


def test_base_tool_error_handling(test_tool, test_home):
    """Test error handling in various operations."""
    # Test config loading errors
    config_file = test_tool.get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("invalid: yaml: content")

    with patch("builtins.open", side_effect=Exception("Test error")):
        config = test_tool.load_config({"default": "value"})
        assert config == {"default": "value"}

    # Test config saving errors
    with patch("builtins.open", side_effect=Exception("Test error")):
        assert not test_tool.save_config({"key": "value"})

    # Test data cleanup errors
    test_file = test_tool.get_data_file("test.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("test")

    with patch("pathlib.Path.unlink", side_effect=Exception("Test error")):
        assert not test_tool.cleanup_data("test.txt")

    # Test data listing errors
    with patch("pathlib.Path.iterdir", side_effect=Exception("Test error")):
        assert test_tool.list_data_files() == []

    # Test backup errors
    with patch("shutil.copy2", side_effect=Exception("Test error")):
        assert test_tool.backup_config() is None

    # Test restore errors
    with patch("shutil.copy2", side_effect=Exception("Test error")):
        assert not test_tool.restore_config(Path("backup.yaml"))
