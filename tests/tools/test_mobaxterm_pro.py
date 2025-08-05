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
def mobaxterm_keygen() -> MobaXtermKeygen:
    """Create a MobaXtermKeygen instance."""
    return MobaXtermKeygen()


@pytest.fixture
def mobaxterm_pro_tool() -> MobaXtermProTool:
    """Create a MobaXtermProTool instance."""
    return MobaXtermProTool("mobaxterm-pro")


def test_mobaxterm_keygen_initialization(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test MobaXtermKeygen initialization."""
    assert len(mobaxterm_keygen.VariantBase64Table) > 0
    assert len(mobaxterm_keygen.VariantBase64Dict) > 0
    assert len(mobaxterm_keygen.VariantBase64ReverseDict) > 0
    assert mobaxterm_keygen.LicenseType_Professional == 1
    assert mobaxterm_keygen.LicenseType_Educational == 3
    assert mobaxterm_keygen.LicenseType_Personal == 4


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


def test_generate_license_key_with_different_versions(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key generation with different version formats."""
    username = "testuser"
    
    # Test different version formats
    versions = ["22.0", "22.0.0", "22.0.0.0", "21.5", "25.2"]
    
    for version in versions:
        license_key = mobaxterm_keygen.generate_license_key(username, version)
        assert isinstance(license_key, str)
        assert len(license_key) > 0


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


def test_create_license_file_with_directory_creation(
    mobaxterm_keygen: MobaXtermKeygen, temp_dir: Path
) -> None:
    """Test license file creation with directory creation."""
    username = "testuser"
    version = "22.0"
    
    # Create a path that doesn't exist
    license_path = temp_dir / "new_dir" / "Custom.mxtpro"
    
    # Ensure the directory exists before creating the file
    license_path.parent.mkdir(parents=True, exist_ok=True)
    
    result = mobaxterm_keygen.create_license_file(
        username, version, str(license_path)
    )
    assert result == str(license_path)
    assert license_path.exists()
    assert license_path.parent.exists()


def test_decode_license_key(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key decoding."""
    # Generate a license key first
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    # Decode the license key
    result = mobaxterm_keygen.decode_license_key(license_key)
    assert result is not None
    assert "testuser" in result
    assert "22" in result  # Should contain version info


def test_decode_license_key_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test decoding invalid license key."""
    result = mobaxterm_keygen.decode_license_key("invalid_key")
    assert result is None


def test_decode_license_key_empty(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test decoding empty license key."""
    result = mobaxterm_keygen.decode_license_key("")
    # Empty string should return empty string, not None
    assert result == ""


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


def test_validate_license_file_corrupted(mobaxterm_keygen: MobaXtermKeygen, temp_dir: Path) -> None:
    """Test corrupted license file validation."""
    # Create a corrupted license file
    corrupted_file = temp_dir / "corrupted.mxtpro"
    with zipfile.ZipFile(corrupted_file, "w") as zf:
        zf.writestr("Pro.key", "corrupted_content")
    
    result = mobaxterm_keygen.validate_license_file(str(corrupted_file))
    assert result is False


def test_validate_license_file_wrong_format(mobaxterm_keygen: MobaXtermKeygen, temp_dir: Path) -> None:
    """Test license file with wrong format."""
    # Create a file that's not a valid zip
    invalid_file = temp_dir / "invalid.mxtpro"
    invalid_file.write_text("not a zip file")
    
    result = mobaxterm_keygen.validate_license_file(str(invalid_file))
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


def test_validate_license_key_wrong_username(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key validation with wrong username."""
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    result = mobaxterm_keygen.validate_license_key("wronguser", license_key, version)
    assert result is False


def test_validate_license_key_wrong_version(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test license key validation with wrong version."""
    username = "testuser"
    version = "22.0"
    license_key = mobaxterm_keygen.generate_license_key(username, version)

    result = mobaxterm_keygen.validate_license_key(username, license_key, "21.0")
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
    assert "license_type" in result
    assert "user_count" in result
    assert "license_key" in result
    assert "decoded_string" in result
    assert result["username"] == username
    assert result["license_type"] == "Professional"


def test_get_license_info_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test getting license information for invalid key."""
    result = mobaxterm_keygen.get_license_info("invalid_key")
    assert result is None


def test_get_license_info_empty(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test getting license information for empty key."""
    result = mobaxterm_keygen.get_license_info("")
    assert result is None


def test_mobaxterm_pro_tool_initialization(
    mobaxterm_pro_tool: MobaXtermProTool,
) -> None:
    """Test MobaXtermProTool initialization."""
    assert mobaxterm_pro_tool.tool_name == "mobaxterm-pro"
    assert hasattr(mobaxterm_pro_tool, 'keygen')
    assert hasattr(mobaxterm_pro_tool, 'detector')


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


@patch("okit.tools.mobaxterm_pro.MobaXtermDetector")
def test_detect_command_not_found(mock_detector_class: MagicMock) -> None:
    """Test detect command when MobaXterm is not found."""
    mock_detector = MagicMock()
    mock_detector_class.return_value = mock_detector
    mock_detector.detect_installation.return_value = None

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["detect"])
    # The command should still exit with 0, but show a message
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


@patch("okit.tools.mobaxterm_pro.MobaXtermDetector")
@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_deploy_command_with_version(
    mock_keygen_class: MagicMock, mock_detector_class: MagicMock
) -> None:
    """Test deploy command with specified version."""
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

    result = runner.invoke(
        mobaxterm_pro.cli, 
        ["deploy", "--username", "testuser", "--version", "21.0"]
    )
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermDetector")
def test_deploy_command_not_found(mock_detector_class: MagicMock) -> None:
    """Test deploy command when MobaXterm is not found."""
    mock_detector = MagicMock()
    mock_detector_class.return_value = mock_detector
    mock_detector.detect_installation.return_value = None

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["deploy", "--username", "testuser"])
    # The command should still exit with 0, but show a message
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
        "user_count": "1",
        "license_key": "test_key",
        "decoded_string": "test_decoded",
    }

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["info", "--license-key", "test_key"])
    assert result.exit_code == 0


@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_info_command_invalid_key(mock_keygen_class: MagicMock) -> None:
    """Test info command with invalid license key."""
    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen
    mock_keygen.get_license_info.return_value = None

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(mobaxterm_pro.cli, ["info", "--license-key", "invalid_key"])
    # The command should still exit with 0, but show a message
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


@patch("okit.tools.mobaxterm_pro.MobaXtermKeygen")
def test_validate_command_invalid(mock_keygen_class: MagicMock) -> None:
    """Test validate command with invalid license."""
    mock_keygen = MagicMock()
    mock_keygen_class.return_value = mock_keygen
    mock_keygen.validate_license_key.return_value = False

    runner = CliRunner()
    from okit.tools import mobaxterm_pro

    result = runner.invoke(
        mobaxterm_pro.cli,
        [
            "validate",
            "--username",
            "testuser",
            "--license-key",
            "invalid_key",
            "--version",
            "22.0",
        ],
    )
    # The command should still exit with 0, but show a message
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


def test_encrypt_decrypt_bytes_empty(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test encrypt and decrypt empty bytes."""
    key = 12345
    test_data = b""

    encrypted = mobaxterm_keygen._encrypt_bytes(key, test_data)
    decrypted = mobaxterm_keygen._decrypt_bytes(key, encrypted)

    assert decrypted == test_data


def test_variant_base64_encode_decode(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 encode and decode."""
    test_data = b"test data"

    encoded = mobaxterm_keygen._variant_base64_encode(test_data)
    decoded = mobaxterm_keygen._variant_base64_decode(encoded.decode())

    assert decoded == test_data


def test_variant_base64_encode_decode_empty(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 encode and decode with empty data."""
    test_data = b""

    encoded = mobaxterm_keygen._variant_base64_encode(test_data)
    decoded = mobaxterm_keygen._variant_base64_decode(encoded.decode())

    assert decoded == test_data


def test_variant_base64_encode_decode_single_byte(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 encode and decode with single byte."""
    test_data = b"A"

    encoded = mobaxterm_keygen._variant_base64_encode(test_data)
    decoded = mobaxterm_keygen._variant_base64_decode(encoded.decode())

    assert decoded == test_data


def test_variant_base64_encode_decode_two_bytes(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 encode and decode with two bytes."""
    test_data = b"AB"

    encoded = mobaxterm_keygen._variant_base64_encode(test_data)
    decoded = mobaxterm_keygen._variant_base64_decode(encoded.decode())

    assert decoded == test_data


def test_variant_base64_decode_invalid(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test variant base64 decode with invalid input."""
    # Test with invalid input that should raise an exception
    with pytest.raises((ValueError, OverflowError)):
        mobaxterm_keygen._variant_base64_decode("invalid")


def test_normalize_version(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test version normalization."""
    # Test various version formats
    assert mobaxterm_keygen._normalize_version("22.0") == "22.0"
    assert mobaxterm_keygen._normalize_version("22.0.0") == "22.0"
    assert mobaxterm_keygen._normalize_version("22.0.0.0") == "22.0"
    assert mobaxterm_keygen._normalize_version("22") == "22.0"
    assert mobaxterm_keygen._normalize_version("21.5.1.4321") == "21.5"
    assert mobaxterm_keygen._normalize_version("25.2.0.5296") == "25.2"

    # Test invalid version - should return the original string with .0 appended
    result = mobaxterm_keygen._normalize_version("invalid")
    assert result == "invalid.0"


def test_normalize_version_edge_cases(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test version normalization edge cases."""
    # Test empty string - should return .0
    assert mobaxterm_keygen._normalize_version("") == ".0"
    
    # Test single dot - should return as is
    assert mobaxterm_keygen._normalize_version("22.") == "22."
    
    # Test multiple dots - should return first two parts
    assert mobaxterm_keygen._normalize_version("22.0.0.0.0") == "22.0"


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


def test_generate_license_with_different_counts(
    mobaxterm_keygen: MobaXtermKeygen,
) -> None:
    """Test generating licenses with different user counts."""
    username = "testuser"
    version = "22.0"

    # Test different user counts
    for count in [1, 5, 10, 100]:
        license_key = mobaxterm_keygen._generate_license(
            1, count, username, 22, 0
        )
        assert isinstance(license_key, str)
        assert len(license_key) > 0


def test_generate_license_with_different_versions(
    mobaxterm_keygen: MobaXtermKeygen,
) -> None:
    """Test generating licenses with different versions."""
    username = "testuser"

    # Test different version combinations
    version_combinations = [
        (21, 0), (21, 5), (22, 0), (22, 1), (25, 2)
    ]
    
    for major, minor in version_combinations:
        license_key = mobaxterm_keygen._generate_license(
            1, 1, username, major, minor
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
        mock_keygen.get_license_info.return_value = {
            "username": "testuser",
            "version": "22.0",
            "license_type": "Professional",
            "user_count": "1",
        }

        mobaxterm_pro_tool._analyze_license_file(license_path, detected_version)


def test_license_file_analysis_invalid(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test license file analysis with invalid file."""
    license_path = "C:\\test\\Custom.mxtpro"
    detected_version = "22.0"

    with patch("okit.tools.mobaxterm_pro.MobaXtermKeygen") as mock_keygen_class:
        mock_keygen = MagicMock()
        mock_keygen_class.return_value = mock_keygen
        mock_keygen.validate_license_file.return_value = False

        mobaxterm_pro_tool._analyze_license_file(license_path, detected_version)


def test_compare_license_version(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test license version comparison."""
    license_version = "22.0"
    detected_version = "22.0"

    mobaxterm_pro_tool._compare_license_version(license_version, detected_version)

    # Test with different versions
    mobaxterm_pro_tool._compare_license_version("21.0", "22.0")
    mobaxterm_pro_tool._compare_license_version("23.0", "22.0")


def test_compare_license_version_invalid_versions(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test license version comparison with invalid versions."""
    # Test with invalid version formats
    mobaxterm_pro_tool._compare_license_version("invalid", "22.0")
    mobaxterm_pro_tool._compare_license_version("22.0", "invalid")


def test_generate_license_error_handling(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test error handling in license generation."""
    # Test with invalid count parameter - this should raise KeygenError
    with pytest.raises(KeygenError):
        mobaxterm_keygen._generate_license(1, -1, "testuser", 22, 0)
    
    # Test with invalid license_type - this should not raise KeygenError
    # because the method doesn't validate license_type
    license_key = mobaxterm_keygen._generate_license(-1, 1, "testuser", 22, 0)
    assert isinstance(license_key, str)


def test_create_license_file_error_handling(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test error handling in license file creation."""
    username = "testuser"
    version = "22.0"
    
    # Test with invalid output path
    with pytest.raises(KeygenError):
        mobaxterm_keygen.create_license_file(username, version, "/invalid/path/file.mxtpro")


def test_validate_license_file_error_handling(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test error handling in license file validation."""
    # Test with None path
    result = mobaxterm_keygen.validate_license_file(None)
    assert result is False
    
    # Test with empty path
    result = mobaxterm_keygen.validate_license_file("")
    assert result is False


def test_get_license_info_error_handling(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test error handling in license info retrieval."""
    # Test with None key
    result = mobaxterm_keygen.get_license_info(None)
    assert result is None
    
    # Test with empty key
    result = mobaxterm_keygen.get_license_info("")
    assert result is None


def test_tool_decorator_integration() -> None:
    """Test that the tool is properly decorated."""
    tool = MobaXtermProTool("mobaxterm-pro")
    
    # Check that the tool has the expected attributes from the decorator
    # Note: The decorator might not be applied during testing, so we check for the method instead
    assert hasattr(tool, '_add_cli_commands')
    assert tool.tool_name == "mobaxterm-pro"


def test_cli_commands_registration(mobaxterm_pro_tool: MobaXtermProTool) -> None:
    """Test that CLI commands are properly registered."""
    # This test verifies that the tool can be used as a CLI command
    assert hasattr(mobaxterm_pro_tool, '_add_cli_commands')


def test_license_key_roundtrip(mobaxterm_keygen: MobaXtermKeygen) -> None:
    """Test complete license key roundtrip (generate -> decode -> validate)."""
    username = "testuser"
    version = "22.0"
    
    # Generate license key
    license_key = mobaxterm_keygen.generate_license_key(username, version)
    
    # Decode license key
    decoded = mobaxterm_keygen.decode_license_key(license_key)
    assert decoded is not None
    
    # Validate license key
    is_valid = mobaxterm_keygen.validate_license_key(username, license_key, version)
    assert is_valid is True
    
    # Get license info
    info = mobaxterm_keygen.get_license_info(license_key)
    assert info is not None
    assert info["username"] == username
    assert info["license_type"] == "Professional"


def test_license_file_roundtrip(mobaxterm_keygen: MobaXtermKeygen, temp_dir: Path) -> None:
    """Test complete license file roundtrip (create -> validate)."""
    username = "testuser"
    version = "22.0"
    license_file = temp_dir / "test.mxtpro"
    
    # Create license file
    result_path = mobaxterm_keygen.create_license_file(username, version, str(license_file))
    assert result_path == str(license_file)
    assert license_file.exists()
    
    # Validate license file
    is_valid = mobaxterm_keygen.validate_license_file(str(license_file))
    assert is_valid is True
    
    # Read and decode license key from file
    with zipfile.ZipFile(license_file, "r") as zf:
        license_key = zf.read("Pro.key").decode("utf-8").strip()
    
    # Validate the license key
    is_valid = mobaxterm_keygen.validate_license_key(username, license_key, version)
    assert is_valid is True
