"""Tests for pedump tool."""

import os
import struct
import json
import io
from pathlib import Path
from typing import Generator
from unittest.mock import patch
from click.testing import CliRunner

import pytest

from okit.tools.pedump import PEDump, PEParser, PEFormatError


@pytest.fixture
def sample_pe_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a sample PE file for testing."""
    pe_file = temp_dir / "test.exe"

    # Create minimal PE file structure
    with open(pe_file, "wb") as f:
        # DOS Header
        f.write(b"MZ")  # Magic number
        f.write(b"\x00" * 58)  # Padding
        f.write(struct.pack("<L", 0x80))  # e_lfanew

        # PE Header
        f.seek(0x80)
        f.write(b"PE\x00\x00")  # PE Signature
        f.write(struct.pack("<H", 0x14C))  # Machine (i386)
        f.write(struct.pack("<H", 2))  # Number of sections
        f.write(struct.pack("<L", 0))  # Timestamp
        f.write(struct.pack("<L", 0))  # PointerToSymbolTable
        f.write(struct.pack("<L", 0))  # NumberOfSymbols
        f.write(struct.pack("<H", 0xE0))  # SizeOfOptionalHeader
        f.write(struct.pack("<H", 0x102))  # Characteristics

        # Optional Header
        f.write(struct.pack("<H", 0x10B))  # Magic (PE32)
        f.write(b"\x00" * 0xDE)  # Rest of optional header

        # Section Headers
        f.write(b".text\x00\x00\x00")  # Name
        f.write(struct.pack("<L", 0x1000))  # VirtualSize
        f.write(struct.pack("<L", 0x1000))  # VirtualAddress
        f.write(struct.pack("<L", 0x1000))  # SizeOfRawData
        f.write(struct.pack("<L", 0x400))  # PointerToRawData
        f.write(b"\x00" * 16)  # Rest of section header

        f.write(b".data\x00\x00\x00")  # Name
        f.write(struct.pack("<L", 0x1000))  # VirtualSize
        f.write(struct.pack("<L", 0x2000))  # VirtualAddress
        f.write(struct.pack("<L", 0x1000))  # SizeOfRawData
        f.write(struct.pack("<L", 0x1400))  # PointerToRawData
        f.write(b"\x00" * 16)  # Rest of section header

    yield pe_file


@pytest.fixture
def invalid_pe_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create an invalid PE file for testing."""
    invalid_file = temp_dir / "invalid.exe"
    with open(invalid_file, "wb") as f:
        f.write(b"Not a PE file")
    yield invalid_file


@pytest.fixture
def pe_parser(sample_pe_file: Path) -> PEParser:
    """Create a PEParser instance with sample PE file."""
    parser = PEParser(sample_pe_file)
    return parser


@pytest.fixture
def pe_dump() -> PEDump:
    """Create a PEDump instance."""
    return PEDump("pedump")


def test_pe_parser_initialization(pe_parser: PEParser) -> None:
    """Test PEParser initialization."""
    assert pe_parser.file_path.exists()
    assert len(pe_parser.data) > 0
    assert isinstance(pe_parser.dos_header, dict)
    assert isinstance(pe_parser.pe_header, dict)
    assert isinstance(pe_parser.optional_header, dict)
    assert isinstance(pe_parser.sections, list)


def test_pe_parser_dos_header(pe_parser: PEParser) -> None:
    """Test DOS header parsing."""
    pe_parser._parse_dos_header()
    assert pe_parser.dos_header["e_magic"] == "MZ"
    assert "e_lfanew" in pe_parser.dos_header


def test_pe_parser_pe_header(pe_parser: PEParser) -> None:
    """Test PE header parsing."""
    pe_parser._parse_dos_header()
    pe_parser._parse_pe_header()
    assert pe_parser.pe_header["Signature"] == "PE"
    assert pe_parser.pe_header["NumberOfSections"] == 2
    assert "Machine" in pe_parser.pe_header
    assert "Characteristics" in pe_parser.pe_header


def test_pe_parser_optional_header(pe_parser: PEParser) -> None:
    """Test optional header parsing."""
    pe_parser._parse_dos_header()
    pe_parser._parse_pe_header()
    pe_parser._parse_optional_header()
    assert "Magic" in pe_parser.optional_header
    assert "AddressOfEntryPoint" in pe_parser.optional_header


def test_pe_parser_sections(pe_parser: PEParser) -> None:
    """Test section parsing."""
    pe_parser.parse()
    assert len(pe_parser.sections) == 2
    assert pe_parser.sections[0]["Name"] == ".text"
    assert pe_parser.sections[1]["Name"] == ".data"


def test_pe_parser_invalid_file(invalid_pe_file: Path) -> None:
    """Test parsing invalid PE file."""
    parser = PEParser(invalid_pe_file)
    with pytest.raises(PEFormatError):
        parser.parse()


