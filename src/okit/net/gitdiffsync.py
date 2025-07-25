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
from okit.utils.log import logger

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
    
    # Check if each remote directory exists
    for rel_dir in source_dirs:
        logger.debug(f"Verifying target directory {rel_dir} exists...")
        remote_path = os.path.join(remote_root, rel_dir).replace('\\', '/')
        stdin, stdout, stderr = ssh_client.exec_command(f'test -d {remote_path} && echo "exists"')
        result = stdout.read().decode().strip()
        
        if result != "exists":
            logger.error(f"Target directory {remote_path} does not exist")
            return False
        logger.debug(f"Target directory {remote_path} exists")
    
    return True


def ensure_remote_dir(sftp: Any, remote_directory):
    """递归创建远程目录（如不存在），并检查创建结果。"""
    dirs = []
    while remote_directory not in ('/', ''):
        dirs.append(remote_directory)
        remote_directory = os.path.dirname(remote_directory)
    dirs.reverse()
    for d in dirs:
        try:
            sftp.stat(d)
        except FileNotFoundError:
            try:
                logger.info(f"Creating remote directory: {d}")
                sftp.mkdir(d)
                # 创建后立即检查
                try:
                    sftp.stat(d)
                except Exception as stat_e:
                    logger.error(f"Directory {d} creation failed to verify: {stat_e}")
                    raise Exception(f"Remote directory {d} creation failed to verify: {stat_e}")
            except PermissionError as e:
                logger.error(f"Permission denied creating remote directory {d}: {str(e)}")
                raise Exception(f"Permission denied creating remote directory {d}: {str(e)}")
            except OSError as e:
                logger.error(f"OS error creating remote directory {d}: {str(e)}")
                raise Exception(f"OS error creating remote directory {d}: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to create remote directory {d}: {str(e)}")
                raise Exception(f"Failed to create remote directory {d}: {str(e)}")


def sync_via_rsync(
    source_dir: str,
    files: List[str],
    target: str,
    dry_run: bool
) -> None:
    # project_name = os.path.basename(os.path.abspath(source_dir))
    project_name = source_dir
    logger.info(f"Synchronizing {len(files)} files via rsync...")
    for file in files:
        source_path = os.path.join(source_dir, file)
        # 先处理 file 路径
        file_unix = file.replace('\\', '/')
        target_path = f"{target}/{project_name}/{file_unix}"
        logger.info(f"Syncing file: {source_path} -> {target_path}")
        cmd = ['rsync', '-avz']
        if dry_run:
            cmd.append('--dry-run')
            logger.info("Dry run mode enabled")
        cmd.extend([source_path, target_path])
    logger.debug(f"Running rsync command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Rsync failed: {result.stderr}")
        raise SyncError(f"Rsync failed: {result.stderr}")
        logger.info(f"Rsync completed for {file}")
        logger.debug(result.stdout)


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
    project_name = source_dir
    logger.info(f"Synchronizing {len(files)} files via SFTP... (depth {current_depth})")
    if current_depth > max_depth:
        logger.error(f"Maximum recursion depth {max_depth} exceeded at {source_dir}")
        raise SyncError(f"Maximum recursion depth {max_depth} exceeded at {source_dir}")
    for file in files:
        source_path = os.path.join(source_dir, file).replace('\\', '/')
        file_unix = file.replace('\\', '/')
        target_path = os.path.join(target_root, project_name, file_unix).replace('\\', '/')
        target_dir = os.path.dirname(target_path)
        if os.path.isdir(source_path):
            logger.info(f"Syncing directory: {source_path} -> {target_path}")
            try:
                ensure_remote_dir(sftp, target_path)
                if not dry_run and recursive:
                    # 获取子目录下所有内容的相对路径列表
                    sub_files = []
                    for root, dirs, files_in_dir in os.walk(source_path):
                        for f in files_in_dir:
                            local_file = os.path.join(root, f)
                            rel_file = os.path.relpath(local_file, source_dir).replace('\\', '/')
                            sub_files.append(rel_file)
                    if sub_files:
                        sync_via_sftp(source_dir, sub_files, sftp, target_root, dry_run, max_depth, current_depth + 1, recursive)
            except Exception as e:
                logger.error(f"SFTP directory sync failed for {file}: {str(e)}")
                raise SyncError(f"SFTP directory sync failed for {file}: {str(e)}")
        else:
            logger.info(f"Syncing file: {source_path} -> {target_path}")
            if dry_run:
                logger.info(f"Would copy {source_path} to {target_path}")
            else:
                try:
                    ensure_remote_dir(sftp, target_dir)
                    logger.debug(f"Copying {source_path} to {target_path}")
                    sftp.put(source_path, target_path)
                    logger.info(f"Successfully copied {file}")
                except Exception as e:
                    logger.error(f"SFTP transfer failed for {file}: {str(e)}")
                    raise SyncError(f"SFTP transfer failed for {file}: {str(e)}")


def fix_target_root_path(target_root: str) -> str:
    # 检查是否被 git bash 转换成了 /c/Program Files/Git/xxx 或 C:/Program Files/Git/xxx 这种格式
    m = re.match(r'^(/[a-zA-Z]|[A-Z]:)/Program Files/Git(/.*)$', target_root)
    if m:
        # 还原为 /xxx
        return m.group(2)
    return target_root


@click.command()
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
def cli(source_dirs, host, port, user, target_root, dry_run, max_depth, recursive):
    import paramiko
    from paramiko.ssh_exception import AuthenticationException, SSHException
    """Synchronize Git project folders to remote Linux server."""
    target_root = fix_target_root_path(target_root)

    logger.debug(f"Source directories: {source_dirs}")
    logger.debug(f"Target root: {target_root}")

    if dry_run:
        logger.info("Running in dry-run mode")

    logger.debug("Verifying Git repositories...")
    for directory in source_dirs:
        if not check_git_repo(directory):
            logger.error(f"Error: {directory} is not a Git repository")
            sys.exit(1)
        else:
            logger.debug(f"Git repository verified: {directory}")

    logger.debug(f"Setting up SSH connection to {host}...")
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
            logger.info("SSH connection established successfully")
        except AuthenticationException as e:
            logger.error(f"SSH authentication failed: {str(e)}")
            sys.exit(1)
        except SSHException as e:
            logger.error(f"SSH protocol error: {str(e)}")
            sys.exit(1)
        except socket.error as e:
            logger.error(f"SSH network error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"SSH connection failed: {str(e)}")
            sys.exit(1)

        # Verify directory structure
        if not verify_directory_structure(source_dirs, target_root, ssh):
            logger.error("Error: Required target directories do not exist")
            sys.exit(1)

        # Determine sync method
        use_rsync = check_rsync_available()
        if not use_rsync:
            try:
                sftp = ssh.open_sftp()
            except SSHException as e:
                logger.error(f"Failed to open SFTP session: {str(e)}")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Unknown error opening SFTP session: {str(e)}")
                sys.exit(1)
        else:
            sftp = None

        # Process each source directory
        for directory in source_dirs:
            try:
                logger.info(f"Processing directory: {directory}")
                changes = get_git_changes(directory)
                if not changes:
                    logger.info(f"No changes in {directory}")
                    continue

                logger.info(f"Synchronizing {directory}...")
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

            except SyncError as e:
                logger.error(f"Error synchronizing {directory}: {str(e)}")
                sys.exit(1)

        logger.info("Synchronization completed successfully")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

    finally:
        logger.debug("Cleaning up connections...")
        if sftp:
            sftp.close()
        ssh.close()
        logger.debug("Script finished")

if __name__ == "__main__":
    cli()
