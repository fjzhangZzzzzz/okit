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

from okit.utils.log import logger, console
from okit.core.base_tool import BaseTool
from okit.core.tool_decorator import okit_tool


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
            fmt = "<HBBLLLIHHHHHH"
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
        section_offset = e_lfanew + 24 + self.pe_header["OptionalHeaderSize"]
        
        for i in range(num_sections):
            section_data = self.data[section_offset + i*40:section_offset + (i+1)*40]
            if len(section_data) < 40:
                break
            name, virtual_size, virtual_address, size_of_raw_data, pointer_to_raw_data, pointer_to_relocations, pointer_to_line_numbers, num_relocations, num_line_numbers, characteristics = struct.unpack("<8sLLLLLLHH", section_data)
            section_name = name.decode(errors="replace").rstrip('\x00')
            self.sections.append({
                "Name": section_name,
                "VirtualSize": virtual_size,
                "VirtualAddress": hex(virtual_address),
                "SizeOfRawData": size_of_raw_data,
                "PointerToRawData": pointer_to_raw_data,
                "Characteristics": hex(characteristics)
            })
        logger.debug(f"Parsed {len(self.sections)} sections")

    def get_info(self) -> Dict[str, Any]:
        """获取 PE 文件信息"""
        return {
            "file_path": str(self.file_path),
            "dos_header": self.dos_header,
            "pe_header": self.pe_header,
            "optional_header": self.optional_header,
            "sections": self.sections
        }


@okit_tool("pedump", "PE File Info Parser")
class PEDump(BaseTool):
    """PE 文件信息解析工具"""

    def __init__(self, tool_name: str, description: str = ""):
        super().__init__(tool_name, description)

    def _get_cli_help(self) -> str:
        """自定义 CLI 帮助信息"""
        return """
PE Dump Tool - Parse PE file (EXE/DLL) header and section information.

This tool analyzes PE files and displays:
• DOS header information
• PE header details
• Optional header data
• Section information
• File characteristics and metadata

Use 'pedump --help' to see available commands.
        """.strip()

    def _get_cli_short_help(self) -> str:
        """自定义 CLI 简短帮助信息"""
        return "Parse PE file (EXE/DLL) header and section information"

    def _add_cli_commands(self, cli_group: click.Group) -> None:
        """添加工具特定的 CLI 命令"""

        @cli_group.command()
        @click.argument('files', nargs=-1, type=click.Path(exists=True, path_type=Path))
        @click.option('--format', '-f', type=click.Choice(['table', 'json', 'csv']), 
                      default='table', help='Output format')
        def parse(files: Tuple[Path, ...], format: str) -> None:
            """Parse PE files and display information"""
            try:
                self.logger.info(f"Executing parse command, files: {files}, format: {format}")
                
                if not files:
                    console.print("[red]No files specified[/red]")
                    return
                
                for file_path in files:
                    self._parse_pe_file(file_path, format)
                    
            except Exception as e:
                self.logger.error(f"parse command execution failed: {e}")
                console.print(f"[red]Error: {e}[/red]")

    def _parse_pe_file(self, file_path: Path, format: str) -> None:
        """解析单个 PE 文件"""
        try:
            parser = PEParser(file_path)
            parser.parse()
            info = parser.get_info()
            
            if format == 'json':
                import json
                console.print(json.dumps(info, indent=2))
            elif format == 'csv':
                self._output_csv(info)
            else:
                self._output_table(info)
                
        except PEFormatError as e:
            console.print(f"[red]PE format error for {file_path}: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error parsing {file_path}: {e}[/red]")

    def _output_table(self, info: Dict[str, Any]) -> None:
        """以表格形式输出信息"""
        from rich.table import Table
        
        # 文件信息表格
        file_table = Table(title=f"PE File: {info['file_path']}")
        file_table.add_column("Property", style="cyan")
        file_table.add_column("Value", style="green")
        
        file_table.add_row("File Path", info['file_path'])
        file_table.add_row("Machine", info['pe_header']['Machine'])
        file_table.add_row("Sections", str(info['pe_header']['NumberOfSections']))
        file_table.add_row("Entry Point", info['optional_header']['AddressOfEntryPoint'])
        file_table.add_row("Image Base", info['optional_header']['ImageBase'])
        file_table.add_row("Subsystem", info['optional_header']['Subsystem'])
        
        console.print(file_table)
        
        # 节信息表格
        if info['sections']:
            section_table = Table(title="Sections")
            section_table.add_column("Name", style="cyan")
            section_table.add_column("Virtual Size", style="green")
            section_table.add_column("Virtual Address", style="blue")
            section_table.add_column("Raw Size", style="yellow")
            
            for section in info['sections']:
                section_table.add_row(
                    section['Name'],
                    str(section['VirtualSize']),
                    section['VirtualAddress'],
                    str(section['SizeOfRawData'])
                )
            
            console.print(section_table)

    def _output_csv(self, info: Dict[str, Any]) -> None:
        """以 CSV 形式输出信息"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入文件信息
        writer.writerow(['Property', 'Value'])
        writer.writerow(['File Path', info['file_path']])
        writer.writerow(['Machine', info['pe_header']['Machine']])
        writer.writerow(['Sections', info['pe_header']['NumberOfSections']])
        writer.writerow(['Entry Point', info['optional_header']['AddressOfEntryPoint']])
        writer.writerow(['Image Base', info['optional_header']['ImageBase']])
        writer.writerow(['Subsystem', info['optional_header']['Subsystem']])
        
        # 写入节信息
        writer.writerow([])
        writer.writerow(['Section Name', 'Virtual Size', 'Virtual Address', 'Raw Size'])
        for section in info['sections']:
            writer.writerow([
                section['Name'],
                section['VirtualSize'],
                section['VirtualAddress'],
                section['SizeOfRawData']
            ])
        
        console.print(output.getvalue())

    def validate_config(self) -> bool:
        """验证配置"""
        if not self.tool_name:
            self.logger.warning("Tool name is empty")
            return False

        self.logger.info("Configuration validation passed")
        return True

    def _cleanup_impl(self) -> None:
        """自定义清理逻辑"""
        self.logger.info("Executing custom cleanup logic")
        pass