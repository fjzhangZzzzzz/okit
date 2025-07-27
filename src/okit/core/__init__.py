"""
Core framework components for okit tools.

This module contains the foundational classes and decorators that all okit tools
are built upon, including BaseTool, the okit_tool decorator, auto-registration,
and completion functionality.
"""

from .base_tool import BaseTool
from .tool_decorator import okit_tool
from .autoreg import auto_register_commands, register_all_tools
from .completion import (
    enable_completion,
    disable_completion,
    auto_enable_completion_if_possible,
    detect_shell,
    get_supported_shells,
)

__all__ = [
    "BaseTool",
    "okit_tool",
    "auto_register_commands",
    "register_all_tools",
    "enable_completion",
    "disable_completion",
    "auto_enable_completion_if_possible",
    "detect_shell",
    "get_supported_shells",
]
