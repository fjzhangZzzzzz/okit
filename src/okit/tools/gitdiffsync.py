#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = ["paramiko~=3.4"]
# ///
"""
File synchronization script that supports Git projects synchronization via rsync or sftp.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Any
import re
import click
import socket
from okit.utils.log import logger, console
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool

# paramiko 相关 import 延迟到 cli 和相关函数内部


class SyncError(Exception):
    """Custom exception for sync related errors."""
    pass


def check_git_repo(directory: str) -> bool:
    """Check if directory is a Git repository."""
    if not os.path.isdir(directory):
        logger.error(f"Directory does not exist: {directory}")
        sys.exit(1)
    logger.info(f"Checking if {directory} is a Git repository...")
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=directory,
            capture_output=True,
            text=True
        )
        is_repo = result.returncode == 0
        if is_repo:
            logger.debug(f"{directory} is a valid Git repository")
        else:
            logger.warning(f"{directory} is not a Git repository")
        return is_repo
    except subprocess.CalledProcessError:
        logger.error(f"Failed to check Git repository status for {directory}")
        return False


def get_git_changes(directory: str) -> List[str]:
    """Get list of changed files in Git repository."""
    logger.info(f"Getting Git changes for {directory}...")
    result = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=directory,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error(f"Failed to get Git status for {directory}")
        raise SyncError(f"Failed to get Git status for {directory}")
    
    changes = []
    for line in result.stdout.splitlines():
        status = line[:2]
        file_path = line[3:]
        # Skip deleted files and .cursor directory
        if status.strip() != 'D' and not file_path.startswith('.cursor/'):
            changes.append(file_path)
    
    logger.info(f"Found {len(changes)} changed files in {directory}")
    return changes


def check_rsync_available() -> bool:
    """Check if rsync is available in the system."""
    logger.info("Checking if rsync is available...")
    try:
        subprocess.run(
            ['rsync', '--version'],
            capture_output=True
        )
        logger.info("rsync is available")
        return True
    except FileNotFoundError:
        logger.info("rsync is not available, will use SFTP instead")
        return False


def verify_directory_structure(
    source_dirs: List[str],
    remote_root: str,
    ssh_client: Any
) -> bool:
    """Verify if target directories exist on remote server."""
    logger.info(f"Verifying target {remote_root} directories exist...")
    
    for directory in source_dirs:
        project_name = os.path.basename(os.path.abspath(directory))
        target_dir = f"{remote_root}/{project_name}"
        
        try:
            stdin, stdout, stderr = ssh_client.exec_command(f"test -d '{target_dir}'")
            if stdout.channel.recv_exit_status() != 0:
                logger.error(f"Target directory {target_dir} does not exist")
                return False
            logger.debug(f"Target directory {target_dir} exists")
        except Exception as e:
            logger.error(f"Failed to verify directory {target_dir}: {e}")
            return False
    
    return True


def ensure_remote_dir(sftp: Any, remote_directory):
    """Ensure remote directory exists, create if necessary."""
    try:
        sftp.stat(remote_directory)
    except FileNotFoundError:
        try:
            sftp.mkdir(remote_directory)
            logger.debug(f"Created remote directory: {remote_directory}")
        except Exception as e:
            logger.error(f"Failed to create remote directory {remote_directory}: {e}")
            raise


def sync_via_rsync(
    source_dir: str,
    files: List[str],
    target: str,
    dry_run: bool
) -> None:
    # project_name = os.path.basename(os.path.abspath(source_dir))
    logger.info(f"Syncing {len(files)} files via rsync to {target}")
    
    if not files:
        logger.info("No files to sync")
        return
    
    # Create file list for rsync
    file_list = "\n".join(files)
    
    cmd = [
        'rsync',
        '-avz',
        '--files-from=-',
        '--relative',
        source_dir + '/',
        target
    ]
    
    if dry_run:
        cmd.insert(1, '--dry-run')
    
    try:
        result = subprocess.run(
            cmd,
            input=file_list,
            text=True,
            capture_output=True
        )
        
        if result.returncode == 0:
            logger.info("rsync completed successfully")
            if dry_run:
                console.print(result.stdout)
        else:
            logger.error(f"rsync failed: {result.stderr}")
            raise SyncError(f"rsync failed: {result.stderr}")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"rsync command failed: {e}")
        raise SyncError(f"rsync command failed: {e}")


def sync_via_sftp(
    source_dir: str,
    files: List[str],
    sftp: Any,
    target_root: str,
    dry_run: bool,
    max_depth: int = 5,
    current_depth: int = 1,
    recursive: bool = True
) -> None:
    # project_name = os.path.basename(os.path.abspath(source_dir))
    logger.info(f"Syncing {len(files)} files via SFTP to {target_root}")
    
    if not files:
        logger.info("No files to sync")
        return
    
    if current_depth > max_depth:
        logger.warning(f"Maximum recursion depth {max_depth} reached")
        return
    
    synced_count = 0
    failed_count = 0
    
    for file_path in files:
        try:
            # Get relative path from source directory
            abs_file_path = os.path.join(source_dir, file_path)
            if not os.path.exists(abs_file_path):
                logger.warning(f"File not found: {abs_file_path}")
                continue
            
            # Create target path
            target_path = f"{target_root}/{file_path}"
            target_dir = os.path.dirname(target_path)
            
            if not dry_run:
                # Ensure target directory exists
                try:
                    ensure_remote_dir(sftp, target_dir)
                except Exception as e:
                    logger.error(f"Failed to ensure target directory {target_dir}: {e}")
                    failed_count += 1
                    continue
                
                # Upload file
                try:
                    sftp.put(abs_file_path, target_path)
                    synced_count += 1
                    logger.debug(f"Uploaded: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")
                    failed_count += 1
            else:
                console.print(f"[cyan]Would upload: {file_path} -> {target_path}[/cyan]")
                synced_count += 1
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            failed_count += 1
    
    logger.info(f"SFTP sync completed: {synced_count} files synced, {failed_count} failed")


def fix_target_root_path(target_root: str) -> str:
    # 检查是否被 git bash 转换成了 /c/Program Files/Git/xxx 或 C:/Program Files/Git/xxx 这种格式
    m = re.match(r'^(/[a-zA-Z]|[A-Z]:)/Program Files/Git(/.*)$', target_root)
    if m:
        # 还原为 /xxx
        return m.group(2)
    return target_root


@okit_tool("gitdiffsync", "Git project synchronization tool", use_subcommands=False)
class GitDiffSync(BaseTool):
    """Git 项目同步工具"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
