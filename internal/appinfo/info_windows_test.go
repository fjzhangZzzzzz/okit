package appinfo

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
)

func TestCollectFallsBackToExecutableSuffixOnWindows_INFO002(t *testing.T) {
	root := t.TempDir()
	executable := filepath.Join(root, "current", "okit.exe")
	legacy := filepath.Join(root, "legacy", "okit.exe")
	calls := make([]string, 0, 2)
	collector := testCollector(Build{Version: "v2.0.0"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(name string) (string, error) {
			calls = append(calls, name)
			if name == "okit.exe" {
				return legacy, nil
			}
			return "", errors.New("not found")
		}
		system.Home = func() (string, error) { return filepath.Join(root, ".okit"), nil }
		system.Getenv = func(string) string { return "" }
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{}, os.ErrNotExist
		}
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if len(calls) != 2 || calls[0] != "okit" || calls[1] != "okit.exe" {
		t.Fatalf("look path calls=%v", calls)
	}
	if info.Resolved != legacy || info.PathStatus != "shadowed" || !hasWarning(info, "PATH_SHADOWED") {
		t.Fatalf("path diagnosis=%+v", info)
	}
}

func TestSameNativePathIgnoresWindowsCase(t *testing.T) {
	if !sameNativePath(`C:\Programs\okit\okit.exe`, `c:\programs\OKIT\okit.exe`) {
		t.Fatal("Windows path comparison should ignore case")
	}
}
