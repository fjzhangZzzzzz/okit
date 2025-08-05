#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = ["cryptography~=41.0", "click~=8.1"]
# ///
"""
MobaXterm Pro Tool - Generate and manage MobaXterm Professional license.

Based on the reference project: https://github.com/ryanlycch/MobaXterm-keygen
"""

import os
import sys
import zipfile
import subprocess
import winreg
import re
from pathlib import Path
from typing import Dict, Optional
import click
from okit.utils.log import output
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool
from okit.utils.mobaxterm_detector import MobaXtermDetector


class KeygenError(Exception):
    """Custom exception for keygen related errors."""

    pass


class MobaXtermKeygen:
    """MobaXterm key generator core class"""

    def __init__(self) -> None:
        # Variant Base64 table from reference project
        self.VariantBase64Table = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        )
        self.VariantBase64Dict = {
            i: self.VariantBase64Table[i] for i in range(len(self.VariantBase64Table))
        }
        self.VariantBase64ReverseDict = {
            self.VariantBase64Table[i]: i for i in range(len(self.VariantBase64Table))
        }

        # License types from reference project
        self.LicenseType_Professional = 1
        self.LicenseType_Educational = 3
        self.LicenseType_Personal = 4

    def generate_license_key(self, username: str, version: str) -> str:
        """Generate MobaXterm license key (exact reference project algorithm)"""
        try:
            # Extract major.minor version (consistent with reference project)
            normalized_version = self._normalize_version(version)
            major_str, minor_str = normalized_version.split(".")
            major_version = int(major_str)
            minor_version = int(minor_str)

            # Generate license using exact reference project logic
            return self._generate_license(
                self.LicenseType_Professional,
                1,  # Count
                username,
                major_version,
                minor_version,
            )

        except Exception as e:
            output.error(f"Failed to generate license key: {e}")
            raise KeygenError(f"License key generation failed: {e}")

    def _generate_license(
        self,
        license_type: int,
        count: int,
        username: str,
        major_version: int,
        minor_version: int,
    ) -> str:
        """Generate license with exact reference project format"""
        try:
            assert count >= 0

            # Exact LicenseString format from reference project
            license_string = "%d#%s|%d%d#%d#%d3%d6%d#%d#%d#%d#" % (
                license_type,
                username,
                major_version,
                minor_version,
                count,
                major_version,
                minor_version,
                minor_version,
                0,  # Unknown
                0,  # No Games flag. 0 means "NoGames = false". But it does not work.
                0,  # No Plugins flag. 0 means "NoPlugins = false". But it does not work.
            )

            # Exact encoding from reference project
            encrypted_bytes = self._encrypt_bytes(0x787, license_string.encode())
            encoded_license_string = self._variant_base64_encode(
                encrypted_bytes
            ).decode()

            return encoded_license_string

        except Exception as e:
            output.error(f"Failed to generate license: {e}")
            raise KeygenError(f"License generation failed: {e}")

    def _encrypt_bytes(self, key: int, bs: bytes) -> bytes:
        """EncryptBytes function from reference project"""
        result = bytearray()
        for i in range(len(bs)):
            result.append(bs[i] ^ ((key >> 8) & 0xFF))
            key = result[-1] & key | 0x482D
        return bytes(result)

    def _decrypt_bytes(self, key: int, bs: bytes) -> bytes:
        """DecryptBytes function from reference project"""
        result = bytearray()
        for i in range(len(bs)):
            result.append(bs[i] ^ ((key >> 8) & 0xFF))
            key = bs[i] & key | 0x482D
        return bytes(result)

    def _variant_base64_encode(self, bs: bytes) -> bytes:
        """VariantBase64Encode function from reference project"""
        result = b""
        blocks_count, left_bytes = divmod(len(bs), 3)

        for i in range(blocks_count):
            coding_int = int.from_bytes(bs[3 * i : 3 * i + 3], "little")
            block = self.VariantBase64Dict[coding_int & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 6) & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 12) & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 18) & 0x3F]
            result += block.encode()

        if left_bytes == 0:
            return result
        elif left_bytes == 1:
            coding_int = int.from_bytes(bs[3 * blocks_count :], "little")
            block = self.VariantBase64Dict[coding_int & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 6) & 0x3F]
            result += block.encode()
            return result
        else:
            coding_int = int.from_bytes(bs[3 * blocks_count :], "little")
            block = self.VariantBase64Dict[coding_int & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 6) & 0x3F]
            block += self.VariantBase64Dict[(coding_int >> 12) & 0x3F]
            result += block.encode()
            return result

    def _variant_base64_decode(self, s: str) -> bytes:
        """VariantBase64Decode function from reference project"""
        result = b""
        blocks_count, left_bytes = divmod(len(s), 4)

        for i in range(blocks_count):
            block = self.VariantBase64ReverseDict[s[4 * i]]
            block += self.VariantBase64ReverseDict[s[4 * i + 1]] << 6
            block += self.VariantBase64ReverseDict[s[4 * i + 2]] << 12
            block += self.VariantBase64ReverseDict[s[4 * i + 3]] << 18
            result += block.to_bytes(3, "little")

        if left_bytes == 0:
            return result
        elif left_bytes == 2:
            block = self.VariantBase64ReverseDict[s[4 * blocks_count]]
            block += self.VariantBase64ReverseDict[s[4 * blocks_count + 1]] << 6
            result += block.to_bytes(1, "little")
            return result
        elif left_bytes == 3:
            block = self.VariantBase64ReverseDict[s[4 * blocks_count]]
            block += self.VariantBase64ReverseDict[s[4 * blocks_count + 1]] << 6
            block += self.VariantBase64ReverseDict[s[4 * blocks_count + 2]] << 12
            result += block.to_bytes(2, "little")
            return result
        else:
            raise ValueError("Invalid encoding.")

    def _normalize_version(self, version: str) -> str:
        """Normalize version to major.minor format (consistent with reference project)"""
        try:
            # Extract major.minor from full version
            # Examples:
            #   "25.2.0.5296" -> "25.2"
            #   "22.0" -> "22.0"
            #   "21.5.1.4321" -> "21.5"
            version_parts = version.split(".")
            if len(version_parts) >= 2:
                return f"{version_parts[0]}.{version_parts[1]}"
            elif len(version_parts) == 1:
                # Single number, add .0
                return f"{version_parts[0]}.0"
            else:
                # Fallback to original version
                return version
        except Exception as e:
            output.debug(f"Failed to normalize version '{version}': {e}")
            return version

    def create_license_file(self, username: str, version: str, output_path: str) -> str:
        """Create Custom.mxtpro file (exact reference project format)"""
        try:
            # Generate encoded license string using exact reference project algorithm
            encoded_license_string = self.generate_license_key(username, version)

            # Create zip file with Pro.key containing the encoded license string (exact reference project format)
            with zipfile.ZipFile(output_path, "w") as f:
                f.writestr("Pro.key", data=encoded_license_string)

            output.info(f"License file created: {output_path}")
            return output_path

        except Exception as e:
            output.error(f"Failed to create license file: {e}")
            raise KeygenError(f"License file creation failed: {e}")

    def decode_license_key(self, encoded_license_string: str) -> Optional[str]:
        """Decode license key using exact reference project algorithm"""
        try:
            # Decode using exact reference project reverse process
            encrypted_bytes = self._variant_base64_decode(encoded_license_string)
            license_bytes = self._decrypt_bytes(0x787, encrypted_bytes)
            license_string = license_bytes.decode("utf-8")
            return license_string

        except Exception as e:
            output.debug(f"Failed to decode license key: {e}")
            return None

    def validate_license_file(self, file_path: str) -> bool:
        """Validate license file"""
        try:
            if not os.path.exists(file_path):
                return False

            with zipfile.ZipFile(file_path, "r") as zf:
                if "Pro.key" not in zf.namelist():
                    return False

                pro_key_content = zf.read("Pro.key").decode("utf-8").strip()

                # Try to decode the license key to verify it's valid
                decoded_content = self.decode_license_key(pro_key_content)
                if decoded_content:
                    # Check if decoded content has expected format from reference project
                    # Format: Type#UserName|MajorMinor#Count#Major3Minor6Minor#0#0#0#
                    return "#" in decoded_content and "|" in decoded_content

                return False

        except Exception as e:
            output.debug(f"License file validation failed: {e}")
            return False

    def validate_license_key(
        self, username: str, license_key: str, version: str
    ) -> bool:
        """Validate license key for specific user and version"""
        try:
            normalized_version = self._normalize_version(version)
            major_version, minor_version = normalized_version.split(".")

            # Decode the license key
            decoded_content = self.decode_license_key(license_key)
            if not decoded_content:
                return False

            # Parse the decoded content according to reference project format
            # Format: Type#UserName|MajorMinor#Count#Major3Minor6Minor#0#0#0#
            parts = decoded_content.split("#")
            if len(parts) < 7:
                return False

            license_type = parts[0]
            username_version = parts[1]

            # Extract username and version from UserName|MajorMinor
            if "|" not in username_version:
                return False

            key_username, version_part = username_version.split("|", 1)

            # Verify username matches
            if key_username != username:
                return False

            # Verify version matches (format: MajorMinor, e.g., "252" for version 25.2)
            expected_version_part = f"{major_version}{minor_version}"
            if version_part != expected_version_part:
                return False

            # Verify license type is Professional (1)
            if license_type != "1":
                return False

            return True

        except Exception as e:
            output.debug(f"License key validation failed: {e}")
            return False

    def get_license_info(self, license_key: str) -> Optional[Dict]:
        """Get license information from license key"""
        try:
            decoded_content = self.decode_license_key(license_key)
            if not decoded_content:
                return None

            # Parse according to reference project format
            # Format: Type#UserName|MajorMinor#Count#Major3Minor6Minor#0#0#0#
            parts = decoded_content.split("#")
            if len(parts) < 7:
                return None

            license_type = parts[0]
            username_version = parts[1]
            count = parts[2]

            # Extract username and version
            if "|" not in username_version:
                return None

            username, version_part = username_version.split("|", 1)

            # Convert license type number to string
            license_type_names = {
                "1": "Professional",
                "3": "Educational",
                "4": "Personal",
            }
            license_type_name = license_type_names.get(
                license_type, f"Type {license_type}"
            )

            # Try to extract major/minor version from version_part
            # This is a bit tricky since it's concatenated like "252" for "25.2"
            version_display = version_part  # fallback to raw value
            if len(version_part) >= 2:
                # Try common patterns
                if len(version_part) == 3:  # like "252" -> "25.2"
                    version_display = f"{version_part[:-1]}.{version_part[-1]}"
                elif len(version_part) == 2:  # like "22" -> "22.0"
                    version_display = f"{version_part}.0"

            return {
                "username": username,
                "version": version_display,
                "license_type": license_type_name,
                "user_count": count,
                "license_key": license_key,
                "decoded_string": decoded_content,
            }

        except Exception as e:
            output.debug(f"Failed to get license info: {e}")
            return None


