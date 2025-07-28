import click
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Union, Type, List
import json
import logging
from datetime import datetime
import shutil
from ruamel.yaml import YAML


class BaseTool(ABC):
    """
    Base class for okit tools based on Click CLI

    Provides common functionality for all tools while maintaining compatibility with existing auto-registration mechanism
    """

    def __init__(self, tool_name: str, description: str = ""):
        """
        Initialize base tool

        Args:
            tool_name: Tool name for identification
            description: Tool description
        """
        self.tool_name = tool_name
        self.description = description

        # Initialize managers
        self._init_managers()

        # Initialize config and data directories
        self._init_config_data()

        # Tool lifecycle
        self._start_time = datetime.now()

        # YAML instance, created on demand
        self._yaml: Optional[YAML] = None

    def _init_managers(self) -> None:
        """Initialize various managers"""
        from okit.utils.log import console
        from okit.utils.log import logger

        self.logger = logger
        self.console = console

    def _init_config_data(self) -> None:
        """Initialize config and data directories"""
        # Ensure base directories exist
        self._ensure_dir(self._get_okit_root_dir())
        self._ensure_dir(self._get_tool_config_dir())
        self._ensure_dir(self._get_tool_data_dir())

    def is_git_bash(self) -> bool:
        """Check if running in git bash environment (public method for tools)"""
        return self._is_git_bash()

    def convert_to_git_bash_path(self, path: Path) -> str:
        """Convert Windows path to git bash compatible path (public method for tools)"""
        if not self._is_git_bash():
            return str(path)

        # Convert Windows path to Unix style for git bash
        path_str = str(path)
        if ":" in path_str and "\\" in path_str:  # Windows path like C:\Users\...
            # Convert C:\Users\... to /c/Users/...
            drive, rest = path_str.split(":", 1)
            unix_path = f"/{drive.lower()}{rest.replace('\\', '/')}"
            return unix_path

        return path_str

    def _is_git_bash(self) -> bool:
        """Detect if running in git bash environment"""
        import os

        # 1. Check MSYSTEM environment variable
        msystem = os.environ.get("MSYSTEM", "")
        if msystem not in ["MINGW32", "MINGW64"]:
            return False

        # 2. Check SHELL environment variable (optional, may not exist in git bash)
        shell = os.environ.get("SHELL", "")
        if shell and not shell.endswith("bash"):
            return False

        # 3. Check for Windows path mapping feature using environment variables
        # In git bash, we can check for specific environment variables that indicate Windows path mapping
        home = os.environ.get("HOME", "")

        # Check if HOME contains Windows path (like C:\Users\...)
        if home and ":" in home and "\\" in home:
            return True

        # Alternative: check for git bash specific environment variables
        ostype = os.environ.get("OSTYPE", "")
        if ostype.startswith("msys"):
            return True

        return False

    def _get_okit_root_dir(self) -> Path:
        """Get okit root directory (~/.okit/)"""
        return Path.home() / ".okit"

    def _get_tool_config_dir(self) -> Path:
        """Get tool config directory (~/.okit/config/{tool_name}/)"""
        return self._get_okit_root_dir() / "config" / self.tool_name

    def _get_tool_data_dir(self) -> Path:
        """Get tool data directory (~/.okit/data/{tool_name}/)"""
        return self._get_okit_root_dir() / "data" / self.tool_name

    def _ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists, return directory path"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_yaml(self) -> YAML:
        """Get YAML instance, create on demand"""
        if self._yaml is None:
            self._yaml = YAML()
            self._yaml.preserve_quotes = True
            self._yaml.indent(mapping=2, sequence=4, offset=2)
        assert self._yaml is not None
        return self._yaml

    # ===== Configuration Management Interface =====

    def get_config_path(self) -> Path:
        """Get tool config directory path"""
        return self._get_tool_config_dir()

    def get_config_file(self) -> Path:
        """Get config file path (defaults to config.yaml)"""
        return self._get_tool_config_dir() / "config.yaml"

    def load_config(self, default: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Load configuration file

        Args:
            default: Default configuration, used if file doesn't exist

        Returns:
            Dict: Configuration dictionary
        """
        config_file = self.get_config_file()
        default_config = default or {}

        if not config_file.exists():
            self.logger.info(
                f"Config file does not exist, using default config: {config_file}"
            )
            return default_config.copy()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = self._get_yaml().load(f) or {}

            self.logger.info(f"Successfully loaded config file: {config_file}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load config file: {config_file}, Error: {e}")
            return default_config.copy()

    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration file

        Args:
            config: Configuration dictionary to save

        Returns:
            bool: Whether save was successful
        """
        config_file = self.get_config_file()

        try:
            # Ensure directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w", encoding="utf-8") as f:
                self._get_yaml().dump(config, f)

            self.logger.info(f"Successfully saved config file: {config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config file: {config_file}, Error: {e}")
            return False

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key, supports dot-separated nested keys (e.g., "database.host")
            default: Default value

        Returns:
            Any: Configuration value
        """
        config = self.load_config()

        # Handle nested keys
        keys = key.split(".")
        value = config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set_config_value(self, key: str, value: Any) -> bool:
        """
        Set configuration value

        Args:
            key: Configuration key, supports dot-separated nested keys
            value: Configuration value

        Returns:
            bool: Whether setting was successful
        """
        config = self.load_config()

        # Handle nested keys
        keys = key.split(".")
        current = config

        # Create nested structure
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        # Set value
        current[keys[-1]] = value

        return self.save_config(config)

    def has_config(self) -> bool:
        """Check if configuration file exists"""
        return self.get_config_file().exists()

    # ===== Data Management Interface =====

    def get_data_path(self) -> Path:
        """Get tool data directory path"""
        return self._get_tool_data_dir()

    def get_data_file(self, *path_parts: str) -> Path:
        """
        Get data file path

        Args:
            *path_parts: Path parts, e.g., ("cache", "temp", "file.txt")

        Returns:
            Path: Complete data file path
        """
        return self._get_tool_data_dir().joinpath(*path_parts)

    def ensure_data_dir(self, *path_parts: str) -> Path:
        """
        Ensure data directory exists

        Args:
            *path_parts: Directory path parts

        Returns:
            Path: Created directory path
        """
        data_dir = self._get_tool_data_dir().joinpath(*path_parts)
        return self._ensure_dir(data_dir)

    def cleanup_data(self, *path_parts: str) -> bool:
        """
        Clean up data directory or file

        Args:
            *path_parts: Path parts to clean up

        Returns:
            bool: Whether cleanup was successful
        """
        target_path = self._get_tool_data_dir().joinpath(*path_parts)

        try:
            if target_path.exists():
                if target_path.is_file():
                    target_path.unlink()
                else:
                    shutil.rmtree(target_path)
                self.logger.info(f"Successfully cleaned data: {target_path}")
                return True
            return True
        except Exception as e:
            self.logger.error(f"Failed to clean data: {target_path}, Error: {e}")
            return False

    def list_data_files(self, *path_parts: str) -> List[Path]:
        """
        List files in data directory

        Args:
            *path_parts: Directory path parts

        Returns:
            List[Path]: List of file paths
        """
        target_dir = self._get_tool_data_dir().joinpath(*path_parts)

        if not target_dir.exists() or not target_dir.is_dir():
            return []

        try:
            return list(target_dir.iterdir())
        except Exception as e:
            self.logger.error(f"Failed to list data files: {target_dir}, Error: {e}")
            return []

    # ===== Advanced Features =====

    def backup_config(self) -> Optional[Path]:
        """
        Backup configuration file

        Returns:
            Optional[Path]: Backup file path, None if backup failed
        """
        config_file = self.get_config_file()

        if not config_file.exists():
            return None

        try:
            backup_dir = self.get_data_path() / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"config.yaml.{timestamp}.bak"

            shutil.copy2(config_file, backup_file)
            self.logger.info(f"Config file backed up: {backup_file}")
            return backup_file
        except Exception as e:
            self.logger.error(f"Failed to backup config file: {e}")
            return None

    def restore_config(self, backup_path: Path) -> bool:
        """
        Restore configuration file from backup

        Args:
            backup_path: Backup file path

        Returns:
            bool: Whether restore was successful
        """
        config_file = self.get_config_file()

        try:
            # Backup current config first
            if config_file.exists():
                self.backup_config()

            # Restore config
            config_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, config_file)

            self.logger.info(f"Config file restored: {config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore config file: {e}")
            return False

    def migrate_config(self, old_version: str, new_version: str) -> bool:
        """
        Migrate configuration (subclasses can override)

        Args:
            old_version: Old version number
            new_version: New version number

        Returns:
            bool: Whether migration was successful
        """
        self.logger.info(f"Config migration: {old_version} -> {new_version}")
        return True

    def create_cli_group(
        self, tool_name: str = "", description: str = ""
    ) -> Union[click.Group, click.Command]:
        """
        Create Click command group for tool

        This is a key method ensuring compatibility with auto-registration mechanism
        """
        # Use instance attributes if not provided
        if not tool_name:
            tool_name = self.tool_name
        if not description:
            description = self.description

        use_subcommands = getattr(self, "use_subcommands", True)

        if use_subcommands:
            # Create subcommand group
            @click.group()
            def cli() -> None:
                """Tool CLI entry point"""
                pass

            # Set CLI help information
            cli.help = self._get_cli_help()
            cli.short_help = self._get_cli_short_help()

            # Add tool-specific commands
            self._add_cli_commands(cli)

            return cli
        else:
            # Create direct command (no subcommands)
            # We need to create a command that can be called directly
            # We'll create a temporary group to add the command, then return the command itself

            @click.group()
            def temp_group() -> None:
                """Temporary group for command creation"""
                pass

            # Add tool-specific commands to the temporary group
            self._add_cli_commands(temp_group)

            # Get the first command from the temporary group
            if temp_group.commands:
                main_command = list(temp_group.commands.values())[0]
                # Set the command name to the tool name
                main_command.name = tool_name
                main_command.help = self._get_cli_help()
                main_command.short_help = self._get_cli_short_help()
                return main_command
            else:
                # Fallback: create a simple command
                @click.command()
                def fallback_command() -> None:
                    """Fallback command"""
                    pass

                fallback_command.name = tool_name
                fallback_command.help = self._get_cli_help()
                fallback_command.short_help = self._get_cli_short_help()
                return fallback_command

    @abstractmethod
    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """
        Subclasses must implement this method to add tool-specific CLI commands

        Args:
            cli_group: Click command group for adding subcommands
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate tool configuration

        Returns:
            bool: Whether configuration is valid
        """
        pass

    def get_tool_info(self) -> Dict[str, Any]:
        """Get tool information"""
        return {
            "name": self.tool_name,
            "description": self.description,
            "start_time": self._start_time.isoformat(),
            "config_path": str(self.get_config_path()),
            "data_path": str(self.get_data_path()),
        }

    def cleanup(self) -> None:
        """Tool cleanup work"""
        self.logger.info(f"Tool {self.tool_name} is cleaning up")
        self._cleanup_impl()

    def _cleanup_impl(self) -> None:
        """Cleanup implementation that subclasses can override"""
        pass

    def _get_cli_help(self) -> str:
        """
        Get CLI help information

        Subclasses can override this method to provide custom help information

        Returns:
            str: CLI help information
        """
        return self.description or f"{self.tool_name} tool"

    def _get_cli_short_help(self) -> str:
        """
        Get CLI short help information

        Subclasses can override this method to provide custom short help information

        Returns:
            str: CLI short help information
        """
        return self.description or self.tool_name
