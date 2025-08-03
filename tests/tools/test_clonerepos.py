"""Tests for clonerepos tool."""

import os
import shutil
from pathlib import Path
from typing import Generator

import git
import pytest
from git import Repo
from click.testing import CliRunner

from okit.tools.clonerepos import CloneRepos, get_repo_name, read_repo_list


@pytest.fixture
def repo_list_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary repository list file."""
    repo_list = temp_dir / "repos.txt"
    repo_list.write_text(
        """
# Test repositories
https://github.com/test/repo1.git
https://github.com/test/repo2
https://gitlab.com/test/repo3.git
# Empty lines and comments should be ignored

https://github.com/test/repo4/
"""
    )
    yield repo_list


@pytest.fixture
def work_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary working directory."""
    work_dir = temp_dir / "work"
    work_dir.mkdir()
    old_cwd = os.getcwd()
    os.chdir(work_dir)
    try:
        yield work_dir
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(work_dir)


def test_read_repo_list(repo_list_file: Path) -> None:
    """Test reading repository list from file."""
    repos = read_repo_list(str(repo_list_file))
    assert len(repos) == 4
    assert repos[0] == "https://github.com/test/repo1.git"
    assert repos[1] == "https://github.com/test/repo2"
    assert repos[2] == "https://gitlab.com/test/repo3.git"
    assert repos[3] == "https://github.com/test/repo4/"


def test_get_repo_name() -> None:
    """Test extracting repository name from URL."""
    test_cases = [
        ("https://github.com/test/repo1.git", "repo1"),
        ("https://github.com/test/repo2", "repo2"),
        ("https://gitlab.com/test/repo3.git/", "repo3"),
        ("https://github.com/test/repo4/", "repo4"),
    ]
    for url, expected in test_cases:
        assert get_repo_name(url) == expected


def test_clone_repositories(work_dir: Path, test_repo: Repo) -> None:
    """Test cloning repositories."""
    # Create test data
    repo_url = str(test_repo.working_dir)
    repo_list = [repo_url]

    # Initialize tool
    tool = CloneRepos("clonerepos")

    # Test cloning
    tool._clone_repositories(repo_list)

    # Verify clone
    repo_name = get_repo_name(repo_url)
    cloned_repo_path = work_dir / repo_name
    assert cloned_repo_path.exists()
    assert cloned_repo_path.is_dir()

    # Verify repository content
    cloned_repo = Repo(cloned_repo_path)
    assert not cloned_repo.bare
    assert (cloned_repo_path / "test.txt").exists()

    # Test skipping existing repository
    tool._clone_repositories(repo_list)  # Should skip


def test_clone_repositories_with_branch(work_dir: Path, test_repo: Repo) -> None:
    """Test cloning repositories with specific branch."""
    # Create a new branch in test repo
    test_branch = "test-branch"
    current = test_repo.create_head(test_branch)
    current.checkout()

    # Add a file in the new branch
    branch_file = Path(test_repo.working_dir) / "branch-test.txt"
    branch_file.write_text("branch specific content")
    test_repo.index.add([str(branch_file)])
    test_repo.index.commit("Branch commit")

    # Test cloning with branch
    repo_url = str(test_repo.working_dir)
    repo_list = [repo_url]
    tool = CloneRepos("clonerepos")
    tool._clone_repositories(repo_list, branch=test_branch)

    # Verify branch content
    repo_name = get_repo_name(repo_url)
    cloned_repo_path = work_dir / repo_name
    assert (cloned_repo_path / "branch-test.txt").exists()

    cloned_repo = Repo(cloned_repo_path)
    assert cloned_repo.active_branch.name == test_branch


def test_clone_repositories_failure(work_dir: Path) -> None:
    """Test handling of clone failures."""
    # Test with invalid repository URL
    invalid_repo = "https://invalid-url/repo.git"
    tool = CloneRepos("clonerepos")
    tool._clone_repositories([invalid_repo])  # Should handle failure gracefully


def test_clonerepos_cli_interface() -> None:
    """Test command line interface."""
    runner = CliRunner()

    # Create tool instance and test CLI
    tool = CloneRepos("clonerepos")
    cli = tool.create_cli_group()

    # Test help command
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Batch clone git repositories from a list file" in result.output

    # Test that options are properly displayed
    assert "--branch" in result.output
    assert "-b" in result.output

    # Test command help
    result = runner.invoke(cli, ["clonerepos", "--help"])
    assert result.exit_code == 0
    assert "Branch name to clone (optional)" in result.output
