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
from typing import List
import re

import paramiko
import click


from okit.utils.log import logger


class SyncError(Exception):
    """Custom exception for sync related errors."""
    pass


def check_git_repo(directory: str) -> bool:
    """Check if directory is a Git repository."""
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
    ssh_client: paramiko.SSHClient
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
    sftp: paramiko.SFTPClient,
    target_root: str,
    dry_run: bool
) -> None:
    # project_name = os.path.basename(os.path.abspath(source_dir))
    project_name = source_dir
    logger.info(f"Synchronizing {len(files)} files via SFTP...")
    for file in files:
        source_path = os.path.join(source_dir, file).replace('\\', '/')
        file_unix = file.replace('\\', '/')
        target_path = os.path.join(target_root, project_name, file_unix).replace('\\', '/')
        logger.info(f"Syncing file: {source_path} -> {target_path}")
        if dry_run:
            logger.info(f"Would copy {source_path} to {target_path}")
        else:
            try:
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
def cli(source_dirs, host, port, user, target_root, dry_run):
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
        ssh.connect(
            host,
            port=port,
            username=user
        )
        logger.info("SSH connection established successfully")

        # Verify directory structure
        if not verify_directory_structure(source_dirs, target_root, ssh):
            logger.error("Error: Required target directories do not exist")
            sys.exit(1)

        # Determine sync method
        use_rsync = check_rsync_available()
        sftp = None if use_rsync else ssh.open_sftp()

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
                        dry_run
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
