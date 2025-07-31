"""Common test fixtures and utilities."""

import os
import shutil
import socket
import struct
import tempfile
from pathlib import Path
from typing import Generator, Optional, Tuple, cast

import git
import paramiko
import pytest
from git import Repo


class TestSSHServer:
    """A simple SSH server for testing."""

    def __init__(self, host: str = "localhost", port: int = 0) -> None:
        self.host = host
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.transport: Optional[paramiko.Transport] = None
        self.server_thread = None
        self.temp_dir = tempfile.mkdtemp()

    def start(self) -> None:
        """Start the SSH server."""
        host_key = paramiko.RSAKey.generate(2048)
        self.transport = paramiko.Transport(self.sock.accept()[0])
        self.transport.add_server_key(host_key)
        self.transport.start_server(server=TestSSHServerHandler(self.temp_dir))

    def stop(self) -> None:
        """Stop the SSH server."""
        if self.transport:
            self.transport.close()
        self.sock.close()
        shutil.rmtree(self.temp_dir)


class TestSSHServerHandler(paramiko.ServerInterface):
    """SSH server handler for testing."""

    def __init__(self, temp_dir: str) -> None:
        super().__init__()
        self.temp_dir = temp_dir

    def check_auth_password(self, username: str, password: str) -> int:
        """Always authenticate with any credentials."""
        return 0  # AUTH_SUCCESSFUL

    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        """Always authenticate with any key."""
        return 0  # AUTH_SUCCESSFUL

    def check_channel_request(self, kind: str, chanid: int) -> int:
        """Allow any channel."""
        return 0  # OPEN_SUCCEEDED

    def get_allowed_auths(self, username: str) -> str:
        """Return allowed authentication methods."""
        return "password,publickey"

    def check_channel_exec_request(
        self, channel: paramiko.Channel, command: bytes
    ) -> bool:
        """Handle command execution requests."""
        cmd = command.decode("utf-8")
        if cmd.startswith("mkdir -p "):
            # Extract path from command
            path = cmd[8:].strip()
            # Convert to local path
            local_path = os.path.join(self.temp_dir, path.lstrip("/"))
            # Create directory
            os.makedirs(local_path, exist_ok=True)
            channel.send_exit_status(0)
        elif cmd.startswith("test -d "):
            # Extract path from command
            path = cmd[7:].strip().strip("'")
            # Convert to local path
            local_path = os.path.join(self.temp_dir, path.lstrip("/"))
            # Check if directory exists
            if os.path.isdir(local_path):
                channel.send_exit_status(0)
            else:
                channel.send_exit_status(1)
        else:
            channel.send_exit_status(1)
        return True


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir)


@pytest.fixture
def test_repo(temp_dir: Path) -> Generator[Repo, None, None]:
    """Create a test Git repository."""
    repo_path = temp_dir / "test_repo"
    repo_path.mkdir()
    repo = git.Repo.init(repo_path)

    # Create some test files and commits
    (repo_path / "test.txt").write_text("test content")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit")

    try:
        yield repo
    finally:
        repo.close()


@pytest.fixture
def ssh_server() -> Generator[TestSSHServer, None, None]:
    """Create and start a test SSH server."""
    server = TestSSHServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()
