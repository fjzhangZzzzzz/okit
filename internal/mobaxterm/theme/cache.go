package theme

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

const RepositoryURL = "https://github.com/mbadolato/iTerm2-Color-Schemes.git"

func UpdateCache(cachePath string) error {
	if _, err := os.Stat(cachePath); os.IsNotExist(err) {
		if err := os.MkdirAll(filepath.Dir(cachePath), 0o700); err != nil {
			return err
		}
		return runGit("clone", "--depth", "1", RepositoryURL, cachePath)
	} else if err != nil {
		return err
	}
	return runGit("-C", cachePath, "pull", "--ff-only")
}

func runGit(args ...string) error {
	command := exec.Command("git", args...)
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("git %s failed: %w: %s", strings.Join(args, " "), err, strings.TrimSpace(string(output)))
	}
	return nil
}

func List(cachePath, search string, limit int) ([]string, error) {
	if limit <= 0 {
		limit = 20
	}
	search = strings.ToLower(search)
	var schemes []string
	err := filepath.WalkDir(cachePath, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() || !strings.EqualFold(filepath.Ext(path), ".ini") {
			return nil
		}
		name := strings.TrimSuffix(entry.Name(), filepath.Ext(entry.Name()))
		if search == "" || strings.Contains(strings.ToLower(name), search) {
			schemes = append(schemes, name)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(schemes)
	if len(schemes) > limit {
		schemes = schemes[:limit]
	}
	return schemes, nil
}

func Resolve(cachePath, name string) (string, error) {
	var match string
	err := filepath.WalkDir(cachePath, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !entry.IsDir() && strings.EqualFold(strings.TrimSuffix(entry.Name(), filepath.Ext(entry.Name())), name) && strings.EqualFold(filepath.Ext(path), ".ini") {
			match = path
			return filepath.SkipAll
		}
		return nil
	})
	if err != nil {
		return "", err
	}
	if match == "" {
		return "", fmt.Errorf("theme %q was not found in cache", name)
	}
	return match, nil
}

func LatestBackup(backupDir string) (string, error) {
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		return "", err
	}
	var latest string
	var latestTime int64
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".bak") {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			return "", err
		}
		if latest == "" || info.ModTime().UnixNano() > latestTime {
			latest = filepath.Join(backupDir, entry.Name())
			latestTime = info.ModTime().UnixNano()
		}
	}
	if latest == "" {
		return "", fmt.Errorf("no MobaXterm backup was found")
	}
	return latest, nil
}
