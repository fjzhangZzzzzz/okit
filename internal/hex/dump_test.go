package hex

import (
	"bytes"
	"fmt"
	"io"
	"strings"
	"testing"
)

func TestCanonicalOutput_HEX001(t *testing.T) {
	var out bytes.Buffer
	if err := Dump(bytes.NewReader([]byte("Hello\x00world")), &out, Options{}); err != nil {
		t.Fatal(err)
	}
	got := out.String()
	if !strings.Contains(got, "00000000") || !strings.Contains(got, "48 65 6c 6c 6f") || !strings.Contains(got, "|Hello.world|") {
		t.Fatalf("unexpected canonical output: %q", got)
	}
}

func TestSkipAndLength_HEX002(t *testing.T) {
	var out bytes.Buffer
	if err := Dump(bytes.NewReader([]byte{0, 1, 2, 3, 4, 5}), &out, Options{Skip: 2, Length: 3, LengthSet: true}); err != nil {
		t.Fatal(err)
	}
	got := out.String()
	if !strings.Contains(got, "02 03 04") || strings.Contains(got, "05") {
		t.Fatalf("range not respected: %q", got)
	}
}

func TestDisplaysAreDeterministic_HEX003(t *testing.T) {
	for _, display := range []string{"canonical", "hex", "octal", "char", "decimal"} {
		for _, size := range []int{1, 2} {
			t.Run(fmt.Sprintf("%s-%d", display, size), func(t *testing.T) {
				options := Options{Display: display, WordSize: size}
				var first, second bytes.Buffer
				if err := Dump(bytes.NewReader([]byte("abcdef")), &first, options); err != nil {
					t.Fatal(err)
				}
				if err := Dump(bytes.NewReader([]byte("abcdef")), &second, options); err != nil {
					t.Fatal(err)
				}
				if first.String() == "" || first.String() != second.String() {
					t.Fatalf("non-deterministic output: %q != %q", first.String(), second.String())
				}
			})
		}
	}
}

func TestRepeatedLines_HEX004(t *testing.T) {
	data := make([]byte, 16*4)
	var squeezed, full bytes.Buffer
	if err := Dump(bytes.NewReader(data), &squeezed, Options{}); err != nil {
		t.Fatal(err)
	}
	if err := Dump(bytes.NewReader(data), &full, Options{NoSqueeze: true}); err != nil {
		t.Fatal(err)
	}
	if strings.Count(squeezed.String(), "\n*\n") != 1 || strings.Contains(full.String(), "\n*\n") {
		t.Fatalf("squeezed=%q full=%q", squeezed.String(), full.String())
	}
}

type boundedReader struct {
	data []byte
	max  int
}

func (r *boundedReader) Read(p []byte) (int, error) {
	if len(p) > r.max {
		return 0, fmt.Errorf("read buffer %d exceeds %d", len(p), r.max)
	}
	if len(r.data) == 0 {
		return 0, io.EOF
	}
	n := copy(p, r.data)
	r.data = r.data[n:]
	return n, nil
}

func TestBoundedReads_HEX005(t *testing.T) {
	reader := &boundedReader{data: make([]byte, 1024), max: 32}
	if err := Dump(reader, &bytes.Buffer{}, Options{}); err != nil {
		t.Fatal(err)
	}
}
