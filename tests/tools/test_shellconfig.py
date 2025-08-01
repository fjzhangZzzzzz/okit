"""Tests for shellconfig tool."""

import os
import sys
import json
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import click
from click.testing import CliRunner

from okit.tools.shellconfig import ShellConfig


@pytest.fixture
def shell_tool():
    """Create a ShellConfig instance."""
    return ShellConfig("shellconfig", "Shell configuration management tool")


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_output():
    """Mock output module."""
    with patch("okit.tools.shellconfig.output") as mock_out:
        yield mock_out


@pytest.fixture
def mock_home(tmp_path):
    """Mock home directory."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_tool_initialization(shell_tool):
    """Test tool initialization."""
    assert shell_tool.tool_name == "shellconfig"
    assert shell_tool.description == "Shell configuration management tool"
    assert isinstance(shell_tool.create_cli_group(), click.Group)


def test_cli_help(shell_tool):
    """Test CLI help information."""
    assert "Shell Config Tool" in shell_tool._get_cli_help()
    assert "Shell configuration management tool" == shell_tool._get_cli_short_help()


def test_get_shell_info(shell_tool):
    """Test shell info retrieval."""
    # Test valid shell
    bash_info = shell_tool.get_shell_info("bash")
    assert bash_info["rc_file"] == ".bashrc"
    assert bash_info["comment_char"] == "#"
    assert bash_info["source_cmd"] == "source"
    
    # Test invalid shell
    with pytest.raises(ValueError, match="Unsupported shell: invalid"):
        shell_tool.get_shell_info("invalid")


def test_get_shell_config_dir(shell_tool, mock_home):
    """Test shell config directory path retrieval."""
    config_dir = shell_tool.get_shell_config_dir("bash")
    assert config_dir == mock_home / ".okit" / "data" / "shellconfig" / "bash"


def test_get_shell_config_file(shell_tool, mock_home):
    """Test shell config file path retrieval."""
    # Test regular shell
    bash_config = shell_tool.get_shell_config_file("bash")
    assert bash_config == mock_home / ".okit" / "data" / "shellconfig" / "bash" / "config"
    
    # Test PowerShell
    ps_config = shell_tool.get_shell_config_file("powershell")
    assert ps_config == mock_home / ".okit" / "data" / "shellconfig" / "powershell" / "config.ps1"


def test_ensure_shell_config_dir(shell_tool, mock_home):
    """Test shell config directory creation."""
    config_dir = shell_tool.ensure_shell_config_dir("bash")
    assert config_dir.exists()
    assert config_dir.is_dir()


def test_create_default_config(shell_tool):
    """Test default configuration creation."""
    # Test bash config
    bash_config = shell_tool.create_default_config("bash")
    assert "# Bash configuration" in bash_config
    assert "alias ll='ls -la'" in bash_config
    
    # Test PowerShell config
    ps_config = shell_tool.create_default_config("powershell")
    assert "# PowerShell configuration" in ps_config
    assert "Set-Alias -Name ll -Value Get-ChildItem" in ps_config


def test_show_source_commands(shell_tool, mock_output, mock_home):
    """Test source command display."""
    config_file = shell_tool.get_shell_config_file("bash")
    config_file.parent.mkdir(parents=True)
    config_file.touch()
    
    shell_tool.show_source_commands("bash")
    mock_output.result.assert_any_call("[bold]Source commands for bash:[/bold]")
    mock_output.result.assert_any_call(f"source {config_file}")


def test_setup_git_repo(shell_tool, mock_output, mock_home):
    """Test git repository setup."""
    with patch("git.Repo") as mock_repo:
        # Test setup without repo URL
        result = shell_tool.setup_git_repo()
        assert result is False
        mock_output.error.assert_called_with("Error: repo_url is required")
        
        # Test setup with repo URL
        repo_path = shell_tool.configs_repo_path
        if repo_path.exists():
            import shutil
            shutil.rmtree(repo_path)
            
        result = shell_tool.setup_git_repo("https://github.com/user/repo.git")
        assert result is True
        mock_output.success.assert_any_call("Git repository initialized")
        mock_output.success.assert_any_call("Added remote origin: https://github.com/user/repo.git")


def test_update_repo(shell_tool, mock_output):
    """Test git repository update."""
    with patch("git.Repo") as mock_repo:
        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        
        # Test successful update
        result = shell_tool.update_repo()
        assert result is True
        mock_output.result.assert_any_call("[green]Repository updated successfully[/green]")


def test_sync_config(shell_tool, mock_output, mock_home):
    """Test configuration synchronization."""
    with patch("git.Repo") as mock_repo:
        # Test sync with non-existent repo
        result = shell_tool.sync_config("bash")
        assert result is False
        mock_output.warning.assert_called_with("No configuration found in repository for bash")
        
        # Test sync with existing repo but no config
        repo_path = shell_tool.configs_repo_path
        repo_path.mkdir(parents=True, exist_ok=True)
        result = shell_tool.sync_config("bash")
        assert result is False
        mock_output.warning.assert_called_with("No configuration found in repository for bash")
        
        # Test sync with existing repo and config
        repo_config_path = shell_tool.get_repo_config_path("bash")
        repo_config_path.parent.mkdir(parents=True, exist_ok=True)
        repo_config_path.write_text("test config")
        result = shell_tool.sync_config("bash")
        assert result is True
        mock_output.info.assert_called_with("Creating new configuration for bash from repository")
        mock_output.success.assert_called_with("Configuration synced for bash")
        
        # Test sync with existing repo and config, but no changes
        result = shell_tool.sync_config("bash")
        assert result is True
        mock_output.warning.assert_called_with("Configuration for bash is already up to date")


def test_list_configs(shell_tool, mock_output, mock_home):
    """Test configuration listing."""
    # Create some test configs
    bash_config = shell_tool.get_shell_config_file("bash")
    bash_config.parent.mkdir(parents=True, exist_ok=True)
    bash_config.touch()
    
    # Create repo config
    repo_config = shell_tool.get_repo_config_path("bash")
    repo_config.parent.mkdir(parents=True, exist_ok=True)
    repo_config.touch()
    
    shell_tool.list_configs()
    mock_output.result.assert_any_call("[bold]Available configurations:[/bold]")
    mock_output.result.assert_any_call("  bash: local, repo")


def test_initialize_config_if_needed(shell_tool, mock_output, mock_home):
    """Test configuration initialization."""
    # Test new config creation with repo config
    repo_config = shell_tool.get_repo_config_path("bash")
    repo_config.parent.mkdir(parents=True, exist_ok=True)
    repo_config.write_text("test config")
    
    result = shell_tool.initialize_config_if_needed("bash")
    assert result is True
    mock_output.success.assert_called_with("Created configuration for bash from repository")
    
    # Test new config creation without repo config
    result = shell_tool.initialize_config_if_needed("zsh")
    assert result is True
    mock_output.success.assert_called_with("Created default configuration for zsh")
    
    # Test existing config
    result = shell_tool.initialize_config_if_needed("bash")
    assert result is True


def test_enable_config(shell_tool, mock_output, mock_home):
    """Test configuration enablement."""
    # Test bash config enablement
    result = shell_tool.enable_config("bash")
    assert result is True
    mock_output.success.assert_any_call("Configuration enabled for bash")


def test_disable_config(shell_tool, mock_output, mock_home):
    """Test configuration disablement."""
    # Create and enable config first
    shell_tool.enable_config("bash")
    
    # Test disablement
    result = shell_tool.disable_config("bash")
    assert result is True
    mock_output.success.assert_called_with("Configuration disabled for bash")


def test_check_config_status(shell_tool, mock_home):
    """Test configuration status check."""
    # Test disabled config
    assert not shell_tool.check_config_status("bash")
    
    # Enable config and test again
    shell_tool.enable_config("bash")
    assert shell_tool.check_config_status("bash")


def test_cli_config_command(shell_tool, cli_runner, mock_output):
    """Test config CLI command."""
    cli = shell_tool.create_cli_group()
    
    # Test config get
    with patch.object(shell_tool, "get_config_value", return_value="test_value"):
        result = cli_runner.invoke(cli, ["config", "get", "test_key"])
        assert result.exit_code == 0
        mock_output.result.assert_called_with("test_value")
    
    # Test config set
    result = cli_runner.invoke(cli, ["config", "set", "test_key", "test_value"])
    assert result.exit_code == 0
    mock_output.success.assert_called_with("Set test_key = test_value")


def test_cli_sync_command(shell_tool, cli_runner, mock_output):
    """Test sync CLI command."""
    cli = shell_tool.create_cli_group()
    
    with patch.object(shell_tool, "sync_config") as mock_sync:
        result = cli_runner.invoke(cli, ["sync", "bash"])
        assert result.exit_code == 0
        mock_sync.assert_called_with("bash")


def test_cli_source_command(shell_tool, cli_runner, mock_output):
    """Test source CLI command."""
    cli = shell_tool.create_cli_group()
    
    with patch.object(shell_tool, "show_source_commands") as mock_show:
        result = cli_runner.invoke(cli, ["source", "bash"])
        assert result.exit_code == 0
        mock_show.assert_called_with("bash")


def test_cli_enable_command(shell_tool, cli_runner, mock_output):
    """Test enable CLI command."""
    cli = shell_tool.create_cli_group()
    
    with patch.object(shell_tool, "enable_config") as mock_enable:
        result = cli_runner.invoke(cli, ["enable", "bash"])
        assert result.exit_code == 0
        mock_enable.assert_called_with("bash")


def test_cli_disable_command(shell_tool, cli_runner, mock_output):
    """Test disable CLI command."""
    cli = shell_tool.create_cli_group()
    
    with patch.object(shell_tool, "disable_config") as mock_disable:
        result = cli_runner.invoke(cli, ["disable", "bash"])
        assert result.exit_code == 0
        mock_disable.assert_called_with("bash")


def test_cli_status_command(shell_tool, cli_runner, mock_output):
    """Test status CLI command."""
    cli = shell_tool.create_cli_group()
    
    with patch.object(shell_tool, "check_config_status", return_value=True):
        result = cli_runner.invoke(cli, ["status", "bash"])
        assert result.exit_code == 0
        mock_output.success.assert_called_with("✓ Configuration is enabled for bash")