package theme

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

var knownColors = map[string]bool{
	"Black": true, "Red": true, "Green": true, "Yellow": true, "Blue": true, "Magenta": true, "Cyan": true, "White": true,
	"BoldBlack": true, "BoldRed": true, "BoldGreen": true, "BoldYellow": true, "BoldBlue": true, "BoldMagenta": true, "BoldCyan": true, "BoldWhite": true,
	"ForegroundColour": true, "BackgroundColour": true, "CursorColour": true,
}

type Result struct {
	Changed    bool
	BackupPath string
}

type ReplaceFunc func(path string, data []byte, mode os.FileMode) error

func Apply(configPath, schemePath, backupDir string, dryRun bool, replace ReplaceFunc) (Result, error) {
	return apply(configPath, schemePath, backupDir, dryRun, true, replace)
}

func ApplyWithoutBackup(configPath, schemePath string, dryRun bool, replace ReplaceFunc) (Result, error) {
	return apply(configPath, schemePath, "", dryRun, false, replace)
}

func apply(configPath, schemePath, backupDir string, dryRun, createBackup bool, replace ReplaceFunc) (Result, error) {
	config, err := os.ReadFile(configPath)
	if err != nil {
		return Result{}, err
	}
	scheme, err := os.ReadFile(schemePath)
	if err != nil {
		return Result{}, err
	}
	colors, err := parseColors(string(scheme))
	if err != nil {
		return Result{}, err
	}
	updated, changed := applyColors(string(config), colors)
	if !changed || dryRun {
		return Result{Changed: changed}, nil
	}
	backup := ""
	if createBackup {
		if err := os.MkdirAll(backupDir, 0o700); err != nil {
			return Result{}, err
		}
		backup = filepath.Join(backupDir, filepath.Base(configPath)+"."+time.Now().UTC().Format("20060102T150405.000000000Z")+".bak")
		if err := os.WriteFile(backup, config, 0o600); err != nil {
			return Result{}, err
		}
	}
	result := Result{Changed: true, BackupPath: backup}
	info, err := os.Stat(configPath)
	if err != nil {
		return result, err
	}
	if replace == nil {
		replace = atomicReplace
	}
	if err := replace(configPath, []byte(updated), info.Mode().Perm()); err != nil {
		return result, err
	}
	return result, nil
}

func parseColors(content string) (map[string]string, error) {
	colors := make(map[string]string)
	content = strings.ReplaceAll(content, "\r\n", "\n")
	for _, line := range strings.Split(content, "\n") {
		parts := strings.SplitN(strings.TrimSpace(line), "=", 2)
		if len(parts) != 2 || !knownColors[parts[0]] {
			continue
		}
		components := strings.Split(parts[1], ",")
		if len(components) != 3 {
			return nil, fmt.Errorf("invalid color %s=%s", parts[0], parts[1])
		}
		for _, component := range components {
			var value int
			if _, err := fmt.Sscanf(strings.TrimSpace(component), "%d", &value); err != nil || value < 0 || value > 255 {
				return nil, fmt.Errorf("invalid color %s=%s", parts[0], parts[1])
			}
		}
		colors[parts[0]] = strings.Join([]string{strings.TrimSpace(components[0]), strings.TrimSpace(components[1]), strings.TrimSpace(components[2])}, ",")
	}
	if len(colors) == 0 {
		return nil, errors.New("scheme contains no supported colors")
	}
	return colors, nil
}

func applyColors(content string, colors map[string]string) (string, bool) {
	lines := strings.SplitAfter(content, "\n")
	changed := false
	for i, line := range lines {
		ending := ""
		body := line
		if strings.HasSuffix(body, "\n") {
			ending = "\n"
			body = strings.TrimSuffix(body, "\n")
		}
		if strings.HasSuffix(body, "\r") {
			ending = "\r" + ending
			body = strings.TrimSuffix(body, "\r")
		}
		parts := strings.SplitN(body, "=", 2)
		if len(parts) != 2 {
			continue
		}
		value, ok := colors[strings.TrimSpace(parts[0])]
		if !ok {
			continue
		}
		next := parts[0] + "=" + value + ending
		if next != line {
			lines[i] = next
			changed = true
		}
	}
	return strings.Join(lines, ""), changed
}

func Restore(configPath, backupPath string, dryRun bool) error {
	data, err := os.ReadFile(backupPath)
	if err != nil {
		return err
	}
	if dryRun {
		return nil
	}
	mode := os.FileMode(0o600)
	if info, err := os.Stat(configPath); err == nil {
		mode = info.Mode().Perm()
	}
	return atomicReplace(configPath, data, mode)
}

func CleanCache(okitHome, cachePath string, dryRun bool) error {
	expected := filepath.Clean(filepath.Join(okitHome, "cache", "mobaxterm", "themes"))
	actual := filepath.Clean(cachePath)
	equal := expected == actual
	if runtime.GOOS == "windows" {
		equal = strings.EqualFold(expected, actual)
	}
	if !equal {
		return fmt.Errorf("refusing to remove unmanaged cache path %s", cachePath)
	}
	if dryRun {
		return nil
	}
	return os.RemoveAll(actual)
}

func atomicReplace(path string, data []byte, mode os.FileMode) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), ".mobaxterm-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(mode); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	swap := path + ".okit-swap"
	if err := os.Rename(path, swap); err != nil {
		return err
	}
	if err := os.Rename(tmpName, path); err != nil {
		_ = os.Rename(swap, path)
		return err
	}
	return os.Remove(swap)
}
