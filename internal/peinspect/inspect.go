package peinspect

import (
	"debug/pe"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
)

type Section struct {
	Name            string `json:"name"`
	VirtualAddress  uint32 `json:"virtual_address"`
	VirtualSize     uint32 `json:"virtual_size"`
	RawSize         uint32 `json:"raw_size"`
	Characteristics uint32 `json:"characteristics"`
}

type Info struct {
	Path            string    `json:"path"`
	Machine         string    `json:"machine"`
	Timestamp       uint32    `json:"timestamp"`
	Characteristics uint16    `json:"characteristics"`
	PEType          string    `json:"pe_type"`
	EntryPoint      uint32    `json:"entry_point"`
	ImageBase       uint64    `json:"image_base"`
	Sections        []Section `json:"sections"`
}

func Parse(reader io.ReaderAt, path string) (Info, error) {
	file, err := pe.NewFile(reader)
	if err != nil {
		return Info{}, fmt.Errorf("parse PE %s: %w", path, err)
	}
	defer file.Close()

	info := Info{
		Path:            path,
		Machine:         machineName(file.Machine),
		Timestamp:       file.TimeDateStamp,
		Characteristics: file.Characteristics,
		Sections:        make([]Section, 0, len(file.Sections)),
	}
	switch header := file.OptionalHeader.(type) {
	case *pe.OptionalHeader32:
		info.PEType = "PE32"
		info.EntryPoint = header.AddressOfEntryPoint
		info.ImageBase = uint64(header.ImageBase)
	case *pe.OptionalHeader64:
		info.PEType = "PE32+"
		info.EntryPoint = header.AddressOfEntryPoint
		info.ImageBase = header.ImageBase
	default:
		return Info{}, errors.New("unsupported or missing PE optional header")
	}
	for _, section := range file.Sections {
		info.Sections = append(info.Sections, Section{
			Name:            section.Name,
			VirtualAddress:  section.VirtualAddress,
			VirtualSize:     section.VirtualSize,
			RawSize:         section.Size,
			Characteristics: section.Characteristics,
		})
	}
	return info, nil
}

func machineName(machine uint16) string {
	switch machine {
	case pe.IMAGE_FILE_MACHINE_I386:
		return "i386"
	case pe.IMAGE_FILE_MACHINE_AMD64:
		return "amd64"
	case pe.IMAGE_FILE_MACHINE_ARM64:
		return "arm64"
	default:
		return fmt.Sprintf("0x%04x", machine)
	}
}

func Write(output io.Writer, infos []Info, format string) error {
	switch format {
	case "", "table":
		for _, info := range infos {
			fmt.Fprintf(output, "File: %s\nMachine: %s\nType: %s\nTimestamp: %d\nEntry point: 0x%x\nImage base: 0x%x\n", info.Path, info.Machine, info.PEType, info.Timestamp, info.EntryPoint, info.ImageBase)
			fmt.Fprintln(output, "Sections:")
			fmt.Fprintln(output, "NAME\tVIRTUAL_ADDRESS\tVIRTUAL_SIZE\tRAW_SIZE\tCHARACTERISTICS")
			for _, section := range info.Sections {
				fmt.Fprintf(output, "%s\t0x%x\t%d\t%d\t0x%x\n", section.Name, section.VirtualAddress, section.VirtualSize, section.RawSize, section.Characteristics)
			}
		}
		return nil
	case "json":
		encoder := json.NewEncoder(output)
		encoder.SetIndent("", "  ")
		return encoder.Encode(infos)
	case "csv":
		writer := csv.NewWriter(output)
		if err := writer.Write([]string{"path", "machine", "pe_type", "timestamp", "entry_point", "image_base", "section", "virtual_address", "virtual_size", "raw_size", "characteristics"}); err != nil {
			return err
		}
		for _, info := range infos {
			sections := info.Sections
			if len(sections) == 0 {
				sections = []Section{{}}
			}
			for _, section := range sections {
				record := []string{
					info.Path, info.Machine, info.PEType, strconv.FormatUint(uint64(info.Timestamp), 10),
					fmt.Sprintf("0x%x", info.EntryPoint), fmt.Sprintf("0x%x", info.ImageBase), section.Name,
					fmt.Sprintf("0x%x", section.VirtualAddress), strconv.FormatUint(uint64(section.VirtualSize), 10),
					strconv.FormatUint(uint64(section.RawSize), 10), fmt.Sprintf("0x%x", section.Characteristics),
				}
				if err := writer.Write(record); err != nil {
					return err
				}
			}
		}
		writer.Flush()
		return writer.Error()
	default:
		return fmt.Errorf("unsupported output format %q (want table, json, or csv)", strings.TrimSpace(format))
	}
}
