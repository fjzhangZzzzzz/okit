"""Tests for minimal_example tool."""

import json
import os
from pathlib import Path
from typing import Generator

import pytest

from okit.tools.minimal_example import MinimalExample


@pytest.fixture
def minimal_tool(temp_dir: Path) -> Generator[MinimalExample, None, None]:
    """Create a minimal example tool instance with temporary directories."""
    # Set up temporary config and data directories
    os.environ["OKIT_CONFIG_DIR"] = str(temp_dir / "config")
    os.environ["OKIT_DATA_DIR"] = str(temp_dir / "data")

    tool = MinimalExample("minimal")
    yield tool

    # Clean up environment variables
    del os.environ["OKIT_CONFIG_DIR"]
    del os.environ["OKIT_DATA_DIR"]


def test_tool_initialization(minimal_tool: MinimalExample) -> None:
    """Test tool initialization and basic properties."""
    tool_info = minimal_tool.get_tool_info()
    assert tool_info["name"] == "minimal"
    assert tool_info["description"] == "Minimal Example Tool"
    assert "config_path" in tool_info
    assert "data_path" in tool_info


def test_config_management(minimal_tool: MinimalExample) -> None:
    """Test configuration management functions."""
    # Test setting and getting config values
    minimal_tool.set_config_value("test_key", "test_value")
    assert minimal_tool.get_config_value("test_key") == "test_value"

    # Test non-existent key
    assert minimal_tool.get_config_value("non_existent") is None

    # Test loading entire config
    config = minimal_tool.load_config()
    assert isinstance(config, dict)
    assert config.get("test_key") == "test_value"

    # Test overwriting value
    minimal_tool.set_config_value("test_key", "new_value")
    assert minimal_tool.get_config_value("test_key") == "new_value"


def test_directory_management(minimal_tool: MinimalExample) -> None:
    """Test directory management and path handling."""
    config_path = minimal_tool.get_config_path()
    data_path = minimal_tool.get_data_path()

    # Check that paths are created
    assert config_path.exists()
    assert config_path.is_dir()
    assert data_path.exists()
    assert data_path.is_dir()

    # Check config file creation
    config_file = config_path / "config.json"
    minimal_tool.set_config_value("test", "value")
    assert config_file.exists()
    assert config_file.is_file()

    # Verify config file content
    with open(config_file, "r") as f:
        config_data = json.load(f)
    assert isinstance(config_data, dict)
    assert "test" in config_data
    assert config_data["test"] == "value"


def test_help_messages(minimal_tool: MinimalExample) -> None:
    """Test help message generation."""
    assert minimal_tool._get_cli_help().strip() != ""
    assert minimal_tool._get_cli_short_help().strip() != ""
    assert "Minimal Example Tool" in minimal_tool._get_cli_help()


def test_cleanup(minimal_tool: MinimalExample) -> None:
    """Test cleanup functionality."""
    # Create some test data
    minimal_tool.set_config_value("test", "value")

    # Run cleanup
    minimal_tool.cleanup()

    # Config should still exist after cleanup
    assert minimal_tool.get_config_value("test") == "value"


def test_tool_with_empty_description() -> None:
    """Test tool initialization with empty description."""
    tool = MinimalExample("minimal", "")
    tool_info = tool.get_tool_info()
    assert tool_info["name"] == "minimal"
    assert tool_info["description"] == ""
    assert tool._get_cli_short_help() == "Minimal example tool"
