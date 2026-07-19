package appinfo

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"unsafe"

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
	if info.Resolved != mustCanonicalPath(t, legacy) || info.PathStatus != "shadowed" || !hasWarning(info, "PATH_SHADOWED") {
		t.Fatalf("path diagnosis=%+v", info)
	}
}

func TestSameNativePathIgnoresWindowsCase(t *testing.T) {
	if !sameNativePath(`C:\Programs\okit\okit.exe`, `c:\programs\OKIT\okit.exe`) {
		t.Fatal("Windows path comparison should ignore case")
	}
}

func TestCollectTreatsWindowsShortAndLongPathsAsTheSameFile(t *testing.T) {
	longRoot := filepath.Join(t.TempDir(), "Long Directory Name For Okit")
	executable := filepath.Join(longRoot, "okit.exe")
	home := filepath.Join(longRoot, "Okit Home")
	if err := os.MkdirAll(home, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(executable, []byte("fixture"), 0o600); err != nil {
		t.Fatal(err)
	}
	shortExecutable := windowsShortPath(t, executable)
	shortRoot := filepath.Dir(shortExecutable)
	shortHome := windowsShortPath(t, home)
	if strings.EqualFold(shortExecutable, executable) {
		t.Skip("8.3 short names are unavailable on this volume")
	}

	collector := testCollector(Build{Version: "v2.0.0"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return shortExecutable, nil }
		system.LookPath = func(string) (string, error) { return shortExecutable, nil }
		system.Home = func() (string, error) { return shortHome, nil }
		system.Getenv = func(string) string { return shortRoot }
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{Version: "v2.0.0", Executable: shortExecutable}, nil
		}
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.PathStatus != "ok" || !info.InstallDirInPath {
		t.Fatalf("path diagnosis=%+v", info)
	}
	if hasWarning(info, "METADATA_EXECUTABLE_MISMATCH") {
		t.Fatalf("metadata diagnosis=%+v", info)
	}
	if strings.Contains(strings.ToUpper(info.Executable), "~") {
		t.Fatalf("executable was not canonicalized: %s", info.Executable)
	}
}

func windowsShortPath(t *testing.T, path string) string {
	t.Helper()
	input, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		t.Fatal(err)
	}
	buffer := make([]uint16, 32768)
	getShortPathName := syscall.NewLazyDLL("kernel32.dll").NewProc("GetShortPathNameW")
	length, _, callErr := getShortPathName.Call(
		uintptr(unsafe.Pointer(input)),
		uintptr(unsafe.Pointer(&buffer[0])),
		uintptr(len(buffer)),
	)
	if length == 0 {
		t.Fatalf("GetShortPathNameW(%q): %v", path, callErr)
	}
	if length >= uintptr(len(buffer)) {
		t.Fatalf("GetShortPathNameW(%q) returned an oversized path", path)
	}
	return syscall.UTF16ToString(buffer[:length])
}
