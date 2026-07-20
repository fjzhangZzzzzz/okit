package cli

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/spf13/cobra"
)

func TestEveryLeafCommandDeclaresOutputFormats(t *testing.T) {
	root := New("dev").newRootCommand()
	var visit func(*cobra.Command)
	visit = func(command *cobra.Command) {
		if command.Hidden {
			return
		}
		children := command.Commands()
		if len(children) == 0 && command != root && command.Name() != "help" {
			if len(commandFormats(command)) == 0 || command.Annotations["formats"] == "" {
				t.Errorf("leaf command %q does not declare output formats", command.CommandPath())
			}
			return
		}
		for _, child := range children {
			visit(child)
		}
	}
	visit(root)
}

func TestHumanErrorsAcrossCommandFamiliesDoNotExposeDiagnosticProtocol(t *testing.T) {
	home := t.TempDir()
	t.Setenv("OKIT_HOME", home)
	missing := filepath.Join(home, "missing.bin")
	badPE := filepath.Join(home, "bad.exe")
	if err := os.WriteFile(badPE, []byte("not a PE"), 0o600); err != nil {
		t.Fatal(err)
	}

	cases := []struct {
		name string
		app  func() *App
		args []string
	}{
		{name: "unknown command", app: func() *App { return New("dev") }, args: []string{"unknown"}},
		{name: "missing argument", app: func() *App { return New("dev") }, args: []string{"shell", "status"}},
		{name: "hex file error", app: func() *App { return New("dev") }, args: []string{"hex", missing}},
		{name: "PE parse error", app: func() *App { return New("dev") }, args: []string{"pe", "inspect", badPE}},
		{name: "config key error", app: func() *App { return New("dev") }, args: []string{"git-sync", "config", "get", "host"}},
		{name: "MobaXterm argument error", app: func() *App { return New("dev") }, args: []string{"mobaxterm", "license", "inspect"}},
	}
	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			code := testCase.app().Run(testCase.args, &stdout, &stderr)
			if code == 0 || stderr.Len() == 0 {
				t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
			}
			for _, technical := range []string{"error:", "hint:", "CLI_", "SELF_", "HEX_", "PE_", "CONFIG_", "GITSYNC_", "MOBA_", "SHELL_"} {
				if strings.Contains(stderr.String(), technical) {
					t.Fatalf("human output leaked %q: %q", technical, stderr.String())
				}
			}
			if !strings.Contains(stderr.String(), "\n\n") {
				t.Fatalf("diagnostic does not separate problem and action: %q", stderr.String())
			}
		})
	}
}

func TestHelpShowsOnlyCommandFormats(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"self", "update", "--help"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "output format: table, json") || strings.Contains(stdout.String(), "table, json, csv") {
		t.Fatalf("help formats are not command-specific: %q", stdout.String())
	}
}

func TestGitSyncStatusHasExplicitEmptyStateAndJSON(t *testing.T) {
	t.Setenv("OKIT_HOME", t.TempDir())
	app := New("dev")
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"git-sync", "status"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "No git-sync configuration found") || !strings.Contains(stdout.String(), "config set") {
		t.Fatalf("empty state is not actionable: %q", stdout.String())
	}

	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"--format", "json", "git-sync", "status"}, &stdout, &stderr); code != 0 {
		t.Fatalf("json code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	var payload map[string]string
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil || len(payload) != 0 || stderr.Len() != 0 {
		t.Fatalf("payload=%v err=%v stderr=%q", payload, err, stderr.String())
	}
}

func TestConfigSetReportsMutation(t *testing.T) {
	t.Setenv("OKIT_HOME", t.TempDir())
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"shell", "config", "set", "repo-url", "https://example.invalid/config.git"}, &stdout, &stderr)
	if code != 0 || !strings.Contains(stdout.String(), "Configuration updated") || !strings.Contains(stdout.String(), "shell.repo-url") || stderr.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestQuietKeepsBusinessResult(t *testing.T) {
	t.Setenv("OKIT_HOME", t.TempDir())
	var stdout, stderr bytes.Buffer
	code := NewBuild("v2.0.0", "abc123", "2026-07-18").Run([]string{"--quiet", "info"}, &stdout, &stderr)
	if code != 0 || !strings.Contains(stdout.String(), "v2.0.0") || !strings.Contains(stdout.String(), "executable") {
		t.Fatalf("quiet discarded business result: code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestSelfUpdateCheckIsActionableAndStructured(t *testing.T) {
	updater := &fakeSelfUpdater{}
	app := New("v1.0.0")
	app.selfUpdater = updater
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"self", "update", "--check"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for _, want := range []string{"Update available", "v1.0.0", "v1.1.0", "okit self update"} {
		if !strings.Contains(stdout.String(), want) {
			t.Fatalf("output does not contain %q: %q", want, stdout.String())
		}
	}

	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"--format", "json", "self", "update", "--check"}, &stdout, &stderr); code != 0 {
		t.Fatalf("json code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	var payload map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &payload); err != nil || payload["update_available"] != true {
		t.Fatalf("payload=%v err=%v", payload, err)
	}
}

func TestSelfUpdateScheduledHumanOutputExplainsWhenItTakesEffect(t *testing.T) {
	updater := &fakeSelfUpdater{result: selfmanage.UpdateResult{Current: "v1.0.0", Available: "v1.1.0", Updated: true, Scheduled: true}}
	app := New("v1.0.0")
	app.selfUpdater = updater
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"self", "update"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "Update scheduled") || !strings.Contains(stdout.String(), "after the current process exits") {
		t.Fatalf("scheduled output is not actionable: %q", stdout.String())
	}
	if strings.Contains(stdout.String(), "scheduled: true") {
		t.Fatalf("human output leaked machine field: %q", stdout.String())
	}
}

