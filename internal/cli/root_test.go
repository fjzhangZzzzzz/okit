package cli

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
)

func TestRootHelpListsDocumentedCommands(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("v0.0.0-test").Run([]string{"--help"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("exit code = %d, stderr = %q", code, stderr.String())
	}
	for _, command := range []string{"info", "hex", "pe", "git-sync", "shell", "mobaxterm", "self"} {
		if !strings.Contains(stdout.String(), command) {
			t.Errorf("help does not contain %q: %s", command, stdout.String())
		}
	}
}

func TestInfoTextAndJSON_INFO006(t *testing.T) {
	home := t.TempDir()
	t.Setenv("OKIT_HOME", home)
	if err := os.WriteFile(filepath.Join(home, "config.yaml"), []byte("token: supersecret\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	app := NewBuild("v2.0.0", "abc123", "2026-07-18")
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"info"}, &stdout, &stderr); code != 0 {
		t.Fatalf("text code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for _, value := range []string{"version", "v2.0.0", "executable", "data-dir", "path-status", "metadata-status"} {
		if !strings.Contains(stdout.String(), value) {
			t.Errorf("text output does not contain %q: %s", value, stdout.String())
		}
	}
	if strings.Contains(stdout.String(), "supersecret") || strings.Contains(stderr.String(), "supersecret") {
		t.Fatal("info leaked configuration content")
	}

	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"info", "--format", "json"}, &stdout, &stderr); code != 0 {
		t.Fatalf("json code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	var payload map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil {
		t.Fatalf("invalid JSON: %v: %s", err, stdout.String())
	}
	if payload["version"] != "v2.0.0" || payload["commit"] != "abc123" || payload["built"] != "2026-07-18" {
		t.Fatalf("payload=%v", payload)
	}
	if _, ok := payload["warnings"].([]any); !ok || stderr.Len() != 0 {
		t.Fatalf("warnings=%T stderr=%q", payload["warnings"], stderr.String())
	}

	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"--format", "json", "info"}, &stdout, &stderr); code != 0 || json.Unmarshal(stdout.Bytes(), &payload) != nil {
		t.Fatalf("global format code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestInfoRejectsCSVFormat(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"info", "--format", "csv"}, &stdout, &stderr)
	if code != 2 || !strings.Contains(stderr.String(), "not supported") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestHexPartialFailure_HEX006(t *testing.T) {
	good := filepath.Join(t.TempDir(), "good.bin")
	if err := os.WriteFile(good, []byte("ok"), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"hex", good, filepath.Join(t.TempDir(), "missing.bin")}, &stdout, &stderr)
	if code != 3 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "6f 6b") || !strings.Contains(stderr.String(), "missing.bin") {
		t.Fatalf("stdout=%q stderr=%q", stdout.String(), stderr.String())
	}
}

func TestPEPartialFailure_PE004(t *testing.T) {
	good := filepath.Join(t.TempDir(), "good.exe")
	bad := filepath.Join(t.TempDir(), "bad.exe")
	if err := os.WriteFile(good, minimalPE32(), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(bad, []byte("not a PE"), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"pe", "inspect", good, bad, "--format", "json"}, &stdout, &stderr)
	if code != 3 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "machine") || !strings.Contains(stderr.String(), "bad.exe") {
		t.Fatalf("stdout=%q stderr=%q", stdout.String(), stderr.String())
	}
}

func minimalPE32() []byte {
	const optionalSize = 224
	data := make([]byte, 0x80+4+20+optionalSize+40+16)
	data[0], data[1] = 'M', 'Z'
	binary.LittleEndian.PutUint32(data[0x3c:], 0x80)
	offset := 0x80
	copy(data[offset:], []byte{'P', 'E', 0, 0})
	offset += 4
	binary.LittleEndian.PutUint16(data[offset:], 0x14c)
	binary.LittleEndian.PutUint16(data[offset+2:], 1)
	binary.LittleEndian.PutUint16(data[offset+16:], optionalSize)
	binary.LittleEndian.PutUint16(data[offset+18:], 2)
	offset += 20
	binary.LittleEndian.PutUint16(data[offset:], 0x10b)
	binary.LittleEndian.PutUint32(data[offset+16:], 0x1000)
	binary.LittleEndian.PutUint32(data[offset+28:], 0x400000)
	binary.LittleEndian.PutUint32(data[offset+32:], 0x1000)
	binary.LittleEndian.PutUint32(data[offset+36:], 0x200)
	binary.LittleEndian.PutUint32(data[offset+56:], 0x2000)
	binary.LittleEndian.PutUint32(data[offset+60:], 0x200)
	binary.LittleEndian.PutUint32(data[offset+92:], 16)
	offset += optionalSize
	copy(data[offset:], []byte(".text\x00\x00\x00"))
	binary.LittleEndian.PutUint32(data[offset+8:], 16)
	binary.LittleEndian.PutUint32(data[offset+12:], 0x1000)
	binary.LittleEndian.PutUint32(data[offset+16:], 16)
	binary.LittleEndian.PutUint32(data[offset+20:], uint32(offset+40))
	binary.LittleEndian.PutUint32(data[offset+36:], 0x60000020)
	return data
}

type fakeGitSyncService struct{}

func (fakeGitSyncService) Run(_ context.Context, paths []string, _ gitsync.Options) []gitsync.Result {
	results := make([]gitsync.Result, 0, len(paths))
	for _, path := range paths {
		result := gitsync.Result{Plan: gitsync.Plan{Root: path, Repository: filepath.Base(path)}}
		if strings.Contains(path, "bad") {
			result.Err = os.ErrNotExist
		}
		results = append(results, result)
	}
	return results
}

type capturingGitSyncService struct {
	options gitsync.Options
}

