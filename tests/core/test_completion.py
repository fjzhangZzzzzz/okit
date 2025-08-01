"""Tests for completion module."""

import os
import sys
import platform
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import click

from okit.core.completion import (
    detect_shell,
    get_home_dir,
    get_completion_file,
    get_rc_files,
    is_source_line_present,
    append_source_line,
    generate_completion_script,
    write_completion_script,
    get_source_command,
    auto_enable_completion_if_possible,
    enable_completion,
    disable_completion,
    get_supported_shells,
    get_shell_rc_files,
    get_program_name,
    get_completion_file_template,
)


@pytest.fixture
def mock_home(tmp_path):
    """Mock home directory."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        yield tmp_path


def test_detect_shell():
    """Test shell detection."""
    # Test with SHELL environment variable
    with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
        assert detect_shell() == "bash"
    
    with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
        assert detect_shell() == "zsh"
    
    with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}):
        assert detect_shell() == "fish"
    
    # Test Windows git bash detection
    with patch.dict(os.environ, {"SHELL": "", "MSYSTEM": "MINGW64"}):
        with patch("os.name", "nt"):
            assert detect_shell() == "bash"
    
    # Test Windows process detection
    with patch.dict(os.environ, {"SHELL": ""}):
        with patch("os.name", "nt"):
            with patch("psutil.Process") as mock_process:
                mock_parent = MagicMock()
                mock_parent.name.return_value = "bash.exe"
                mock_process.return_value = mock_parent
                assert detect_shell() == "bash"
    
    # Test unsupported shell
    with patch.dict(os.environ, {"SHELL": "/bin/tcsh"}):
        assert detect_shell() is None


def test_get_home_dir(mock_home):
    """Test home directory retrieval."""
    assert get_home_dir() == mock_home


def test_get_completion_file(mock_home):
    """Test completion file path generation."""
    # Test with for_shell_rc=False (absolute path)
    assert get_completion_file("bash", False) == mock_home / ".okit-complete.bash"
    
    # Test with for_shell_rc=True (tilde path)
    assert get_completion_file("bash", True) == "~/.okit-complete.bash"


def test_get_rc_files(mock_home):
    """Test rc files retrieval."""
    rc_files = get_rc_files("bash")
    assert len(rc_files) == 2
    assert mock_home / ".bashrc" in rc_files
    assert mock_home / ".bash_profile" in rc_files


def test_is_source_line_present(mock_home):
    """Test source line presence check."""
    rc_file = mock_home / ".bashrc"
    completion_file = "~/.okit-complete.bash"
    
    # Test with non-existent file
    assert not is_source_line_present(rc_file, completion_file)
    
    # Test with file containing source line
    rc_file.write_text(f"source {completion_file}\n")
    assert is_source_line_present(rc_file, completion_file)
    
    # Test with file not containing source line
    rc_file.write_text("some other content\n")
    assert not is_source_line_present(rc_file, completion_file)
    
    # Test with file read error
    with patch("pathlib.Path.read_text", side_effect=IOError):
        assert not is_source_line_present(rc_file, completion_file)


def test_append_source_line(mock_home):
    """Test source line appending."""
    rc_file = mock_home / ".bashrc"
    completion_file = "~/.okit-complete.bash"
    
    # Test appending to empty file
    append_source_line(rc_file, "bash", completion_file)
    content = rc_file.read_text()
    assert "# Enable okit CLI completion" in content
    assert f"source {completion_file}" in content
    
    # Test appending to existing file
    original_content = "existing content\n"
    rc_file.write_text(original_content)
    append_source_line(rc_file, "bash", completion_file)
    content = rc_file.read_text()
    assert original_content in content
    assert "# Enable okit CLI completion" in content
    assert f"source {completion_file}" in content
    
    # Test with file write error
    with patch("builtins.print") as mock_print:
        with patch("pathlib.Path.open", side_effect=IOError("Permission denied")):
            append_source_line(rc_file, "bash", completion_file)
            mock_print.assert_called_with(
                f"Failed to write to {rc_file}: Permission denied",
                file=sys.stderr
            )


def test_generate_completion_script():
    """Test completion script generation."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="test completion script"
        )
        
        script = generate_completion_script("bash", "test-program")
        assert script == "test completion script"
        
        # Verify environment variable
        mock_run.assert_called_once()
        env = mock_run.call_args[1]["env"]
        assert "_TEST_PROGRAM_COMPLETE" in env
        assert env["_TEST_PROGRAM_COMPLETE"] == "bash_source"
    
    # Test error case
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Command not found"
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            generate_completion_script("bash", "test-program")
        assert str(exc_info.value) == "Failed to generate completion script: Command not found"


