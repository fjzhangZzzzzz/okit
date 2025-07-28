import os
import sys
import json
import platform
import click
from pathlib import Path
from typing import Dict, List, Optional, Any
from okit.utils.log import logger, console
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool

from git import Repo, GitCommandError


@okit_tool("shellconfig", "Shell configuration management tool")
class ShellConfig(BaseTool):
    """Shell configuration management tool"""

    SUPPORTED_SHELLS: Dict[str, Dict[str, Any]] = {
        "bash": {
            "rc_file": ".bashrc",
            "profile_file": ".bash_profile",
            "comment_char": "#",
            "source_cmd": "source",
        },
        "zsh": {
            "rc_file": ".zshrc",
            "comment_char": "#",
            "source_cmd": "source",
        },
        "cmd": {
            "rc_file": None,
            "comment_char": "REM",
            "source_cmd": "call",
        },
        "powershell": {
            "rc_file": "$PROFILE",
            "comment_char": "#",
            "source_cmd": ".",
        },
    }

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)
        self.home_dir = Path.home()
        # Git repository path using BaseTool data directory
        self.configs_repo_path = self.get_data_path() / "configs_repo"
        self.configs_repo: Optional[Repo] = None

    def _get_cli_help(self) -> str:
        """Custom CLI help information"""
        return """
Shell Config Tool - Manage shell configurations across multiple shells.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """Custom CLI short help information"""
        return "Shell configuration management tool"

    def get_shell_info(self, shell_name: str) -> Dict[str, Any]:
        """Get shell configuration information"""
        if shell_name not in self.SUPPORTED_SHELLS:
            raise ValueError(f"Unsupported shell: {shell_name}")
        return self.SUPPORTED_SHELLS[shell_name]

    def get_shell_config_dir(self, shell_name: str) -> Path:
        """Get shell configuration directory path"""
        return self.get_data_path() / shell_name

    def get_shell_config_file(self, shell_name: str) -> Path:
        """Get shell configuration file path"""
        return self.get_shell_config_dir(shell_name) / "config"

    def get_repo_config_path(self, shell_name: str) -> Path:
        """Get repository configuration file path for shell"""
        return self.configs_repo_path / shell_name / "config"

    def ensure_shell_config_dir(self, shell_name: str) -> Path:
        """Ensure shell configuration directory exists and return path"""
        config_dir = self.get_shell_config_dir(shell_name)
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def create_default_config(self, shell_name: str) -> str:
        """Create default configuration content for shell"""
        shell_info = self.get_shell_info(shell_name)
        comment_char = shell_info["comment_char"]

        if shell_name in ["bash", "zsh"]:
            # bash and zsh use the same configuration
            return f"""# {shell_name.title()} configuration
{comment_char} This file is managed by okit shellconfig tool
{comment_char} Manual changes will be overwritten

# Add custom aliases
alias ll='ls -la'
alias la='ls -A'
alias l='ls -CF'

# Add custom functions
function mkcd() {{
    mkdir -p "$1" && cd "$1"
}}

# Add custom environment variables
export EDITOR=vim
export VISUAL=vim

# Add custom PATH
# export PATH="$HOME/bin:$PATH"

# ===== PROXY CONFIGURATION =====
{comment_char} Proxy settings - uncomment and modify as needed
{comment_char} export http_proxy=http://127.0.0.1:7897
{comment_char} export https_proxy=http://127.0.0.1:7897
{comment_char} export HTTP_PROXY=http://127.0.0.1:7897
{comment_char} export HTTPS_PROXY=http://127.0.0.1:7897

# ===== PROXY MANAGEMENT FUNCTIONS =====
{comment_char} Proxy management functions
proxy() {{
    export http_proxy=http://127.0.0.1:7897
    export https_proxy=http://127.0.0.1:7897
    export HTTP_PROXY=http://127.0.0.1:7897
    export HTTPS_PROXY=http://127.0.0.1:7897
    echo "Proxy enabled: http://127.0.0.1:7897"
}}

noproxy() {{
    unset http_proxy
    unset https_proxy
    unset HTTP_PROXY
    unset HTTPS_PROXY
    echo "Proxy disabled"
}}

