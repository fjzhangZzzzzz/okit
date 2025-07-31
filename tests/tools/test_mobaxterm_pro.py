"""Tests for mobaxterm_pro tool."""

import os
import sys
from pathlib import Path
from typing import Dict, Generator, Optional
from unittest.mock import MagicMock, patch

import pytest

from okit.tools.mobaxterm_pro import (
    KeygenError,
    MobaXtermDetector,
    MobaXtermKeygen,
    MobaXtermProTool,
)


@pytest.fixture
def mock_winreg() -> Generator[MagicMock, None, None]:
    """Mock winreg module for testing."""
    with patch("okit.tools.mobaxterm_pro.winreg") as mock:
        # Setup mock registry data
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=None)
        mock.OpenKey.return_value = mock_key
        mock.QueryValueEx.side_effect = [
            ("C:\\Program Files\\Mobatek\\MobaXterm", 0),  # InstallLocation
            ("MobaXterm Professional", 0),  # DisplayName
            ("22.0", 0),  # DisplayVersion
        ]
        yield mock


@pytest.fixture
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Mock subprocess module for testing."""
    with patch("okit.tools.mobaxterm_pro.subprocess") as mock:
        mock.run.return_value = MagicMock(
            returncode=0,
            stdout=b"MobaXterm version 22.0",
            stderr=b"",
        )
        yield mock


@pytest.fixture
def detector(mock_winreg: MagicMock) -> MobaXtermDetector:
    """Create a MobaXtermDetector instance with mocked dependencies."""
    return MobaXtermDetector()


@pytest.fixture
def keygen() -> MobaXtermKeygen:
    """Create a MobaXtermKeygen instance."""
    return MobaXtermKeygen()


@pytest.fixture
def tool() -> MobaXtermProTool:
    """Create a MobaXtermProTool instance."""
    return MobaXtermProTool("mobaxterm-pro")


def test_detector_registry_detection(
    detector: MobaXtermDetector, mock_winreg: MagicMock
) -> None:
    """Test MobaXterm detection from registry."""
    info = detector._detect_from_registry()
    assert info is not None
    assert info["install_path"] == "C:\\Program Files\\Mobatek\\MobaXterm"
    assert info["display_name"] == "MobaXterm Professional"
    assert info["version"] == "22.0"
    assert info["detection_method"] == "registry"


def test_detector_path_detection(detector: MobaXtermDetector) -> None:
    """Test MobaXterm detection from known paths."""
    # Create a mock installation directory
    test_path = detector.known_paths[0]
    os.makedirs(test_path, exist_ok=True)
    try:
        info = detector._detect_from_paths()
        assert info is not None
        assert info["install_path"] == test_path
        assert info["detection_method"] == "known_path"
    finally:
        # Clean up
        if os.path.exists(test_path):
            os.rmdir(test_path)


def test_detector_environment_detection(detector: MobaXtermDetector) -> None:
    """Test MobaXterm detection from environment variables."""
    test_path = "C:\\Test\\MobaXterm"
    os.environ["MOBAXTERM_HOME"] = test_path
    try:
        info = detector._detect_from_environment()
        assert info is not None
        assert info["detection_method"] == "environment"
    finally:
        del os.environ["MOBAXTERM_HOME"]


def test_keygen_license_generation(keygen: MobaXtermKeygen) -> None:
    """Test license key generation."""
    username = "test_user"
    version = "22.0"

    # Generate license key
    license_key = keygen.generate_license_key(username, version)
    assert license_key is not None
    assert isinstance(license_key, str)

    # Validate generated license
    assert keygen.validate_license_key(username, license_key, version)

    # Test license info extraction
    info = keygen.get_license_info(license_key)
    assert info is not None
    assert info["username"] == username
    assert info["version"] == "22.0"


def test_keygen_license_file_creation(keygen: MobaXtermKeygen, temp_dir: Path) -> None:
    """Test license file creation."""
    username = "test_user"
    version = "22.0"
    output_path = temp_dir / "Custom.mxtpro"

    # Create license file
    license_path = keygen.create_license_file(username, version, str(output_path))
    assert os.path.exists(license_path)

    # Validate created file
    assert keygen.validate_license_file(license_path)


def test_keygen_version_normalization(keygen: MobaXtermKeygen) -> None:
    """Test version string normalization."""
    test_cases = [
        ("22", "22.0"),
        ("22.0", "22.0"),
        ("22.1", "22.1"),
        ("22.0.1", "22.0"),
        ("v22.0", "22.0"),
        ("Version 22.0", "22.0"),
    ]

    for input_version, expected in test_cases:
        assert keygen._normalize_version(input_version) == expected


def test_tool_detect_command(
    tool: MobaXtermProTool, mock_winreg: MagicMock, mock_subprocess: MagicMock
) -> None:
    """Test the detect command."""
    # Add mock installation
    test_path = "C:\\Program Files\\Mobatek\\MobaXterm"
    os.makedirs(test_path, exist_ok=True)
    try:
        # Run detect command through tool
        detector = MobaXtermDetector()
        result = detector.detect_installation()
        assert result is not None
        assert "install_path" in result
    finally:
        if os.path.exists(test_path):
            os.rmdir(test_path)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
def test_tool_deploy_command(
    tool: MobaXtermProTool, mock_winreg: MagicMock, temp_dir: Path
) -> None:
    """Test the deploy command."""
    # Mock installation detection
    detector = MobaXtermDetector()
    with patch.object(detector, "detect_installation") as mock_detect:
        mock_detect.return_value = {
            "install_path": str(temp_dir),
            "version": "22.0",
        }

        # Create mock installation directory
        license_dir = temp_dir / "Custom.mxtpro"
        os.makedirs(str(license_dir.parent), exist_ok=True)

        # Test deploy
        keygen = MobaXtermKeygen()
        license_path = keygen.create_license_file("test_user", "22.0", str(license_dir))

        # Verify license file was created
        assert os.path.exists(str(license_dir))
