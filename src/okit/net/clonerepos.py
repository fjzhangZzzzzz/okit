import os
import sys
import click
from okit.utils.log import logger, console


def read_repo_list(file_path):
    repos = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            repos.append(line)
    return repos


def get_repo_name(repo_url):
    repo_name = repo_url.rstrip('/').split('/')[-1]
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    return repo_name


def clone_repositories(repo_list, branch=None):
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


@click.command()
@click.argument('repo_list', type=click.Path(exists=True, dir_okay=False))
@click.option('-b', '--branch', default=None, help='Branch name to clone (optional)')
def cli(repo_list, branch):
    from git import Repo, GitCommandError
    """Batch clone git repositories from a list file."""
    repo_list_data = read_repo_list(repo_list)
    if not repo_list_data:
        console.print("[red]No valid repository URLs found in the list file.[/red]")
        sys.exit(1)
    clone_repositories(repo_list_data, branch=branch)


if __name__ == "__main__":
    cli() 