import click
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Type
import json
import logging
from datetime import datetime


class BaseTool(ABC):
    """
    基于 Click CLI 的 okit 工具基础类

    提供所有工具共享的基础功能，同时保持与现有自动注册机制的兼容性
    """

    def __init__(self, tool_name: str, description: str = ""):
        """
        初始化基础工具

        Args:
            tool_name: 工具名称，用于标识工具
            description: 工具描述
        """
        self.tool_name = tool_name
        self.description = description

        # 初始化各个管理器
        self._init_managers()

        # 工具生命周期
        self._start_time = datetime.now()

    def _init_managers(self) -> None:
        """初始化各种管理器"""
        from okit.utils.log import console
        from okit.utils.log import logger

        self.logger = logger
        self.console = console

    def create_cli_group(
        self, tool_name: str = "", description: str = ""
    ) -> click.Group:
        """
        创建工具的 Click 命令组

        这是关键方法，确保与自动注册机制兼容
        """
        # Use instance attributes if not provided
        if not tool_name:
            tool_name = self.tool_name
        if not description:
            description = self.description

        @click.group()
        def cli() -> None:
            """Tool CLI entry point"""
            pass

        # 设置 CLI 帮助信息
        cli.help = self._get_cli_help()
        cli.short_help = self._get_cli_short_help()

        # 添加工具特定的命令
        self._add_cli_commands(cli)

        return cli

    @abstractmethod
    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """
        子类必须实现此方法来添加工具特定的 CLI 命令

        Args:
            cli_group: Click 命令组，用于添加子命令
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        验证工具配置是否正确

        Returns:
            bool: 配置是否有效
        """
        pass

    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.tool_name,
            "description": self.description,
            "start_time": self._start_time.isoformat(),
        }

    def cleanup(self) -> None:
        """工具清理工作"""
        self.logger.info(f"工具 {self.tool_name} 正在清理")
        self._cleanup_impl()

    def _cleanup_impl(self) -> None:
        """子类可以重写的清理实现"""
        pass

    def _get_cli_help(self) -> str:
        """
        获取 CLI 帮助信息

        子类可以重写此方法来提供自定义的帮助信息

        Returns:
            str: CLI 帮助信息
        """
        return self.description or f"{self.tool_name} tool"

    def _get_cli_short_help(self) -> str:
        """
        获取 CLI 简短帮助信息

        子类可以重写此方法来提供自定义的简短帮助信息

        Returns:
            str: CLI 简短帮助信息
        """
        return self.description or self.tool_name
