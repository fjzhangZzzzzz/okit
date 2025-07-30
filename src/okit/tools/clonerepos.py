import os
import sys
import click
from pathlib import Path
from typing import List
from okit.utils.log import output
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool


def read_repo_list(file_path: str) -> List[str]:
    """读取仓库列表文件"""
    repos = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            repos.append(line)
    return repos


def get_repo_name(repo_url: str) -> str:
    """从仓库URL中提取仓库名称"""
    repo_name = repo_url.rstrip('/').split('/')[-1]
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    return repo_name


@okit_tool("clonerepos", "Batch clone git repositories from a list file", use_subcommands=False)
class CloneRepos(BaseTool):
    """批量克隆 Git 仓库工具"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
Clone Repos Tool - Batch clone git repositories from a list file.

Example:

  clonerepos repos.txt                    # Clone from default branch
  clonerepos repos.txt -b main            # Clone from 'main' branch
  clonerepos repos.txt --branch develop   # Clone from 'develop' branch
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Batch clone git repositories from a list file"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""

        @cli_group.command(name="clonerepos")
        @click.argument('repo_list', type=click.Path(exists=True, dir_okay=False))
        @click.option('-b', '--branch', default=None, help='Branch name to clone (optional)')
        def main(repo_list: str, branch: str) -> None:
            """Batch clone git repositories from a list file"""
            try:
                output.debug(f"Executing clonerepos command, file: {repo_list}, branch: {branch}")
                
                from git import Repo, GitCommandError
                repo_list_data = read_repo_list(repo_list)
                
                if not repo_list_data:
                    output.error("No valid repository URLs found in the list file")
                    sys.exit(1)
                
                self._clone_repositories(repo_list_data, branch=branch)
                
            except Exception as e:
                output.error(f"clonerepos command execution failed: {e}")

    def _clone_repositories(self, repo_list: List[str], branch: str = None) -> None:
        """克隆仓库列表"""
        from git import Repo, GitCommandError
        
        success_count = 0
        fail_count = 0
        skip_count = 0

        for repo_url in repo_list:
            repo_name = get_repo_name(repo_url)
            if os.path.isdir(repo_name):
                output.warning(f"Skip existing repo: {repo_url}")
                skip_count += 1
                continue
                
            output.progress(f"Cloning: {repo_url}")
            try:
                if branch:
                    Repo.clone_from(repo_url, repo_name, branch=branch)
                    output.success(f"Successfully cloned branch {branch}: {repo_url}")
                else:
                    Repo.clone_from(repo_url, repo_name)
                    output.success(f"Successfully cloned: {repo_url}")
                success_count += 1
            except GitCommandError as e:
                output.error(f"Clone failed: {repo_url}\n  Reason: {e}")
                fail_count += 1
                
        output.info("Clone finished! Summary:")
        output.result(f"Success: {success_count}")
        output.result(f"Failed: {fail_count}")
        output.result(f"Skipped: {skip_count}")



    def _cleanup_impl(self) -> None:
        """自定义清理逻辑"""
        output.debug("Executing custom cleanup logic")
        # 工具特定的清理代码可以在这里添加
        pass 