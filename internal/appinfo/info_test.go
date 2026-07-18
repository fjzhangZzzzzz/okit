package appinfo

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
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
	collector := testCollector(Build{Version: "v2.0.0", Commit: "abc123", Built: "2026-07-18"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(string) (string, error) { return resolved, nil }
		system.Home = func() (string, error) { return home, nil }
		system.Getenv = func(key string) string {
			if key == "PATH" {
				return filepath.Dir(resolved) + string(os.PathListSeparator) + filepath.Dir(executable)
			}
			return ""
		}
		system.Stat = os.Stat
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{Method: "official", Channel: "stable", Version: "v2.0.0", Executable: executable}, nil
		}
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.Version != "v2.0.0" || info.Platform != runtime.GOOS+"/"+runtime.GOARCH || info.Executable != executable || info.DataDir != home {
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
	executable := filepath.Join(home, "bin", "okit")
	collector := testCollector(Build{Version: "dev"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(string) (string, error) { return "", errors.New("not found") }
		system.Home = func() (string, error) { return home, nil }
		system.Getenv = func(string) string { return "" }
		system.Stat = os.Stat
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{}, os.ErrNotExist
		}
	})
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
	home := t.TempDir()
	executable := filepath.Join(home, "bin", "okit")
	collector := testCollector(Build{Version: "dev"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(string) (string, error) { return executable, nil }
		system.Home = func() (string, error) { return home, nil }
		system.Getenv = func(string) string { return filepath.Dir(executable) }
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) { return selfmanage.Metadata{}, errors.New("invalid json") }
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.MetadataStatus != "invalid" || !hasWarning(info, "METADATA_INVALID") {
		t.Fatalf("metadata diagnosis=%+v", info)
	}
}

func TestDiagnoseDoesNotInterpretForeignPathSyntax(t *testing.T) {
	executable := `C:\Programs\okit\okit.exe`
	state := snapshot{
		Build:         Build{Version: "v2.0.0"},
		Platform:      "windows/amd64",
		Executable:    executable,
		InstallDir:    `C:\Programs\okit`,
		Resolved:      `c:\programs\OKIT\okit.exe`,
		PathEntries:   []string{`c:\programs\OKIT`},
		DataDir:       `C:\Users\test\.okit`,
		ConfigFile:    `C:\Users\test\.okit\config.yaml`,
		MetadataFile:  `C:\Users\test\.okit\install.json`,
		MetadataError: os.ErrNotExist,
	}
	info := diagnose(state, strings.EqualFold)
	if info.PathStatus != "ok" || !info.InstallDirInPath {
		t.Fatalf("diagnosis=%+v", info)
	}
	if info.Executable != executable {
		t.Fatalf("diagnose changed executable path to %q", info.Executable)
	}
}

func TestCollectFailsWhenCorePathsCannotBeResolved(t *testing.T) {
	collector := testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return "", errors.New("injected executable failure") }
	})
	if _, err := collector.Collect(); err == nil || err.Error() != "resolve executable: injected executable failure" {
		t.Fatalf("error=%v", err)
	}

	collector = testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return filepath.Join(t.TempDir(), "okit"), nil }
		system.Home = func() (string, error) { return "", errors.New("injected home failure") }
	})
	if _, err := collector.Collect(); err == nil || err.Error() != "injected home failure" {
		t.Fatalf("error=%v", err)
	}
}

func testCollector(build Build, configure func(*collectorSystem)) Collector {
	system := nativeSystem()
	configure(&system)
	return Collector{Build: build, system: system}
}

func hasWarning(info Info, code string) bool {
	for _, warning := range info.Warnings {
		if warning.Code == code {
			return true
		}
	}
	return false
}
