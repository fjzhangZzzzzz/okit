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
	wantExecutable := mustCanonicalPath(t, executable)
	wantHome := mustCanonicalPath(t, home)
	if info.Version != "v2.0.0" || info.Platform != runtime.GOOS+"/"+runtime.GOARCH || info.Executable != wantExecutable || info.DataDir != wantHome {
		t.Fatalf("info=%+v", info)
	}
	if info.PathStatus != "shadowed" || !info.InstallDirInPath || !hasWarning(info, "PATH_SHADOWED") {
		t.Fatalf("path diagnosis=%+v", info)
	}
	if info.MetadataStatus != "ok" || info.InstallMethod != "official" || info.InstallChannel != "stable" || info.InstallVersion != "v2.0.0" {
		t.Fatalf("metadata=%+v", info)
	}
	if !info.ConfigExists || info.ConfigFile != filepath.Join(wantHome, "config.yaml") {
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

func TestCollectCanonicalizesEveryComparablePathBeforeDiagnosis(t *testing.T) {
	root := t.TempDir()
	rawExecutable := filepath.Join(root, "raw-current", "okit")
	rawResolved := filepath.Join(root, "raw-legacy", "okit")
	rawHome := filepath.Join(root, "raw-home")
	rawCurrentDir := filepath.Dir(rawExecutable)
	rawLegacyDir := filepath.Dir(rawResolved)
	canonicalExecutable := filepath.Join(root, "canonical-current", "okit")
	canonicalResolved := filepath.Join(root, "canonical-legacy", "okit")
	canonicalHome := filepath.Join(root, "canonical-home")
	canonicalCurrentDir := filepath.Dir(canonicalExecutable)
	canonicalLegacyDir := filepath.Dir(canonicalResolved)

	canonical := map[string]string{
		rawExecutable: rawExecutable,
		rawResolved:   rawResolved,
		rawHome:       rawHome,
		rawCurrentDir: rawCurrentDir,
		rawLegacyDir:  rawLegacyDir,
	}
	canonical[rawExecutable] = canonicalExecutable
	canonical[rawResolved] = canonicalResolved
	canonical[rawHome] = canonicalHome
	canonical[rawCurrentDir] = canonicalCurrentDir
	canonical[rawLegacyDir] = canonicalLegacyDir
	calls := make(map[string]int)

	collector := testCollector(Build{Version: "v2.0.0"}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return rawExecutable, nil }
		system.LookPath = func(string) (string, error) { return rawResolved, nil }
		system.Home = func() (string, error) { return rawHome, nil }
		system.Getenv = func(string) string {
			return rawLegacyDir + string(os.PathListSeparator) + rawCurrentDir
		}
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(home string) (selfmanage.Metadata, error) {
			if home != canonicalHome {
				t.Fatalf("LoadMetadata home = %q, want %q", home, canonicalHome)
			}
			return selfmanage.Metadata{Version: "v2.0.0", Executable: rawExecutable}, nil
		}
		system.Canonicalize = func(path string) (string, error) {
			calls[path]++
			return canonical[path], nil
		}
	})

	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if info.Executable != canonicalExecutable || info.Resolved != canonicalResolved || info.DataDir != canonicalHome {
		t.Fatalf("info=%+v", info)
	}
	if !info.InstallDirInPath || hasWarning(info, "METADATA_EXECUTABLE_MISMATCH") {
		t.Fatalf("diagnosis=%+v", info)
	}
	for _, path := range []string{rawExecutable, rawResolved, rawHome, rawCurrentDir, rawLegacyDir} {
		if calls[path] == 0 {
			t.Errorf("path was not canonicalized: %s", path)
		}
	}
}

func TestCollectPreservesUnresolvableMetadataPathForWarning(t *testing.T) {
	root := t.TempDir()
	executable := filepath.Join(root, "current", "okit")
	stale := filepath.Join(root, "missing", "okit")
	collector := testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.LookPath = func(string) (string, error) { return executable, nil }
		system.Home = func() (string, error) { return root, nil }
		system.Getenv = func(string) string { return filepath.Dir(executable) }
		system.Stat = func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }
		system.LoadMetadata = func(string) (selfmanage.Metadata, error) {
			return selfmanage.Metadata{Executable: stale}, nil
		}
		system.Canonicalize = func(path string) (string, error) {
			if path == stale {
				return "", errors.New("cannot canonicalize stale path")
			}
			return path, nil
		}
	})
	info, err := collector.Collect()
	if err != nil {
		t.Fatal(err)
	}
	if !hasWarning(info, "METADATA_EXECUTABLE_MISMATCH") {
		t.Fatalf("metadata diagnosis=%+v", info)
	}
	if got := warningMessage(info, "METADATA_EXECUTABLE_MISMATCH"); !strings.Contains(got, stale) {
		t.Fatalf("warning %q does not preserve raw metadata path %q", got, stale)
	}
}

func TestCanonicalPathBestEffortFallsBackWithoutGuessing(t *testing.T) {
	raw := filepath.Join("missing", "okit")
	canonical := canonicalPathBestEffort(func(string) (string, error) {
		return "", errors.New("cannot resolve")
	}, raw)
	if canonical != raw {
		t.Fatalf("canonical path = %q, want raw path %q", canonical, raw)
	}
}

func TestAbsolutePathKeepsNonexistentPathLexicallyNormalized(t *testing.T) {
	raw := filepath.Join(t.TempDir(), "missing", "..", "stale", "okit")
	want, err := filepath.Abs(filepath.Clean(raw))
	if err != nil {
		t.Fatal(err)
	}
	got, err := absolutePath(raw)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("absolutePath() = %q, want %q", got, want)
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

	executable := filepath.Join(t.TempDir(), "okit")
	collector = testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.Canonicalize = func(string) (string, error) { return "", errors.New("injected canonicalization failure") }
	})
	if _, err := collector.Collect(); err == nil || err.Error() != "resolve executable: injected canonicalization failure" {
		t.Fatalf("error=%v", err)
	}

	home := filepath.Join(t.TempDir(), ".okit")
	collector = testCollector(Build{}, func(system *collectorSystem) {
		system.Executable = func() (string, error) { return executable, nil }
		system.Home = func() (string, error) { return home, nil }
		system.Canonicalize = func(path string) (string, error) {
			if path == home {
				return "", errors.New("injected home canonicalization failure")
			}
			return path, nil
		}
	})
	if _, err := collector.Collect(); err == nil || err.Error() != "resolve data directory: injected home canonicalization failure" {
		t.Fatalf("error=%v", err)
	}
}

func testCollector(build Build, configure func(*collectorSystem)) Collector {
	system := nativeSystem()
	configure(&system)
	return Collector{Build: build, system: system}
}

func mustCanonicalPath(t *testing.T, path string) string {
	t.Helper()
	canonical, err := absolutePath(path)
	if err != nil {
		t.Fatal(err)
	}
	return canonical
}

func hasWarning(info Info, code string) bool {
	for _, warning := range info.Warnings {
		if warning.Code == code {
			return true
		}
	}
	return false
}

func warningMessage(info Info, code string) string {
	for _, warning := range info.Warnings {
		if warning.Code == code {
			return warning.Message
		}
	}
	return ""
}
