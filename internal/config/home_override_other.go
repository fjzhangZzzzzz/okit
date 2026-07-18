//go:build !windows

package config

import "path/filepath"

func normalizeHomeOverride(home string) (string, error) {
	return filepath.Clean(home), nil
}
