package appinfo

import (
	"path/filepath"
	"strings"
)

func executableNames() []string {
	return []string{"okit", "okit.exe"}
}

func sameNativePath(left, right string) bool {
	if left == "" || right == "" {
		return false
	}
	return strings.EqualFold(filepath.Clean(left), filepath.Clean(right))
}
