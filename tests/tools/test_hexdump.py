"""
Tests for hexdump tool
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

from okit.tools.hexdump import HexDumper, HexDumpError, HexDump
from click.testing import CliRunner


class TestHexDumper:
    """Test HexDumper class"""

    def test_init_with_valid_file(self) -> None:
        """Test HexDumper initialization with valid file"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            assert dumper.file_path == Path(f.name)
            assert dumper.data == b"Hello World"

            os.unlink(f.name)

    def test_init_with_invalid_file(self) -> None:
        """Test HexDumper initialization with invalid file"""
        with pytest.raises(HexDumpError):
            HexDumper(Path("nonexistent_file.txt"))

    def test_format_canonical(self) -> None:
        """Test canonical formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_canonical(0, b"Hello World")

            # Check that result contains expected elements
            assert "00000000" in result  # Offset
            assert "4865 6c6c 6f20 576f 726c 64" in result  # Hex values
            assert "|Hello World|" in result  # ASCII representation

            os.unlink(f.name)

    def test_format_one_byte_hex(self) -> None:
        """Test one-byte hex formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_one_byte_hex(0, b"Hello World")

            assert "00000000" in result  # Offset
            assert "48 65 6c 6c 6f 20 57 6f 72 6c 64" in result  # Hex values

            os.unlink(f.name)

    def test_format_one_byte_octal(self) -> None:
        """Test one-byte octal formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_one_byte_octal(0, b"Hello World")

            assert "00000000" in result  # Offset
            assert (
                "110 145 154 154 157 040 127 157 162 154 144" in result
            )  # Octal values

            os.unlink(f.name)

    def test_format_one_byte_char(self) -> None:
        """Test one-byte char formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_one_byte_char(0, b"Hello World")

            assert "00000000" in result  # Offset
            assert " H  e  l  l  o    W  o  r  l  d" in result  # Char values

            os.unlink(f.name)

    def test_format_two_bytes_decimal(self) -> None:
        """Test two-bytes decimal formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x01\x02\x03\x04")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_two_bytes_decimal(0, b"\x01\x02\x03\x04")

            assert "00000000" in result  # Offset
            assert " 258 772" in result  # Decimal values (big-endian)

            os.unlink(f.name)

    def test_format_two_bytes_octal(self) -> None:
        """Test two-bytes octal formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x01\x02\x03\x04")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_two_bytes_octal(0, b"\x01\x02\x03\x04")

            assert "00000000" in result  # Offset
            assert " 402 1404" in result  # Octal values (big-endian)

            os.unlink(f.name)

    def test_format_two_bytes_hex(self) -> None:
        """Test two-bytes hex formatting"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"\x01\x02\x03\x04")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            result = dumper._format_two_bytes_hex(0, b"\x01\x02\x03\x04")

            assert "00000000" in result  # Offset
            assert " 0102 0304" in result  # Hex values (big-endian)

            os.unlink(f.name)

    def test_dump_basic(self) -> None:
        """Test basic dump functionality"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            lines = list(dumper.dump())

            assert len(lines) == 1  # One line for 11 bytes
            assert "00000000" in lines[0]  # Offset
            assert "4865 6c6c 6f20 576f 726c 64" in lines[0]  # Hex

            os.unlink(f.name)

    def test_dump_with_length(self) -> None:
        """Test dump with length limit"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            lines = list(dumper.dump(length=5))

            assert len(lines) == 1  # One line for 5 bytes
            assert "4865 6c6c 6f" in lines[0]  # First 5 bytes

            os.unlink(f.name)

    def test_dump_with_skip(self) -> None:
        """Test dump with skip"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            lines = list(dumper.dump(skip=6))

            assert len(lines) == 1  # One line for remaining bytes
            assert "576f 726c 64" in lines[0]  # "World" bytes

            os.unlink(f.name)

    def test_dump_empty_file(self) -> None:
        """Test dump with empty file"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))
            lines = list(dumper.dump())

            assert len(lines) == 0  # No lines for empty file

            os.unlink(f.name)

    def test_dump_different_formats(self) -> None:
        """Test dump with different format types"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            dumper = HexDumper(Path(f.name))

            # Test canonical format
            lines = list(dumper.dump(format_type="canonical"))
            assert len(lines) == 1
            assert "|Hello World|" in lines[0]

            # Test one-byte hex format
            lines = list(dumper.dump(format_type="one-byte-hex"))
            assert len(lines) == 1
            assert "48 65 6c 6c 6f 20 57 6f 72 6c 64" in lines[0]

            # Test two-bytes hex format
            lines = list(dumper.dump(format_type="two-bytes-hex"))
            assert len(lines) == 1
            assert "4865 6c6c 6f20 576f 726c" in lines[0]

            os.unlink(f.name)


