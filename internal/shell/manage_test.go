package shell

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type fakeCmdAutoRun struct {
	value string
	sets  int
}

func (f *fakeCmdAutoRun) Get() (string, error) { return f.value, nil }
func (f *fakeCmdAutoRun) Set(value string) error {
	f.value = value
	f.sets++
	return nil
}

func testManager(t *testing.T) *Manager {
	t.Helper()
	root := t.TempDir()
	return &Manager{
		OKITHome: filepath.Join(root, "okit"),
		UserHome: filepath.Join(root, "user"),
		GOOS:     "linux",
	}
}

func TestEnableDisableIdempotent_SHELL001(t *testing.T) {
	m := testManager(t)
	if err := os.MkdirAll(m.UserHome, 0o700); err != nil {
		t.Fatal(err)
	}
	profile := filepath.Join(m.UserHome, ".bashrc")
	if err := os.WriteFile(profile, []byte("# user\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 2; i++ {
		if _, err := m.Enable("bash", false); err != nil {
			t.Fatal(err)
		}
	}
	data, _ := os.ReadFile(profile)
	if strings.Count(string(data), beginMarker) != 1 {
		t.Fatalf("duplicate managed block: %s", data)
	}
	for i := 0; i < 2; i++ {
		if _, err := m.Disable("bash", false); err != nil {
			t.Fatal(err)
		}
	}
	data, _ = os.ReadFile(profile)
	if string(data) != "# user\n" {
		t.Fatalf("unexpected profile: %q", data)
	}
}

func TestAtomicFailureKeepsOriginal_SHELL002(t *testing.T) {
	m := testManager(t)
	if err := os.MkdirAll(m.UserHome, 0o700); err != nil {
		t.Fatal(err)
	}
	profile := filepath.Join(m.UserHome, ".zshrc")
	if err := os.WriteFile(profile, []byte("original\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	m.Replace = func(string, []byte, os.FileMode) error { return errors.New("injected failure") }
	if _, err := m.Enable("zsh", false); err == nil {
		t.Fatal("expected failure")
	}
	data, _ := os.ReadFile(profile)
	if string(data) != "original\n" {
		t.Fatalf("original changed: %q", data)
	}
}

func TestOnlyManagedBlockChanges_SHELL003(t *testing.T) {
	m := testManager(t)
	if err := os.MkdirAll(m.UserHome, 0o700); err != nil {
		t.Fatal(err)
	}
	profile := filepath.Join(m.UserHome, ".bashrc")
	original := "export KEEP=1\n# unrelated source\n"
	if err := os.WriteFile(profile, []byte(original), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := m.Enable("bash", false); err != nil {
		t.Fatal(err)
	}
	if _, err := m.Disable("bash", false); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(profile)
	if string(data) != original {
		t.Fatalf("user content changed: %q", data)
	}
}

func TestDryRunHasNoSideEffects_SHELL004(t *testing.T) {
	m := testManager(t)
	plan, err := m.Enable("bash", true)
	if err != nil || !strings.Contains(plan, "would enable") {
		t.Fatalf("plan=%q err=%v", plan, err)
	}
	if _, err := os.Stat(m.OKITHome); !os.IsNotExist(err) {
		t.Fatalf("OKIT_HOME created: %v", err)
	}
	if _, err := os.Stat(m.UserHome); !os.IsNotExist(err) {
		t.Fatalf("user home created: %v", err)
	}
}

func TestTestsUseIsolatedHomes_SHELL006(t *testing.T) {
	m := testManager(t)
	if m.OKITHome == "" || m.UserHome == "" || filepath.Dir(m.OKITHome) != filepath.Dir(m.UserHome) {
		t.Fatalf("test manager is not isolated: %+v", m)
	}
}

func TestSourcePathConversion_SHELL005(t *testing.T) {
	m := &Manager{OKITHome: `C:\Users\Alice\.okit`, UserHome: `C:\Users\Alice`, GOOS: "windows"}
	line, err := m.Source("bash")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(line, `/c/Users/Alice/.okit/`) || strings.Contains(line, `C:\`) {
		t.Fatalf("invalid Git Bash source line: %q", line)
	}
	m.PowerShellProfile = func() (string, error) { return `C:\Users\Alice\Documents\PowerShell\Profile.ps1`, nil }
	path, err := m.ProfilePath("powershell")
	if err != nil || !strings.HasSuffix(path, `Profile.ps1`) {
		t.Fatalf("path=%q err=%v", path, err)
	}
}

func TestCMDEnableDisableUsesAutoRunAndIsIdempotent_SHELL001(t *testing.T) {
	registry := &fakeCmdAutoRun{value: `echo user-startup`}
	root := t.TempDir()
	m := &Manager{OKITHome: filepath.Join(root, ".okit"), UserHome: root, GOOS: "windows", CmdAutoRun: registry}
	for range 2 {
		if _, err := m.Enable("cmd", false); err != nil {
			t.Fatal(err)
		}
	}
	source, _ := m.Source("cmd")
	if registry.sets != 1 || strings.Count(registry.value, source) != 1 || !strings.Contains(registry.value, "echo user-startup") {
		t.Fatalf("sets=%d value=%q", registry.sets, registry.value)
	}
	for range 2 {
		if _, err := m.Disable("cmd", false); err != nil {
			t.Fatal(err)
		}
	}
	if registry.sets != 2 || registry.value != `echo user-startup` {
		t.Fatalf("sets=%d value=%q", registry.sets, registry.value)
	}
}

func TestCMDDryRunDoesNotWriteAutoRun_SHELL004(t *testing.T) {
	registry := &fakeCmdAutoRun{}
	root := t.TempDir()
	m := &Manager{OKITHome: filepath.Join(root, ".okit"), UserHome: root, GOOS: "windows", CmdAutoRun: registry}
	if _, err := m.Enable("cmd", true); err != nil {
		t.Fatal(err)
	}
	if registry.sets != 0 {
		t.Fatalf("dry-run wrote registry %d times", registry.sets)
	}
}

func TestSyncUpdatesManagedCopy(t *testing.T) {
	m := testManager(t)
	repo := filepath.Join(m.OKITHome, "data", "shell", "repo")
	if err := os.MkdirAll(repo, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(repo, "bash"), []byte("export SYNCED=1\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	called := false
	m.RunGit = func(args ...string) error { called = true; return nil }
	if _, err := m.Sync("bash", "https://example.invalid/config.git", false); err != nil {
		t.Fatal(err)
	}
	if !called {
		t.Fatal("git pull was not called")
	}
	data, err := os.ReadFile(filepath.Join(m.OKITHome, "data", "shell", "bash.rc"))
	if err != nil || string(data) != "export SYNCED=1\n" {
		t.Fatalf("data=%q err=%v", data, err)
	}
}
