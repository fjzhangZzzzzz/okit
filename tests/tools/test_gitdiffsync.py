"""Tests for gitdiffsync tool."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, mock_open
import pytest
from click.testing import CliRunner

from okit.tools.gitdiffsync import (
    GitDiffSync,
    check_git_repo,
    get_git_changes,
    check_rsync_available,
    verify_directory_structure,
    ensure_remote_dir,
    sync_via_rsync,
    sync_via_sftp,
    fix_target_root_path,
    SyncError,
)


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """Create a temporary Git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir)

    try:
        # Initialize git repository
        subprocess.run(["git", "init"], cwd=repo_path, check=True)

        # Create some test files
        (repo_path / "test1.txt").write_text("test content 1")
        (repo_path / "test2.txt").write_text("test content 2")
        (repo_path / "subdir").mkdir(exist_ok=True)
        (repo_path / "subdir" / "test3.txt").write_text("test content 3")

        # Add and commit files
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"], cwd=repo_path, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True
        )

        yield repo_path
    finally:
        # Force cleanup with ignore_errors to handle Windows file handle issues
        try:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            # Ignore any cleanup errors on Windows
            pass


@pytest.fixture
def git_diff_sync() -> GitDiffSync:
    """Create a GitDiffSync instance."""
    return GitDiffSync("gitdiffsync")


def test_check_git_repo_valid(temp_git_repo: Path) -> None:
    """Test checking a valid Git repository."""
    assert check_git_repo(str(temp_git_repo))


def test_check_git_repo_invalid(temp_dir: Path) -> None:
    """Test checking an invalid Git repository."""
    assert not check_git_repo(str(temp_dir))


def test_check_git_repo_nonexistent() -> None:
    """Test checking a non-existent directory."""
    with pytest.raises(SystemExit):
        check_git_repo("/nonexistent/path")


def test_get_git_changes(temp_git_repo: Path) -> None:
    """Test getting Git changes."""
    # Create a new file to trigger changes
    (temp_git_repo / "new_file.txt").write_text("new content")

    changes = get_git_changes(str(temp_git_repo))
    assert "new_file.txt" in changes


def test_get_git_changes_with_cursor_files(temp_git_repo: Path) -> None:
    """Test getting Git changes with .cursor files (should be filtered out)."""
    # Create .cursor directory first
    (temp_git_repo / ".cursor").mkdir(exist_ok=True)
    # Create .cursor files
    (temp_git_repo / ".cursor" / "settings.json").write_text("{}")

    changes = get_git_changes(str(temp_git_repo))
    # .cursor files should be filtered out
    assert not any(".cursor" in change for change in changes)


@patch("subprocess.run")
def test_check_rsync_available(mock_run: MagicMock) -> None:
    """Test checking if rsync is available."""
    # Test when rsync is available
    mock_run.return_value.returncode = 0
    assert check_rsync_available()

    # Test when rsync is not available
    mock_run.side_effect = FileNotFoundError()
    assert not check_rsync_available()


def test_verify_directory_structure() -> None:
    """Test directory structure verification."""
    mock_ssh = MagicMock()
    mock_stdin = MagicMock()
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()
    mock_channel = MagicMock()

    # Mock SSH exec_command
    mock_ssh.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
    mock_stdout.channel = mock_channel
    mock_channel.recv_exit_status.return_value = 0

    result = verify_directory_structure(["test_dir"], "/remote/root", mock_ssh)
    assert result


def test_ensure_remote_dir() -> None:
    """Test ensuring remote directory exists."""
    mock_sftp = MagicMock()

    # Test when directory doesn't exist
    mock_sftp.stat.side_effect = FileNotFoundError()

    ensure_remote_dir(mock_sftp, "/remote/test/dir")
    mock_sftp.mkdir.assert_called()


@patch("subprocess.run")
def test_sync_via_rsync(mock_run: MagicMock) -> None:
    """Test syncing via rsync."""
    mock_run.return_value.returncode = 0

    sync_via_rsync("/source", ["file1.txt", "file2.txt"], "/target", False)
    mock_run.assert_called()

    # Test dry run
    sync_via_rsync("/source", ["file1.txt"], "/target", True)
    # Should still call rsync but with --dry-run flag


@patch("os.path.exists")
def test_sync_via_sftp(mock_exists: MagicMock) -> None:
    """Test syncing via SFTP."""
    mock_sftp = MagicMock()
    mock_sftp.stat.return_value = MagicMock()
    mock_exists.return_value = True

    files = ["file1.txt", "subdir/file2.txt"]

    sync_via_sftp("/source", files, mock_sftp, "/target", False)
    # Verify SFTP operations were called
    assert mock_sftp.put.called or mock_sftp.mkdir.called


def test_fix_target_root_path() -> None:
    """Test fixing target root path."""
    # Test Git Bash path conversion
    result = fix_target_root_path("/c/Program Files/Git/usr/bin")
    assert result == "/usr/bin"

    # Test normal path
    result = fix_target_root_path("/normal/path")
    assert result == "/normal/path"


def test_git_diff_sync_initialization(git_diff_sync: GitDiffSync) -> None:
    """Test GitDiffSync initialization."""
    assert git_diff_sync.tool_name == "gitdiffsync"


def test_git_diff_sync_cli_help(git_diff_sync: GitDiffSync) -> None:
    """Test CLI help generation."""
    help_text = git_diff_sync._get_cli_help()
    assert "Git Diff Sync Tool" in help_text

    short_help = git_diff_sync._get_cli_short_help()
    assert "Synchronize Git project folders" in short_help