func (f *capturingGitSyncService) Run(_ context.Context, paths []string, options gitsync.Options) []gitsync.Result {
	f.options = options
	return []gitsync.Result{{Plan: gitsync.Plan{Root: paths[0]}}}
}

func TestGitSyncPartialFailure_GITSYNC006(t *testing.T) {
	app := New("dev")
	app.gitSync = fakeGitSyncService{}
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"git-sync", "run", "good", "bad", "--host", "dev", "--target-root", "/srv"}, &stdout, &stderr)
	if code != 3 || !strings.Contains(stdout.String(), "good") || !strings.Contains(stderr.String(), "bad") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestGitSyncRunUsesFeatureConfiguration(t *testing.T) {
	t.Setenv("OKIT_HOME", t.TempDir())
	service := &capturingGitSyncService{}
	app := New("dev")
	app.gitSync = service
	var stdout, stderr bytes.Buffer
	for _, args := range [][]string{
		{"git-sync", "config", "set", "host", "devbox"},
		{"git-sync", "config", "set", "target-root", "/srv/src"},
	} {
		if code := app.Run(args, &stdout, &stderr); code != 0 {
			t.Fatalf("args=%v code=%d stderr=%q", args, code, stderr.String())
		}
	}
	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"git-sync", "run", "."}, &stdout, &stderr); code != 0 {
		t.Fatalf("run code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if service.options.Host != "devbox" || service.options.TargetRoot != "/srv/src" {
		t.Fatalf("options=%+v", service.options)
	}
}

func TestVersion(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("v1.2.3").Run([]string{"--version"}, &stdout, &stderr)
	if code != 0 || strings.TrimSpace(stdout.String()) != "okit v1.2.3" {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestUnknownCommandIsUsageError(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"unknown"}, &stdout, &stderr)
	if code != 2 {
		t.Fatalf("exit code = %d, want 2", code)
	}
	if stdout.Len() != 0 || !strings.Contains(stderr.String(), "unknown command") {
		t.Fatalf("stdout=%q stderr=%q", stdout.String(), stderr.String())
	}
}

func TestGlobalOptionsAreParsedBeforeCommand(t *testing.T) {
	file := filepath.Join(t.TempDir(), "sample.exe")
	if err := os.WriteFile(file, minimalPE32(), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"--no-color", "--format", "json", "pe", "inspect", file}, &stdout, &stderr)
	if code != 0 || !strings.HasPrefix(strings.TrimSpace(stdout.String()), "[") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestQuietAndVerboseAreMutuallyExclusive(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"--quiet", "--verbose", "hex", "ignored"}, &stdout, &stderr)
	if code != 2 || !strings.Contains(stderr.String(), "mutually exclusive") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestFeatureConfigKeysAreConsistentlyNamespaced(t *testing.T) {
	t.Setenv("OKIT_HOME", t.TempDir())
	app := New("dev")
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"shell", "config", "set", "repo-url", "https://example.invalid/config.git"}, &stdout, &stderr); code != 0 {
		t.Fatalf("set code=%d stderr=%q", code, stderr.String())
	}
	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"shell", "config", "get", "repo-url"}, &stdout, &stderr); code != 0 || strings.TrimSpace(stdout.String()) != "https://example.invalid/config.git" {
		t.Fatalf("get code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

type fakeSelfUpdater struct {
	options selfmanage.UpdateOptions
}

func (f *fakeSelfUpdater) Update(_ context.Context, options selfmanage.UpdateOptions) (selfmanage.UpdateResult, error) {
	f.options = options
	return selfmanage.UpdateResult{Current: "v1.0.0", Available: "v1.1.0", Plan: "would update v1.0.0 to v1.1.0"}, nil
}

type fakeSelfUninstaller struct {
	options selfmanage.UninstallOptions
}

func (f *fakeSelfUninstaller) Uninstall(options selfmanage.UninstallOptions) (selfmanage.UninstallResult, error) {
	f.options = options
	return selfmanage.UninstallResult{Plan: []string{"okit", "install.json"}}, nil
}

func TestSelfUpdateParsesDocumentedOptions(t *testing.T) {
	updater := &fakeSelfUpdater{}
	app := New("v1.0.0")
	app.selfUpdater = updater
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "update", "--check", "--version", "v1.1.0", "--prerelease", "--dry-run"}, &stdout, &stderr)
	if code != 0 || !updater.options.Check || !updater.options.DryRun || !updater.options.Prerelease || updater.options.Version != "v1.1.0" {
		t.Fatalf("code=%d options=%+v stdout=%q stderr=%q", code, updater.options, stdout.String(), stderr.String())
	}
}

func TestSelfUninstallParsesDocumentedOptions(t *testing.T) {
	uninstaller := &fakeSelfUninstaller{}
	app := New("v1.0.0")
	app.selfUninstaller = uninstaller
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "uninstall", "--purge", "--yes", "--dry-run"}, &stdout, &stderr)
	if code != 0 || !uninstaller.options.Purge || !uninstaller.options.Yes || !uninstaller.options.DryRun {
		t.Fatalf("code=%d options=%+v stdout=%q stderr=%q", code, uninstaller.options, stdout.String(), stderr.String())
	}
}

func TestSelfPurgeRequiresInteractiveConfirmation(t *testing.T) {
	uninstaller := &fakeSelfUninstaller{}
	app := New("v1.0.0")
	app.selfUninstaller = uninstaller
	app.stdin = strings.NewReader("y\n")
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "uninstall", "--purge"}, &stdout, &stderr)
	if code != 0 || !uninstaller.options.Yes || !strings.Contains(stderr.String(), "Permanently") {
		t.Fatalf("code=%d options=%+v stdout=%q stderr=%q", code, uninstaller.options, stdout.String(), stderr.String())
	}
}
