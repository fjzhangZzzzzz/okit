"""
MobaXterm Color Scheme Management Tool

This tool provides functionality to manage MobaXterm color schemes by:
- Auto-detecting MobaXterm.ini configuration file
- Downloading and applying color schemes from iTerm2-Color-Schemes repository
- Managing local cache for offline usage
- Supporting both automatic and manual cache updates
"""

import os
import re
import shutil
import configparser
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool
from okit.utils.log import output
from okit.utils.mobaxterm_detector import MobaXtermDetector

console = Console()


@okit_tool(
    "mobaxterm-colors", "MobaXterm color scheme management tool", use_subcommands=True
)
class MobaXtermColors(BaseTool):
    """MobaXterm color scheme management tool"""
    
    # GitHub repository information
    REPO_URL = "https://github.com/mbadolato/iTerm2-Color-Schemes"
    MOBAXTERM_DIR = "mobaxterm"
    
    def __init__(self, tool_name: str = "mobaxterm-colors", description: str = "MobaXterm color scheme management tool"):
        super().__init__(tool_name, description)
        self._ensure_cache_dir()
        self.detector = MobaXtermDetector()
        
        # Auto-initialize cache if needed
        self._auto_init_cache()
    
    def _auto_init_cache(self):
        """Auto-initialize cache if it doesn't exist or is invalid"""
        cache_path = self._get_cache_path()
        
        # Check if auto-update is enabled
        auto_update = self.get_config_value("auto_update", False)
        
        if not cache_path.exists():
            if auto_update:
                output.info("Auto-initializing cache...")
                self._update_cache()
            else:
                output.debug("Cache not found, auto-update disabled")
            return
        
        # Check if existing cache is valid
        if not self._is_valid_git_repo(cache_path):
            if auto_update:
                output.warning("Cache exists but is invalid. Auto-reinitializing...")
                self._update_cache()
            else:
                output.debug("Cache exists but is invalid, auto-update disabled")
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        cache_dir = self.get_data_file("cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _add_cli_commands(self, cli_group):
        """Add CLI commands"""
        
        @cli_group.command()
        @click.option('--scheme', required=True, help='Color scheme name')
        @click.option('--force', is_flag=True, help='Force apply without confirmation')
        @click.option('--backup', is_flag=True, default=True, help='Create backup before applying')
        def apply(scheme: str, force: bool, backup: bool):
            """Apply a color scheme to MobaXterm"""
            self._apply_scheme(scheme, force, backup)
        
        @cli_group.command()
        @click.option('--search', help='Search for schemes containing this text')
        @click.option('--limit', default=20, help='Maximum number of schemes to display')
        def list(search: Optional[str], limit: int):
            """List available color schemes"""
            self._list_schemes(search, limit)
        
        @cli_group.command()
        @click.option('--update', is_flag=True, help='Update local cache')
        @click.option('--clean', is_flag=True, help='Clean local cache')
        @click.option('--sync', is_flag=True, help='Sync cache (update if needed)')
        def cache(update: bool, clean: bool, sync: bool):
            """Manage local cache"""
            if update:
                self._update_cache()
            elif clean:
                self._clean_cache()
            elif sync:
                self._sync_cache()
            else:
                self._show_cache_status()
        
        @cli_group.command()
        def status():
            """Show current status and configuration"""
            self._show_status()
        
        @cli_group.command()
        @click.argument('key', required=False)
        @click.argument('value', required=False)
        @click.option('--list', 'list_config', is_flag=True, help='List all configuration')
        @click.option('--unset', help='Unset a configuration key')
        def config(key: Optional[str], value: Optional[str], list_config: bool, unset: str):
            """Configure tool settings (similar to git config)
            
            Examples:
              okit mobaxterm-colors config auto-update true
              okit mobaxterm-colors config mobaxterm_config_path /path/to/config.ini
              okit mobaxterm-colors config --list
              okit mobaxterm-colors config --unset auto-update
            """
            if list_config:
                self._list_config()
            elif unset:
                self._unset_config(unset)
            elif key and value is not None:
                self._set_config(key, value)
            elif key:
                self._get_config(key)
            else:
                self._list_config()
    
    def _set_config(self, key: str, value: str):
        """Set a configuration value"""
        # Convert string values to appropriate types
        if value.lower() in ('true', 'false'):
            bool_value = value.lower() == 'true'
            self.set_config_value(key, bool_value)
            output.success(f"Set {key} = {bool_value}")
        else:
            self.set_config_value(key, value)
            output.success(f"Set {key} = {value}")
    
    def _get_config(self, key: str):
        """Get a configuration value"""
        value = self.get_config_value(key)
        if value is not None:
            output.result(f"{key}: {value}")
        else:
            output.warning(f"Configuration key '{key}' not found")
    
    def _unset_config(self, key: str):
        """Unset a configuration value"""
        config_data = self.load_config()
        if key in config_data:
            del config_data[key]
            self.save_config(config_data)
            output.success(f"Unset {key}")
        else:
            output.warning(f"Configuration key '{key}' not found")
    
    def _list_config(self):
        """List all configuration"""
        config_data = self.load_config()
        if config_data:
            output.info("Configuration:")
            for key, value in sorted(config_data.items()):
                output.result(f"  {key}: {value}")
        else:
            output.info("No configuration found")
    
    def _get_mobaxterm_config_path(self) -> Optional[Path]:
        """Auto-detect MobaXterm.ini configuration file path"""
        # Check if user specified a custom path
        custom_path = self.get_config_value("mobaxterm_config_path")
        if custom_path:
            custom_path = Path(custom_path)
            if custom_path.exists():
                return custom_path
            else:
                output.warning(f"Specified config path does not exist: {custom_path}")
        
        # Use detector to find installation and get config path
        installation_info = self.detector.detect_installation()
        if installation_info:
            install_path = installation_info["install_path"]
            config_path = self.detector.get_config_file_path(install_path)
            if config_path:
                return Path(config_path)
        
        # Fallback to default paths if detection fails
        possible_paths = [
            Path(os.environ.get('APPDATA', '')) / 'Mobatek' / 'MobaXterm' / 'MobaXterm.ini',
            Path.home() / 'AppData' / 'Roaming' / 'Mobatek' / 'MobaXterm' / 'MobaXterm.ini',
            Path.home() / 'Documents' / 'MobaXterm' / 'MobaXterm.ini',
        ]
        
        # Try to find existing configuration file
        for path in possible_paths:
            if path.exists():
                output.info(f"Found MobaXterm.ini at: {path}")
                return path
        
        # If not found, return the most likely default path
        default_path = possible_paths[0]
        output.warning(f"MobaXterm.ini not found. Will create at: {default_path}")
        return default_path
    
    def _get_cache_path(self) -> Path:
        """Get local cache directory path"""
        return self.get_data_file("cache", "iterm2-color-schemes")
    
    def _get_backup_path(self) -> Path:
        """Get backup directory path"""
        return self.get_data_file("backups")
    
    def _update_cache(self):
        """Update local cache from GitHub repository"""
        cache_path = self._get_cache_path()
        
        try:
            import git
        except ImportError:
            output.error("gitpython is required for cache operations. Install with: pip install gitpython")
            return
        
        try:
            if cache_path.exists():
                # Check if it's a valid git repository
                try:
                    repo = git.Repo(cache_path)
                    # Verify it's the correct repository
                    origin_url = repo.remotes.origin.url
                    if self.REPO_URL not in origin_url:
                        output.warning("Cache directory exists but is not the correct repository")
                        output.info("Removing existing cache and re-cloning...")
                        shutil.rmtree(cache_path)
                        git.Repo.clone_from(self.REPO_URL, cache_path)
                        output.success("Cache recreated successfully")
                    else:
                        output.info("Updating existing cache...")
                        origin = repo.remotes.origin
                        origin.pull()
                        output.success("Cache updated successfully")
                except (git.InvalidGitRepositoryError, AttributeError):
                    # Not a git repository or missing origin
                    output.warning("Cache directory exists but is not a valid git repository")
                    output.info("Removing existing cache and re-cloning...")
                    shutil.rmtree(cache_path)
                    git.Repo.clone_from(self.REPO_URL, cache_path)
                    output.success("Cache recreated successfully")
            else:
                output.info("Cloning repository to cache...")
                git.Repo.clone_from(self.REPO_URL, cache_path)
                output.success("Cache created successfully")
                
        except Exception as e:
            output.error(f"Failed to update cache: {e}")
            return
    
    def _clean_cache(self):
        """Clean local cache"""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            shutil.rmtree(cache_path)
            output.success("Cache cleaned successfully")
        else:
            output.info("Cache is already clean")
    
    def _sync_cache(self):
        """Sync cache - update if needed or initialize if missing"""
        cache_path = self._get_cache_path()
        
        if not cache_path.exists():
            output.info("Cache not found. Initializing...")
            self._update_cache()
            return
        
        if not self._is_valid_git_repo(cache_path):
            output.warning("Cache exists but is not a valid git repository. Reinitializing...")
            self._update_cache()
            return
        
        # Check if update is needed
        try:
            import git
            repo = git.Repo(cache_path)
            origin = repo.remotes.origin
            
            # Fetch latest changes
            origin.fetch()
            
            # Check if local is behind remote
            local_commit = repo.head.commit
            remote_commit = repo.refs['origin/main'].commit
            
            if local_commit.hexsha != remote_commit.hexsha:
                output.info("Updates available. Pulling latest changes...")
                origin.pull()
                output.success("Cache synchronized successfully")
            else:
                output.success("Cache is already up to date")
                
        except Exception as e:
            output.error(f"Failed to sync cache: {e}")
            output.info("Attempting to reinitialize cache...")
            self._update_cache()
    
    def _is_valid_git_repo(self, path: Path) -> bool:
        """Check if path is a valid git repository for the expected repo"""
        try:
            import git
            repo = git.Repo(path)
            origin_url = repo.remotes.origin.url
            return self.REPO_URL in origin_url
        except (git.InvalidGitRepositoryError, AttributeError, ImportError):
            return False
    
    def _show_cache_status(self):
        """Show cache status"""
        cache_path = self._get_cache_path()
        mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
        
        if not cache_path.exists():
            output.info("Cache: Not available")
            return
        
        # Check if it's a valid git repository
        is_valid_repo = self._is_valid_git_repo(cache_path)
        
        # Count available schemes
        scheme_count = 0
        if mobaxterm_dir.exists():
            scheme_count = len(list(mobaxterm_dir.glob("*.ini")))
        
        # Get last update time
        last_update = "Unknown"
        if is_valid_repo:
            try:
                import git
                repo = git.Repo(cache_path)
                last_commit = repo.head.commit
                last_update = last_commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        output.info("Cache Status:")
        output.result(f"  Cache Path: {cache_path}")
        output.result(f"  Valid Git Repo: {'Yes' if is_valid_repo else 'No'}")
        output.result(f"  Available Schemes: {scheme_count}")
        output.result(f"  Last Update: {last_update}")
        
        if not is_valid_repo:
            output.warning("Cache directory exists but is not a valid git repository")
            output.info("Run 'okit mobaxterm-colors cache --update' to fix this")
    
    def _list_schemes(self, search: Optional[str] = None, limit: int = 20):
        """List available color schemes"""
        cache_path = self._get_cache_path()
        mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
        
        if not mobaxterm_dir.exists():
            output.warning("Cache not available. Attempting to initialize cache...")
            self._update_cache()
            
            # Check again after update attempt
            if not mobaxterm_dir.exists():
                output.error("Failed to initialize cache. Please run 'okit mobaxterm-colors cache --update' manually")
                return
        
        # Find all .ini files
        scheme_files = list(mobaxterm_dir.glob("*.ini"))
        
        if search:
            scheme_files = [f for f in scheme_files if search.lower() in f.stem.lower()]
        
        # Sort and limit
        scheme_files.sort()
        scheme_files = scheme_files[:limit]
        
        if not scheme_files:
            output.info("No schemes found" + (f" matching '{search}'" if search else ""))
            return
        
        output.info(f"Available Color Schemes ({len(scheme_files)}):")
        for scheme_file in scheme_files:
            output.result(f"  {scheme_file.stem} ({scheme_file.name})")
    
    def _parse_mobaxterm_scheme(self, scheme_path: Path) -> Dict[str, str]:
        """Parse .ini file and extract color values"""
        colors = {}
        
        try:
            with open(scheme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse color values using regex
            # Only support the exact color names used in MobaXterm.ini
            # Format: ColorName=R,G,B
            color_pattern = r'(Black|Red|Green|Yellow|Blue|Magenta|Cyan|White|BoldBlack|BoldRed|BoldGreen|BoldYellow|BoldBlue|BoldMagenta|BoldCyan|BoldWhite|ForegroundColour|BackgroundColour|CursorColour)=(\d+),(\d+),(\d+)'
            matches = re.findall(color_pattern, content)
            
            for match in matches:
                color_name = match[0]
                r, g, b = match[1], match[2], match[3]
                colors[color_name] = f"{r},{g},{b}"
            
            return colors
            
        except Exception as e:
            output.error(f"Failed to parse scheme file {scheme_path}: {e}")
            return {}
    
    def _read_mobaxterm_config(self, config_path: Path) -> configparser.ConfigParser:
        """Read MobaXterm.ini configuration file"""
        config = configparser.ConfigParser(allow_no_value=True, strict=False)
        # Keep original case for option names
        config.optionxform = str
        
        if config_path.exists():
            try:
                config.read(config_path, encoding='utf-8')
            except configparser.DuplicateOptionError as e:
                output.warning(f"Duplicate option found in config file: {e}")
                # Try to read with more lenient settings
                config = configparser.ConfigParser(allow_no_value=True, strict=False, empty_lines_in_values=False)
                config.optionxform = str
                config.read(config_path, encoding='utf-8')
            except Exception as e:
                output.error(f"Failed to read config file: {e}")
        
        return config
    
    def _write_mobaxterm_config(self, config: configparser.ConfigParser, config_path: Path):
        """Write MobaXterm.ini configuration file"""
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            config.write(f)
    
    def _backup_config(self, config_path: Path) -> Optional[Path]:
        """Create backup of MobaXterm.ini"""
        if not config_path.exists():
            return None
        
        backup_dir = self._get_backup_path()
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"MobaXterm_backup_{timestamp}.ini"
        
        shutil.copy2(config_path, backup_path)
        output.info(f"Backup created: {backup_path}")
        
        return backup_path
    
    def _apply_scheme(self, scheme_name: str, force: bool = False, backup: bool = True):
        """Apply a color scheme to MobaXterm"""
        # Get configuration file path
        config_path = self._get_mobaxterm_config_path()
        if not config_path:
            output.error("Could not determine MobaXterm.ini path")
            return
        
        # Check if scheme exists in cache
        cache_path = self._get_cache_path()
        scheme_file = cache_path / self.MOBAXTERM_DIR / f"{scheme_name}.ini"
        
        if not scheme_file.exists():
            output.warning(f"Color scheme '{scheme_name}' not found in cache")
            output.info("Attempting to update cache and search again...")
            self._update_cache()
            
            # Check again after update
            if not scheme_file.exists():
                output.error(f"Color scheme '{scheme_name}' not found after cache update")
                output.info("Available schemes:")
                self._list_schemes(limit=10)
                return
        
        # Parse color scheme
        colors = self._parse_mobaxterm_scheme(scheme_file)
        if not colors:
            output.error(f"Failed to parse color scheme '{scheme_name}'")
            return
        
        # Read current configuration
        config = self._read_mobaxterm_config(config_path)
        
        # Create backup if requested
        if backup and config_path.exists():
            self._backup_config(config_path)
        
        # Apply color scheme
        if 'Colors' not in config:
            config.add_section('Colors')
        
        # Only replace colors that exist in both the scheme and the config
        # Get existing colors in the config
        existing_colors = set(config['Colors'].keys())
        
        # Only apply colors that exist in both the scheme and the config
        for color_key, color_value in colors.items():
            if color_key in existing_colors:
                config['Colors'][color_key] = color_value
        
        # Confirm before writing (unless forced)
        if not force:
            console.print(Panel(
                f"About to apply color scheme '{scheme_name}' to:\n{config_path}",
                title="Confirmation",
                border_style="yellow"
            ))
            if not click.confirm("Continue?"):
                output.info("Operation cancelled")
                return
        
        # Write configuration
        try:
            self._write_mobaxterm_config(config, config_path)
            output.success(f"Color scheme '{scheme_name}' applied successfully")
            
            # Show applied colors
            self._show_applied_colors(colors)
            
        except Exception as e:
            output.error(f"Failed to apply color scheme: {e}")
    
    def _show_applied_colors(self, colors: Dict[str, str]):
        """Show the applied colors in a table"""
        output.info("Applied Colors:")
        for color_key, color_value in sorted(colors.items()):
            output.result(f"  {color_key}: {color_value}")
    
    def _show_status(self):
        """Show current status and configuration"""
        # Configuration file status
        config_path = self._get_mobaxterm_config_path()
        config_exists = config_path.exists() if config_path else False
        
        # Cache status
        cache_path = self._get_cache_path()
        cache_exists = cache_path.exists()
        is_valid_repo = self._is_valid_git_repo(cache_path) if cache_exists else False
        
        # Local repository path
        local_repo_path = self.get_config_value("local_repo_path")
        
        # Auto update setting
        auto_update = self.get_config_value("auto_update", False)
        
        output.info("MobaXterm Colors Status:")
        output.result(f"  Config File: {config_path}")
        output.result(f"  Config Exists: {'Yes' if config_exists else 'No'}")
        output.result(f"  Cache Path: {cache_path}")
        output.result(f"  Cache Exists: {'Yes' if cache_exists else 'No'}")
        output.result(f"  Valid Git Repo: {'Yes' if is_valid_repo else 'No'}")
        output.result(f"  Local Repo Path: {local_repo_path or 'Not set'}")
        output.result(f"  Auto Update: {'Enabled' if auto_update else 'Disabled'}")
        
        # Show available schemes count
        if cache_exists and is_valid_repo:
            mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
            if mobaxterm_dir.exists():
                scheme_count = len(list(mobaxterm_dir.glob("*.ini")))
                output.info(f"Available color schemes: {scheme_count}")
        
        # Show cache recommendations
        if cache_exists and not is_valid_repo:
            output.warning("Cache exists but is not a valid git repository")
            output.info("Run 'okit mobaxterm-colors cache --sync' to fix this")
        elif not cache_exists:
            output.info("Cache not initialized. Run 'okit mobaxterm-colors cache --sync' to initialize") 