def test_git_diff_sync_cli_interface() -> None:
    """Test command line interface."""
    runner = CliRunner()

    # Create tool instance and test CLI
    tool = GitDiffSync("gitdiffsync")
    cli = tool.create_cli_group()

    # Test help command
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Git Diff Sync Tool" in result.output

    # Test that options are properly displayed
    assert "main" in result.output

    # Test command help
    result = runner.invoke(cli, ["main", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--user" in result.output
    assert "--target-root" in result.output
    assert "--dry-run" in result.output
    assert "--max-depth" in result.output
    assert "--recursive" in result.output

    # Test that option descriptions are shown
    assert "Source directories to sync" in result.output
    assert "Target host address" in result.output
    assert "SSH port number" in result.output
    assert "SSH username" in result.output
    assert "Target root directory on remote server" in result.output
    assert "Show what would be transferred" in result.output
    assert "Maximum recursion depth" in result.output
    assert "Enable or disable recursive directory sync" in result.output


@patch("okit.tools.gitdiffsync.check_git_repo")
@patch("okit.tools.gitdiffsync.get_git_changes")
@patch("okit.tools.gitdiffsync.verify_directory_structure")
def test_git_diff_sync_execute_sync(
    mock_verify_dir: MagicMock,
    mock_get_changes: MagicMock,
    mock_check_repo: MagicMock,
    git_diff_sync: GitDiffSync,
) -> None:
    """Test sync execution."""
    mock_check_repo.return_value = True
    mock_get_changes.return_value = ["file1.txt", "file2.txt"]
    mock_verify_dir.return_value = True

    # Mock SSH connection
    with patch("paramiko.SSHClient") as mock_ssh_client:
        mock_ssh = MagicMock()
        mock_ssh_client.return_value = mock_ssh

        git_diff_sync._execute_sync(
            ["/test/repo"],
            "localhost",
            22,
            "testuser",
            "/remote/target",
            False,
            5,
            True,
        )

        mock_check_repo.assert_called()
        mock_get_changes.assert_called()


def test_git_diff_sync_cleanup(git_diff_sync: GitDiffSync) -> None:
    """Test cleanup implementation."""
    # Since cleanup is a no-op in current implementation,
    # we just verify it doesn't raise any exceptions
    git_diff_sync._cleanup_impl()


def test_sync_error_exception() -> None:
    """Test SyncError exception."""
    error = SyncError("Test sync error")
    assert str(error) == "Test sync error"


@patch("subprocess.run")
def test_sync_via_rsync_error_handling(mock_run: MagicMock) -> None:
    """Test rsync error handling."""
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = b"rsync error"

    with pytest.raises(SyncError):
        sync_via_rsync("/source", ["file1.txt"], "/target", False)


def test_sync_via_sftp_error_handling() -> None:
    """Test SFTP error handling."""
    mock_sftp = MagicMock()
    mock_sftp.stat.side_effect = Exception("SFTP error")

    # Should handle exceptions gracefully
    sync_via_sftp("/source", ["file1.txt"], mock_sftp, "/target", False)


def test_verify_directory_structure_error() -> None:
    """Test directory structure verification with errors."""
    mock_ssh = MagicMock()
    mock_sftp = MagicMock()
    mock_ssh.open_sftp.return_value = mock_sftp

    # Mock SFTP error
    mock_sftp.stat.side_effect = Exception("SFTP error")

    result = verify_directory_structure(["test_dir"], "/remote/root", mock_ssh)
    assert not result


def test_ensure_remote_dir_error() -> None:
    """Test ensuring remote directory with errors."""
    mock_sftp = MagicMock()
    mock_sftp.stat.side_effect = FileNotFoundError()
    mock_sftp.mkdir.side_effect = Exception("Permission denied")

    # Should handle exceptions gracefully
    with pytest.raises(Exception):
        ensure_remote_dir(mock_sftp, "/remote/test/dir")


def test_get_git_changes_error(temp_git_repo: Path) -> None:
    """Test getting Git changes with errors."""
    # Test with invalid repository path
    with pytest.raises(SyncError):
        get_git_changes("/invalid/repo/path")


def test_fix_target_root_path_edge_cases() -> None:
    """Test fixing target root path with edge cases."""
    # Test empty path
    result = fix_target_root_path("")
    assert result == ""

    # Test None path
    with pytest.raises(TypeError):
        fix_target_root_path(None)

    # Test path with spaces
    result = fix_target_root_path("/c/Program Files (x86)/Git")
    assert "Program Files (x86)" in result


def test_git_diff_sync_with_multiple_source_dirs() -> None:
    """Test sync with multiple source directories."""
    git_diff_sync = GitDiffSync("gitdiffsync")

    with patch("okit.tools.gitdiffsync.check_git_repo") as mock_check_repo:
        with patch("okit.tools.gitdiffsync.get_git_changes") as mock_get_changes:
            with patch(
                "okit.tools.gitdiffsync.verify_directory_structure"
            ) as mock_verify_dir:
                mock_check_repo.return_value = True
                mock_get_changes.return_value = ["file1.txt"]
                mock_verify_dir.return_value = True

                with patch("paramiko.SSHClient") as mock_ssh_client:
                    mock_ssh = MagicMock()
                    mock_ssh_client.return_value = mock_ssh

                    git_diff_sync._execute_sync(
                        ["/repo1", "/repo2"],
                        "localhost",
                        22,
                        "testuser",
                        "/remote/target",
                        False,
                        5,
                        True,
                    )

                    # Should be called for each source directory
                    assert mock_check_repo.call_count == 2
                    assert mock_get_changes.call_count == 2
