import pkgutil
import importlib
import os
import sys
from okit.utils.log import with_timing

def auto_register_commands(package, package_path, parent_group):
    """
    递归扫描 package_path 下所有 .py 文件（不含 __init__.py），
    自动导入并注册 cli 命令到 parent_group。
    """
    for _, modname, ispkg in pkgutil.iter_modules([package_path]):
        full_modname = f"{package}.{modname}"
        mod_path = os.path.join(package_path, modname)
        if ispkg:
            auto_register_commands(full_modname, mod_path, parent_group)
        else:
            if modname == "__init__":
                continue
            try:
                module = importlib.import_module(full_modname)
                if hasattr(module, "cli"):
                    cmd = getattr(module, "cli")
                    if hasattr(cmd, "callback") and callable(cmd.callback):
                        cmd.callback = with_timing(cmd.callback)
                    parent_group.add_command(cmd, name=modname)
            except Exception as e:
                print(f"Failed to import {full_modname}: {e}", file=sys.stderr)

def register_all_tools(main_group=None):
    from okit import tools
    tool_packages = [
        ("okit.tools", os.path.dirname(tools.__file__)),
    ]
    if main_group is None:
        from .main import main as main_group
    for pkg_name, pkg_path in tool_packages:
        auto_register_commands(pkg_name, pkg_path, main_group)
