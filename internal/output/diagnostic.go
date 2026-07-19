package output

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
)

type Diagnostic struct {
	Code    string            `json:"code"`
	Message string            `json:"message"`
	Action  string            `json:"action,omitempty"`
	Fields  map[string]string `json:"fields,omitempty"`
}

func writeDiagnostic(w io.Writer, format, level string, verbose bool, diagnostic Diagnostic) {
	if format == FormatJSON || format == FormatJSONL {
		_ = json.NewEncoder(w).Encode(struct {
			Level string `json:"level"`
			Diagnostic
		}{Level: level, Diagnostic: diagnostic})
		return
	}
	fmt.Fprintln(w, humanSentence(diagnostic.Message))
	if diagnostic.Action != "" {
		fmt.Fprintln(w)
		fmt.Fprintln(w, humanSentence(diagnostic.Action))
	}
	if verbose {
		fmt.Fprintln(w)
		fmt.Fprintf(w, "Diagnostic level: %s\n", level)
		if diagnostic.Code != "" {
			fmt.Fprintf(w, "Diagnostic code: %s\n", diagnostic.Code)
		}
		keys := make([]string, 0, len(diagnostic.Fields))
		for key := range diagnostic.Fields {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			value := diagnostic.Fields[key]
			fmt.Fprintf(w, "%s: %s\n", key, value)
		}
	}
}

func humanSentence(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return value
	}
	runes := []rune(value)
	if strings.ContainsRune(".!?", runes[len(runes)-1]) {
		return value
	}
	return value + "."
}
