"""
MobaXterm Installation Detector

This module provides comprehensive MobaXterm installation detection functionality,
including support for package managers like scoop and chocolatey.
"""

import os
import re
import subprocess
import winreg
from pathlib import Path
from typing import Dict, Optional

from okit.utils.log import output


class MobaXtermDetector:
    """MobaXterm installation detector with package manager support"""

    def __init__(self) -> None:
        self.known_paths = [
            r"C:\Program Files (x86)\Mobatek\MobaXterm",
            r"C:\Program Files\Mobatek\MobaXterm",
            r"C:\Program Files (x86)\Mobatek\MobaXterm Home Edition",
            r"C:\Program Files\Mobatek\MobaXterm Home Edition",
            r"C:\Program Files (x86)\Mobatek\MobaXterm Professional",
            r"C:\Program Files\Mobatek\MobaXterm Professional",
        ]

    def detect_installation(self) -> Optional[Dict[str, str]]:
        """Detect MobaXterm installation information"""
        try:
            # Method 1: Detect from registry
            reg_info = self._detect_from_registry()
            if reg_info:
                return reg_info

            # Method 2: Detect from known paths
            path_info = self._detect_from_paths()
            if path_info:
                return path_info

            # Method 3: Detect from environment variables
            env_info = self._detect_from_environment()
            if env_info:
                return env_info

            return None

        except Exception as e:
            output.error(f"Failed to detect MobaXterm installation: {e}")
            return None

    def _detect_from_registry(self) -> Optional[Dict[str, str]]:
        """Detect MobaXterm installation from registry"""
        try:
            # Check common registry paths
            registry_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm Home Edition",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm Home Edition",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm Professional",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MobaXterm Professional",
            ]

            for reg_path in registry_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                        install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
                        display_name = winreg.QueryValueEx(key, "DisplayName")[0]
                        display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]

                        if install_location and os.path.exists(install_location):
                            return {
                                "install_path": install_location,
                                "display_name": display_name,
                                "version": display_version,
                                "detection_method": "registry",
                            }
                except (FileNotFoundError, OSError):
                    continue

            return None

        except Exception as e:
            output.debug(f"Registry detection failed: {e}")
            return None

    def _detect_from_paths(self) -> Optional[Dict[str, str]]:
        """Detect MobaXterm installation from known paths"""
        for install_path in self.known_paths:
            if os.path.exists(install_path):
                # Look for executable file
                exe_path = os.path.join(install_path, "MobaXterm.exe")
                if os.path.exists(exe_path):
                    version = self._get_file_version(exe_path)
                    return {
                        "install_path": install_path,
                        "exe_path": exe_path,
                        "version": version or "Unknown",
                        "detection_method": "known_paths",
                    }

        return None

    def _detect_from_environment(self) -> Optional[Dict[str, str]]:
        """Detect MobaXterm installation from environment variables"""
        try:
            # Check PATH environment variable
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            for path_dir in path_dirs:
                mobaxterm_exe = os.path.join(path_dir, "MobaXterm.exe")
                if os.path.exists(mobaxterm_exe):
                    version = self._get_file_version(mobaxterm_exe)

                    # Resolve real installation path for package managers
                    real_install_path = self._resolve_real_install_path(
                        mobaxterm_exe, path_dir
                    )
                    real_exe_path = self._resolve_real_executable_path(mobaxterm_exe)

                    result = {
                        "install_path": real_install_path,
                        "exe_path": mobaxterm_exe,
                        "version": version or "Unknown",
                        "detection_method": "environment",
                    }

                    # Add real executable path if different
                    if real_exe_path and real_exe_path != mobaxterm_exe:
                        result["real_exe_path"] = real_exe_path

                    # Add package manager info if detected
                    if "scoop" in mobaxterm_exe.lower():
                        result["package_manager"] = "scoop"
                    elif "chocolatey" in mobaxterm_exe.lower():
                        result["package_manager"] = "chocolatey"

                    return result

            return None

        except Exception as e:
            output.debug(f"Environment detection failed: {e}")
            return None

    def _resolve_real_install_path(self, exe_path: str, detected_path: str) -> str:
        """Resolve real installation path for package manager installations"""
        try:
            # Handle scoop installations
            if "scoop" in exe_path.lower() and "shims" in exe_path.lower():
                # Try to find the real scoop app directory
                real_exe = self._resolve_scoop_executable(exe_path)
                if real_exe:
                    # Return the directory containing the real executable
                    return os.path.dirname(real_exe)

                # Fallback: construct typical scoop app path
                shim_dir = os.path.dirname(exe_path)
                scoop_root = os.path.dirname(shim_dir)

                # Try different possible app directory names
                for app_dir_name in [
                    "mobaxterm",
                    "MobaXterm",
                    "mobaxterm-home",
                    "mobaxterm-professional",
                ]:
                    app_path = os.path.join(scoop_root, "apps", app_dir_name, "current")
                    if os.path.exists(app_path):
                        return app_path

            # Handle chocolatey installations
            elif "chocolatey" in exe_path.lower():
                real_exe = self._resolve_chocolatey_executable(exe_path)
                if real_exe:
                    return os.path.dirname(real_exe)

            # For regular installations, return the detected path
            return detected_path

        except Exception as e:
            output.debug(f"Failed to resolve real install path: {e}")
            return detected_path

    def _get_file_version(self, exe_path: str) -> Optional[str]:
        """Get executable file version information using multiple methods (non-intrusive first)"""
        try:
            # Method 1: Try PowerShell on original path (safe, won't launch app)
            version = self._get_version_from_powershell(exe_path)
            if version:
                return version

            # Method 2: Resolve real executable path for scoop/chocolatey installations
            real_exe_path = self._resolve_real_executable_path(exe_path)
            if real_exe_path and real_exe_path != exe_path:
                output.debug(f"Resolved real executable path: {real_exe_path}")

                # Try PowerShell version info on real executable (safe)
                version = self._get_version_from_powershell(real_exe_path)
                if version:
                    return version

            # Method 3: Try to extract version from file path (safe)
            version = self._extract_version_from_path(exe_path)
            if version:
                return version

            # Method 4: Last resort - try command line (may launch app briefly)
            output.debug("Trying command line version detection as last resort")
            version = self._get_version_from_command(exe_path)
            if version:
                return version

            # Try command line on real executable if available
            if real_exe_path and real_exe_path != exe_path:
                version = self._get_version_from_command(real_exe_path)
                if version:
                    return version

            return None

        except Exception as e:
            output.debug(f"Failed to get file version: {e}")
            return None

    def _get_version_from_command(self, exe_path: str) -> Optional[str]:
        """Try to get version by running MobaXterm with version flag"""
        try:
            # Try common version flags
            for flag in ["-v", "--version", "/version", "-version"]:
                try:
                    cmd = [exe_path, flag]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=10
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        message = result.stdout.strip()
                        # Extract version from output using regex
                        version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", message)
                        if version_match:
                            return version_match.group(1)
                except Exception:
                    continue

            return None

        except Exception as e:
            output.debug(f"Failed to get version from command: {e}")
            return None

    def _resolve_real_executable_path(self, exe_path: str) -> Optional[str]:
        """Resolve real executable path for package manager installations"""
        try:
            # Handle scoop installations
            if "scoop" in exe_path.lower() and "shims" in exe_path.lower():
                return self._resolve_scoop_executable(exe_path)

            # Handle chocolatey installations
            if "chocolatey" in exe_path.lower():
                return self._resolve_chocolatey_executable(exe_path)

            # Handle other symlinks/shortcuts
            if os.path.islink(exe_path):
                return os.path.realpath(exe_path)

            return exe_path

        except Exception as e:
            output.debug(f"Failed to resolve real executable path: {e}")
            return exe_path

    def _resolve_scoop_executable(self, shim_path: str) -> Optional[str]:
        """Resolve scoop shim to actual executable"""
        try:
            # Read shim file to find real executable path
            if os.path.exists(shim_path):
                with open(shim_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Look for path patterns in shim content
                path_patterns = [
                    r'"([^"]*MobaXterm[^"]*\.exe)"',
                    r"'([^']*MobaXterm[^']*\.exe)'",
                    r"(\S+MobaXterm\S*\.exe)",
                ]

                for pattern in path_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if os.path.exists(match):
                            return str(match)

            # Try to construct scoop app path from shim path
            # Typical scoop structure: {scoop}/shims/app.exe -> {scoop}/apps/app/current/app.exe
            shim_dir = os.path.dirname(shim_path)
            scoop_root = os.path.dirname(shim_dir)
            app_name = "mobaxterm"

            # Try different possible app directory names
            for app_dir_name in [
                "mobaxterm",
                "MobaXterm",
                "mobaxterm-home",
                "mobaxterm-professional",
            ]:
                app_path = os.path.join(
                    scoop_root, "apps", app_dir_name, "current", "MobaXterm.exe"
                )
                if os.path.exists(app_path):
                    return app_path

            return None

        except Exception as e:
            output.debug(f"Failed to resolve scoop executable: {e}")
            return None

    def _resolve_chocolatey_executable(self, exe_path: str) -> Optional[str]:
        """Resolve chocolatey installation to actual executable"""
        try:
            # Chocolatey usually installs to Program Files
            # Try to find real installation
            choco_dir = os.path.dirname(exe_path)

            # Look for tools directory
            tools_dir = os.path.join(choco_dir, "tools")
            if os.path.exists(tools_dir):
                for root, dirs, files in os.walk(tools_dir):
                    for file in files:
                        if file.lower() == "mobaxterm.exe":
                            return os.path.join(root, file)

            return None

        except Exception as e:
            output.debug(f"Failed to resolve chocolatey executable: {e}")
            return None

    def _get_version_from_powershell(self, exe_path: str) -> Optional[str]:
        """Get version using PowerShell VersionInfo"""
        try:
            cmd = [
                "powershell",
                "-Command",
                f"(Get-Item '{exe_path}').VersionInfo.FileVersion",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            # Try alternative PowerShell method
            cmd = [
                "powershell",
                "-Command",
                f"(Get-ItemProperty '{exe_path}').VersionInfo.ProductVersion",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            return None

        except Exception as e:
            output.debug(f"Failed to get version from PowerShell: {e}")
            return None

    def _extract_version_from_path(self, exe_path: str) -> Optional[str]:
        """Try to extract version from file path"""
        try:
            # Look for version patterns in the path
            version_patterns = [
                r"(?:mobaxterm|MobaXterm)[_\-\s]*v?(\d+\.\d+(?:\.\d+)?)",
                r"(?:mobaxterm|MobaXterm)[/\\](\d+\.\d+(?:\.\d+)?)",
                r"(\d+\.\d+(?:\.\d+)?)(?:[/\\]|$)",
            ]

            path_str = exe_path.replace("\\", "/")
            for pattern in version_patterns:
                match = re.search(pattern, path_str, re.IGNORECASE)
                if match:
                    return match.group(1)

            return None

        except Exception as e:
            output.debug(f"Failed to extract version from path: {e}")
            return None

    def get_config_file_path(self, install_path: str) -> Optional[str]:
        """Get MobaXterm.ini configuration file path"""
        # Common MobaXterm.ini locations
        possible_paths = [
            os.path.join(install_path, "MobaXterm.ini"),
            os.path.join(os.environ.get('APPDATA', ''), 'Mobatek', 'MobaXterm', 'MobaXterm.ini'),
            os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Mobatek', 'MobaXterm', 'MobaXterm.ini'),
            os.path.join(os.path.expanduser('~'), 'Documents', 'MobaXterm', 'MobaXterm.ini'),
        ]

        # Check if user specified a custom path
        custom_path = os.environ.get('MOBAXTERM_CONFIG_PATH')
        if custom_path:
            custom_path = Path(custom_path)
            if custom_path.exists():
                return str(custom_path)
            else:
                output.warning(f"Specified config path does not exist: {custom_path}")

        # Try to find existing configuration file
        for path in possible_paths:
            if os.path.exists(path):
                output.info(f"Found MobaXterm.ini at: {path}")
                return path

        # If not found, return the most likely default path
        default_path = possible_paths[1]  # APPDATA path
        output.warning(f"MobaXterm.ini not found. Will create at: {default_path}")
        return default_path

    def get_license_file_path(self, install_path: str) -> Optional[str]:
        """Get license file path"""
        license_paths = [
            os.path.join(install_path, "Custom.mxtpro"),
            os.path.join(install_path, "Custom", "Custom.mxtpro"),
        ]

        for license_path in license_paths:
            if os.path.exists(license_path):
                return license_path

        return None 