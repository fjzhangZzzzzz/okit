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
    
    def __init__(self):
        super().__init__("mobaxterm-colors", "MobaXterm color scheme management tool")
        self._ensure_cache_dir()
        self.detector = MobaXtermDetector()
    
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
        def cache(update: bool, clean: bool):
            """Manage local cache"""
            if update:
                self._update_cache()
            elif clean:
                self._clean_cache()
            else:
                self._show_cache_status()
        
        @cli_group.command()
        def status():
            """Show current status and configuration"""
            self._show_status()
    
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
            if cache_path.exists():
                output.info("Updating existing cache...")
                # Use git to update existing repository
                import git
                repo = git.Repo(cache_path)
                origin = repo.remotes.origin
                origin.pull()
                output.success("Cache updated successfully")
            else:
                output.info("Cloning repository to cache...")
                # Clone repository
                import git
                git.Repo.clone_from(self.REPO_URL, cache_path)
                output.success("Cache created successfully")
                
        except ImportError:
            output.error("gitpython is required for cache operations. Install with: pip install gitpython")
            return
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
    
    def _show_cache_status(self):
        """Show cache status"""
        cache_path = self._get_cache_path()
        mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
        
        if not cache_path.exists():
            output.info("Cache: Not available")
            return
        
        # Count available schemes
        scheme_count = 0
        if mobaxterm_dir.exists():
            scheme_count = len(list(mobaxterm_dir.glob("*.mobaxterm")))
        
        # Get last update time
        last_update = "Unknown"
        if cache_path.exists():
            try:
                import git
                repo = git.Repo(cache_path)
                last_commit = repo.head.commit
                last_update = last_commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        output.info("Cache Status:")
        output.result(f"  Cache Path: {cache_path}")
        output.result(f"  Available Schemes: {scheme_count}")
        output.result(f"  Last Update: {last_update}")
    
    def _list_schemes(self, search: Optional[str] = None, limit: int = 20):
        """List available color schemes"""
        cache_path = self._get_cache_path()
        mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
        
        if not mobaxterm_dir.exists():
            output.error("Cache not available. Run 'okit mobaxterm-colors cache --update' first")
            return
        
        # Find all .mobaxterm files
        scheme_files = list(mobaxterm_dir.glob("*.mobaxterm"))
        
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
        """Parse .mobaxterm file and extract color values"""
        colors = {}
        
        try:
            with open(scheme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse color values using regex
            # Format: Color0=0,0,0 (RGB values)
            color_pattern = r'Color(\d+)=(\d+),(\d+),(\d+)'
            matches = re.findall(color_pattern, content)
            
            for match in matches:
                color_index = match[0]
                r, g, b = match[1], match[2], match[3]
                colors[f"Color{color_index}"] = f"{r},{g},{b}"
            
            return colors
            
        except Exception as e:
            output.error(f"Failed to parse scheme file {scheme_path}: {e}")
            return {}
    
    def _read_mobaxterm_config(self, config_path: Path) -> configparser.ConfigParser:
        """Read MobaXterm.ini configuration file"""
        config = configparser.ConfigParser()
        
        if config_path.exists():
            config.read(config_path, encoding='utf-8')
        
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
        scheme_file = cache_path / self.MOBAXTERM_DIR / f"{scheme_name}.mobaxterm"
        
        if not scheme_file.exists():
            output.error(f"Color scheme '{scheme_name}' not found in cache")
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
        
        for color_key, color_value in colors.items():
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
        
        # Local repository path
        local_repo_path = self.get_config_value("local_repo_path")
        
        # Auto update setting
        auto_update = self.get_config_value("auto_update", False)
        
        output.info("MobaXterm Colors Status:")
        output.result(f"  Config File: {config_path}")
        output.result(f"  Config Exists: {'Yes' if config_exists else 'No'}")
        output.result(f"  Cache Path: {cache_path}")
        output.result(f"  Cache Exists: {'Yes' if cache_exists else 'No'}")
        output.result(f"  Local Repo Path: {local_repo_path or 'Not set'}")
        output.result(f"  Auto Update: {'Enabled' if auto_update else 'Disabled'}")
        
        # Show available schemes count
        if cache_exists:
            mobaxterm_dir = cache_path / self.MOBAXTERM_DIR
            if mobaxterm_dir.exists():
                scheme_count = len(list(mobaxterm_dir.glob("*.mobaxterm")))
                output.info(f"Available color schemes: {scheme_count}") 