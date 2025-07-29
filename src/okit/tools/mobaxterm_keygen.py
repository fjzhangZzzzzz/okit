#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.7"
# dependencies = ["cryptography~=41.0", "click~=8.1"]
# ///
"""
MobaXterm Keygen Tool - Generate and manage MobaXterm license keys.
"""

import os
import sys
import hashlib
import base64
import json
import subprocess
import winreg
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, cast
import click
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from okit.utils.log import logger, console
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool


class KeygenError(Exception):
    """Custom exception for keygen related errors."""

    pass


class MobaXtermDetector:
    """MobaXterm 安装信息探测器"""

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
        """检测 MobaXterm 安装信息"""
        try:
            # 方法1: 通过注册表检测
            reg_info = self._detect_from_registry()
            if reg_info:
                return reg_info

            # 方法2: 通过已知路径检测
            path_info = self._detect_from_paths()
            if path_info:
                return path_info

            # 方法3: 通过环境变量检测
            env_info = self._detect_from_environment()
            if env_info:
                return env_info

            return None

        except Exception as e:
            logger.error(f"Failed to detect MobaXterm installation: {e}")
            return None

    def _detect_from_registry(self) -> Optional[Dict[str, str]]:
        """从注册表检测 MobaXterm 安装信息"""
        try:
            # 检查常见的注册表路径
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
                        install_location = winreg.QueryValueEx(key, "InstallLocation")[
                            0
                        ]
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
            logger.debug(f"Registry detection failed: {e}")
            return None

    def _detect_from_paths(self) -> Optional[Dict[str, str]]:
        """从已知路径检测 MobaXterm 安装信息"""
        for install_path in self.known_paths:
            if os.path.exists(install_path):
                # 查找可执行文件
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
        """从环境变量检测 MobaXterm 安装信息"""
        try:
            # 检查 PATH 环境变量
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            for path_dir in path_dirs:
                mobaxterm_exe = os.path.join(path_dir, "MobaXterm.exe")
                if os.path.exists(mobaxterm_exe):
                    version = self._get_file_version(mobaxterm_exe)
                    install_path = os.path.dirname(mobaxterm_exe)
                    return {
                        "install_path": install_path,
                        "exe_path": mobaxterm_exe,
                        "version": version or "Unknown",
                        "detection_method": "environment",
                    }

            return None

        except Exception as e:
            logger.debug(f"Environment detection failed: {e}")
            return None

    def _get_file_version(self, exe_path: str) -> Optional[str]:
        """获取可执行文件的版本信息"""
        try:
            # 使用 PowerShell 获取文件版本
            cmd = [
                "powershell",
                "-Command",
                f"(Get-Item '{exe_path}').VersionInfo.FileVersion",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            return None

        except Exception as e:
            logger.debug(f"Failed to get file version: {e}")
            return None

    def get_license_file_path(self, install_path: str) -> Optional[str]:
        """获取许可证文件路径"""
        license_paths = [
            os.path.join(install_path, "Custom", "license.txt"),
            os.path.join(install_path, "license.txt"),
            os.path.join(install_path, "Custom", "license.key"),
            os.path.join(install_path, "license.key"),
        ]

        for license_path in license_paths:
            if os.path.exists(license_path):
                return license_path

        return None

    def get_config_file_path(self, install_path: str) -> Optional[str]:
        """获取配置文件路径"""
        config_paths = [
            os.path.join(install_path, "MobaXterm.ini"),
            os.path.join(install_path, "Custom", "MobaXterm.ini"),
        ]

        for config_path in config_paths:
            if os.path.exists(config_path):
                return config_path

        return None


class MobaXtermKeygen:
    """MobaXterm 密钥生成器核心类"""

    def __init__(self) -> None:
        self.version = "22.0"
        self.salt = b"MobaXterm"
        self.key_length = 32

    def generate_license_key(self, username: str, version: Optional[str] = None) -> str:
        """生成 MobaXterm 许可证密钥"""
        if version is None:
            version = self.version

        # 创建许可证数据
        license_data = {
            "username": username,
            "version": version,
            "type": "Professional",
            "created": datetime.now().isoformat(),
            "expires": (
                datetime.now() + timedelta(days=365 * 10)
            ).isoformat(),  # 10年有效期
        }

        # 生成密钥种子
        seed = f"{username}:{version}:{license_data['type']}"
        seed_bytes = seed.encode("utf-8")

        # 使用 PBKDF2 生成密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.key_length,
            salt=self.salt,
            iterations=10000,
            backend=default_backend(),
        )

        key = kdf.derive(seed_bytes)

        # 生成许可证密钥（Base64 编码）
        license_key = base64.b64encode(key).decode("utf-8")

        # 格式化密钥（每4个字符添加一个分隔符）
        formatted_key = "-".join(
            [license_key[i : i + 4] for i in range(0, len(license_key), 4)]
        )

        return formatted_key

    def validate_license_key(
        self, username: str, license_key: str, version: Optional[str] = None
    ) -> bool:
        """验证许可证密钥"""
        if version is None:
            version = self.version

        try:
            # 移除分隔符
            clean_key = license_key.replace("-", "")

            # 解码密钥
            key_bytes = base64.b64decode(clean_key)

            # 重新生成密钥进行验证
            expected_key = self.generate_license_key(username, version)
            expected_clean = expected_key.replace("-", "")
            expected_bytes = base64.b64decode(expected_clean)

            return key_bytes == expected_bytes

        except Exception as e:
            logger.error(f"License key validation failed: {e}")
            return False

    def generate_activation_code(self, username: str, license_key: str) -> str:
        """生成激活码"""
        # 组合用户名和许可证密钥
        activation_data = f"{username}:{license_key}"

        # 生成 SHA256 哈希
        hash_obj = hashlib.sha256(activation_data.encode("utf-8"))
        activation_hash = hash_obj.hexdigest()

        # 取前16位作为激活码
        activation_code = activation_hash[:16].upper()

        return activation_code

    def get_license_info(
        self, username: str, license_key: str, version: Optional[str] = None
    ) -> Dict:
        """获取许可证信息"""
        if version is None:
            version = self.version

        if not self.validate_license_key(username, license_key, version):
            raise KeygenError("Invalid license key")

        # 解析许可证信息
        license_info = {
            "username": username,
            "version": version,
            "type": "Professional",
            "status": "Valid",
            "created": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(days=365 * 10)).isoformat(),
            "license_key": license_key,
            "activation_code": self.generate_activation_code(username, license_key),
        }

        return license_info


