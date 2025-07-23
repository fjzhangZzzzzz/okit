"""
okit version module

Simplifies version management, prioritizing package version information.
"""

import os
from typing import Optional


def get_version() -> str:
    """Get okit version number

    Get version number in the following order:
    1. Environment variable OKIT_VERSION
    2. Installed package version
    3. Version number in the module
    """
    # 1. Environment variable
    env_version = os.environ.get("ONEKIT_VERSION")
    if env_version:
        return env_version

    # 2. Installed package version
    try:
        import importlib.metadata

        version = importlib.metadata.version("okit")
        if version:
            return version
    except Exception:
        pass

    # 3. Version number in the module
    try:
        from .. import __version__

        return __version__
    except ImportError:
        pass

    # 4. Default version
    return "0.1.0"


def get_version_info() -> dict:
    """Get version information"""
    version = get_version()
    return {
        "version": version,
        "project_name": "okit",
        "description": "OK Kit",
        "source": _get_version_source(),
    }


def _get_version_source() -> str:
    """Get version number source"""
    if os.environ.get("ONEKIT_VERSION"):
        return "environment"

    try:
        import importlib.metadata

        importlib.metadata.version("okit")
        return "package"
    except Exception:
        pass

    return "module"


def is_development_version() -> bool:
    """Check if it is a development version"""
    version = get_version()
    return version.endswith((".dev", ".alpha", ".beta", ".rc"))


def get_version_tuple() -> tuple:
    """Get version tuple"""
    import re

    version = get_version()
    # Extract numbers
    numbers = re.findall(r"\d+", version)
    return tuple(int(n) for n in numbers)


def is_installed_package() -> bool:
    """Check if it is an installed package"""
    try:
        import importlib.metadata

        importlib.metadata.version("okit")
        return True
    except Exception:
        return False


def is_development_environment() -> bool:
    """Check if it is a development environment"""
    import sys
    from pathlib import Path

    # Check if it is running in a development environment
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        return True

    # Check if pyproject.toml exists
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        return (project_root / "pyproject.toml").exists()
    except Exception:
        return False


# For backward compatibility, provide __version__ variable
__version__ = get_version()