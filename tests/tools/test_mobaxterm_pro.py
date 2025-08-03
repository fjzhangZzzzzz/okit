"""Tests for mobaxterm_pro tool."""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock, mock_open
import pytest
from click.testing import CliRunner

from okit.tools.mobaxterm_pro import (
    MobaXtermDetector,
    MobaXtermKeygen,
    MobaXtermProTool,
    KeygenError,
)


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

        # Create mock license file
        license_path = install_path / "Custom.mxtpro"
        license_path.write_text("mock license")

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
def temp_license_file() -> Generator[Path, None, None]:
    """Create a temporary license file."""
    with tempfile.NamedTemporaryFile(suffix=".mxtpro", delete=False) as f:
        f.write(b"mock license content")
        license_path = Path(f.name)

    yield license_path
    license_path.unlink(missing_ok=True)


@pytest.fixture
def mobaxterm_detector() -> MobaXtermDetector:
    """Create a MobaXtermDetector instance."""
    return MobaXtermDetector()


@pytest.fixture
def mobaxterm_keygen() -> MobaXtermKeygen:
    """Create a MobaXtermKeygen instance."""
    return MobaXtermKeygen()


@pytest.fixture
def mobaxterm_pro_tool() -> MobaXtermProTool:
    """Create a MobaXtermProTool instance."""
    return MobaXtermProTool("mobaxterm-pro")


def test_mobaxterm_detector_initialization(
    mobaxterm_detector: MobaXtermDetector,
) -> None:
    """Test MobaXtermDetector initialization."""
    assert len(mobaxterm_detector.known_paths) > 0
    assert all("Mobatek" in path for path in mobaxterm_detector.known_paths)


@patch("okit.tools.mobaxterm_pro.winreg")
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