@okit_tool(
    "mobaxterm-pro", "MobaXterm license key generator tool", use_subcommands=True
)
class MobaXtermProTool(BaseTool):
    """MobaXterm Pro license management tool"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)
        self.keygen = MobaXtermKeygen()
        self.detector = MobaXtermDetector()

    def _get_cli_help(self) -> str:
        """Custom CLI help information"""
        return """
MobaXterm Pro Tool - Generate and manage MobaXterm license keys.

Based on: https://github.com/ryanlycch/MobaXterm-keygen
        """.strip()

    def _get_cli_short_help(self) -> str:
        """Custom CLI short help information"""
        return "Generate and manage MobaXterm Professional license"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """Add tool-specific CLI commands"""

        @cli_group.command()
        def detect() -> None:
            """Auto-detect MobaXterm installation information (including version)"""
            try:
                output.result(
                    "[cyan]Detecting MobaXterm installation information...[/cyan]"
                )

                installation_info = self.detector.detect_installation()

                if installation_info:
                    output.success(f"✓ MobaXterm installation found")
                    output.result(
                        f"  Install path: {installation_info['install_path']}"
                    )
                    output.result(f"  Version: {installation_info['version']}")
                    output.result(
                        f"  Detection method: {installation_info['detection_method']}"
                    )

                    if "display_name" in installation_info:
                        output.result(
                            f"  Display name: {installation_info['display_name']}"
                        )

                    if "package_manager" in installation_info:
                        output.result(
                            f"  Package manager: {installation_info['package_manager']}"
                        )

                    if "exe_path" in installation_info:
                        output.result(
                            f"  Executable file: {installation_info['exe_path']}"
                        )

                    if "real_exe_path" in installation_info:
                        output.result(
                            f"  Real executable: {installation_info['real_exe_path']}"
                        )

                    # Check license file
                    license_path = self.detector.get_license_file_path(
                        installation_info["install_path"]
                    )
                    if license_path:
                        output.result(f"  License file: {license_path}")
                        self._analyze_license_file(
                            license_path, installation_info["version"]
                        )
                    else:
                        output.result("  License file: Not found")

                else:
                    output.result("[yellow]⚠ MobaXterm installation not found[/yellow]")
                    output.result("  Please check the following locations:")
                    for path in self.detector.known_paths:
                        output.result(f"    - {path}")
                    output.result(
                        "  Or ensure MobaXterm is properly installed and added to PATH environment variable"
                    )

            except Exception as e:
                output.error(f"Failed to detect MobaXterm: {e}")
                output.error(f"Error detecting MobaXterm: {e}")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username for the license")
        @click.option("--version", required=True, help="MobaXterm version (e.g., 22.0)")
        @click.option(
            "--output-path", required=True, help="Output file path for Custom.mxtpro"
        )
        def generate(username: str, version: str, output_path: str) -> None:
            """Generate Custom.mxtpro license file"""
            try:
                # Ensure output directory exists
                output_dir = os.path.dirname(os.path.abspath(output_path))
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)

                # Show normalized version for license generation
                normalized_version = self.keygen._normalize_version(version)
                if normalized_version != version:
                    output.info(
                        f"Normalizing version for license generation: {version} -> {normalized_version}"
                    )

                # Generate license file
                license_file = self.keygen.create_license_file(
                    username, version, output_path
                )

                # Get license key info for display
                with zipfile.ZipFile(license_file, "r") as zf:
                    license_key = zf.read("Pro.key").decode("utf-8").strip()

                license_info = self.keygen.get_license_info(license_key)

                output.success(f"✓ License file generated successfully!")
                output.result(f"  Username: {username}")
                output.result(
                    f"  Version: {normalized_version} (from {version})"
                    if normalized_version != version
                    else f"  Version: {version}"
                )
                output.result(f"  License Type: Professional")
                if license_info:
                    output.result(f"  User Count: {license_info['user_count']}")
                output.result(f"  Output file: {license_file}")
                output.warning(
                    f"Please copy the file to MobaXterm's installation directory."
                )

            except Exception as e:
                output.error(f"Failed to generate license: {e}")
                output.error(f"Error generating license: {e}")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username for the license")
        @click.option(
            "--version", help="MobaXterm version (auto-detect if not specified)"
        )
        def deploy(username: str, version: str) -> None:
            """One-click deploy: auto-detect installation and generate license file"""
            try:
                # Auto-detect installation
                output.result("[cyan]Auto-detecting MobaXterm installation...[/cyan]")
                installation_info = self.detector.detect_installation()

                if not installation_info:
                    output.result("[red]✗ MobaXterm installation not found[/red]")
                    output.result(
                        "Please install MobaXterm first or use 'generate' command instead."
                    )
                    sys.exit(1)

                install_path = installation_info["install_path"]
                detected_version = installation_info["version"]

                output.success(f"✓ Found MobaXterm installation")
                output.result(f"  Path: {install_path}")
                output.result(f"  Version: {detected_version}")

                # Use detected version if not specified
                if not version:
                    version = detected_version
                    output.result(f"  Using detected version: {version}")

                # Show normalized version for license generation
                normalized_version = self.keygen._normalize_version(version)
                if normalized_version != version:
                    output.result(
                        f"  Normalized version for license: {normalized_version}"
                    )

                # Generate license file in installation directory
                license_path = os.path.join(install_path, "Custom.mxtpro")
                self.keygen.create_license_file(username, version, license_path)

                # Get license key info for display
                with zipfile.ZipFile(license_path, "r") as zf:
                    license_key = zf.read("Pro.key").decode("utf-8").strip()

                license_info = self.keygen.get_license_info(license_key)

                output.success(f"✓ License deployed successfully!")
                output.result(f"  Username: {username}")
                output.result(
                    f"  Version: {normalized_version} (from {version})"
                    if normalized_version != version
                    else f"  Version: {version}"
                )
                output.result(f"  License Type: Professional")
                if license_info:
                    output.result(f"  User Count: {license_info['user_count']}")
                output.result(f"  License file: {license_path}")
                output.warning(f"Please restart MobaXterm to activate the license.")

            except Exception as e:
                output.error(f"Failed to deploy license: {e}")
                output.error(f"Error deploying license: {e}")
                sys.exit(1)

        @cli_group.command()
        @click.option(
            "--license-key", required=True, help="License key to decode and display"
        )
        def info(license_key: str) -> None:
            """Display license key information"""
            try:
                license_info = self.keygen.get_license_info(license_key)

                if license_info:
                    output.success(f"✓ License key information:")
                    output.result(f"  Username: {license_info['username']}")
                    output.result(f"  Version: {license_info['version']}")
                    output.result(f"  License Type: {license_info['license_type']}")
                    output.result(f"  User Count: {license_info['user_count']}")
                    output.result(f"  License Key: {license_info['license_key']}")
                    output.result(f"  Decoded String: {license_info['decoded_string']}")
                else:
                    output.error(f"✗ Invalid or corrupted license key")

            except Exception as e:
                output.error(f"Failed to display license info: {e}")
                output.error(f"Error displaying license info: {e}")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username to validate")
        @click.option("--license-key", required=True, help="License key to validate")
        @click.option(
            "--version", required=True, help="MobaXterm version to validate against"
        )
        def validate(username: str, license_key: str, version: str) -> None:
            """Validate license key for specific user and version"""
            try:
                is_valid = self.keygen.validate_license_key(
                    username, license_key, version
                )

                if is_valid:
                    output.success(
                        f"✓ License key is valid for {username} version {version}"
                    )

                    # Show license info
                    license_info = self.keygen.get_license_info(license_key)
                    if license_info:
                        output.result(f"  License Type: {license_info['license_type']}")
                        output.result(f"  User Count: {license_info['user_count']}")
                else:
                    output.error(
                        f"✗ License key is invalid for {username} version {version}"
                    )

            except Exception as e:
                output.error(f"Failed to validate license: {e}")
                output.error(f"Error validating license: {e}")
                sys.exit(1)

    def _analyze_license_file(self, license_path: str, detected_version: str) -> None:
        """Analyze existing license file and display detailed information"""
        try:
            # Validate license file format
            is_valid = self.keygen.validate_license_file(license_path)

            if not is_valid:
                output.result("    [red]✗ Invalid or corrupted license file[/red]")
                return

            # Read license content
            with zipfile.ZipFile(license_path, "r") as zf:
                license_key = zf.read("Pro.key").decode("utf-8").strip()

            # Get license information
            license_info = self.keygen.get_license_info(license_key)

            if license_info:
                output.result("    [green]✓ License file is valid[/green]")
                output.result(f"      Username: {license_info['username']}")
                output.result(f"      Version: {license_info['version']}")
                output.result(f"      License Type: {license_info['license_type']}")
                output.result(f"      User Count: {license_info['user_count']}")

                # Compare versions
                self._compare_license_version(license_info["version"], detected_version)

                # Show decoded string for debugging - using debug output
                output.debug(f"      Decoded String: {license_info['decoded_string']}")

            else:
                output.result("    [red]✗ Failed to parse license content[/red]")

        except Exception as e:
            output.debug(f"Failed to analyze license file: {e}")
            output.result(f"    [red]✗ Error analyzing license file: {e}[/red]")

    def _compare_license_version(
        self, license_version: str, detected_version: str
    ) -> None:
        """Compare license version with detected MobaXterm version"""
        try:
            # Normalize both versions to major.minor format
            normalized_license_version = self.keygen._normalize_version(license_version)
            normalized_detected_version = self.keygen._normalize_version(
                detected_version
            )

            if normalized_license_version == normalized_detected_version:
                output.result(
                    f"      [green]✓ Version matches detected MobaXterm version ({normalized_detected_version})[/green]"
                )
            else:
                output.result(f"      [yellow]⚠ Version mismatch detected![/yellow]")
                output.result(f"        License version: {normalized_license_version}")
                output.result(
                    f"        MobaXterm version: {normalized_detected_version}"
                )

                # Determine if license is older or newer
                try:
                    license_parts = normalized_license_version.split(".")
                    detected_parts = normalized_detected_version.split(".")
                    license_major, license_minor = int(license_parts[0]), int(
                        license_parts[1]
                    )
                    detected_major, detected_minor = int(detected_parts[0]), int(
                        detected_parts[1]
                    )

                    if (license_major < detected_major) or (
                        license_major == detected_major
                        and license_minor < detected_minor
                    ):
                        output.result(
                            f"      [yellow]The license is for an older version and may not work properly.[/yellow]"
                        )
                    elif (license_major > detected_major) or (
                        license_major == detected_major
                        and license_minor > detected_minor
                    ):
                        output.result(
                            f"      [yellow]The license is for a newer version than installed.[/yellow]"
                        )
                    else:
                        output.result(
                            f"      [yellow]Version mismatch detected.[/yellow]"
                        )

                except ValueError:
                    output.result(
                        f"      [yellow]Could not determine version relationship.[/yellow]"
                    )

                output.result(
                    f"      [yellow]Consider regenerating the license with the current version.[/yellow]"
                )

                # Provide regeneration suggestion
                output.result(
                    f"      [cyan]💡 Regenerate license: okit mobaxterm-pro deploy --username <your_username>[/cyan]"
                )

        except Exception as e:
            output.debug(f"Failed to compare versions: {e}")
            output.result(f"      [yellow]⚠ Could not compare versions: {e}[/yellow]")

    def _cleanup_impl(self) -> None:
        """Custom cleanup logic"""
        output.info("Executing custom cleanup logic")
        pass
