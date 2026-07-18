package peinspect

import (
	"bytes"
	"encoding/binary"
	"reflect"
	"strings"
	"testing"
)

func fixture(t *testing.T, pe64 bool) []byte {
	t.Helper()
	machine := uint16(0x14c)
	magic := uint16(0x10b)
	optionalSize := uint16(224)
	if pe64 {
		machine, magic, optionalSize = 0x8664, 0x20b, 240
	}
	data := make([]byte, 0x80+4+20+int(optionalSize)+40+16)
	data[0], data[1] = 'M', 'Z'
	binary.LittleEndian.PutUint32(data[0x3c:], 0x80)
	offset := 0x80
	copy(data[offset:], []byte{'P', 'E', 0, 0})
	offset += 4
	binary.LittleEndian.PutUint16(data[offset:], machine)
	binary.LittleEndian.PutUint16(data[offset+2:], 1)
	binary.LittleEndian.PutUint32(data[offset+4:], 123456789)
	binary.LittleEndian.PutUint16(data[offset+16:], optionalSize)
	binary.LittleEndian.PutUint16(data[offset+18:], 0x0002)
	offset += 20
	binary.LittleEndian.PutUint16(data[offset:], magic)
	binary.LittleEndian.PutUint32(data[offset+16:], 0x1000)
	if pe64 {
		binary.LittleEndian.PutUint64(data[offset+24:], 0x140000000)
		binary.LittleEndian.PutUint32(data[offset+108:], 16)
	} else {
		binary.LittleEndian.PutUint32(data[offset+28:], 0x400000)
		binary.LittleEndian.PutUint32(data[offset+92:], 16)
	}
	binary.LittleEndian.PutUint32(data[offset+32:], 0x1000)
	binary.LittleEndian.PutUint32(data[offset+36:], 0x200)
	binary.LittleEndian.PutUint32(data[offset+56:], 0x2000)
	binary.LittleEndian.PutUint32(data[offset+60:], 0x200)
	offset += int(optionalSize)
	copy(data[offset:], []byte(".text\x00\x00\x00"))
	binary.LittleEndian.PutUint32(data[offset+8:], 16)
	binary.LittleEndian.PutUint32(data[offset+12:], 0x1000)
	binary.LittleEndian.PutUint32(data[offset+16:], 16)
	binary.LittleEndian.PutUint32(data[offset+20:], uint32(offset+40))
	binary.LittleEndian.PutUint32(data[offset+36:], 0x60000020)
	return data
}

func TestPlatformIndependentStructuredResult_PE005(t *testing.T) {
	first, err := Parse(bytes.NewReader(fixture(t, true)), "fixture.exe")
	if err != nil {
		t.Fatal(err)
	}
	second, err := Parse(bytes.NewReader(fixture(t, true)), "fixture.exe")
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(first, second) {
		t.Fatalf("same bytes produced different structures: %#v != %#v", first, second)
	}
}

func TestParsePE32AndPE64_PE001(t *testing.T) {
	for _, pe64 := range []bool{false, true} {
		info, err := Parse(bytes.NewReader(fixture(t, pe64)), "fixture.exe")
		if err != nil {
			t.Fatalf("pe64=%v: %v", pe64, err)
		}
		if info.EntryPoint != 0x1000 || len(info.Sections) != 1 || info.Sections[0].Name != ".text" {
			t.Fatalf("pe64=%v info=%+v", pe64, info)
		}
		wantBase := uint64(0x400000)
		if pe64 {
			wantBase = 0x140000000
		}
		if info.ImageBase != wantBase {
			t.Fatalf("image base=%x, want %x", info.ImageBase, wantBase)
		}
	}
}

func TestFormats_PE002(t *testing.T) {
	info, err := Parse(bytes.NewReader(fixture(t, false)), "fixture.exe")
	if err != nil {
		t.Fatal(err)
	}
	for _, format := range []string{"table", "json", "csv"} {
		var out bytes.Buffer
		if err := Write(&out, []Info{info}, format); err != nil {
			t.Fatalf("format %s: %v", format, err)
		}
		text := out.String()
		for _, expected := range []string{"fixture.exe", ".text"} {
			if !strings.Contains(text, expected) {
				t.Fatalf("format %s missing %q: %s", format, expected, text)
			}
		}
	}
}

func TestCorruptInput_PE003(t *testing.T) {
	for _, data := range [][]byte{{}, {'M', 'Z'}, fixture(t, false)[:100]} {
		if _, err := Parse(bytes.NewReader(data), "broken.exe"); err == nil {
			t.Fatalf("accepted corrupt input of length %d", len(data))
		}
	}
}
