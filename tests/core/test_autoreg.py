"""Tests for autoreg module."""

import os
import sys
import click
import pytest
import importlib.util
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

from okit.core.autoreg import auto_register_commands, register_all_tools
from okit.core.base_tool import BaseTool


@pytest.fixture
def mock_package():
    """Create a mock package for testing."""
    return "test_package"


@pytest.fixture
def mock_package_path(tmp_path):
    """Create a mock package path with test files."""
    pkg_path = tmp_path / "test_package"
    pkg_path.mkdir()
    
    # Create __init__.py
    (pkg_path / "__init__.py").write_text("")
    
    # Create a test module with CLI command
    test_module = """
import click

@click.command()
def cli():
    \"\"\"Test command\"\"\"
    pass
"""
    (pkg_path / "test_module.py").write_text(test_module)
    
    # Create a test module with tool class
    tool_module = """
import click
from okit.core.base_tool import BaseTool

class TestTool(BaseTool):
    def __init__(self):
        super().__init__("test_tool", "Test Tool")
        
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            \"\"\"Test command\"\"\"
            pass

test_tool = TestTool()
cli = test_tool.create_cli_group()
"""
    (pkg_path / "tool_module.py").write_text(tool_module)
    
    # Create a test package with submodules
    sub_pkg = pkg_path / "sub_package"
    sub_pkg.mkdir()
    (sub_pkg / "__init__.py").write_text("")
    
    # Create a test module in subpackage
    sub_module = """
import click

@click.command()
def cli():
    \"\"\"Sub command\"\"\"
    pass
"""
    (sub_pkg / "sub_module.py").write_text(sub_module)
    
    return pkg_path


