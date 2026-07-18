package hex

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
)

type Options struct {
	Display   string
	WordSize  int
	Skip      int64
	Length    int64
	LengthSet bool
	NoSqueeze bool
}

func (o *Options) normalize() error {
	if o.Display == "" {
		o.Display = "canonical"
	}
	if o.WordSize == 0 {
		o.WordSize = 1
	}
	validDisplay := map[string]bool{"canonical": true, "hex": true, "octal": true, "char": true, "decimal": true}
	if !validDisplay[o.Display] {
		return fmt.Errorf("unsupported display %q", o.Display)
	}
	if o.WordSize != 1 && o.WordSize != 2 {
		return errors.New("word size must be 1 or 2")
	}
	if o.Skip < 0 || o.Length < 0 {
		return errors.New("skip and length must be non-negative")
	}
	return nil
}

func Dump(input io.Reader, output io.Writer, options Options) error {
	if err := options.normalize(); err != nil {
		return err
	}
	if options.Skip > 0 {
		if _, err := io.CopyN(io.Discard, input, options.Skip); err != nil && !errors.Is(err, io.EOF) {
			return fmt.Errorf("skip input: %w", err)
		}
	}
	reader := input
	if options.LengthSet {
		reader = io.LimitReader(input, options.Length)
	}

	const lineSize = 16
	buffer := make([]byte, lineSize)
	var previous []byte
	squeezing := false
	offset := options.Skip
	for {
		n, err := io.ReadFull(reader, buffer)
		if errors.Is(err, io.EOF) && n == 0 {
			break
		}
		if err != nil && !errors.Is(err, io.ErrUnexpectedEOF) {
			return fmt.Errorf("read input: %w", err)
		}
		line := buffer[:n]
		if !options.NoSqueeze && n == lineSize && len(previous) == lineSize && bytes.Equal(line, previous) {
			if !squeezing {
				fmt.Fprintln(output, "*")
				squeezing = true
			}
		} else {
			squeezing = false
			fmt.Fprintln(output, formatLine(offset, line, options))
		}
		previous = append(previous[:0], line...)
		offset += int64(n)
		if errors.Is(err, io.ErrUnexpectedEOF) {
			break
		}
	}
	return nil
}

func formatLine(offset int64, data []byte, options Options) string {
	if options.Display == "canonical" {
		var hexPart strings.Builder
		for i := 0; i < 16; i++ {
			if i == 8 {
				hexPart.WriteByte(' ')
			}
			if i < len(data) {
				fmt.Fprintf(&hexPart, "%02x ", data[i])
			} else {
				hexPart.WriteString("   ")
			}
		}
		var ascii strings.Builder
		for _, b := range data {
			if b >= 32 && b <= 126 {
				ascii.WriteByte(b)
			} else {
				ascii.WriteByte('.')
			}
		}
		return fmt.Sprintf("%08x  %s|%s|", offset, hexPart.String(), ascii.String())
	}

	values := make([]string, 0, (len(data)+options.WordSize-1)/options.WordSize)
	for i := 0; i < len(data); i += options.WordSize {
		chunk := data[i:min(i+options.WordSize, len(data))]
		var value uint16
		if len(chunk) == 2 {
			value = binary.LittleEndian.Uint16(chunk)
		} else {
			value = uint16(chunk[0])
		}
		switch options.Display {
		case "hex":
			values = append(values, fmt.Sprintf("%0*x", options.WordSize*2, value))
		case "octal":
			width := 3
			if options.WordSize == 2 {
				width = 6
			}
			values = append(values, fmt.Sprintf("%0*o", width, value))
		case "decimal":
			width := 3
			if options.WordSize == 2 {
				width = 5
			}
			values = append(values, fmt.Sprintf("%0*d", width, value))
		case "char":
			var text strings.Builder
			for _, b := range chunk {
				if b >= 32 && b <= 126 {
					text.WriteByte(b)
				} else {
					text.WriteByte('.')
				}
			}
			values = append(values, strconv.Quote(text.String()))
		}
	}
	return fmt.Sprintf("%08x  %s", offset, strings.Join(values, " "))
}
