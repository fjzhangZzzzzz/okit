package config

import (
	"fmt"
	"os"
	"path/filepath"
)

func Home() (string, error) {
	if home := os.Getenv("OKIT_HOME"); home != "" {
		return normalizeHomeOverride(home)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve user home: %w", err)
	}
	return filepath.Join(home, ".okit"), nil
}