def test_auto_register_basic(mock_package, mock_package_path):
    """Test basic command registration."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create test module
    test_module_path = mock_package_path / "test_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.test_module", str(test_module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.test_module"] = module
    spec.loader.exec_module(module)
    
    # Create tool module
    tool_module_path = mock_package_path / "tool_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.tool_module", str(tool_module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.tool_module"] = module
    spec.loader.exec_module(module)
    
    # Register commands
    auto_register_commands(mock_package, str(mock_package_path), parent_group)
    
    # Verify commands were registered
    assert "test_module" in parent_group.commands
    assert "test_tool" in parent_group.commands
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.test_module"]
    del sys.modules[f"{mock_package}.tool_module"]


def test_auto_register_subpackage(mock_package, mock_package_path):
    """Test subpackage command registration."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create subpackage module
    sub_pkg_path = mock_package_path / "sub_package"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.sub_package", str(sub_pkg_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.sub_package"] = module
    
    # Create submodule
    sub_module_path = sub_pkg_path / "sub_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.sub_package.sub_module", str(sub_module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.sub_package.sub_module"] = module
    spec.loader.exec_module(module)
    
    # Register commands
    auto_register_commands(mock_package, str(mock_package_path), parent_group)
    
    # Verify subpackage command was registered
    assert "sub_module" in parent_group.commands
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.sub_package"]
    del sys.modules[f"{mock_package}.sub_package.sub_module"]


def test_auto_register_debug_enabled(mock_package, mock_package_path):
    """Test command registration with debug enabled."""
    parent_group = click.Group()
    
    with patch("okit.utils.timing.with_timing") as mock_timing:
        # Create test package module
        spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[mock_package] = module
        
        # Create test module
        test_module_path = mock_package_path / "test_module.py"
        spec = importlib.util.spec_from_file_location(f"{mock_package}.test_module", str(test_module_path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{mock_package}.test_module"] = module
        spec.loader.exec_module(module)
        
        # Register commands with debug enabled
        auto_register_commands(mock_package, str(mock_package_path), parent_group, debug_enabled=True)
        assert mock_timing.called
        
        # Clean up
        del sys.modules[mock_package]
        del sys.modules[f"{mock_package}.test_module"]


def test_auto_register_import_error(mock_package, mock_package_path):
    """Test handling of import errors."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create a module that will raise an import error
    error_module = """
import non_existent_module

@click.command()
def cli():
    pass
"""
    (mock_package_path / "error_module.py").write_text(error_module)
    
    # Create error module
    error_module_path = mock_package_path / "error_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.error_module", str(error_module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.error_module"] = module
    
    # Test that the error is handled gracefully
    with patch("builtins.print") as mock_print:
        # Mock importlib.import_module to raise ImportError
        def mock_import_module(name, *args, **kwargs):
            if name == f"{mock_package}.error_module":
                raise ImportError("No module named 'non_existent_module'")
            return MagicMock()
        
        with patch("importlib.import_module", side_effect=mock_import_module):
            auto_register_commands(mock_package, str(mock_package_path), parent_group)
            mock_print.assert_called_with(
                f"Failed to import {mock_package}.error_module: No module named 'non_existent_module'",
                file=sys.stderr
            )
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.error_module"]


def test_register_all_tools():
    """Test registration of all tools."""
    main_group = click.Group()
    
    with patch("okit.tools.__file__", "/path/to/tools"):
        with patch("okit.core.autoreg.auto_register_commands") as mock_register:
            register_all_tools(main_group)
            mock_register.assert_called_with(
                "okit.tools",
                "/path/to",
                main_group,
                False
            )


def test_register_all_tools_no_main_group():
    """Test registration of all tools without main group."""
    with patch("okit.tools.__file__", "/path/to/tools"):
        with patch("okit.cli.main.main") as mock_main:
            with patch("okit.core.autoreg.auto_register_commands") as mock_register:
                register_all_tools()
                mock_register.assert_called_with(
                    "okit.tools",
                    "/path/to",
                    mock_main,
                    False
                )


def test_auto_register_multiple_tools(mock_package, mock_package_path):
    """Test registration of multiple tools in the same module."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create a module with multiple tools
    multi_tool_module = """
import click
from okit.core.base_tool import BaseTool

class Tool1(BaseTool):
    def __init__(self):
        super().__init__("tool1", "Tool 1")
        
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            \"\"\"Test command\"\"\"
            pass

class Tool2(BaseTool):
    def __init__(self):
        super().__init__("tool2", "Tool 2")
        
    def _add_cli_commands(self, cli_group):
        @cli_group.command()
        def test():
            \"\"\"Test command\"\"\"
            pass

tool1 = Tool1()
tool2 = Tool2()
cli = tool1.create_cli_group()  # First tool's CLI should be used
"""
    (mock_package_path / "multi_tool_module.py").write_text(multi_tool_module)
    
    # Create module
    module_path = mock_package_path / "multi_tool_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.multi_tool_module", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.multi_tool_module"] = module
    spec.loader.exec_module(module)
    
    # Register commands
    auto_register_commands(mock_package, str(mock_package_path), parent_group)
    
    # Verify first tool's name was used
    assert "tool1" in parent_group.commands
    assert "tool2" not in parent_group.commands
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.multi_tool_module"]


def test_auto_register_invalid_tool(mock_package, mock_package_path):
    """Test handling of invalid tool instances."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create a module with invalid tool
    invalid_tool_module = """
import click

class InvalidTool:
    def __init__(self):
        self.tool_name = "invalid_tool"
        # Missing create_cli_group method

invalid_tool = InvalidTool()
@click.command()
def cli():
    \"\"\"Test command\"\"\"
    pass
"""
    (mock_package_path / "invalid_tool_module.py").write_text(invalid_tool_module)
    
    # Create module
    module_path = mock_package_path / "invalid_tool_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.invalid_tool_module", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.invalid_tool_module"] = module
    spec.loader.exec_module(module)
    
    # Register commands
    auto_register_commands(mock_package, str(mock_package_path), parent_group)
    
    # Verify module name was used instead of tool name
    assert "invalid_tool_module" in parent_group.commands
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.invalid_tool_module"]


def test_auto_register_debug_timing(mock_package, mock_package_path):
    """Test debug timing decorator application."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create a test module with callback
    test_module = """
import click

def original_callback():
    return "test"

@click.command()
def cli():
    \"\"\"Test command\"\"\"
    return original_callback()
"""
    (mock_package_path / "timing_module.py").write_text(test_module)
    
    # Create module
    module_path = mock_package_path / "timing_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.timing_module", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.timing_module"] = module
    spec.loader.exec_module(module)
    
    with patch("okit.utils.timing.with_timing") as mock_timing:
        # Mock the timing decorator
        def timing_wrapper(func):
            def wrapped(*args, **kwargs):
                return f"timed_{func(*args, **kwargs)}"
            return wrapped
        mock_timing.side_effect = timing_wrapper
        
        # Register commands with debug enabled
        auto_register_commands(mock_package, str(mock_package_path), parent_group, debug_enabled=True)
        
        # Verify timing decorator was applied
        assert mock_timing.called
        result = parent_group.commands["timing_module"].callback()
        assert result == "timed_test"
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.timing_module"]


def test_auto_register_other_exceptions(mock_package, mock_package_path):
    """Test handling of other exceptions during registration."""
    parent_group = click.Group()
    
    # Create test package module
    spec = importlib.util.spec_from_file_location(mock_package, str(mock_package_path / "__init__.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[mock_package] = module
    
    # Create a module that will raise an attribute error
    error_module = """
import click

@click.command()
def cli():
    \"\"\"Test command\"\"\"
    pass
"""
    (mock_package_path / "error_module.py").write_text(error_module)
    
    # Create error module
    error_module_path = mock_package_path / "error_module.py"
    spec = importlib.util.spec_from_file_location(f"{mock_package}.error_module", str(error_module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{mock_package}.error_module"] = module
    
    # Mock importlib.import_module to raise AttributeError
    def mock_import_module(name, *args, **kwargs):
        if name == f"{mock_package}.error_module":
            raise AttributeError("'module' object has no attribute 'cli'")
        return module
    
    # Test that the error is handled gracefully
    with patch("builtins.print") as mock_print:
        with patch("importlib.import_module", side_effect=mock_import_module):
            auto_register_commands(mock_package, str(mock_package_path), parent_group)
            mock_print.assert_called()
            assert "Failed to import" in mock_print.call_args[0][0]
    
    # Clean up
    del sys.modules[mock_package]
    del sys.modules[f"{mock_package}.error_module"]