def test_pe_dump_parse_command(pe_dump: PEDump, sample_pe_file: Path) -> None:
    """Test PEDump parse command with different formats."""
    # Test table format
    pe_dump._parse_pe_file(sample_pe_file, "table")

    # Test JSON format
    pe_dump._parse_pe_file(sample_pe_file, "json")

    # Test CSV format
    pe_dump._parse_pe_file(sample_pe_file, "csv")


def test_pe_dump_output_formats(pe_dump: PEDump, pe_parser: PEParser) -> None:
    """Test different output formats."""
    pe_parser.parse()
    info = pe_parser.get_info()

    # Test table output
    pe_dump._output_table(info)

    # Test CSV output
    pe_dump._output_csv(info)


@pytest.fixture
def pe32plus_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a sample PE32+ (64-bit) file for testing."""
    pe_file = temp_dir / "test64.exe"
    
    with open(pe_file, "wb") as f:
        # DOS Header
        f.write(b"MZ")
        f.write(b"\x00" * 58)
        f.write(struct.pack("<L", 0x80))

        # PE Header
        f.seek(0x80)
        f.write(b"PE\x00\x00")
        f.write(struct.pack("<H", 0x8664))  # Machine (AMD64)
        f.write(struct.pack("<H", 2))  # Number of sections
        f.write(struct.pack("<L", 0))  # Timestamp
        f.write(struct.pack("<L", 0))  # PointerToSymbolTable
        f.write(struct.pack("<L", 0))  # NumberOfSymbols
        f.write(struct.pack("<H", 0xF0))  # SizeOfOptionalHeader
        f.write(struct.pack("<H", 0x22))  # Characteristics

        # Optional Header (PE32+)
        f.write(struct.pack("<H", 0x20B))  # Magic (PE32+)
        f.write(b"\x00" * 0xEE)  # Rest of optional header

        # Section Headers (same as PE32)
        f.write(b".text\x00\x00\x00")
        f.write(struct.pack("<L", 0x1000))
        f.write(struct.pack("<L", 0x1000))
        f.write(struct.pack("<L", 0x1000))
        f.write(struct.pack("<L", 0x400))
        f.write(b"\x00" * 16)

    yield pe_file


def test_pe_parser_pe32plus(pe32plus_file: Path) -> None:
    """Test parsing of PE32+ (64-bit) files."""
    parser = PEParser(pe32plus_file)
    parser.parse()
    
    assert parser.pe_header["Machine"] == hex(0x8664)  # AMD64
    assert "Magic" in parser.optional_header
    assert parser.optional_header["Magic"] == hex(0x20B)  # PE32+


def test_file_read_error(temp_dir: Path) -> None:
    """Test handling of file read errors."""
    non_existent_file = temp_dir / "non_existent.exe"
    
    with pytest.raises(FileNotFoundError):
        parser = PEParser(non_existent_file)
        parser.parse()


def test_pe_dump_cli(pe_dump: PEDump, sample_pe_file: Path) -> None:
    """Test command line interface."""
    runner = CliRunner()
    
    # Import the module to get the cli attribute
    from okit.tools import pedump
    
    # Test help command
    result = runner.invoke(pedump.cli, ["--help"])
    assert result.exit_code == 0
    assert "PE File Info Parser" in result.output
    
    # Test parse command with different formats (just check exit codes)
    result = runner.invoke(pedump.cli, ["parse", str(sample_pe_file)])
    assert result.exit_code == 0
    
    result = runner.invoke(pedump.cli, ["parse", "-f", "json", str(sample_pe_file)])
    assert result.exit_code == 0
    
    result = runner.invoke(pedump.cli, ["parse", "-f", "csv", str(sample_pe_file)])
    assert result.exit_code == 0


def test_output_format_completeness(pe_dump: PEDump, pe_parser: PEParser) -> None:
    """Test completeness of different output formats."""
    pe_parser.parse()
    info = pe_parser.get_info()
    
    # Test table output
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        pe_dump._output_table(info)
        table_output = fake_out.getvalue()
        assert "PE File:" in table_output
        assert "Sections" in table_output
        assert info["file_path"] in table_output
        for section in info["sections"]:
            assert section["Name"] in table_output
    
    # Test CSV output
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        pe_dump._output_csv(info)
        csv_output = fake_out.getvalue()
        assert "Property,Value" in csv_output
        assert "Section Name,Virtual Size" in csv_output
        for section in info["sections"]:
            assert section["Name"] in csv_output


def test_cleanup(pe_dump: PEDump) -> None:
    """Test cleanup implementation."""
    # Since cleanup is a no-op in current implementation,
    # we just verify it doesn't raise any exceptions
    pe_dump._cleanup_impl()