import pkgutil
import importlib
import os
import sys
from typing import Optional, Any


def auto_register_commands(
    package: str, package_path: str, parent_group: Any, debug_enabled: bool = False
) -> None:
    """
    递归扫描 package_path 下所有 .py 文件（不含 __init__.py），
    自动导入并注册 cli 命令到 parent_group。
    """
    for _, modname, ispkg in pkgutil.iter_modules([package_path]):
        full_modname = f"{package}.{modname}"
        mod_path = os.path.join(package_path, modname)
        if ispkg:
            auto_register_commands(full_modname, mod_path, parent_group, debug_enabled)
        else:
            if modname == "__init__":
                continue
            try:
                module = importlib.import_module(full_modname)
                if hasattr(module, "cli"):
                    cmd = getattr(module, "cli")
                    if (
                        hasattr(cmd, "callback")
                        and callable(cmd.callback)
                        and debug_enabled
                    ):
                        from okit.utils.timing import with_timing

                        cmd.callback = with_timing(cmd.callback)
                    
                    # 确定命令名称：优先使用工具实例的 tool_name，否则使用模块名
                    command_name = modname
                    
                    # 查找模块中的工具类实例（支持 @okit_tool 装饰器）
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        
                        # 检查是否是工具实例（有 tool_name 和 create_cli_group 方法）
                        if (hasattr(attr, 'tool_name') and 
                            hasattr(attr, 'create_cli_group') and 
                            callable(getattr(attr, 'create_cli_group'))):
                            command_name = attr.tool_name
                            break
                    
                    parent_group.add_command(cmd, name=command_name)

            except Exception as e:
                print(f"Failed to import {full_modname}: {e}", file=sys.stderr)


def register_all_tools(
    main_group: Optional[Any] = None, debug_enabled: bool = False
) -> None:
    from okit import tools

    tool_packages = [
        ("okit.tools", os.path.dirname(tools.__file__)),
    ]
    if main_group is None:
        from okit.cli.main import main as main_group
    for pkg_name, pkg_path in tool_packages:
        auto_register_commands(pkg_name, pkg_path, main_group, debug_enabled)