def test_write_completion_script(mock_home):
    """Test completion script writing."""
    with patch("okit.core.completion.generate_completion_script") as mock_generate:
        mock_generate.return_value = "test completion script"
        
        completion_file = write_completion_script("bash")
        assert completion_file is not None
        assert completion_file.exists()
        assert completion_file.read_text() == "test completion script"
    
    # Test error case
    with patch("okit.core.completion.generate_completion_script") as mock_generate:
        mock_generate.side_effect = RuntimeError("Failed to generate")
        
        with patch("builtins.print") as mock_print:
            completion_file = write_completion_script("bash")
            assert completion_file is None
            mock_print.assert_called_with(
                "Failed to write completion script for bash: Failed to generate",
                file=sys.stderr
            )


def test_get_source_command():
    """Test source command retrieval."""
    assert get_source_command("bash") == "source ~/.bashrc"
    assert get_source_command("zsh") == "source ~/.zshrc"
    assert get_source_command("fish") == "source ~/.config/fish/config.fish"
    assert get_source_command("unknown") is None


def test_auto_enable_completion_if_possible(mock_home):
    """Test automatic completion enablement."""
    rc_file = mock_home / ".bashrc"
    
    # Test with non-existent rc file
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        with patch("okit.core.completion.write_completion_script") as mock_write:
            mock_write.return_value = mock_home / ".okit-complete.bash"
            
            # Ensure rc file doesn't exist
            if rc_file.exists():
                rc_file.unlink()
            
            auto_enable_completion_if_possible()
            assert rc_file.exists()
            assert "source ~/.okit-complete.bash" in rc_file.read_text()
    
    # Test with unsupported shell
    with patch("okit.core.completion.detect_shell", return_value="tcsh"):
        # Ensure rc file doesn't exist
        if rc_file.exists():
            rc_file.unlink()
        
        auto_enable_completion_if_possible()
        assert not (mock_home / ".tcshrc").exists()
    
    # Test with write_completion_script failure
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        with patch("okit.core.completion.write_completion_script", return_value=None):
            # Ensure rc file doesn't exist
            if rc_file.exists():
                rc_file.unlink()
            
            auto_enable_completion_if_possible()
            assert not rc_file.exists()


def test_enable_completion(mock_home):
    """Test manual completion enablement."""
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        with patch("okit.core.completion.write_completion_script") as mock_write:
            mock_write.return_value = mock_home / ".okit-complete.bash"
            
            # Test enabling completion
            enable_completion()
            rc_file = mock_home / ".bashrc"
            assert rc_file.exists()
            assert "source ~/.okit-complete.bash" in rc_file.read_text()
    
    # Test with unsupported shell
    with patch("okit.core.completion.detect_shell", return_value="tcsh"):
        with patch("click.echo") as mock_echo:
            enable_completion()
            mock_echo.assert_called_with("Shell completion is only supported for bash, zsh, fish.")
    
    # Test with write_completion_script failure
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        with patch("okit.core.completion.write_completion_script", return_value=None):
            with patch("click.echo") as mock_echo:
                enable_completion()
                mock_echo.assert_called_with("Failed to write completion script for bash.")


def test_disable_completion(mock_home):
    """Test manual completion disablement."""
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        rc_file = mock_home / ".bashrc"
        
        # Create rc file with completion source
        rc_file.write_text(
            "# Enable okit CLI completion\n"
            "source ~/.okit-complete.bash\n"
            "other content\n"
        )
        
        # Create completion script file
        completion_file = mock_home / ".okit-complete.bash"
        completion_file.touch()
        
        # Test disabling completion
        disable_completion()
        
        # Verify source line is removed
        content = rc_file.read_text()
        assert "# Enable okit CLI completion" not in content
        assert "source ~/.okit-complete.bash" not in content
        assert "other content" in content
        
        # Verify completion script is deleted
        assert not completion_file.exists()
    
    # Test with unsupported shell
    with patch("okit.core.completion.detect_shell", return_value="tcsh"):
        with patch("click.echo") as mock_echo:
            disable_completion()
            mock_echo.assert_called_with("Shell completion is only supported for bash, zsh, fish.")
    
    # Test with no completion source
    with patch("okit.core.completion.detect_shell", return_value="bash"):
        rc_file = mock_home / ".bashrc"
        rc_file.write_text("other content\n")
        
        with patch("click.echo") as mock_echo:
            disable_completion()
            mock_echo.assert_called_with("No okit completion source found in shell config.")


def test_get_supported_shells():
    """Test supported shells list."""
    shells = get_supported_shells()
    assert "bash" in shells
    assert "zsh" in shells
    assert "fish" in shells


def test_get_shell_rc_files():
    """Test shell rc files mapping."""
    rc_files = get_shell_rc_files()
    assert ".bashrc" in rc_files["bash"]
    assert ".bash_profile" in rc_files["bash"]
    assert ".zshrc" in rc_files["zsh"]
    assert os.path.join(".config", "fish", "config.fish") in rc_files["fish"]


def test_get_program_name():
    """Test program name retrieval."""
    assert get_program_name() == "okit"


def test_get_completion_file_template():
    """Test completion file template retrieval."""
    assert get_completion_file_template() == ".okit-complete.{shell}"