"""Tests for CLI main module."""

import pytest
import click
from click.testing import CliRunner
from unittest.mock import patch

from okit.cli.main import main


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture(scope="module", autouse=True)
def _register_test_subcommand():
    """Register a no-op subcommand on main once for this module, clean up after."""
    @main.command('_test_dummy')
    def dummy():
        pass
    yield
    main.commands.pop('_test_dummy', None)


def test_version_command(cli_runner):
    """Test version command."""
    result = cli_runner.invoke(main, ['--version'])
    assert result.exit_code == 0
    assert result.output.startswith('v')
    import re
    version_pattern = r'^v\d+\.\d+\.\d+.*$'
    assert re.match(version_pattern, result.output.strip()), f"Version format invalid: {result.output.strip()}"


def test_log_level_option(cli_runner):
    """Test --log-level option routes correct level to output configuration."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        result = cli_runner.invoke(main, ['--log-level', 'DEBUG', '_test_dummy'])
        assert result.exit_code == 0
        mock_configure.assert_called_once_with('DEBUG')


def test_verbose_flag(cli_runner):
    """Test --verbose flag maps to DEBUG level."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        result = cli_runner.invoke(main, ['--verbose', '_test_dummy'])
        assert result.exit_code == 0
        mock_configure.assert_called_once_with('DEBUG')


def test_quiet_flag(cli_runner):
    """Test --quiet flag maps to QUIET level."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        result = cli_runner.invoke(main, ['--quiet', '_test_dummy'])
        assert result.exit_code == 0
        mock_configure.assert_called_once_with('QUIET')


def test_verbose_quiet_precedence(cli_runner):
    """Test that --verbose takes precedence over --quiet when both are given."""
    with patch('okit.cli.main._configure_output_level') as mock_configure:
        result = cli_runner.invoke(main, ['--verbose', '--quiet', '_test_dummy'])
        assert result.exit_code == 0
        mock_configure.assert_called_once_with('DEBUG')


def test_ctx_log_level(cli_runner):
    """Test that ctx.obj['log_level'] is set to the resolved level."""
    captured = {}

    @main.command('_test_ctx_log_level')
    @click.pass_context
    def capture(ctx):
        captured['log_level'] = ctx.obj.get('log_level')

    try:
        result = cli_runner.invoke(main, ['--log-level', 'WARNING', '_test_ctx_log_level'])
        assert result.exit_code == 0
        assert captured.get('log_level') == 'WARNING'
    finally:
        main.commands.pop('_test_ctx_log_level', None)


def test_completion_command_registration():
    """Test that the completion command is registered in the main group."""
    assert 'completion' in main.commands


def test_tool_registration():
    """Test that tools are registered in the main group at startup."""
    # _register_all_tools(main) is called at module import time
    assert len(main.commands) > 0


def test_invalid_log_level(cli_runner):
    """Test invalid log level."""
    result = cli_runner.invoke(main, ['--log-level', 'INVALID'])
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
