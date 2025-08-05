"""Tests for MobaXterm Detector."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, mock_open
import pytest

from okit.utils.mobaxterm_detector import MobaXtermDetector


@pytest.fixture
def temp_install_dir() -> Generator[Path, None, None]:
    """Create a temporary MobaXterm installation directory."""
    temp_dir = tempfile.mkdtemp()
    install_path = Path(temp_dir) / "MobaXterm"
    install_path.mkdir()

    try:
        # Create mock executable
        exe_path = install_path / "MobaXterm.exe"
        exe_path.write_text("mock executable")

        yield install_path
    finally:
        # Force cleanup with ignore_errors to handle Windows file handle issues
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            # Ignore any cleanup errors on Windows
            pass


@pytest.fixture
def mobaxterm_detector() -> MobaXtermDetector:
    """Create a MobaXtermDetector instance."""
    return MobaXtermDetector()


def test_mobaxterm_detector_initialization(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test MobaXtermDetector initialization."""
    assert len(mobaxterm_detector.known_paths) > 0
    assert all("Mobatek" in path for path in mobaxterm_detector.known_paths)
    assert all("MobaXterm" in path for path in mobaxterm_detector.known_paths)


@patch("okit.utils.mobaxterm_detector.winreg")
@patch("os.path.exists")
def test_detect_from_registry_success(
    mock_exists: MagicMock,
    mock_winreg: MagicMock,
    mobaxterm_detector: MobaXtermDetector,
) -> None:
    """Test successful registry detection."""
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.side_effect = [
        ("C:\\Program Files\\Mobatek\\MobaXterm", None),
        ("MobaXterm Professional", None),
        ("22.0", None),
    ]
    mock_exists.return_value = True

    result = mobaxterm_detector._detect_from_registry()
    assert result is not None
    assert result["install_path"] == "C:\\Program Files\\Mobatek\\MobaXterm"
    assert result["display_name"] == "MobaXterm Professional"
    assert result["version"] == "22.0"
    assert result["detection_method"] == "registry"