@okit_tool(
    "mobaxterm_keygen", "MobaXterm license key generator tool", use_subcommands=True
)
class MobaXtermKeygenTool(BaseTool):
    """MobaXterm 密钥生成工具"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)
        self.keygen = MobaXtermKeygen()
        self.detector = MobaXtermDetector()

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
MobaXterm Keygen Tool - Generate and manage MobaXterm license keys.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Generate and manage MobaXterm license keys"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""

        @cli_group.command()
        def detect() -> None:
            """自动探测系统中安装的 MobaXterm 信息"""
            try:
                console.print("[cyan]正在探测 MobaXterm 安装信息...[/cyan]")

                installation_info = self.detector.detect_installation()

                if installation_info:
                    console.print(f"[green]✓ 发现 MobaXterm 安装[/green]")
                    console.print(f"  安装路径: {installation_info['install_path']}")
                    console.print(f"  版本: {installation_info['version']}")
                    console.print(
                        f"  检测方法: {installation_info['detection_method']}"
                    )

                    if "display_name" in installation_info:
                        console.print(
                            f"  显示名称: {installation_info['display_name']}"
                        )

                    if "exe_path" in installation_info:
                        console.print(f"  可执行文件: {installation_info['exe_path']}")

                    # 检查许可证文件
                    license_path = self.detector.get_license_file_path(
                        installation_info["install_path"]
                    )
                    if license_path:
                        console.print(f"  许可证文件: {license_path}")
                    else:
                        console.print("  许可证文件: 未找到")

                    # 检查配置文件
                    config_path = self.detector.get_config_file_path(
                        installation_info["install_path"]
                    )
                    if config_path:
                        console.print(f"  配置文件: {config_path}")
                    else:
                        console.print("  配置文件: 未找到")

                    # 保存检测结果到配置
                    self._save_detection_info(installation_info)

                else:
                    console.print("[yellow]⚠ 未发现 MobaXterm 安装[/yellow]")
                    console.print("  请检查以下位置:")
                    for path in self.detector.known_paths:
                        console.print(f"    - {path}")
                    console.print(
                        "  或者确保 MobaXterm 已正确安装并添加到 PATH 环境变量"
                    )

            except Exception as e:
                logger.error(f"Failed to detect MobaXterm: {e}")
                console.print(f"[red]Error detecting MobaXterm: {e}[/red]")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username for the license")
        @click.option(
            "--version", default="22.0", help="MobaXterm version (default: 22.0)"
        )
        @click.option("--output", help="Output file path for license info")
        @click.option(
            "--format",
            type=click.Choice(["json", "text"]),
            default="text",
            help="Output format",
        )
        def generate(username: str, version: str, output: str, format: str) -> None:
            """生成 MobaXterm 许可证密钥"""
            try:
                # 生成许可证密钥
                license_key = self.keygen.generate_license_key(username, version)
                activation_code = self.keygen.generate_activation_code(
                    username, license_key
                )

                # 获取许可证信息
                license_info = self.keygen.get_license_info(
                    username, license_key, version
                )

                # 保存到配置
                self._save_license_info(username, license_info)

                # 输出结果
                if format == "json":
                    result = {
                        "username": username,
                        "version": version,
                        "license_key": license_key,
                        "activation_code": activation_code,
                        "license_info": license_info,
                    }
                    output_text = json.dumps(result, indent=2, ensure_ascii=False)
                else:
                    output_text = self._format_license_output(
                        username, version, license_key, activation_code, license_info
                    )

                if output:
                    with open(output, "w", encoding="utf-8") as f:
                        f.write(output_text)
                    console.print(
                        f"[green]License information saved to: {output}[/green]"
                    )
                else:
                    console.print(output_text)

            except Exception as e:
                logger.error(f"Failed to generate license: {e}")
                console.print(f"[red]Error generating license: {e}[/red]")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username for the license")
        @click.option("--license-key", required=True, help="License key to validate")
        @click.option(
            "--version", default="22.0", help="MobaXterm version (default: 22.0)"
        )
        def validate(username: str, license_key: str, version: str) -> None:
            """验证许可证密钥"""
            try:
                is_valid = self.keygen.validate_license_key(
                    username, license_key, version
                )

                if is_valid:
                    console.print(
                        f"[green]✓ License key is valid for {username}[/green]"
                    )

                    # 获取详细信息
                    license_info = self.keygen.get_license_info(
                        username, license_key, version
                    )
                    activation_code = self.keygen.generate_activation_code(
                        username, license_key
                    )

                    console.print(f"  Username: {username}")
                    console.print(f"  Version: {version}")
                    console.print(f"  Type: {license_info['type']}")
                    console.print(f"  Status: {license_info['status']}")
                    console.print(f"  Activation Code: {activation_code}")
                    console.print(f"  Expires: {license_info['expires']}")
                else:
                    console.print(f"[red]✗ License key is invalid for {username}[/red]")

            except Exception as e:
                logger.error(f"Failed to validate license: {e}")
                console.print(f"[red]Error validating license: {e}[/red]")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username for the license")
        @click.option("--license-key", required=True, help="License key")
        def activate(username: str, license_key: str) -> None:
            """生成激活码"""
            try:
                activation_code = self.keygen.generate_activation_code(
                    username, license_key
                )

                console.print(
                    f"[green]Activation code generated for {username}[/green]"
                )
                console.print(f"  Username: {username}")
                console.print(f"  License Key: {license_key}")
                console.print(f"  Activation Code: {activation_code}")

            except Exception as e:
                logger.error(f"Failed to generate activation code: {e}")
                console.print(f"[red]Error generating activation code: {e}[/red]")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", help="Filter by username")
        def list(username: str) -> None:
            """列出已保存的许可证信息"""
            try:
                licenses = self._get_saved_licenses()

                if not licenses:
                    console.print("[yellow]No saved licenses found[/yellow]")
                    return

                console.print(f"[green]Found {len(licenses)} saved license(s):[/green]")

                for license_data in licenses:
                    if username and license_data.get("username") != username:
                        continue

                    console.print(f"  Username: {license_data.get('username', 'N/A')}")
                    console.print(f"  Version: {license_data.get('version', 'N/A')}")
                    console.print(f"  Type: {license_data.get('type', 'N/A')}")
                    console.print(f"  Status: {license_data.get('status', 'N/A')}")
                    console.print(f"  Created: {license_data.get('created', 'N/A')}")
                    console.print(f"  Expires: {license_data.get('expires', 'N/A')}")
                    console.print("  " + "-" * 40)

            except Exception as e:
                logger.error(f"Failed to list licenses: {e}")
                console.print(f"[red]Error listing licenses: {e}[/red]")
                sys.exit(1)

        @cli_group.command()
        @click.option("--username", required=True, help="Username to remove")
        def remove(username: str) -> None:
            """删除保存的许可证信息"""
            try:
                licenses = self._get_saved_licenses()
                original_count = len(licenses)

                # 过滤掉指定用户名的许可证
                filtered_licenses = [
                    l for l in licenses if l.get("username") != username
                ]

                if len(filtered_licenses) == original_count:
                    console.print(
                        f"[yellow]No license found for username: {username}[/yellow]"
                    )
                    return

                # 保存更新后的许可证列表
                self._save_licenses(filtered_licenses)

                removed_count = original_count - len(filtered_licenses)
                console.print(
                    f"[green]Removed {removed_count} license(s) for username: {username}[/green]"
                )

            except Exception as e:
                logger.error(f"Failed to remove license: {e}")
                console.print(f"[red]Error removing license: {e}[/red]")
                sys.exit(1)

    def _save_detection_info(self, detection_info: Dict[str, str]) -> None:
        """保存检测信息到配置"""
        try:
            config_file = self.get_data_file("detection_info.json")
            self.ensure_data_dir()

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(detection_info, f, indent=2, ensure_ascii=False)

            logger.info("Detection information saved")

        except Exception as e:
            logger.error(f"Failed to save detection info: {e}")
            # 不抛出异常，因为这不是关键功能

    def _get_detection_info(self) -> Optional[Dict[str, str]]:
        """获取保存的检测信息"""
        try:
            config_file = self.get_data_file("detection_info.json")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    return cast(Dict[str, str], json.load(f))
            return None
        except Exception as e:
            logger.error(f"Failed to load detection info: {e}")
            return None

    def _format_license_output(
        self,
        username: str,
        version: str,
        license_key: str,
        activation_code: str,
        license_info: Dict,
    ) -> str:
        """格式化许可证输出"""
        output_lines = [
            "=" * 60,
            "MobaXterm License Information",
            "=" * 60,
            f"Username: {username}",
            f"Version: {version}",
            f"Type: {license_info['type']}",
            f"Status: {license_info['status']}",
            f"Created: {license_info['created']}",
            f"Expires: {license_info['expires']}",
            "",
            "License Key:",
            f"{license_key}",
            "",
            "Activation Code:",
            f"{activation_code}",
            "",
            "=" * 60,
        ]

        return "\n".join(output_lines)

    def _save_license_info(self, username: str, license_info: Dict) -> None:
        """保存许可证信息到配置"""
        try:
            licenses = self._get_saved_licenses()

            # 更新或添加许可证信息
            updated = False
            for i, license_data in enumerate(licenses):
                if license_data.get("username") == username:
                    licenses[i] = license_info
                    updated = True
                    break

            if not updated:
                licenses.append(license_info)

            self._save_licenses(licenses)
            logger.info(f"License information saved for user: {username}")

        except Exception as e:
            logger.error(f"Failed to save license info: {e}")
            raise KeygenError(f"Failed to save license info: {e}")

    def _get_saved_licenses(self) -> List[Dict[str, Any]]:
        """获取已保存的许可证列表"""
        try:
            config_file = self.get_data_file("licenses.json")
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    return cast(List[Dict], json.load(f))
            return []
        except Exception as e:
            logger.error(f"Failed to load saved licenses: {e}")
            return []

    def _save_licenses(self, licenses: List[Dict]) -> None:
        """保存许可证列表"""
        try:
            config_file = self.get_data_file("licenses.json")
            self.ensure_data_dir()

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(licenses, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save licenses: {e}")
            raise KeygenError(f"Failed to save licenses: {e}")

    def validate_config(self) -> bool:
        """验证配置"""
        try:
            # 检查数据目录
            data_dir = self.get_data_path()
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)

            self.logger.info("Configuration validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _cleanup_impl(self) -> None:
        """自定义清理逻辑"""
        self.logger.info("Executing custom cleanup logic")
        # 可以在这里添加清理逻辑，比如清理过期的许可证信息
        pass
