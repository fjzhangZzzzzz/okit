import os
import sys
import click
from pathlib import Path
from typing import List
from okit.utils.log import logger, console
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


@okit_tool("clone", "Batch clone git repositories from a list file")
class CloneRepos(BaseTool):
    """批量克隆 Git 仓库工具"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
Clone Repos Tool - Batch clone git repositories from a list file.

This tool reads a list of repository URLs from a file and clones them
to the current directory. It supports:
• Reading repository URLs from a text file
• Optional branch specification
• Skip existing repositories
• Progress reporting and summary

Use 'clone --help' to see available commands.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Batch clone git repositories from a list file"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""

        @cli_group.command()
        @click.argument('repo_list', type=click.Path(exists=True, dir_okay=False))
        @click.option('-b', '--branch', default=None, help='Branch name to clone (optional)')
        def batch(repo_list: str, branch: str) -> None:
            """Batch clone git repositories from a list file"""
            try:
                self.logger.info(f"Executing batch clone command, file: {repo_list}, branch: {branch}")
                
                from git import Repo, GitCommandError
                repo_list_data = read_repo_list(repo_list)
                
                if not repo_list_data:
                    console.print("[red]No valid repository URLs found in the list file.[/red]")
                    sys.exit(1)
                
                self._clone_repositories(repo_list_data, branch=branch)
                
            except Exception as e:
                self.logger.error(f"batch clone command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

    def _clone_repositories(self, repo_list: List[str], branch: str = None) -> None:
        """克隆仓库列表"""
        from git import Repo, GitCommandError
        
        success_count = 0
        fail_count = 0
        skip_count = 0

        for repo_url in repo_list:
            repo_name = get_repo_name(repo_url)
            if os.path.isdir(repo_name):
                console.print(f"[yellow]Skip existing repo: {repo_url}[/yellow]")
                skip_count += 1
                continue
                
            console.print(f"Cloning: {repo_url}")
            try:
                if branch:
                    Repo.clone_from(repo_url, repo_name, branch=branch)
                    console.print(f"[green]Successfully cloned branch {branch}: {repo_url}[/green]")
                else:
                    Repo.clone_from(repo_url, repo_name)
                    console.print(f"[green]Successfully cloned: {repo_url}[/green]")
                success_count += 1
            except GitCommandError as e:
                console.print(f"[red]Clone failed: {repo_url}\n  Reason: {e}[/red]")
                fail_count += 1
                
        console.print("----------------------------------------")
        console.print(f"[bold]Clone finished! Summary:[/bold]")
        console.print(f"[green]Success: {success_count}[/green]")
        console.print(f"[red]Failed: {fail_count}[/red]")
        console.print(f"[yellow]Skipped: {skip_count}[/yellow]")

    def validate_config(self) -> bool:
        """验证配置"""
        # 简单的配置验证逻辑
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """自定义清理逻辑"""
        self.logger.info("Executing custom cleanup logic")
        # 工具特定的清理代码可以在这里添加
        pass 