showproxy() {{
    if [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then
        echo "Current proxy settings:"
        echo "HTTP Proxy: $http_proxy"
        echo "HTTPS Proxy: $https_proxy"
    else
        echo "No proxy set"
    fi
}}
"""
        elif shell_name == "cmd":
            return f"""@echo off
REM CMD configuration
REM This file is managed by okit shellconfig tool
REM Manual changes will be overwritten

REM Add custom aliases
doskey ll=dir /la $*
doskey la=dir /a $*
doskey l=dir $*

REM Add custom environment variables
set EDITOR=notepad
set VISUAL=notepad

REM Add custom PATH
REM set PATH=%USERPROFILE%\\bin;%PATH%

REM ===== PROXY CONFIGURATION =====
REM Proxy settings - uncomment and modify as needed
REM set HTTP_PROXY=http://127.0.0.1:7897
REM set HTTPS_PROXY=http://127.0.0.1:7897

REM ===== PROXY MANAGEMENT FUNCTIONS =====
REM Proxy management functions
:proxy
set HTTP_PROXY=http://127.0.0.1:7897
set HTTPS_PROXY=http://127.0.0.1:7897
echo Proxy enabled: http://127.0.0.1:7897
goto :eof

:noproxy
set HTTP_PROXY=
set HTTPS_PROXY=
echo Proxy disabled
goto :eof

:showproxy
if defined HTTP_PROXY (
    echo Current proxy settings:
    echo HTTP Proxy: %HTTP_PROXY%
    echo HTTPS Proxy: %HTTPS_PROXY%
) else (
    echo No proxy set
)
goto :eof
"""
        elif shell_name == "powershell":
            return f"""# PowerShell configuration
{comment_char} This file is managed by okit shellconfig tool
{comment_char} Manual changes will be overwritten

# Add custom aliases
Set-Alias ll Get-ChildItem -Force
Set-Alias la Get-ChildItem -Force -Name
Set-Alias l Get-ChildItem

# Add custom functions
function mkcd {{
    param([string]$path)
    New-Item -ItemType Directory -Path $path -Force
    Set-Location $path
}}

# Add custom environment variables
$env:EDITOR = "notepad"
$env:VISUAL = "notepad"

# Add custom PATH
# $env:PATH = "$env:USERPROFILE\\bin;$env:PATH"

# ===== PROXY CONFIGURATION =====
{comment_char} Proxy settings - uncomment and modify as needed
{comment_char} $env:HTTP_PROXY = "http://127.0.0.1:7897"
{comment_char} $env:HTTPS_PROXY = "http://127.0.0.1:7897"
{comment_char} [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy("http://127.0.0.1:7897")

# ===== PROXY MANAGEMENT FUNCTIONS =====
{comment_char} Proxy management functions
function proxy {{
    $env:http_proxy = "http://127.0.0.1:7897"
    $env:https_proxy = "http://127.0.0.1:7897"
    $env:HTTP_PROXY = "http://127.0.0.1:7897"
    $env:HTTPS_PROXY = "http://127.0.0.1:7897"
    [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy("http://127.0.0.1:7897")
    Write-Host "Proxy Active on: http://127.0.0.1:7897" -ForegroundColor Green
}}

function noproxy {{
    $env:http_proxy = $null
    $env:https_proxy = $null
    $env:HTTP_PROXY = $null
    $env:HTTPS_PROXY = $null
    [System.Net.WebRequest]::DefaultWebProxy = $null
    Write-Host "Proxy Negatived." -ForegroundColor Red
}}

function showproxy {{
    if ($env:http_proxy -or $env:https_proxy) {{
        Write-Host "Current proxy settings:" -ForegroundColor Green
        Write-Host "HTTP Proxy: $env:http_proxy"
        Write-Host "HTTPS Proxy: $env:https_proxy"
    }} else {{
        Write-Host "No proxy set." -ForegroundColor Red
    }}
}}
"""
        else:
            return f"# {shell_name} configuration\n"

    def show_source_commands(self, shell_name: str) -> None:
        """Show commands to source the configuration"""
        shell_info = self.get_shell_info(shell_name)
        config_file = self.get_shell_config_file(shell_name)

        if not config_file.exists():
            console.print(f"[yellow]Configuration file {config_file} does not exist[/yellow]")
            return

        console.print(f"[bold]Source commands for {shell_name}:[/bold]")
        if shell_name in ["bash", "zsh"]:
            console.print(f"source {config_file}")
        elif shell_name == "cmd":
            console.print(f"call {config_file}")
        elif shell_name == "powershell":
            console.print(f". {config_file}")

    def setup_git_repo(self, repo_url: Optional[str] = None) -> bool:
        """Setup git repository for configuration management"""
        try:
            if not repo_url:
                console.print("[red]Error: repo_url is required[/red]")
                return False

            if self.configs_repo_path.exists():
                console.print(f"[yellow]Git repository already exists at {self.configs_repo_path}[/yellow]")
                try:
                    self.configs_repo = Repo(self.configs_repo_path)
                    console.print("[green]Using existing git repository[/green]")
                    return True
                except GitCommandError:
                    console.print("[yellow]Existing directory is not a git repository, reinitializing...[/yellow]")

            console.print(f"Setting up git repository at {self.configs_repo_path}")
            self.configs_repo_path.mkdir(parents=True, exist_ok=True)

            # Initialize git repository
            self.configs_repo = Repo.init(self.configs_repo_path)
            console.print("[green]Git repository initialized[/green]")

            # Add remote origin
            origin = self.configs_repo.create_remote("origin", repo_url)
            console.print(f"[green]Added remote origin: {repo_url}[/green]")

            # Try to pull existing content
            try:
                origin.fetch()
                self.configs_repo.heads.main.checkout()
                console.print("[green]Pulled existing content from remote repository[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not pull from remote: {e}[/yellow]")
                console.print("[yellow]Creating initial commit...[/yellow]")

                # Create initial commit
                self.configs_repo.index.add("*")
                self.configs_repo.index.commit("Initial commit")

            # Save repo_url to config using BaseTool interface
            self.set_config_value("git.remote_url", repo_url)
            console.print("[green]Git repository setup completed[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to setup git repository: {e}[/red]")
            return False

    def update_repo(self) -> bool:
        """Update git repository"""
        try:
            if not self.configs_repo_path.exists():
                console.print("[yellow]Git repository does not exist, run setup first[/yellow]")
                return False

            self.configs_repo = Repo(self.configs_repo_path)
            origin = self.configs_repo.remotes.origin

            console.print("Pulling latest changes from remote repository...")
            origin.pull()
            console.print("[green]Repository updated successfully[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to update repository: {e}[/red]")
            return False

    def sync_config(self, shell_name: str) -> bool:
        """Sync configuration from git repository"""
        try:
            if not self.configs_repo_path.exists():
                console.print("[yellow]Git repository does not exist, run setup first[/yellow]")
                return False

            self.configs_repo = Repo(self.configs_repo_path)
            repo_config_path = self.get_repo_config_path(shell_name)

            if not repo_config_path.exists():
                console.print(f"[yellow]No configuration found in repository for {shell_name}[/yellow]")
                return False

            config_file = self.get_shell_config_file(shell_name)
            self.ensure_shell_config_dir(shell_name)

            # Copy from repository to local
            import shutil
            shutil.copy2(repo_config_path, config_file)
            console.print(f"[green]Configuration synced for {shell_name}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to sync configuration: {e}[/red]")
            return False

    def list_configs(self) -> None:
        """List all available configurations"""
        console.print("[bold]Available configurations:[/bold]")

        for shell_name in self.SUPPORTED_SHELLS:
            config_file = self.get_shell_config_file(shell_name)
            repo_config_path = self.get_repo_config_path(shell_name)

            status = []
            if config_file.exists():
                status.append("local")
            if repo_config_path.exists():
                status.append("repo")

            if status:
                console.print(f"  {shell_name}: {', '.join(status)}")
            else:
                console.print(f"  {shell_name}: none")

    def initialize_config_if_needed(self, shell_name: str) -> bool:
        """Initialize configuration file if it doesn't exist"""
        config_file = self.get_shell_config_file(shell_name)

        if config_file.exists():
            return True

        try:
            self.ensure_shell_config_dir(shell_name)
            content = self.create_default_config(shell_name)

            with open(config_file, "w", encoding="utf-8") as f:
                f.write(content)

            console.print(f"[green]Created default configuration for {shell_name}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to create configuration for {shell_name}: {e}[/red]")
            return False

    def enable_config(self, shell_name: str) -> bool:
        """Enable customconfig by adding source command to rc file"""
        try:
            shell_info = self.get_shell_info(shell_name)
            rc_file_name = shell_info["rc_file"]

            if not rc_file_name:
                console.print(f"[yellow]No rc file configured for {shell_name}[/yellow]")
                return False

            if shell_name == "powershell":
                rc_file = Path(rc_file_name)
            else:
                rc_file = self.home_dir / rc_file_name

            # Initialize config if needed
            if not self.initialize_config_if_needed(shell_name):
                return False

            config_file = self.get_shell_config_file(shell_name)
            source_cmd = shell_info["source_cmd"]

            # Create rc file if it doesn't exist
            if not rc_file.exists():
                rc_file.parent.mkdir(parents=True, exist_ok=True)
                rc_file.touch()

            # Read existing content
            with open(rc_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if already enabled
            source_line = f"{source_cmd} {config_file}"
            if source_line in content:
                console.print(f"[yellow]Configuration already enabled for {shell_name}[/yellow]")
                return True

            # Add source command
            with open(rc_file, "a", encoding="utf-8") as f:
                f.write(f"\n# Added by okit shellconfig tool\n{source_line}\n")

            console.print(f"[green]Configuration enabled for {shell_name}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to enable configuration for {shell_name}: {e}[/red]")
            return False

    def disable_config(self, shell_name: str) -> bool:
        """Disable customconfig by removing source command from rc file"""
        try:
            shell_info = self.get_shell_info(shell_name)
            rc_file_name = shell_info["rc_file"]

            if not rc_file_name:
                console.print(f"[yellow]No rc file configured for {shell_name}[/yellow]")
                return False

            if shell_name == "powershell":
                rc_file = Path(rc_file_name)
            else:
                rc_file = self.home_dir / rc_file_name

            if not rc_file.exists():
                console.print(f"[yellow]RC file {rc_file} does not exist[/yellow]")
                return True

            config_file = self.get_shell_config_file(shell_name)
            source_cmd = shell_info["source_cmd"]
            source_line = f"{source_cmd} {config_file}"

            # Read existing content
            with open(rc_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Remove source command lines
            new_lines = []
            removed = False
            for line in lines:
                if source_line in line or (line.strip().startswith("#") and "okit shellconfig" in line):
                    removed = True
                    continue
                new_lines.append(line)

            if not removed:
                console.print(f"[yellow]Configuration not found in {rc_file}[/yellow]")
                return True

            # Write back content
            with open(rc_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            console.print(f"[green]Configuration disabled for {shell_name}[/green]")
            return True

        except Exception as e:
            console.print(f"[red]Failed to disable configuration for {shell_name}: {e}[/red]")
            return False

    def check_config_status(self, shell_name: str) -> bool:
        """Check if customconfig is enabled in rc file"""
        try:
            shell_info = self.get_shell_info(shell_name)
            rc_file_name = shell_info["rc_file"]

            if not rc_file_name:
                return False

            if shell_name == "powershell":
                rc_file = Path(rc_file_name)
            else:
                rc_file = self.home_dir / rc_file_name

            if not rc_file.exists():
                return False

            config_file = self.get_shell_config_file(shell_name)
            source_cmd = shell_info["source_cmd"]
            source_line = f"{source_cmd} {config_file}"

            with open(rc_file, "r", encoding="utf-8") as f:
                content = f.read()

            return source_line in content

        except Exception:
            return False

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """Add tool-specific CLI commands"""

        @cli_group.command()
        @click.argument("action", type=click.Choice(["get", "set", "list", "setup"]))
        @click.argument("key", required=False)
        @click.argument("value", required=False)
        @click.option(
            "--repo-url", help="Git repository URL for configuration (used with setup action)"
        )
        def config(action: str, key: Optional[str], value: Optional[str], repo_url: Optional[str]) -> None:
            """Manage tool configuration (similar to git config)"""
            try:
                self.logger.info(f"Executing config command, action: {action}, key: {key}")

                if action == "get":
                    if not key:
                        console.print("[red]Error: key is required for 'get' action[/red]")
                        return
                    result = self.get_config_value(key)
                    if result is not None:
                        console.print(result)
                    else:
                        console.print(f"[yellow]No value found for key: {key}[/yellow]")

                elif action == "set":
                    if not key or value is None:
                        console.print(
                            "[red]Error: both key and value are required for 'set' action[/red]"
                        )
                        return
                    if self.set_config_value(key, value):
                        console.print(f"[green]Set {key} = {value}[/green]")
                    else:
                        console.print(f"[red]Failed to set {key}[/red]")

                elif action == "list":
                    # List all config and display
                    config_data = self.load_config()

                    if not config_data:
                        console.print("[yellow]No configuration parameters set[/yellow]")
                        return

                    from rich.table import Table

                    table = Table(title="Tool Configuration")
                    table.add_column("Parameter", style="cyan")
                    table.add_column("Value", style="green")

                    for key, value in config_data.items():
                        table.add_row(key, str(value))

                    console.print(table)

                elif action == "setup":
                    # Setup git repository (replaces old setup_git command)
                    if repo_url:
                        self.setup_git_repo(repo_url)
                    else:
                        # Try to get repo_url from config
                        config_repo_url = self.get_config_value("git.remote_url")
                        if config_repo_url:
                            self.setup_git_repo(config_repo_url)
                        else:
                            console.print(
                                "[yellow]No repo_url provided or configured. Use --repo-url option.[/yellow]"
                            )
                            console.print(
                                "Example: config setup --repo-url https://github.com/user/repo.git"
                            )
                            
            except Exception as e:
                self.logger.error(f"config command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.argument("shell", type=click.Choice(["bash", "zsh", "cmd", "powershell"]))
        def sync(shell: str) -> None:
            """Sync configuration from git repository"""
            try:
                self.logger.info(f"Executing sync command, shell: {shell}")
                self.sync_config(shell)
                
            except Exception as e:
                self.logger.error(f"sync command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.argument("shell", type=click.Choice(["bash", "zsh", "cmd", "powershell"]))
        def source(shell: str) -> None:
            """Show commands to source the configuration"""
            try:
                self.logger.info(f"Executing source command, shell: {shell}")
                self.show_source_commands(shell)
                
            except Exception as e:
                self.logger.error(f"source command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.argument("shell", type=click.Choice(["bash", "zsh", "cmd", "powershell"]))
        def enable(shell: str) -> None:
            """Enable customconfig by adding source command to rc file"""
            try:
                self.logger.info(f"Executing enable command, shell: {shell}")
                self.enable_config(shell)
                
            except Exception as e:
                self.logger.error(f"enable command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.argument("shell", type=click.Choice(["bash", "zsh", "cmd", "powershell"]))
        def disable(shell: str) -> None:
            """Disable customconfig by removing source command from rc file"""
            try:
                self.logger.info(f"Executing disable command, shell: {shell}")
                self.disable_config(shell)
                
            except Exception as e:
                self.logger.error(f"disable command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

        @cli_group.command()
        @click.argument("shell", type=click.Choice(["bash", "zsh", "cmd", "powershell"]))
        def status(shell: str) -> None:
            """Check if customconfig is enabled in rc file"""
            try:
                self.logger.info(f"Executing status command, shell: {shell}")
                is_enabled = self.check_config_status(shell)

                if is_enabled:
                    console.print(f"[green]✓ Configuration is enabled for {shell}[/green]")
                else:
                    console.print(f"[red]✗ Configuration is disabled for {shell}[/red]")

                # Show additional info
                config_file = self.get_shell_config_file(shell)
                shell_info = self.get_shell_info(shell)
                rc_file = (
                    self.home_dir / shell_info["rc_file"] if shell_info["rc_file"] else None
                )

                console.print(
                    f"Config file: {config_file} ({'exists' if config_file.exists() else 'missing'})"
                )
                if rc_file:
                    console.print(
                        f"RC file: {rc_file} ({'exists' if rc_file.exists() else 'missing'})"
                    )
                    
            except Exception as e:
                self.logger.error(f"status command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

    def validate_config(self) -> bool:
        """Validate configuration"""
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """Custom cleanup logic"""
        self.logger.info("Executing custom cleanup logic")
        pass