Git Diff Sync Tool - Synchronize Git project folders to remote Linux server.

This tool synchronizes changed files from Git repositories to remote servers:
• Detects changed files in Git repositories
• Supports both rsync and SFTP transfer methods
• Automatic directory structure verification
• Dry-run mode for testing
• Progress reporting and error handling

Use 'gitdiffsync --help' to see available commands.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Synchronize Git project folders to remote Linux server"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""
        # Add as main command (no subcommand)
        @cli_group.command()
        @click.option(
            '-s', '--source-dirs', multiple=True, required=True,
            help='Source directories to sync (must be Git repositories)'
        )
        @click.option('--host', required=True, help='Target host address')
        @click.option('--port', type=int, default=22, show_default=True, help='SSH port number')
        @click.option('--user', required=True, help='SSH username')
        @click.option('--target-root', required=True, help='Target root directory on remote server')
        @click.option('--dry-run', is_flag=True, help='Show what would be transferred without actual transfer')
        @click.option('--max-depth', type=int, default=5, show_default=True, help='Maximum recursion depth for directory sync')
        @click.option('--recursive/--no-recursive', default=True, show_default=True, help='Enable or disable recursive directory sync')
        def main(source_dirs, host, port, user, target_root, dry_run, max_depth, recursive):
            """Synchronize Git project folders to remote Linux server."""
            self._execute_sync(source_dirs, host, port, user, target_root, dry_run, max_depth, recursive)

    def _execute_sync(self, source_dirs, host, port, user, target_root, dry_run, max_depth, recursive):
        """Execute the sync operation"""
        try:
            self.logger.info(f"Executing sync command, source_dirs: {source_dirs}, host: {host}")
            
            import paramiko
            from paramiko.ssh_exception import AuthenticationException, SSHException
            target_root = fix_target_root_path(target_root)

            self.logger.debug(f"Source directories: {source_dirs}")
            self.logger.debug(f"Target root: {target_root}")

            if dry_run:
                self.logger.info("Running in dry-run mode")

            self.logger.debug("Verifying Git repositories...")
            for directory in source_dirs:
                if not check_git_repo(directory):
                    console.print(f"[red]Error: {directory} is not a Git repository[/red]")
                    sys.exit(1)
                else:
                    self.logger.debug(f"Git repository verified: {directory}")

            self.logger.debug(f"Setting up SSH connection to {host}...")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            sftp = None
            try:
                try:
                    ssh.connect(
                        host,
                        port=port,
                        username=user
                    )
                    self.logger.info("SSH connection established successfully")
                except AuthenticationException as e:
                    console.print(f"[red]SSH authentication failed: {str(e)}[/red]")
                    sys.exit(1)
                except SSHException as e:
                    console.print(f"[red]SSH protocol error: {str(e)}[/red]")
                    sys.exit(1)
                except socket.error as e:
                    console.print(f"[red]SSH network error: {str(e)}[/red]")
                    sys.exit(1)
                except Exception as e:
                    console.print(f"[red]SSH connection failed: {str(e)}[/red]")
                    sys.exit(1)

                # Verify directory structure
                if not verify_directory_structure(source_dirs, target_root, ssh):
                    console.print("[red]Error: Required target directories do not exist[/red]")
                    sys.exit(1)

                # Determine sync method
                use_rsync = check_rsync_available()
                if not use_rsync:
                    try:
                        sftp = ssh.open_sftp()
                    except SSHException as e:
                        console.print(f"[red]Failed to open SFTP session: {str(e)}[/red]")
                        sys.exit(1)
                    except Exception as e:
                        console.print(f"[red]Unknown error opening SFTP session: {str(e)}[/red]")
                        sys.exit(1)
                else:
                    sftp = None

                # Process each source directory
                for directory in source_dirs:
                    try:
                        self.logger.info(f"Processing directory: {directory}")
                        changes = get_git_changes(directory)
                        if not changes:
                            self.logger.info(f"No changes in {directory}")
                            continue

                        self.logger.info(f"Synchronizing {directory}...")
                        if use_rsync:
                            sync_via_rsync(
                                directory,
                                changes,
                                f"{user}@{host}:{target_root}",
                                dry_run
                            )
                        else:
                            sync_via_sftp(
                                directory,
                                changes,
                                sftp,
                                target_root,
                                dry_run,
                                max_depth,
                                1,
                                recursive
                            )

                    except Exception as e:
                        self.logger.error(f"Error processing {directory}: {e}")
                        console.print(f"[red]Error processing {directory}: {e}[/red]")
                        continue

            finally:
                if sftp:
                    sftp.close()
                ssh.close()

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            console.print(f"[red]Unexpected error: {e}[/red]")
            sys.exit(1)

    def validate_config(self) -> bool:
        """验证配置"""
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """自定义清理逻辑"""
        self.logger.info("Executing custom cleanup logic")
        pass
