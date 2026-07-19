package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
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

type failingSelfUpdater struct{ err error }

func (f failingSelfUpdater) Update(context.Context, selfmanage.UpdateOptions) (selfmanage.UpdateResult, error) {
	return selfmanage.UpdateResult{}, f.err
}

func TestSelfUpdateDevelopmentVersionHasActionableDiagnostic(t *testing.T) {
	app := New("dev")
	app.selfUpdater = failingSelfUpdater{err: errors.New(`invalid semantic version "dev"`)}
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"self", "update", "--check"}, &stdout, &stderr)
	if code != 1 || stdout.Len() != 0 || !strings.Contains(stderr.String(), "SELF_VERSION_INVALID") || !strings.Contains(stderr.String(), "official release") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
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
