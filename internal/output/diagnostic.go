package output

import (
	"encoding/json"
	"fmt"
	"io"
)

type Diagnostic struct {
	Code    string            `json:"code"`
	Message string            `json:"message"`
	Hint    string            `json:"hint,omitempty"`
	Fields  map[string]string `json:"fields,omitempty"`
}

func writeDiagnostic(w io.Writer, format, level string, diagnostic Diagnostic) {
	if format == FormatJSON || format == FormatJSONL {
		_ = json.NewEncoder(w).Encode(struct {
			Level string `json:"level"`
			Diagnostic
		}{Level: level, Diagnostic: diagnostic})
		return
	}
	prefix := level
	if diagnostic.Code != "" {
		prefix += " [" + diagnostic.Code + "]"
	}
	fmt.Fprintf(w, "%s: %s\n", prefix, diagnostic.Message)
	if diagnostic.Hint != "" {
		fmt.Fprintf(w, "hint: %s\n", diagnostic.Hint)
	}
}
