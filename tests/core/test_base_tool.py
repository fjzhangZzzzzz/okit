"""Tests for base tool module."""

import os
import sys
import platform
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import click

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


def test_base_tool_init_config_data(test_tool, test_home):
    """Test config and data directory initialization."""
    test_tool._init_config_data()

    # Check directories were created
    assert (test_home / ".okit").exists()
    assert (test_home / ".okit" / "config" / "test_tool").exists()
    assert (test_home / ".okit" / "data" / "test_tool").exists()


def test_base_tool_git_bash_detection(test_tool):
    """Test git bash environment detection."""
    # No MSYSTEM → False
    with patch.dict(os.environ, {}, clear=True):
        assert not test_tool.is_git_bash()

    # MSYSTEM not in allowed set → False
    with patch.dict(os.environ, {"MSYSTEM": "CYGWIN"}, clear=True):
        assert not test_tool.is_git_bash()

    # MSYSTEM valid, SHELL set but not ending with "bash" → False (blocked at condition 2)
    with patch.dict(os.environ, {"MSYSTEM": "MINGW64", "SHELL": "/usr/bin/zsh"}, clear=True):
        assert not test_tool.is_git_bash()

    # MSYSTEM valid, SHELL is bash, HOME has Windows-style path → True (condition 3)
    with patch.dict(
        os.environ,
        {"MSYSTEM": "MINGW64", "SHELL": "/usr/bin/bash", "HOME": "C:\\Users\\test"},
        clear=True,
    ):
        assert test_tool.is_git_bash()

    # MSYSTEM valid, SHELL is bash, HOME is Unix-style, OSTYPE starts with "msys" → True (condition 4)
    with patch.dict(
        os.environ,
        {"MSYSTEM": "MINGW64", "SHELL": "/usr/bin/bash", "HOME": "/home/user", "OSTYPE": "msys"},
        clear=True,
    ):
        assert test_tool.is_git_bash()

    # MSYSTEM valid, SHELL is bash, HOME is Unix-style, OSTYPE does not start with "msys" → False (fall-through)
    with patch.dict(
        os.environ,
        {"MSYSTEM": "MINGW64", "SHELL": "/usr/bin/bash", "HOME": "/home/user", "OSTYPE": "linux-gnu"},
        clear=True,
    ):
        assert not test_tool.is_git_bash()


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


def test_base_tool_cli_help(test_tool):
    """Test CLI help text generation."""
    assert test_tool._get_cli_help() == "Test Tool"
    assert test_tool._get_cli_short_help() == "Test Tool"

    # Test without description
    test_tool.description = ""
    assert test_tool._get_cli_help() == "test_tool tool"
    assert test_tool._get_cli_short_help() == "test_tool"


def test_base_tool_path_conversion_relative(test_tool):
    """Test that a relative path with backslashes is converted to forward slashes."""
    with patch.object(test_tool, "_is_git_bash", return_value=True):
        # Relative path: no drive letter, not Unix-absolute → hits the else branch
        result = test_tool.convert_to_git_bash_path(Path("subdir\\nested\\file.txt"))
        assert "\\" not in result
        assert "subdir" in result


def test_base_tool_load_config_empty_file(test_tool, test_home):
    """Test that an empty YAML file causes load_config to return the default config."""
    config_file = test_tool.get_config_file()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("")  # empty file — YAML loads as None

    result = test_tool.load_config({"default_key": "default_value"})
    assert result == {"default_key": "default_value"}


def test_base_tool_set_config_value_overwrites_scalar(test_tool, test_home):
    """Test that set_config_value silently overwrites a non-dict intermediate key."""
    test_tool.save_config({"level": "a_string_value"})
    # "level" is a scalar; setting "level.nested" overwrites it with a dict
    assert test_tool.set_config_value("level.nested", "new_value")
    assert test_tool.get_config_value("level.nested") == "new_value"


def test_base_tool_create_cli_group_noop_fallback(test_home):
    """Test create_cli_group returns a noop command when no commands are registered."""
    class EmptyTool(BaseTool):
        def _add_cli_commands(self, cli_group):
            pass  # registers nothing

    tool = EmptyTool("empty_tool", "Empty Tool")
    tool.use_subcommands = False
    cli = tool.create_cli_group()
    assert isinstance(cli, click.Command)
    assert cli.name == "empty_tool"
    assert cli.help == "Empty Tool"


def test_base_tool_create_cli_group_tool_name_override(test_tool):
    """Test create_cli_group respects explicit tool_name override."""
    test_tool.use_subcommands = True
    cli = test_tool.create_cli_group(tool_name="overridden_name")
    assert cli.name == "overridden_name"


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

    # Test backup errors
    with patch("shutil.copy2", side_effect=Exception("Test error")):
        assert test_tool.backup_config() is None

    # Test restore errors
    with patch("shutil.copy2", side_effect=Exception("Test error")):
        assert not test_tool.restore_config(Path("backup.yaml"))
