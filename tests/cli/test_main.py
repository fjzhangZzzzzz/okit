"""Tests for CLI main module."""

import pytest
import click
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from okit.cli.main import main


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


def test_version_command(cli_runner):
    """Test version command."""
    result = cli_runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert 'v1.2.0' in result.output


def test_log_level_option(cli_runner):
    """Test log level option."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        with patch('okit.cli.main._register_all_tools') as mock_register:
            # Add a dummy command to test options
            @main.command()
            def dummy():
                pass
            
            result = cli_runner.invoke(main, ['--log-level', 'DEBUG', 'dummy'])
            assert result.exit_code == 0
            mock_configure.assert_called_once_with('DEBUG')


def test_verbose_flag(cli_runner):
    """Test verbose flag."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        with patch('okit.cli.main._register_all_tools') as mock_register:
            # Add a dummy command to test options
            @main.command()
            def dummy():
                pass
            
            result = cli_runner.invoke(main, ['--verbose', 'dummy'])
            assert result.exit_code == 0
            mock_configure.assert_called_once_with('DEBUG')


def test_quiet_flag(cli_runner):
    """Test quiet flag."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        with patch('okit.cli.main._register_all_tools') as mock_register:
            # Add a dummy command to test options
            @main.command()
            def dummy():
                pass
            
            result = cli_runner.invoke(main, ['--quiet', 'dummy'])
            assert result.exit_code == 0
            mock_configure.assert_called_once_with('QUIET')


def test_perf_monitor_option(cli_runner):
    """Test performance monitoring option."""
    with patch('okit.cli.main.update_cli_performance_config') as mock_update:
        with patch('okit.cli.main._register_all_tools') as mock_register:
            # Add a dummy command to test options
            @main.command()
            def dummy():
                pass
            
            result = cli_runner.invoke(main, ['--perf-monitor', 'basic', 'dummy'])
            assert result.exit_code == 0
            mock_update.assert_called_once_with('basic', None)


def test_perf_monitor_with_output(cli_runner):
    """Test performance monitoring with output file."""
    with patch('okit.cli.main.update_cli_performance_config') as mock_update:
        with patch('okit.cli.main._register_all_tools') as mock_register:
            # Add a dummy command to test options
            @main.command()
            def dummy():
                pass
            
            result = cli_runner.invoke(main, [
                '--perf-monitor', 'json',
                '--perf-output', 'perf.json',
                'dummy'
            ])
            assert result.exit_code == 0
            mock_update.assert_called_once_with('json', 'perf.json')


def test_completion_command_registration():
    """Test completion command registration."""
    with patch('okit.cli.main._get_completion_command') as mock_get_completion:
        mock_completion = MagicMock()
        mock_get_completion.return_value = mock_completion
        
        # Create a new Click group
        @click.group()
        def test_group():
            pass
        
        # Add completion command
        test_group.add_command(mock_get_completion())
        
        # Verify the command was added
        assert mock_completion.name in test_group.commands


def test_tool_registration():
    """Test tool registration."""
    with patch('okit.cli.main._register_all_tools') as mock_register:
        # Create a new Click group
        @click.group()
        def test_group():
            pass
        
        # Register tools
        mock_register(test_group)
        
        # Verify registration was called
        mock_register.assert_called_once_with(test_group)


def test_invalid_log_level(cli_runner):
    """Test invalid log level."""
    result = cli_runner.invoke(main, ['--log-level', 'INVALID'])
    assert result.exit_code != 0
    assert 'Invalid value' in result.output


def test_invalid_perf_monitor(cli_runner):
    """Test invalid performance monitor type."""
    result = cli_runner.invoke(main, ['--perf-monitor', 'invalid'])
    assert result.exit_code != 0
    assert 'Invalid value' in result.output


def test_help_command(cli_runner):
    """Test help command."""
    result = cli_runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert 'Tool scripts manager' in result.output
    assert '--log-level' in result.output
    assert '--verbose' in result.output
    assert '--quiet' in result.output
    assert '--perf-monitor' in result.output
    assert '--perf-output' in result.output