class TestHexDump:
    """Test HexDump tool class"""

    def test_init(self) -> None:
        """Test HexDump initialization"""
        tool = HexDump("hexdump", "Hexdump Tool")
        assert tool.tool_name == "hexdump"
        assert tool.description == "Hexdump Tool"

    def test_get_cli_help(self) -> None:
        """Test CLI help generation"""
        tool = HexDump("hexdump", "Hexdump Tool")
        help_text = tool._get_cli_help()

        assert "Hexdump Tool" in help_text
        assert "hexadecimal format" in help_text

    def test_get_cli_short_help(self) -> None:
        """Test CLI short help generation"""
        tool = HexDump("hexdump", "Hexdump Tool")
        short_help = tool._get_cli_short_help()

        assert "hexadecimal format" in short_help

    def test_cleanup(self) -> None:
        """Test cleanup method"""
        tool = HexDump("hexdump", "Hexdump Tool")
        # Should not raise any exceptions
        tool.cleanup()


class TestHexDumpCLI:
    """Test HexDump CLI commands"""

    def test_hexdump_cli_interface(self) -> None:
        """Test command line interface."""
        runner = CliRunner()

        # Create tool instance and test CLI
        tool = HexDump("hexdump", "Hexdump Tool")
        cli = tool.create_cli_group()

        # Test help command
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Hexdump Tool" in result.output

        # Test that the main command is available
        result = runner.invoke(cli, ["main", "--help"])
        assert result.exit_code == 0
        assert "Display file contents in hexadecimal format" in result.output

        # Test that options are properly displayed with correct format
        assert "-C, --canonical" in result.output
        assert "-X, --one-byte-hex" in result.output
        assert "-b, --one-byte-octal" in result.output
        assert "-c, --one-byte-char" in result.output
        assert "-d, --two-bytes-decimal" in result.output
        assert "-o, --two-bytes-octal" in result.output
        assert "-x, --two-bytes-hex" in result.output
        assert "-n, --length" in result.output
        assert "-s, --skip" in result.output
        assert "-v, --no-squeezing" in result.output

        # Test that option descriptions are shown
        assert "Canonical hex+ASCII display (default)" in result.output
        assert "One-byte hexadecimal display" in result.output
        assert "One-byte octal display" in result.output
        assert "One-byte character display" in result.output
        assert "Two-byte decimal display" in result.output
        assert "Two-byte octal display" in result.output
        assert "Two-byte hexadecimal display" in result.output
        assert "Interpret only LENGTH bytes of input" in result.output
        assert "Skip OFFSET bytes from the beginning" in result.output
        assert "Display all input data (no squeezing)" in result.output

    def test_hexdump_command_no_files(self) -> None:
        """Test hexdump command with no files"""
        tool = HexDump("hexdump", "Hexdump Tool")

        # Test the command directly
        runner = CliRunner()
        cli = tool.create_cli_group()

        # Call with no files
        result = runner.invoke(cli, ["main"])
        assert "No files specified" in result.output

    def test_hexdump_command_canonical(self) -> None:
        """Test hexdump command with canonical format"""
        tool = HexDump("hexdump", "Hexdump Tool")

        # Test the command directly
        runner = CliRunner()
        cli = tool.create_cli_group()

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            try:
                # Call hexdump command with canonical format
                result = runner.invoke(cli, ["main", "--canonical", f.name])
                assert result.exit_code == 0
                assert "Hello World" in result.output

            finally:
                os.unlink(f.name)

    def test_hexdump_command_two_bytes_hex(self) -> None:
        """Test hexdump command with two-bytes hex format"""
        tool = HexDump("hexdump", "Hexdump Tool")

        # Test the command directly
        runner = CliRunner()
        cli = tool.create_cli_group()

        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Hello World")
            f.flush()
            f.close()  # Close the file to release the handle

            try:
                # Call hexdump command with two-bytes hex format
                result = runner.invoke(cli, ["main", "--two-bytes-hex", f.name])
                assert result.exit_code == 0
                assert "4865" in result.output  # Check for hex output

            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    pytest.main([__file__])
