import click
from typing import Type, Callable, Any, Optional
from .base_tool import BaseTool


class LazyCommand(click.Command):
    """延迟加载的Command代理类"""

    def __init__(
        self,
        name: str,
        tool_class: Type[BaseTool],
        tool_description: str,
        use_subcommands: bool = False,
        **kwargs: Any,
    ) -> None:
        # 初始化基本的Command属性，暂不设置callback
        super().__init__(name=name, **kwargs)

        self.tool_class = tool_class
        self.tool_name = name
        self.tool_description = tool_description
        self.use_subcommands = use_subcommands
        self._tool_instance: Optional[BaseTool] = None
        self._real_command: Optional[click.Command] = None

        # 设置基本的help信息，无需实例化工具
        self.help = tool_description or f"{name} tool"
        self.short_help = tool_description or f"{name} tool"

        # 对于 use_subcommands=False 的情况，立即创建真正的命令
        if not use_subcommands:
            self._ensure_real_command()

    def _ensure_real_command(self) -> None:
        """确保真正的命令已经创建"""
        if self._real_command is None:
            # 创建工具实例
            self._tool_instance = self.tool_class(self.tool_name, self.tool_description)
            self._tool_instance.use_subcommands = self.use_subcommands

            # 创建真正的CLI命令
            self._real_command = self._tool_instance.create_cli_group()

            # 复制回调函数
            if hasattr(self._real_command, "callback") and self._real_command.callback:
                self.callback = self._real_command.callback

            # 复制帮助信息
            if hasattr(self._real_command, "help"):
                self.help = self._real_command.help
            if hasattr(self._real_command, "short_help"):
                self.short_help = self._real_command.short_help

            # 复制参数定义
            if hasattr(self._real_command, "params"):
                self.params = self._real_command.params

    def invoke(self, ctx: click.Context) -> Any:
        """重写invoke方法以支持延迟加载"""
        self._ensure_real_command()

        # 如果是真正的命令，直接调用
        if self._real_command:
            return self._real_command.invoke(ctx)

        return super().invoke(ctx)

    def get_help(self, ctx: click.Context) -> str:
        """获取帮助信息，优先使用缓存的描述，避免工具实例化"""
        # 确保真正的命令已经创建
        self._ensure_real_command()

        # 如果真正的命令已经创建，使用它的帮助信息
        if self._real_command and hasattr(self._real_command, "get_help"):
            return self._real_command.get_help(ctx)

        return self.help or f"{self.tool_name} tool"


class LazyGroup(click.Group):
    """延迟加载的Group代理类"""

    def __init__(
        self,
        name: str,
        tool_class: Type[BaseTool],
        tool_description: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, **kwargs)

        self.tool_class = tool_class
        self.tool_name = name
        self.tool_description = tool_description
        self._tool_instance: Optional[BaseTool] = None
        self._real_group: Optional[click.Group] = None
        self._commands_loaded = False

        # 设置基本的help信息
        self.help = tool_description or f"{name} tool"
        self.short_help = tool_description or f"{name} tool"

    def _ensure_real_group(self) -> None:
        """确保真正的group已经创建"""
        if self._real_group is None:
            self._tool_instance = self.tool_class(self.tool_name, self.tool_description)
            self._tool_instance.use_subcommands = True
            self._real_group = self._tool_instance.create_cli_group()

            # 复制callback
            if hasattr(self._real_group, "callback") and self._real_group.callback:
                self.callback = self._real_group.callback

    def _load_commands(self) -> None:
        """加载所有子命令"""
        if not self._commands_loaded:
            self._ensure_real_group()

            # 复制所有子命令
            if isinstance(self._real_group, click.Group):
                for cmd_name, cmd in self._real_group.commands.items():
                    self.add_command(cmd, name=cmd_name)

            self._commands_loaded = True

    def invoke(self, ctx: click.Context) -> Any:
        """重写invoke方法"""
        self._ensure_real_group()

        # 如果有callback，调用它
        if self.callback:
            return ctx.invoke(self.callback, **ctx.params)

        return super().invoke(ctx)

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        """获取子命令时才加载真正的group"""
        self._load_commands()
        return super().get_command(ctx, cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        """列出命令时才加载真正的group"""
        self._load_commands()
        return super().list_commands(ctx)


def okit_tool(
    tool_name: str, description: str = "", use_subcommands: bool = True
) -> Callable[[Type[BaseTool]], Type[BaseTool]]:
    """
    装饰器：将类转换为 okit 工具

    使用延迟加载机制避免启动时的重型初始化

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

        # 创建延迟加载的CLI命令/组，避免立即实例化工具类
        if use_subcommands:
            cli = LazyGroup(
                name=tool_name, tool_class=tool_class, tool_description=description
            )
        else:
            cli = LazyCommand(
                name=tool_name,
                tool_class=tool_class,
                tool_description=description,
                use_subcommands=use_subcommands,
            )

        # 将 cli 添加到模块全局变量
        import sys

        current_module = sys.modules[tool_class.__module__]
        setattr(current_module, "cli", cli)

        return tool_class

    return decorator
