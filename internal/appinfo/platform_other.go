//go:build !windows

package appinfo

import "path/filepath"

func executableNames() []string {
	return []string{"okit"}
}

func sameNativePath(left, right string) bool {
	if left == "" || right == "" {
		return false
	}
	return filepath.Clean(left) == filepath.Clean(right)
}
