package config

import (
	"fmt"
	"path/filepath"
	"strings"
)

func normalizeHomeOverride(home string) (string, error) {
	if isMSYSDrivePath(home) {
		if len(home) == 2 {
			home += "/"
		}
		home = strings.ToUpper(home[1:2]) + ":" + home[2:]
	} else if strings.HasPrefix(home, "/") {
		return "", fmt.Errorf("OKIT_HOME %q is an ambiguous POSIX path on Windows; use a drive-qualified path", home)
	}
	return filepath.Clean(home), nil
}

func isMSYSDrivePath(path string) bool {
	if len(path) < 2 || path[0] != '/' || !isASCIILetter(path[1]) {
		return false
	}
	return len(path) == 2 || path[2] == '/'
}

func isASCIILetter(value byte) bool {
	return value >= 'a' && value <= 'z' || value >= 'A' && value <= 'Z'
}
