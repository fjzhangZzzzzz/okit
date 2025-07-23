import pkgutil
import importlib
import os
import sys

def auto_register_commands(package, package_path, parent_group):
    """
    递归扫描 package_path 下所有 .py 文件（不含 __init__.py），
    自动导入并注册 cli 命令到 parent_group。
    """
    for _, modname, ispkg in pkgutil.iter_modules([package_path]):
        full_modname = f"{package}.{modname}"
        mod_path = os.path.join(package_path, modname)
        if ispkg:
            # 递归子包
            auto_register_commands(full_modname, mod_path, parent_group)
        else:
            if modname == "__init__":
                continue
            try:
                module = importlib.import_module(full_modname)
                if hasattr(module, "cli"):
                    parent_group.add_command(getattr(module, "cli"), name=modname)
            except Exception as e:
                print(f"Failed to import {full_modname}: {e}", file=sys.stderr)

def register_all_tools(main_group=None):
    # 需要注册的工具包
    from okit import net, fs
    tool_packages = [
        ("okit.net", os.path.dirname(net.__file__)),
        ("okit.fs", os.path.dirname(fs.__file__)),
    ]
    # 允许外部传入 main group，便于测试和复用
    if main_group is None:
        from .main import main as main_group
    for pkg_name, pkg_path in tool_packages:
        auto_register_commands(pkg_name, pkg_path, main_group)