func TestSelfUpdateDevelopmentBuildReturnsInformationalStatus(t *testing.T) {
	app := New("dev")
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "update", "--check"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 || !strings.Contains(stdout.String(), "development builds") || !strings.Contains(stdout.String(), "released version") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}

	stdout.Reset()
	stderr.Reset()
	code = app.Run([]string{"--format", "json", "self", "update", "--check"}, &stdout, &stderr)
	var status map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &status); code != 0 || err != nil || status["update_supported"] != false || status["reason"] != "development_build" || status["action"] == "" || stderr.Len() != 0 {
		t.Fatalf("json code=%d status=%v err=%v stderr=%q", code, status, err, stderr.String())
	}
}

func TestSelfUpdateLocalSemanticVersionStillUsesDevelopmentStatus(t *testing.T) {
	app := NewBuildMode("v1.2.3", "abc123", "2026-07-19", BuildModeDevelopment)
	app.selfUpdater = &fakeSelfUpdater{}
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "update", "--check"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 || !strings.Contains(stdout.String(), "development builds") || strings.Contains(stdout.String(), "Update available") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestInvalidReleaseMetadataIsDifferentFromDevelopmentBuild(t *testing.T) {
	app := NewBuildMode("broken", "abc123", "2026-07-19", BuildModeRelease)
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "update", "--check"}, &stdout, &stderr)
	if code != 1 || !strings.Contains(stderr.String(), "invalid version information") || !strings.Contains(stderr.String(), "Reinstall okit") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if strings.Contains(stderr.String(), "development build") || strings.Contains(stderr.String(), "SELF_VERSION_INVALID") {
		t.Fatalf("release diagnostic is not human-readable or was misclassified: %q", stderr.String())
	}
}

func TestJSONUsageErrorIsMachineReadable(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"--format", "json", "shell", "status"}, &stdout, &stderr)
	if code != 2 || stdout.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	var diagnostic map[string]any
	if err := json.Unmarshal(stderr.Bytes(), &diagnostic); err != nil || diagnostic["level"] != "error" || diagnostic["code"] != "CLI_USAGE" {
		t.Fatalf("diagnostic=%v err=%v stderr=%q", diagnostic, err, stderr.String())
	}
}

func TestGitSyncJSONLProducesOneObjectPerRepository(t *testing.T) {
	app := New("dev")
	app.gitSync = fakeGitSyncService{}
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"--format", "jsonl", "git-sync", "run", "one", "two", "--host", "dev", "--target-root", "/srv"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	lines := strings.Split(strings.TrimSpace(stdout.String()), "\n")
	if len(lines) != 2 {
		t.Fatalf("JSONL line count=%d output=%q", len(lines), stdout.String())
	}
	for _, line := range lines {
		var payload map[string]any
		if err := json.Unmarshal([]byte(line), &payload); err != nil {
			t.Fatalf("invalid JSONL line %q: %v", line, err)
		}
	}
}
