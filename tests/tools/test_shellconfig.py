"""Tests for shellconfig tool."""

import os
import platform
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import MagicMock, patch

import git
import pytest
from git import Repo

from okit.tools.shellconfig import ShellConfig


@pytest.fixture
def shell_config(temp_dir: Path) -> Generator[ShellConfig, None, None]:
    """Create a ShellConfig instance with temporary directories."""
    # Set up temporary environment
    os.environ["OKIT_CONFIG_DIR"] = str(temp_dir / "config")
    os.environ["OKIT_DATA_DIR"] = str(temp_dir / "data")

    tool = ShellConfig("shellconfig")
    yield tool

    # Clean up environment
    del os.environ["OKIT_CONFIG_DIR"]
    del os.environ["OKIT_DATA_DIR"]


@pytest.fixture
def test_repo(temp_dir: Path) -> Generator[Repo, None, None]:
    """Create a test Git repository with shell configurations."""
    repo_path = temp_dir / "test_repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)

    # Create test configurations
    for shell in ["bash", "zsh", "powershell"]:
        shell_dir = repo_path / shell
        shell_dir.mkdir()
        if shell == "powershell":
            config_file = shell_dir / "config.ps1"
        else:
            config_file = shell_dir / "config"
        config_file.write_text(f"# Test configuration for {shell}")

    # Create initial commit
    repo.index.add(["*"])
    repo.index.commit("Initial commit")

    yield repo


def test_shell_info(shell_config: ShellConfig) -> None:
    """Test getting shell information."""
    # Test valid shells
    for shell in ["bash", "zsh", "cmd", "powershell"]:
        info = shell_config.get_shell_info(shell)
        assert isinstance(info, dict)
        assert "comment_char" in info
        assert "source_cmd" in info

    # Test invalid shell
    with pytest.raises(ValueError):
        shell_config.get_shell_info("invalid_shell")


def test_shell_config_paths(shell_config: ShellConfig) -> None:
    """Test shell configuration path handling."""
    for shell in ["bash", "zsh", "cmd", "powershell"]:
        # Test config directory
        config_dir = shell_config.get_shell_config_dir(shell)
        assert isinstance(config_dir, Path)

        # Test config file
        config_file = shell_config.get_shell_config_file(shell)
        assert isinstance(config_file, Path)

        # Test repo config path
        repo_config = shell_config.get_repo_config_path(shell)
        assert isinstance(repo_config, Path)


def test_default_config_creation(shell_config: ShellConfig) -> None:
    """Test default configuration content creation."""
    for shell in ["bash", "zsh", "cmd", "powershell"]:
        config = shell_config.create_default_config(shell)
        assert isinstance(config, str)
        assert shell.title() in config
        assert shell_config.get_shell_info(shell)["comment_char"] in config


def test_git_repo_setup(shell_config: ShellConfig, test_repo: Repo) -> None:
    """Test Git repository setup and management."""
    repo_url = str(test_repo.working_dir)

    # Test setup with URL
    assert shell_config.setup_git_repo(repo_url)
    assert shell_config.configs_repo is not None
    assert shell_config.configs_repo_path.exists()

    # Test update
    assert shell_config.update_repo()


def test_config_sync(shell_config: ShellConfig, test_repo: Repo) -> None:
    """Test configuration synchronization."""
    # Setup repo
    shell_config.setup_git_repo(str(test_repo.working_dir))

    for shell in ["bash", "zsh", "powershell"]:
        # Test sync
        assert shell_config.sync_config(shell)

        # Verify synced files
        config_file = shell_config.get_shell_config_file(shell)
        assert config_file.exists()
        assert config_file.read_text() == f"# Test configuration for {shell}"


def test_config_enable_disable(shell_config: ShellConfig) -> None:
    """Test enabling and disabling configurations."""
    for shell in ["bash", "zsh", "powershell"]:
        if shell == "powershell" and platform.system() != "Windows":
            continue

        # Initialize config
        shell_config.initialize_config_if_needed(shell)

        # Test enable
        if rc_file := shell_config.get_rc_file_path(shell):
            rc_file.parent.mkdir(parents=True, exist_ok=True)
            rc_file.touch()

            # Enable config
            assert shell_config.enable_config(shell)
            assert shell_config.check_config_status(shell)

            # Disable config
            assert shell_config.disable_config(shell)
            assert not shell_config.check_config_status(shell)


def test_rc_file_handling(shell_config: ShellConfig) -> None:
    """Test RC file content manipulation."""
    test_content = [
        "# Existing content",
        "export PATH=/usr/local/bin:$PATH",
        "# okit shellconfig start",
        "source ~/.okit/data/bash/config",
        "# okit shellconfig end",
        "alias ll='ls -la'",
    ]

    # Test cleaning RC file content
    cleaned = shell_config._clean_rc_file_content(test_content)
    assert len(cleaned) == 3
    assert "# okit shellconfig start" not in cleaned
    assert "source ~/.okit/data/bash/config" not in cleaned
    assert "# okit shellconfig end" not in cleaned


def test_source_command_management(shell_config: ShellConfig) -> None:
    """Test source command management in RC files."""
    for shell in ["bash", "zsh", "powershell"]:
        # Get source line
        source_line = shell_config._get_source_line(shell)
        assert isinstance(source_line, str)
        assert shell_config.get_shell_info(shell)["source_cmd"] in source_line

        if rc_file := shell_config.get_rc_file_path(shell):
            # Create test RC file
            rc_file.parent.mkdir(parents=True, exist_ok=True)
            rc_file.write_text("# Test RC file\n")

            # Add source command
            assert shell_config._add_source_command_to_rc_file(rc_file, source_line)
            assert source_line in rc_file.read_text()

            # Remove source command
            assert shell_config._remove_source_command_from_rc_file(
                rc_file, source_line
            )
            assert source_line not in rc_file.read_text()


def test_file_comparison(shell_config: ShellConfig, temp_dir: Path) -> None:
    """Test file comparison functionality."""
    file1 = temp_dir / "file1"
    file2 = temp_dir / "file2"

    # Test identical files
    content = "test content"
    file1.write_text(content)
    file2.write_text(content)
    assert shell_config._files_are_identical(file1, file2)

    # Test different files
    file2.write_text("different content")
    assert not shell_config._files_are_identical(file1, file2)