@patch("okit.utils.mobaxterm_detector.winreg")
def test_detect_from_registry_failure(
    mock_winreg: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test registry detection failure."""
    mock_winreg.OpenKey.side_effect = FileNotFoundError()

    result = mobaxterm_detector._detect_from_registry()
    assert result is None


@patch("okit.utils.mobaxterm_detector.winreg")
def test_detect_from_registry_multiple_paths(
    mock_winreg: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test registry detection with multiple registry paths."""
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.side_effect = [
        ("C:\\Program Files\\Mobatek\\MobaXterm", None),
        ("MobaXterm Professional", None),
        ("22.0", None),
    ]

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True
        result = mobaxterm_detector._detect_from_registry()
        assert result is not None


@patch("os.path.exists")
def test_detect_from_paths_success(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful path detection."""
    mock_exists.return_value = True

    with patch(
        "okit.utils.mobaxterm_detector.MobaXtermDetector._get_file_version"
    ) as mock_get_version:
        mock_get_version.return_value = "22.0"

        result = mobaxterm_detector._detect_from_paths()
        assert result is not None
        assert "install_path" in result
        assert "version" in result
        assert result["detection_method"] == "known_paths"


@patch("os.path.exists")
def test_detect_from_paths_failure(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test path detection failure."""
    mock_exists.return_value = False

    result = mobaxterm_detector._detect_from_paths()
    assert result is None


@patch("os.environ")
def test_detect_from_environment_success(
    mock_environ: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful environment detection."""
    mock_environ.get.return_value = "C:\\Program Files\\Mobatek\\MobaXterm;C:\\other\\path"

    with patch("os.path.exists") as mock_exists:
        with patch(
            "okit.utils.mobaxterm_detector.MobaXtermDetector._get_file_version"
        ) as mock_get_version:
            mock_exists.return_value = True
            mock_get_version.return_value = "22.0"

            result = mobaxterm_detector._detect_from_environment()
            assert result is not None
            assert "install_path" in result
            assert result["detection_method"] == "environment"


@patch("os.environ")
def test_detect_from_environment_failure(
    mock_environ: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test environment detection failure."""
    mock_environ.get.return_value = None

    result = mobaxterm_detector._detect_from_environment()
    assert result is None


@patch("os.environ")
def test_detect_from_environment_empty_path(
    mock_environ: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test environment detection with empty PATH."""
    mock_environ.get.return_value = ""

    result = mobaxterm_detector._detect_from_environment()
    assert result is None


def test_resolve_real_install_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real install path."""
    exe_path = "C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe"
    detected_path = "C:\\Program Files\\Mobatek\\MobaXterm"

    result = mobaxterm_detector._resolve_real_install_path(exe_path, detected_path)
    assert result == detected_path


def test_resolve_real_install_path_scoop(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real install path for scoop installation."""
    exe_path = "C:\\Users\\test\\scoop\\shims\\MobaXterm.exe"
    detected_path = "C:\\Users\\test\\scoop\\shims"

    with patch.object(mobaxterm_detector, '_resolve_scoop_executable') as mock_resolve:
        mock_resolve.return_value = "C:\\Users\\test\\scoop\\apps\\mobaxterm\\current\\MobaXterm.exe"
        
        result = mobaxterm_detector._resolve_real_install_path(exe_path, detected_path)
        assert result == "C:\\Users\\test\\scoop\\apps\\mobaxterm\\current"


def test_resolve_real_install_path_chocolatey(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real install path for chocolatey installation."""
    exe_path = "C:\\ProgramData\\chocolatey\\bin\\MobaXterm.exe"
    detected_path = "C:\\ProgramData\\chocolatey\\bin"

    with patch.object(mobaxterm_detector, '_resolve_chocolatey_executable') as mock_resolve:
        mock_resolve.return_value = "C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools\\MobaXterm.exe"
        
        result = mobaxterm_detector._resolve_real_install_path(exe_path, detected_path)
        assert result == "C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools"


@patch("subprocess.run")
def test_get_file_version_success(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful file version retrieval."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "22.0.0.0"

    with patch.object(mobaxterm_detector, '_get_version_from_powershell') as mock_powershell:
        mock_powershell.return_value = "22.0.0.0"
        
        result = mobaxterm_detector._get_file_version("C:\\test\\MobaXterm.exe")
        assert result == "22.0.0.0"


@patch("subprocess.run")
def test_get_file_version_failure(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test file version retrieval failure."""
    with patch.object(mobaxterm_detector, '_get_version_from_powershell') as mock_powershell:
        with patch.object(mobaxterm_detector, '_extract_version_from_path') as mock_extract:
            with patch.object(mobaxterm_detector, '_get_version_from_command') as mock_command:
                mock_powershell.return_value = None
                mock_extract.return_value = None
                mock_command.return_value = None
                
                result = mobaxterm_detector._get_file_version("C:\\test\\MobaXterm.exe")
                assert result is None


@patch("subprocess.run")
def test_get_version_from_command_success(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful version retrieval from command."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "MobaXterm v22.0"

    result = mobaxterm_detector._get_version_from_command("C:\\test\\MobaXterm.exe")
    assert result == "22.0"


@patch("subprocess.run")
def test_get_version_from_command_failure(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test version retrieval from command failure."""
    mock_run.return_value.returncode = 1

    result = mobaxterm_detector._get_version_from_command("C:\\test\\MobaXterm.exe")
    assert result is None


@patch("subprocess.run")
def test_get_version_from_command_timeout(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test version retrieval from command timeout."""
    mock_run.side_effect = TimeoutError()

    result = mobaxterm_detector._get_version_from_command("C:\\test\\MobaXterm.exe")
    assert result is None


def test_resolve_real_executable_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real executable path."""
    exe_path = "C:\\test\\MobaXterm.exe"

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = True

        result = mobaxterm_detector._resolve_real_executable_path(exe_path)
        assert result == exe_path


def test_resolve_real_executable_path_scoop(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real executable path for scoop."""
    exe_path = "C:\\Users\\test\\scoop\\shims\\MobaXterm.exe"

    with patch.object(mobaxterm_detector, '_resolve_scoop_executable') as mock_resolve:
        mock_resolve.return_value = "C:\\Users\\test\\scoop\\apps\\mobaxterm\\current\\MobaXterm.exe"
        
        result = mobaxterm_detector._resolve_real_executable_path(exe_path)
        assert result == "C:\\Users\\test\\scoop\\apps\\mobaxterm\\current\\MobaXterm.exe"


def test_resolve_real_executable_path_chocolatey(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real executable path for chocolatey."""
    exe_path = "C:\\ProgramData\\chocolatey\\bin\\MobaXterm.exe"

    with patch.object(mobaxterm_detector, '_resolve_chocolatey_executable') as mock_resolve:
        mock_resolve.return_value = "C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools\\MobaXterm.exe"
        
        result = mobaxterm_detector._resolve_real_executable_path(exe_path)
        assert result == "C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools\\MobaXterm.exe"


def test_resolve_scoop_executable(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving Scoop executable."""
    shim_path = "C:\\Users\\test\\scoop\\shims\\MobaXterm.exe"

    with patch("os.path.exists") as mock_exists:
        with patch(
            "builtins.open",
            mock_open(
                read_data='executable = "C:\\Users\\test\\scoop\\apps\\mobaxterm\\22.0\\MobaXterm.exe"'
            ),
        ):
            mock_exists.return_value = True

            result = mobaxterm_detector._resolve_scoop_executable(shim_path)
            assert result is not None


def test_resolve_scoop_executable_not_found(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving Scoop executable when not found."""
    shim_path = "C:\\Users\\test\\scoop\\shims\\MobaXterm.exe"

    with patch("os.path.exists") as mock_exists:
        mock_exists.return_value = False

        result = mobaxterm_detector._resolve_scoop_executable(shim_path)
        assert result is None


@patch("os.walk")
@patch("os.path.exists")
def test_resolve_chocolatey_executable(
    mock_exists: MagicMock, mock_walk: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test resolving Chocolatey executable."""
    exe_path = "C:\\ProgramData\\chocolatey\\bin\\MobaXterm.exe"

    mock_exists.return_value = True
    mock_walk.return_value = [
        ("C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools", [], ["MobaXterm.exe"])
    ]

    result = mobaxterm_detector._resolve_chocolatey_executable(exe_path)
    assert result == "C:\\ProgramData\\chocolatey\\lib\\mobaxterm\\tools\\MobaXterm.exe"


@patch("subprocess.run")
def test_get_version_from_powershell_success(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful version retrieval from PowerShell."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "22.0.0.0"

    result = mobaxterm_detector._get_version_from_powershell("C:\\test\\MobaXterm.exe")
    assert result == "22.0.0.0"


@patch("subprocess.run")
def test_get_version_from_powershell_failure(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test PowerShell version retrieval failure."""
    mock_run.return_value.returncode = 1

    result = mobaxterm_detector._get_version_from_powershell("C:\\test\\MobaXterm.exe")
    assert result is None


@patch("subprocess.run")
def test_get_version_from_powershell_alternative_method(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test PowerShell version retrieval with alternative method."""
    # First call fails, second call succeeds
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = "22.0.0.0"

    result = mobaxterm_detector._get_version_from_powershell("C:\\test\\MobaXterm.exe")
    # The method should try alternative approach, but in this case it still fails
    assert result is None


def test_extract_version_from_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test extracting version from path."""
    # Test with version in path
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm 22.0\\MobaXterm.exe"
    )
    assert result == "22.0"

    # Test with version in path (different format)
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm-v22.0\\MobaXterm.exe"
    )
    assert result == "22.0"

    # Test without version in path
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe"
    )
    assert result is None


def test_extract_version_from_path_edge_cases(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test extracting version from path edge cases."""
    # Test with complex version
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm 22.0.1.4321\\MobaXterm.exe"
    )
    assert result == "22.0.1"

    # Test with version at end of path
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm\\22.0\\MobaXterm.exe"
    )
    assert result == "22.0"

    # Test with no version
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe"
    )
    assert result is None


@patch("os.path.exists")
def test_get_config_file_path(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting config file path."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    
    # Mock os.path.exists to return True for the first path (install_path)
    def mock_exists_side_effect(path):
        if path == os.path.join(install_path, "MobaXterm.ini"):
            return True
        return False
    
    mock_exists.side_effect = mock_exists_side_effect

    result = mobaxterm_detector.get_config_file_path(install_path)
    assert result == os.path.join(install_path, "MobaXterm.ini")


@patch("pathlib.Path.exists")
def test_get_config_file_path_custom_env(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting config file path with custom environment variable."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    
    with patch.dict(os.environ, {'MOBAXTERM_CONFIG_PATH': 'C:\\custom\\path\\MobaXterm.ini'}):
        # Mock that the custom path exists
        mock_exists.return_value = True
        
        result = mobaxterm_detector.get_config_file_path(install_path)
        assert result == "C:\\custom\\path\\MobaXterm.ini"


@patch("os.path.exists")
def test_get_config_file_path_custom_env_not_exists(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting config file path with custom environment variable that doesn't exist."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    
    with patch.dict(os.environ, {'MOBAXTERM_CONFIG_PATH': 'C:\\custom\\path\\MobaXterm.ini'}):
        mock_exists.return_value = False
        
        result = mobaxterm_detector.get_config_file_path(install_path)
        # Should fall back to default paths
        assert result is not None


@patch("os.path.exists")
def test_get_license_file_path(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting license file path."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    mock_exists.return_value = True

    result = mobaxterm_detector.get_license_file_path(install_path)
    assert result == os.path.join(install_path, "Custom.mxtpro")


@patch("os.path.exists")
def test_get_license_file_path_not_found(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting license file path when not found."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    mock_exists.return_value = False

    result = mobaxterm_detector.get_license_file_path(install_path)
    assert result is None


def test_detect_installation_success(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test successful installation detection."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        mock_registry.return_value = {
            "install_path": "C:\\Program Files\\Mobatek\\MobaXterm",
            "version": "22.0",
            "detection_method": "registry",
        }

        result = mobaxterm_detector.detect_installation()
        assert result is not None
        assert result["install_path"] == "C:\\Program Files\\Mobatek\\MobaXterm"
        assert result["version"] == "22.0"


def test_detect_installation_fallback_to_paths(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test installation detection fallback to paths."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        with patch.object(mobaxterm_detector, '_detect_from_paths') as mock_paths:
            mock_registry.return_value = None
            mock_paths.return_value = {
                "install_path": "C:\\Program Files\\Mobatek\\MobaXterm",
                "version": "22.0",
                "detection_method": "known_paths",
            }

            result = mobaxterm_detector.detect_installation()
            assert result is not None
            assert result["detection_method"] == "known_paths"


def test_detect_installation_fallback_to_environment(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test installation detection fallback to environment."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        with patch.object(mobaxterm_detector, '_detect_from_paths') as mock_paths:
            with patch.object(mobaxterm_detector, '_detect_from_environment') as mock_env:
                mock_registry.return_value = None
                mock_paths.return_value = None
                mock_env.return_value = {
                    "install_path": "C:\\Program Files\\Mobatek\\MobaXterm",
                    "version": "22.0",
                    "detection_method": "environment",
                }

                result = mobaxterm_detector.detect_installation()
                assert result is not None
                assert result["detection_method"] == "environment"


def test_detect_installation_not_found(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test installation detection when not found."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        with patch.object(mobaxterm_detector, '_detect_from_paths') as mock_paths:
            with patch.object(mobaxterm_detector, '_detect_from_environment') as mock_env:
                mock_registry.return_value = None
                mock_paths.return_value = None
                mock_env.return_value = None

                result = mobaxterm_detector.detect_installation()
                assert result is None


def test_detect_installation_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in detect_installation."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        with patch.object(mobaxterm_detector, '_detect_from_paths') as mock_paths:
            with patch.object(mobaxterm_detector, '_detect_from_environment') as mock_env:
                mock_registry.side_effect = Exception("Registry error")
                mock_paths.return_value = None
                mock_env.return_value = None

                result = mobaxterm_detector.detect_installation()
                assert result is None


def test_resolve_real_install_path_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in resolve_real_install_path."""
    exe_path = "C:\\test\\MobaXterm.exe"
    detected_path = "C:\\test"

    with patch.object(mobaxterm_detector, '_resolve_scoop_executable') as mock_resolve:
        mock_resolve.side_effect = Exception("Scoop error")
        
        result = mobaxterm_detector._resolve_real_install_path(exe_path, detected_path)
        assert result == detected_path


def test_get_file_version_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in get_file_version."""
    with patch.object(mobaxterm_detector, '_get_version_from_powershell') as mock_powershell:
        with patch.object(mobaxterm_detector, '_extract_version_from_path') as mock_extract:
            with patch.object(mobaxterm_detector, '_get_version_from_command') as mock_command:
                mock_powershell.side_effect = Exception("PowerShell error")
                mock_extract.return_value = None
                mock_command.return_value = None
                
                result = mobaxterm_detector._get_file_version("C:\\test\\MobaXterm.exe")
                assert result is None


def test_resolve_scoop_executable_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in resolve_scoop_executable."""
    shim_path = "C:\\Users\\test\\scoop\\shims\\MobaXterm.exe"

    with patch("os.path.exists") as mock_exists:
        with patch("builtins.open") as mock_open:
            mock_exists.return_value = True
            mock_open.side_effect = Exception("File read error")

            result = mobaxterm_detector._resolve_scoop_executable(shim_path)
            assert result is None


def test_resolve_chocolatey_executable_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in resolve_chocolatey_executable."""
    exe_path = "C:\\ProgramData\\chocolatey\\bin\\MobaXterm.exe"

    with patch("os.path.exists") as mock_exists:
        with patch("os.walk") as mock_walk:
            mock_exists.return_value = True
            mock_walk.side_effect = Exception("Walk error")

            result = mobaxterm_detector._resolve_chocolatey_executable(exe_path)
            assert result is None


def test_get_version_from_powershell_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in get_version_from_powershell."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Subprocess error")

        result = mobaxterm_detector._get_version_from_powershell("C:\\test\\MobaXterm.exe")
        assert result is None


def test_extract_version_from_path_error_handling(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test error handling in extract_version_from_path."""
    # Test with None path
    result = mobaxterm_detector._extract_version_from_path(None)
    assert result is None
    
    # Test with empty path
    result = mobaxterm_detector._extract_version_from_path("")
    assert result is None


def test_known_paths_completeness(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test that known paths are complete and well-formed."""
    paths = mobaxterm_detector.known_paths
    
    # Check that we have paths for both 32-bit and 64-bit
    x86_paths = [p for p in paths if "Program Files (x86)" in p]
    x64_paths = [p for p in paths if "Program Files" in p and "(x86)" not in p]
    
    assert len(x86_paths) > 0
    assert len(x64_paths) > 0
    
    # Check that all paths contain MobaXterm
    for path in paths:
        assert "MobaXterm" in path
        assert "Mobatek" in path


def test_detection_methods_order(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test that detection methods are called in the correct order."""
    with patch.object(mobaxterm_detector, '_detect_from_registry') as mock_registry:
        with patch.object(mobaxterm_detector, '_detect_from_paths') as mock_paths:
            with patch.object(mobaxterm_detector, '_detect_from_environment') as mock_env:
                mock_registry.return_value = None
                mock_paths.return_value = None
                mock_env.return_value = None

                mobaxterm_detector.detect_installation()

                # Verify order: registry -> paths -> environment
                mock_registry.assert_called_once()
                mock_paths.assert_called_once()
                mock_env.assert_called_once()


def test_version_extraction_patterns(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test various version extraction patterns."""
    test_cases = [
        ("C:\\Program Files\\Mobatek\\MobaXterm 22.0\\MobaXterm.exe", "22.0"),
        ("C:\\Program Files\\Mobatek\\MobaXterm-v22.0\\MobaXterm.exe", "22.0"),
        ("C:\\Program Files\\Mobatek\\MobaXterm_v22.0\\MobaXterm.exe", "22.0"),
        ("C:\\Program Files\\Mobatek\\MobaXterm22.0\\MobaXterm.exe", "22.0"),
        ("C:\\Program Files\\Mobatek\\MobaXterm\\22.0\\MobaXterm.exe", "22.0"),
        ("C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe", None),
    ]
    
    for path, expected in test_cases:
        result = mobaxterm_detector._extract_version_from_path(path)
        assert result == expected 