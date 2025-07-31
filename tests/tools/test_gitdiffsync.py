"""Tests for gitdiffsync tool."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, List, cast

import git
import paramiko
import pytest
from git import Repo
from paramiko.sftp_client import SFTPClient

from okit.tools.gitdiffsync import (
    GitDiffSync,
    check_git_repo,
    check_rsync_available,
    ensure_remote_dir,
    fix_target_root_path,
    get_git_changes,
    sync_via_rsync,
    sync_via_sftp,
    verify_directory_structure,
)
from tests.conftest import TestSSHServer


# 基本测试：不依赖特定环境的测试
@pytest.mark.unit
class TestBasicFunctionality:
    """Basic functionality tests that don't require special environment."""

    @pytest.fixture
    def test_git_repo(self, temp_dir: Path) -> Generator[Repo, None, None]:
        """Create a test Git repository with some changes."""
        repo_path = temp_dir / "test_repo"
        repo_path.mkdir()
        repo = git.Repo.init(repo_path)

        # Create initial files and commit
        (repo_path / "test1.txt").write_text("initial content")
        (repo_path / "test2.txt").write_text("initial content")
        repo.index.add(["test1.txt", "test2.txt"])
        repo.index.commit("Initial commit")

        # Create some changes
        (repo_path / "test1.txt").write_text("modified content")  # Modified
        (repo_path / "test3.txt").write_text("new file")  # Untracked
        (repo_path / "test2.txt").unlink()  # Deleted

        try:
            yield repo
        finally:
            repo.close()

    def test_check_git_repo(self, test_git_repo: Repo) -> None:
        """Test Git repository validation."""
        assert check_git_repo(str(test_git_repo.working_dir))
        assert not check_git_repo(str(Path(test_git_repo.working_dir).parent))

    def test_get_git_changes(self, test_git_repo: Repo) -> None:
        """Test getting Git changes."""
        changes = get_git_changes(str(test_git_repo.working_dir))
        assert len(changes) == 3
        assert "test1.txt" in changes  # Modified
        assert "test2.txt" in changes  # Deleted
        assert "test3.txt" in changes  # Untracked

    def test_check_rsync_available(self) -> None:
        """Test rsync availability check."""
        is_available = check_rsync_available()
        assert isinstance(is_available, bool)

    def test_fix_target_root_path(self) -> None:
        """Test target root path fixing."""
        test_cases = [
            ("/c/Program Files/Git/tmp/test", "/tmp/test"),
            ("C:/Program Files/Git/tmp/test", "/tmp/test"),
            ("/tmp/test", "/tmp/test"),
            ("C:/Users/test", "C:/Users/test"),
        ]
        for input_path, expected in test_cases:
            assert fix_target_root_path(input_path) == expected


# 集成测试：需要特定环境支持的测试
@pytest.mark.integration
@pytest.mark.skipif(os.name == "nt", reason="SSH tests not supported on Windows")
class TestSSHIntegration:
    """Integration tests that require SSH server."""

    def test_verify_directory_structure(
        self, ssh_server: TestSSHServer, temp_dir: Path
    ) -> None:
        """Test remote directory structure verification."""
        # Setup SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            ssh_server.host, port=ssh_server.port, username="test", password="test"
        )

        try:
            # Create test directories
            source_dirs = [str(temp_dir / "dir1"), str(temp_dir / "dir2")]
            remote_root = "/tmp/test"

            # Test with non-existent directories
            assert not verify_directory_structure(source_dirs, remote_root, client)

            # Create directories and test again
            client.exec_command(f"mkdir -p {remote_root}/dir1")
            client.exec_command(f"mkdir -p {remote_root}/dir2")
            assert verify_directory_structure(source_dirs, remote_root, client)
        finally:
            client.close()

    def test_ensure_remote_dir(self, ssh_server: TestSSHServer) -> None:
        """Test remote directory creation."""
        # Setup SFTP client
        transport = paramiko.Transport((ssh_server.host, ssh_server.port))
        transport.connect(username="test", password="test")
        sftp = cast(SFTPClient, paramiko.SFTPClient.from_transport(transport))

        try:
            # Test creating new directory
            remote_dir = "/tmp/test_dir"
            ensure_remote_dir(sftp, remote_dir)

            # Verify directory exists
            sftp.stat(remote_dir)

            # Test with existing directory (should not raise)
            ensure_remote_dir(sftp, remote_dir)
        finally:
            sftp.close()
            transport.close()

    def test_sync_via_sftp(self, ssh_server: TestSSHServer, test_repo: Repo) -> None:
        """Test SFTP synchronization."""
        # Setup SFTP client
        transport = paramiko.Transport((ssh_server.host, ssh_server.port))
        transport.connect(username="test", password="test")
        sftp = cast(SFTPClient, paramiko.SFTPClient.from_transport(transport))

        try:
            source_dir = str(test_repo.working_dir)
            target_root = "/tmp/test_sftp"
            files = ["test1.txt", "test2.txt"]

            # Test dry run
            sync_via_sftp(source_dir, files, sftp, target_root, dry_run=True)

            # Test actual sync
            sync_via_sftp(source_dir, files, sftp, target_root, dry_run=False)

            # Verify files were synced
            for file in files:
                try:
                    sftp.stat(f"{target_root}/{file}")
                except IOError:
                    pytest.fail(f"File {file} was not synced")
        finally:
            sftp.close()
            transport.close()

    def test_gitdiffsync_tool(self, ssh_server: TestSSHServer, test_repo: Repo) -> None:
        """Test GitDiffSync tool end-to-end."""
        tool = GitDiffSync("gitdiffsync")
        source_dirs = [str(test_repo.working_dir)]

        # Test with dry run
        tool._execute_sync(
            source_dirs=source_dirs,
            host=ssh_server.host,
            port=ssh_server.port,
            user="test",
            target_root="/tmp/test_sync",
            dry_run=True,
            max_depth=5,
            recursive=True,
        )

        # Test with actual sync
        tool._execute_sync(
            source_dirs=source_dirs,
            host=ssh_server.host,
            port=ssh_server.port,
            user="test",
            target_root="/tmp/test_sync",
            dry_run=False,
            max_depth=5,
            recursive=True,
        )


@pytest.mark.integration
@pytest.mark.skipif(not check_rsync_available(), reason="rsync not available")
class TestRsyncIntegration:
    """Integration tests that require rsync."""

    def test_sync_via_rsync(self, test_repo: Repo, temp_dir: Path) -> None:
        """Test rsync synchronization."""
        source_dir = str(test_repo.working_dir)
        target_dir = str(temp_dir / "target")
        os.makedirs(target_dir)

        # Create test files
        files = ["test1.txt", "test2.txt"]
        for file in files:
            Path(source_dir, file).write_text("test content")

        # Test dry run
        sync_via_rsync(source_dir, files, target_dir, dry_run=True)

        # Test actual sync
        sync_via_rsync(source_dir, files, target_dir, dry_run=False)

        # Verify files were synced
        for file in files:
            assert Path(target_dir, file).exists()
