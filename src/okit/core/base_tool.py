import click
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Union
import shutil
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ruamel.yaml import YAML  # type-only import

from okit.utils.log import output


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
        self.use_subcommands: bool = True

        # Initialize config and data directories
        self._init_config_data()

        # YAML instance, created on demand
        self._yaml: Optional[YAML] = None

    def _init_config_data(self) -> None:
        """Initialize config and data directories"""
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
            drive, rest = path_str.split(":", 1)
            rest_unix = rest.replace("\\", "/")
            unix_path = f"/{drive.lower()}{rest_unix}"
            return unix_path
        elif path_str.startswith("/"):  # Unix-style path
            return path_str
        else:  # Other paths
            return path_str.replace("\\", "/")

    def _is_git_bash(self) -> bool:
        """Detect if running in git bash environment"""
        import os

        msystem = os.environ.get("MSYSTEM", "")
        if msystem not in ["MINGW32", "MINGW64"]:
            return False

        shell = os.environ.get("SHELL", "")
        if shell and not shell.endswith("bash"):
            return False

        home = os.environ.get("HOME", "")
        if home and ":" in home and "\\" in home:
            return True

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

    def _get_yaml(self) -> "YAML":
        """Get YAML instance, create on demand with lazy import"""
        if self._yaml is None:
            from ruamel.yaml import YAML

            self._yaml = YAML()
            self._yaml.preserve_quotes = True
            self._yaml.indent(mapping=2, sequence=4, offset=2)
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
            output.debug(f"Config file does not exist: {config_file}")
            return default_config.copy()

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = self._get_yaml().load(f) or {}

            output.debug(f"Successfully loaded config file: {config_file}")
            return config if config else default_config.copy()
        except Exception as e:
            output.error(f"Failed to load config file: {config_file}, Error: {e}")
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
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w", encoding="utf-8") as f:
                self._get_yaml().dump(config, f)

            output.debug(f"Successfully saved config file: {config_file}")
            return True
        except Exception as e:
            output.error(f"Failed to save config file: {config_file}, Error: {e}")
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

        keys = key.split(".")
        current = config

        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

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
            output.debug(f"Config file backed up: {backup_file}")
            return backup_file
        except Exception as e:
            output.error(f"Failed to backup config file: {e}")
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
            with open(backup_path, "r", encoding="utf-8") as f:
                backup_content = self._get_yaml().load(f)

            if config_file.exists():
                self.backup_config()

            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                self._get_yaml().dump(backup_content, f)

            with open(config_file, "r", encoding="utf-8") as f:
                restored_content = self._get_yaml().load(f)

            if backup_content != restored_content:
                output.error("Config file restore verification failed")
                return False

            output.debug(f"Config file restored: {config_file}")
            return True
        except Exception as e:
            output.error(f"Failed to restore config file: {e}")
            return False

    def create_cli_group(
        self, tool_name: str = "", description: str = ""
    ) -> Union[click.Group, click.Command]:
        """
        Create Click command group for tool

        This is a key method ensuring compatibility with auto-registration mechanism
        """
        if not tool_name:
            tool_name = self.tool_name
        if not description:
            description = self.description

        use_subcommands = getattr(self, "use_subcommands", True)

        if use_subcommands:
            @click.group(name=tool_name)
            def cli() -> None:
                """Tool CLI entry point"""
                pass

            cli.help = self._get_cli_help()
            cli.short_help = self._get_cli_short_help()

            self._add_cli_commands(cli)

            return cli
        else:
            # Non-subcommand mode: collect commands via a temporary group,
            # then extract the first command as the tool's direct command.
            @click.group()
            def collector() -> None:
                pass

            self._add_cli_commands(collector)

            if collector.commands:
                main_command = list(collector.commands.values())[0]
                main_command.name = tool_name
                main_command.help = self._get_cli_help()
                main_command.short_help = self._get_cli_short_help()
                return main_command

            # No commands registered — return a no-op command
            @click.command(name=tool_name, help=self._get_cli_help())
            def noop() -> None:
                pass

            noop.short_help = self._get_cli_short_help()
            return noop

    @abstractmethod
    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """
        Subclasses must implement this method to add tool-specific CLI commands

        Args:
            cli_group: Click command group for adding subcommands
        """
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
