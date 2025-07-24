#!/usr/bin/env python
# /// script
# dependencies = [
#     "click>=8.1.0",
#     "psutil>=7.0.0",
# ]
# requires-python = ">=3.8"
# ///

"""
PE File Info Parser
Parse PE file (EXE/DLL) header and section information.
"""

import struct
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import click

from okit.utils.log import logger

class PEFormatError(Exception):
    pass

class PEParser:
    """PE file parser"""
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = self._read_file()
        self.dos_header = {}
        self.pe_header = {}
        self.optional_header = {}
        self.sections = []

    def _read_file(self) -> bytes:
        try:
            with open(self.file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {self.file_path}: {e}")
            raise

    def parse(self):
        self._parse_dos_header()
        self._parse_pe_header()
        self._parse_optional_header()
        self._parse_sections()

    def _parse_dos_header(self):
        if len(self.data) < 64 or self.data[:2] != b'MZ':
            logger.error("Not a valid PE file (missing MZ header)")
            raise PEFormatError("Not a valid PE file (missing MZ header)")
        e_magic = self.data[:2]
        e_lfanew = struct.unpack('<L', self.data[60:64])[0]
        self.dos_header = {
            "e_magic": e_magic.decode(errors="replace"),
            "e_lfanew": e_lfanew
        }
        logger.debug(f"DOS Header: {self.dos_header}")

    def _parse_pe_header(self):
        e_lfanew = self.dos_header["e_lfanew"]
        if len(self.data) < e_lfanew + 24:
            logger.error("File too small for PE header")
            raise PEFormatError("File too small for PE header")
        signature = self.data[e_lfanew:e_lfanew+4]
        if signature != b'PE\x00\x00':
            logger.error("Not a valid PE file (missing PE signature)")
            raise PEFormatError("Not a valid PE file (missing PE signature)")
        machine, num_sections, timestamp, _, _, opt_header_size, characteristics = struct.unpack(
            "<HHLLLHH", self.data[e_lfanew+4:e_lfanew+24]
        )
        self.pe_header = {
            "Signature": signature.decode(errors="replace"),
            "Machine": hex(machine),
            "NumberOfSections": num_sections,
            "TimeDateStamp": timestamp,
            "Characteristics": hex(characteristics),
            "OptionalHeaderSize": opt_header_size,
            "PEHeaderOffset": e_lfanew
        }
        logger.debug(f"PE Header: {self.pe_header}")

    def _parse_optional_header(self):
        e_lfanew = self.dos_header["e_lfanew"]
        opt_header_offset = e_lfanew + 24
        magic = struct.unpack("<H", self.data[opt_header_offset:opt_header_offset+2])[0]
        is_pe32plus = (magic == 0x20b)
        if is_pe32plus:
            fmt = "<HBBQQQIHHHHHH"
            size = struct.calcsize(fmt)
            fields = struct.unpack(fmt, self.data[opt_header_offset:opt_header_offset+size])
            self.optional_header = {
                "Magic": hex(magic),
                "AddressOfEntryPoint": hex(fields[3]),
                "ImageBase": hex(fields[4]),
                "Subsystem": hex(fields[7])
            }
        else:
            fmt = "<HBBLLLHHHHHH"
            size = struct.calcsize(fmt)
            fields = struct.unpack(fmt, self.data[opt_header_offset:opt_header_offset+size])
            self.optional_header = {
                "Magic": hex(magic),
                "AddressOfEntryPoint": hex(fields[3]),
                "ImageBase": hex(fields[4]),
                "Subsystem": hex(fields[7])
            }
        logger.debug(f"Optional Header: {self.optional_header}")

    def _parse_sections(self):
        e_lfanew = self.dos_header["e_lfanew"]
        num_sections = self.pe_header["NumberOfSections"]
        opt_header_size = self.pe_header["OptionalHeaderSize"]
        section_table_offset = e_lfanew + 24 + opt_header_size
        section_size = 40
        self.sections = []
        for i in range(num_sections):
            offset = section_table_offset + i * section_size
            if len(self.data) < offset + section_size:
                logger.warning(f"Section {i} header out of file bounds, skipping")
                continue
            entry = self.data[offset:offset+section_size]
            name = entry[:8].rstrip(b'\x00').decode(errors="replace")
            virtual_size, virtual_addr, size_raw, ptr_raw = struct.unpack("<LLLL", entry[8:24])
            characteristics = struct.unpack("<L", entry[36:40])[0]
            self.sections.append({
                "Name": name,
                "VirtualSize": hex(virtual_size),
                "VirtualAddress": hex(virtual_addr),
                "SizeOfRawData": hex(size_raw),
                "PointerToRawData": hex(ptr_raw),
                "Characteristics": hex(characteristics)
            })
        logger.debug(f"Sections: {self.sections}")

    def get_info(self) -> Dict[str, Any]:
        return {
            "file": str(self.file_path),
            "dos_header": self.dos_header,
            "pe_header": self.pe_header,
            "optional_header": self.optional_header,
            "sections": self.sections
        }

@click.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'csv']), 
              default='table', help='Output format')
def cli(files: Tuple[Path, ...], format: str):
    """
    Parse PE file (EXE/DLL) header and section information.
    """
    import json
    import csv
    import io

    if not files:
        logger.error("No files specified")
        sys.exit(1)

    results = []
    for file_path in files:
        try:
            parser = PEParser(file_path)
            parser.parse()
            info = parser.get_info()
            results.append(info)
            logger.info(f"Parsed file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")

    if not results:
        logger.error("No valid PE files parsed")
        sys.exit(1)

    if format == 'table':
        for info in results:
            click.echo(f"File: {info['file']}")
            click.echo("DOS Header:")
            for k, v in info['dos_header'].items():
                click.echo(f"  {k}: {v}")
            click.echo("PE Header:")
            for k, v in info['pe_header'].items():
                click.echo(f"  {k}: {v}")
            click.echo("Optional Header:")
            for k, v in info['optional_header'].items():
                click.echo(f"  {k}: {v}")
            click.echo("Sections:")
            click.echo(f"{'Name':<10} {'VirtSize':<10} {'VirtAddr':<10} {'RawSize':<10} {'RawPtr':<10} {'Charact.':<10}")
            for s in info['sections']:
                click.echo(f"{s['Name']:<10} {s['VirtualSize']:<10} {s['VirtualAddress']:<10} {s['SizeOfRawData']:<10} {s['PointerToRawData']:<10} {s['Characteristics']:<10}")
            click.echo("-" * 60)
    elif format == 'json':
        click.echo(json.dumps(results, indent=2))
    elif format == 'csv':
        output = io.StringIO()
        fieldnames = ['file', 'section_name', 'virtual_size', 'virtual_address', 'size_of_raw_data', 'pointer_to_raw_data', 'characteristics']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for info in results:
            for s in info['sections']:
                writer.writerow({
                    'file': info['file'],
                    'section_name': s['Name'],
                    'virtual_size': s['VirtualSize'],
                    'virtual_address': s['VirtualAddress'],
                    'size_of_raw_data': s['SizeOfRawData'],
                    'pointer_to_raw_data': s['PointerToRawData'],
                    'characteristics': s['Characteristics']
                })
        click.echo(output.getvalue())

if __name__ == '__main__':
    cli()