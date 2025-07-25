"""
okit version module

Simplifies version management, prioritizing package version information.
"""

import os
from typing import Optional


def get_version() -> str:
    """Get okit version number

    优先级：
    1. okit.__version__（推荐自动发布流程写入）
    2. importlib.metadata.version("okit")
    3. 环境变量 ONEKIT_VERSION
    4. 默认值
    """
    # 1. okit.__version__
    try:
        import okit
        if hasattr(okit, "__version__"):
            return okit.__version__
    except Exception:
        pass

    # 2. Installed package version
    try:
        import importlib.metadata
        version = importlib.metadata.version("okit")
        if version:
            return version
    except Exception:
        pass

    # 3. Environment variable
    env_version = os.environ.get("ONEKIT_VERSION")
    if env_version:
        return env_version

    # 4. Default version
    return "0.1.0"
