//go:build !windows

package appinfo

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
)

func TestSameNativePathPreservesCaseSensitivity(t *testing.T) {
	if sameNativePath("/opt/okit", "/opt/OKIT") {
		t.Fatal("non-Windows path comparison must preserve case")
	}
}

func TestCollectTreatsSymlinkedPathsAsTheSameFile(t *testing.T) {
	root := t.TempDir()
	realDir := filepath.Join(root, "real")
	aliasDir := filepath.Join(root, "alias")
	executable := filepath.Join(realDir, "okit")
	if err := os.MkdirAll(realDir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(executable, []byte("fixture"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(realDir, aliasDir); err != nil {
		t.Skipf("symlinks are unavailable: %v", err)
	}
	aliasExecutable := filepath.Join(aliasDir, "okit")

	collector := testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(string) (string, error) { return aliasExecutable, nil }
		system.Home = func() (string, error) { return root, nil }
		system.Getenv = func(string) string { return aliasDir }
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{Executable: aliasExecutable}, nil
		}
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.PathStatus != "ok" || !info.InstallDirInPath || hasWarning(info, "METADATA_EXECUTABLE_MISMATCH") {
		t.Fatalf("diagnosis=%+v", info)
	}
}
