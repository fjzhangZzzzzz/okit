import click
from typing import Type, Callable
from .base_tool import BaseTool


def okit_tool(
    tool_name: str, description: str = "", use_subcommands: bool = True
) -> Callable[[Type[BaseTool]], Type[BaseTool]]:
    """
    装饰器：将类转换为 okit 工具

    使用示例：
    @okit_tool("my_tool", "我的工具描述")
    class MyTool(BaseTool):
        def _add_cli_commands(self, cli_group):
            # 添加命令
            pass
    """

    def decorator(tool_class: Type[BaseTool]) -> Type[BaseTool]:
        # 将 tool_name 和 description 存储为类属性
        tool_class.tool_name = tool_name
        tool_class.description = description
        tool_class.use_subcommands = use_subcommands
        
        # 创建全局 cli 变量（自动注册机制需要）
        tool_instance = tool_class(tool_name, description)
        cli = tool_instance.create_cli_group(tool_name, description)

        # 将 cli 添加到模块全局变量
        import sys

        current_module = sys.modules[tool_class.__module__]
        setattr(current_module, "cli", cli)

        return tool_class

    return decorator