@patch("okit.tools.mobaxterm_pro.winreg")
def test_detect_from_registry_failure(
    mock_winreg: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test registry detection failure."""
    mock_winreg.OpenKey.side_effect = FileNotFoundError()

    result = mobaxterm_detector._detect_from_registry()
    assert result is None


@patch("okit.tools.mobaxterm_pro.os.path.exists")
def test_detect_from_paths_success(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful path detection."""
    mock_exists.return_value = True

    with patch(
        "okit.tools.mobaxterm_pro.MobaXtermDetector._get_file_version"
    ) as mock_get_version:
        mock_get_version.return_value = "22.0"

        result = mobaxterm_detector._detect_from_paths()
        assert result is not None
        assert "install_path" in result
        assert "version" in result
        assert result["detection_method"] == "known_paths"


@patch("okit.tools.mobaxterm_pro.os.path.exists")
def test_detect_from_paths_failure(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test path detection failure."""
    mock_exists.return_value = False

    result = mobaxterm_detector._detect_from_paths()
    assert result is None


@patch("okit.tools.mobaxterm_pro.os.environ")
def test_detect_from_environment_success(
    mock_environ: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful environment detection."""
    mock_environ.get.return_value = "C:\\Program Files\\Mobatek\\MobaXterm"

    with patch("okit.tools.mobaxterm_pro.os.path.exists") as mock_exists:
        with patch(
            "okit.tools.mobaxterm_pro.MobaXtermDetector._get_file_version"
        ) as mock_get_version:
            mock_exists.return_value = True
            mock_get_version.return_value = "22.0"

            result = mobaxterm_detector._detect_from_environment()
            assert result is not None
            assert "install_path" in result
            assert result["detection_method"] == "environment"


@patch("okit.tools.mobaxterm_pro.os.environ")
def test_detect_from_environment_failure(
    mock_environ: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test environment detection failure."""
    mock_environ.get.return_value = None

    result = mobaxterm_detector._detect_from_environment()
    assert result is None


def test_resolve_real_install_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real install path."""
    exe_path = "C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe"
    detected_path = "C:\\Program Files\\Mobatek\\MobaXterm"

    result = mobaxterm_detector._resolve_real_install_path(exe_path, detected_path)
    assert result == detected_path


@patch("subprocess.run")
def test_get_file_version_success(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test successful file version retrieval."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "22.0.0.0"

    result = mobaxterm_detector._get_file_version("C:\\test\\MobaXterm.exe")
    assert result == "22.0.0.0"


@patch("subprocess.run")
def test_get_file_version_failure(
    mock_run: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test file version retrieval failure."""
    mock_run.return_value.returncode = 1

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


def test_resolve_real_executable_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving real executable path."""
    exe_path = "C:\\test\\MobaXterm.exe"

    with patch("okit.tools.mobaxterm_pro.os.path.exists") as mock_exists:
        mock_exists.return_value = True

        result = mobaxterm_detector._resolve_real_executable_path(exe_path)
        assert result == exe_path


def test_resolve_scoop_executable(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test resolving Scoop executable."""
    shim_path = "C:\\Users\\test\\scoop\\apps\\mobaxterm\\current\\MobaXterm.exe"

    with patch("okit.tools.mobaxterm_pro.os.path.exists") as mock_exists:
        with patch(
            "builtins.open",
            mock_open(
                read_data="C:\\Users\\test\\scoop\\apps\\mobaxterm\\22.0\\MobaXterm.exe"
            ),
        ):
            mock_exists.return_value = True

            result = mobaxterm_detector._resolve_scoop_executable(shim_path)
            assert result is not None


@patch("okit.tools.mobaxterm_pro.os.walk")
@patch("okit.tools.mobaxterm_pro.os.path.exists")
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


def test_extract_version_from_path(mobaxterm_detector: MobaXtermDetector) -> None:
    """Test extracting version from path."""
    # Test with version in path
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm 22.0\\MobaXterm.exe"
    )
    assert result == "22.0"

    # Test without version in path
    result = mobaxterm_detector._extract_version_from_path(
        "C:\\Program Files\\Mobatek\\MobaXterm\\MobaXterm.exe"
    )
    assert result is None


@patch("os.path.exists")
def test_get_license_file_path(
    mock_exists: MagicMock, mobaxterm_detector: MobaXtermDetector
) -> None:
    """Test getting license file path."""
    install_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    mock_exists.return_value = True

    result = mobaxterm_detector.get_license_file_path(install_path)
    assert result == os.path.join(install_path, "Custom.mxtpro")


def test_mobaxterm_keygen_initialization(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test MobaXtermKeygen initialization."""
    assert len(mobaxterm_keygen.VariantBase64Table) > 0


def test_generate_license_key(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key generation."""
    username = "testuser"
    version = "22.0"

    license_key = mobaxterm_keygen.generate_license_key(username, version)
    assert isinstance(license_key, str)
    assert len(license_key) > 0


def test_generate_license_key_invalid_version(
    mobaxterm_keygen: MobaXtermKeygen,
) -> None:
    """Test license key generation with invalid version."""
    username = "testuser"
    version = "invalid"

    with pytest.raises(KeygenError):
        mobaxterm_keygen.generate_license_key(username, version)


def test_create_license_file(
    mobaxterm_keygen: MobaXtermKeygen, temp_license_file: Path
) -> None:
    """Test license file creation."""
    username = "testuser"
    version = "22.0"

    result = mobaxterm_keygen.create_license_file(
        username, version, str(temp_license_file)
    )
    assert result == str(temp_license_file)
    assert temp_license_file.exists()


def test_decode_license_key(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key decoding."""
    # Generate a license key first
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    # Decode the license key
    result = mobaxterm_keygen.decode_license_key(license_key)
    assert result is not None


def test_decode_license_key_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test decoding invalid license key."""
    result = mobaxterm_keygen.decode_license_key("invalid_key")
    assert result is None


def test_validate_license_file(
    mobaxterm_keygen: MobaXtermKeygen, temp_license_file: Path
) -> None:
    """Test license file validation."""
    # Create a valid license file
    username = "testuser"
    version = "22.0"
    mobaxterm_keygen.create_license_file(username, version, str(temp_license_file))

    result = mobaxterm_keygen.validate_license_file(str(temp_license_file))
    assert result is True


def test_validate_license_file_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test invalid license file validation."""
    result = mobaxterm_keygen.validate_license_file("/nonexistent/file.mxtpro")
    assert result is False


def test_validate_license_key(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key validation."""
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    result = mobaxterm_keygen.validate_license_key(username, license_key, version)
    assert result is True


def test_validate_license_key_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test invalid license key validation."""
    result = mobaxterm_keygen.validate_license_key("testuser", "invalid_key", "22.0")
    assert result is False


def test_get_license_info(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test getting license information."""
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    result = mobaxterm_keygen.get_license_info(license_key)
    assert result is not None
    assert "username" in result
    assert "version" in result


def test_get_license_info_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test getting license information for invalid key."""
    result = mobaxterm_keygen.get_license_info("invalid_key")
    assert result is None


def test_mobaxterm_pro_tool_initialization(
    mobaxterm_pro_tool: MobaXtermProTool,
) -> None:
    """Test MobaXtermProTool initialization."""
    assert mobaxterm_pro_tool.tool_name == "mobaxterm-pro"


def test_mobaxterm_pro_tool_cli_help(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test CLI help generation."""
    help_text = mobaxterm_pro_tool._get_cli_help()
    assert "MobaXterm Pro Tool" in help_text

    short_help = mobaxterm_pro_tool._get_cli_short_help()
    assert "Generate and manage MobaXterm Professional license" in short_help


def test_mobaxterm_pro_tool_cli_interface() -> None:
    """Test command line interface."""
    runner = CliRunner()

    # Import the module to get the cli attribute
    from okit.tools import mobaxterm_pro

    # Test help command
    result = runner.invoke(mobaxterm_pro.cli, ["--help"])
    assert result.exit_code == 0
    assert "MobaXterm license key generator tool" in result.output


@patch("okit.tools.mobaxterm_pro.MobaXtermDetector")
def test_detect_command(mock_detector_class: MagicMock) -> None:
    """Test detect command."""
    mock_detector = MagicMock()
    mock_detector_class.return_value = mock_detector
    mock_detector.detect_installation.return_value = {
        "install_path": "C:\\Program Files\\Mobatek\\MobaXterm",
        "display_name": "MobaXterm Professional",
        "version": "22.0",
        "detection_method": "registry",
    }

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["detect"])
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_generate_command(
    mock_keygen_class: MagicMock, temp_license_file: Path
) -> None:
    """Test generate command."""
    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen
    mock_keygen.create_license_file.return_value = str(temp_license_file)

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(
        mobaxterm_pro.cli,
        [
            "generate",
            "--username",
            "testuser",
            "--version",
            "22.0",
            "--output-path",
            str(temp_license_file),
        ],
    )
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermDetector")
@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_deploy_command(
    mock_keygen_class: MagicMock, mock_detector_class: MagicMock
) -> None:
    """Test deploy command."""
    mock_detector = MagicMock()
    mock_detector_class.return_value = mock_detector
    mock_detector.detect_installation.return_value = {
        "install_path": "C:\\Program Files\\Mobatek\\MobaXterm",
        "version": "22.0",
    }

    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["deploy", "--username", "testuser"])
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_info_command(mock_keygen_class: MagicMock) -> None:
    """Test info command."""
    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen
    mock_keygen.get_license_info.return_value = {
        "username": "testuser",
        "version": "22.0",
        "license_type": "Professional",
    }

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["info", "--license-key", "test_key"])
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_validate_command(mock_keygen_class: MagicMock) -> None:
    """Test validate command."""
    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen
    mock_keygen.validate_license_key.return_value = True

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(
        mobaxterm_pro.cli,
        [
            "validate",
            "--username",
            "testuser",
            "--license-key",
            "test_key",
            "--version",
            "22.0",
        ],
    )
    assert result.exit_code == 0


def test_mobaxterm_pro_tool_cleanup(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test cleanup implementation."""
    # Since cleanup is a no-op in current implementation,
    # we just verify it doesn't raise any exceptions
    mobaxterm_pro_tool._cleanup_impl()


def test_keygen_error_exception() -> None:
    """Test KeygenError exception."""
    error = KeygenError("Test keygen error")
    assert str(error) == "Test keygen error"


def test_encrypt_decrypt_bytes(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test encrypt and decrypt bytes."""
    key = 12345
    test_data = b"test data"

    encrypted = mobaxterm_keygen._encrypt_bytes(key, test_data)
    decrypted = mobaxterm_keygen._decrypt_bytes(key, encrypted)

    assert decrypted == test_data


def test_variant_base64_encode_decode(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 encode and decode."""
    test_data = b"test data"

    encoded = mobaxterm_keygen._variant_base64_encode(test_data)
    decoded = mobaxterm_keygen._variant_base64_decode(encoded.decode())

    assert decoded == test_data


def test_normalize_version(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test version normalization."""
    # Test various version formats
    assert mobaxterm_keygen._normalize_version("22.0") == "22.0"
    assert mobaxterm_keygen._normalize_version("22.0.0") == "22.0"
    assert mobaxterm_keygen._normalize_version("22") == "22.0"

    # Test invalid version
    result = mobaxterm_keygen._normalize_version("invalid")
    assert result == "invalid.0"


def test_detect_installation_error_handling(
    mobaxterm_detector: MobaXtermDetector,
) -> None:
    """Test error handling in detect_installation."""
    with patch.object(mobaxterm_detector, "_detect_from_registry") as mock_registry:
        with patch.object(mobaxterm_detector, "_detect_from_paths") as mock_paths:
            with patch.object(
                mobaxterm_detector, "_detect_from_environment"
            ) as mock_env:
                mock_registry.side_effect = Exception("Registry error")
                mock_paths.return_value = None
                mock_env.return_value = None

                result = mobaxterm_detector.detect_installation()
                assert result is None


def test_generate_license_with_different_types(
    mobaxterm_keygen: MobaXtermKeygen,
) -> None:
    """Test generating licenses with different types."""
    username = "testuser"
    version = "22.0"

    # Test different license types
    for license_type in [1, 2, 3]:  # Different license types
        license_key = mobaxterm_keygen._generate_license(
            license_type, 1, username, 22, 0
        )
        assert isinstance(license_key, str)
        assert len(license_key) > 0


def test_license_file_analysis(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test license file analysis."""
    license_path = "C:\\test\\Custom.mxtpro"
    detected_version = "22.0"

    with patch("okit.tools.mobaxterm_pro.MobaXtermKeygen") as mock_keygen_class:
        mock_keygen = MagicMock()
        mock_keygen_class.return_value = mock_keygen
        mock_keygen.validate_license_file.return_value = True
        mock_keygen.decode_license_key.return_value = "testuser"

        mobaxterm_pro_tool._analyze_license_file(license_path, detected_version)


def test_compare_license_version(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test license version comparison."""
    license_version = "22.0"
    detected_version = "22.0"

    mobaxterm_pro_tool._compare_license_version(license_version, detected_version)

    # Test with different versions
    mobaxterm_pro_tool._compare_license_version("21.0", "22.0")
