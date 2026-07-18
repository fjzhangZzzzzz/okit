package appinfo

import (
	"errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
)

func TestCollectReportsShadowedExecutable_INFO001_INFO002_INFO005(t *testing.T) {
	root := t.TempDir()
	executable := filepath.Join(root, "current", "okit.exe")
	resolved := filepath.Join(root, "legacy", "okit.exe")
	home := filepath.Join(root, ".okit")
	configFile := filepath.Join(home, "config.yaml")
	for _, path := range []string{executable, resolved, configFile} {
		if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("fixture"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	collector := Collector{
		Build:      Build{Version: "v2.0.0", Commit: "abc123", Built: "2026-07-18"},
		GOOS:       "windows",
		GOARCH:     "amd64",
		Executable: func() (string, error) { return executable, nil },
		LookPath:   func(string) (string, error) { return resolved, nil },
		Home:       func() (string, error) { return home, nil },
		Getenv: func(key string) string {
			if key == "PATH" {
				return filepath.Dir(resolved) + string(os.PathListSeparator) + filepath.Dir(executable)
			}
			return ""
		},
		Stat: os.Stat,
		LoadMetadata: func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{Method: "official", Channel: "stable", Version: "v2.0.0", Executable: executable}, nil
		},
	}
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.Version != "v2.0.0" || info.Platform != "windows/amd64" || info.Executable != executable || info.DataDir != home {
		t.Fatalf("info=%+v", info)
	}
	if info.PathStatus != "shadowed" || !info.InstallDirInPath || !hasWarning(info, "PATH_SHADOWED") {
		t.Fatalf("path diagnosis=%+v", info)
	}
	if info.MetadataStatus != "ok" || info.InstallMethod != "official" || info.InstallChannel != "stable" || info.InstallVersion != "v2.0.0" {
		t.Fatalf("metadata=%+v", info)
	}
	if !info.ConfigExists || info.ConfigFile != configFile {
		t.Fatalf("config=%+v", info)
	}
}

func TestCollectReportsMissingPathAndMetadata_INFO003_INFO004(t *testing.T) {
	home := t.TempDir()
	collector := Collector{
		Build:      Build{Version: "dev"},
		GOOS:       "linux",
		GOARCH:     "arm64",
		Executable: func() (string, error) { return "/opt/okit", nil },
		LookPath:   func(string) (string, error) { return "", errors.New("not found") },
		Home:       func() (string, error) { return home, nil },
		Getenv:     func(string) string { return "" },
		Stat:       os.Stat,
		LoadMetadata: func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{}, os.ErrNotExist
		},
	}
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.PathStatus != "missing" || !hasWarning(info, "PATH_MISSING") {
		t.Fatalf("path diagnosis=%+v", info)
	}
	if info.MetadataStatus != "missing" || !hasWarning(info, "METADATA_MISSING") {
		t.Fatalf("metadata diagnosis=%+v", info)
	}
	if info.Warnings == nil {
		t.Fatal("warnings must encode as an empty array when there are no warnings")
	}
}

func TestCollectReportsInvalidMetadata_INFO004(t *testing.T) {
	collector := Collector{
		Build:        Build{Version: "dev"},
		GOOS:         "linux",
		GOARCH:       "amd64",
		Executable:   func() (string, error) { return "/usr/local/bin/okit", nil },
		LookPath:     func(string) (string, error) { return "/usr/local/bin/okit", nil },
		Home:         func() (string, error) { return "/home/user/.okit", nil },
		Getenv:       func(string) string { return "/usr/local/bin" },
		Stat:         func(string) (os.FileInfo, error) { return nil, os.ErrNotExist },
		LoadMetadata: func(string) (selfmanage.Metadata, error) { return selfmanage.Metadata{}, errors.New("invalid json") },
	}
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.MetadataStatus != "invalid" || !hasWarning(info, "METADATA_INVALID") {
		t.Fatalf("metadata diagnosis=%+v", info)
	}
}

func TestCollectFallsBackToExecutableSuffixOnWindows_INFO002(t *testing.T) {
	legacy := `C:\Users\user\.local\bin\okit.exe`
	calls := make([]string, 0, 2)
	collector := Collector{
		Build:      Build{Version: "v2.0.0"},
		GOOS:       "windows",
		GOARCH:     "amd64",
		Executable: func() (string, error) { return `C:\Programs\okit\bin\okit.exe`, nil },
		LookPath: func(name string) (string, error) {
			calls = append(calls, name)
			if name == "okit.exe" {
				return legacy, nil
			}
			return "", errors.New("not found")
		},
		Home:   func() (string, error) { return `C:\Users\user\.okit`, nil },
		Getenv: func(string) string { return "" },
		Stat:   func(string) (os.FileInfo, error) { return nil, os.ErrNotExist },
		LoadMetadata: func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{}, os.ErrNotExist
		},
	}
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

func TestCollectFailsWhenCorePathsCannotBeResolved(t *testing.T) {
	collector := Collector{Executable: func() (string, error) { return "", errors.New("injected executable failure") }}
	if _, err := collector.Collect(); err == nil || err.Error() != "resolve executable: injected executable failure" {
		t.Fatalf("error=%v", err)
	}

	collector = Collector{
		Executable: func() (string, error) { return "/usr/bin/okit", nil },
		Home:       func() (string, error) { return "", errors.New("injected home failure") },
	}
	if _, err := collector.Collect(); err == nil || err.Error() != "injected home failure" {
		t.Fatalf("error=%v", err)
	}
}

func hasWarning(info Info, code string) bool {
	for _, warning := range info.Warnings {
		if warning.Code == code {
			return true
		}
	}
	return false
}
