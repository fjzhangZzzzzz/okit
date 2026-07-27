package cli

import (
	"bytes"
	"encoding/json"
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
	cases := []struct {
		name string
		app  func() *App
		args []string
	}{
		{name: "unknown command", app: func() *App { return New("dev") }, args: []string{"unknown"}},
		{name: "卸载参数错误", app: func() *App { return New("dev") }, args: []string{"uninstall", "unexpected"}},
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
	code := New("dev").Run([]string{"upgrade", "--help"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "输出格式：table, json") || strings.Contains(stdout.String(), "table, json, csv") {
		t.Fatalf("help formats are not command-specific: %q", stdout.String())
	}
}

func TestSelfUpdateCheckIsActionableAndStructured(t *testing.T) {
	updater := &fakeSelfUpdater{}
	app := New("v1.0.0")
	app.selfUpdater = updater
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"upgrade", "--check"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for _, want := range []string{"有可用更新", "v1.0.0", "v1.1.0", "okit upgrade"} {
		if !strings.Contains(stdout.String(), want) {
			t.Fatalf("output does not contain %q: %q", want, stdout.String())
		}
	}

	stdout.Reset()
	stderr.Reset()
	if code := app.Run([]string{"--format", "json", "upgrade", "--check"}, &stdout, &stderr); code != 0 {
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
	if code := app.Run([]string{"upgrade"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "已计划更新") || !strings.Contains(stdout.String(), "当前进程退出后") {
		t.Fatalf("scheduled output is not actionable: %q", stdout.String())
	}
	if strings.Contains(stdout.String(), "scheduled: true") {
		t.Fatalf("human output leaked machine field: %q", stdout.String())
	}
	if strings.Contains(stdout.String(), "当前版本:") || strings.Contains(stdout.String(), "可用版本:") {
		t.Fatalf("scheduled output exposed check-only fields: %q", stdout.String())
	}
}

func TestSelfUpdateAppliedHumanOutputShowsTargetOnly(t *testing.T) {
	updater := &fakeSelfUpdater{result: selfmanage.UpdateResult{Current: "v1.0.0", Available: "v1.1.0", Updated: true}}
	app := New("v1.0.0")
	app.selfUpdater = updater
	var stdout, stderr bytes.Buffer
	if code := app.Run([]string{"upgrade"}, &stdout, &stderr); code != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if !strings.Contains(stdout.String(), "已更新至:") || !strings.Contains(stdout.String(), "v1.1.0") {
		t.Fatalf("applied output does not identify target: %q", stdout.String())
	}
	if strings.Contains(stdout.String(), "当前版本:") || strings.Contains(stdout.String(), "可用版本:") {
		t.Fatalf("applied output exposed check-only fields: %q", stdout.String())
	}
}

func TestSelfUpdateDevelopmentBuildReturnsInformationalStatus(t *testing.T) {
	app := New("dev")
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"upgrade", "--check"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 || !strings.Contains(stdout.String(), "开发构建") || !strings.Contains(stdout.String(), "已发布") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}

	stdout.Reset()
	stderr.Reset()
	code = app.Run([]string{"--format", "json", "upgrade", "--check"}, &stdout, &stderr)
	var status map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &status); code != 0 || err != nil || status["update_supported"] != false || status["reason"] != "development_build" || status["action"] == "" || stderr.Len() != 0 {
		t.Fatalf("json code=%d status=%v err=%v stderr=%q", code, status, err, stderr.String())
	}
}

func TestSelfUpdateLocalSemanticVersionStillUsesDevelopmentStatus(t *testing.T) {
	app := NewBuildMode("v1.2.3", "abc123", "2026-07-19", BuildModeDevelopment)
	app.selfUpdater = &fakeSelfUpdater{}
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"upgrade", "--check"}, &stdout, &stderr)
	if code != 0 || stderr.Len() != 0 || !strings.Contains(stdout.String(), "开发构建") || strings.Contains(stdout.String(), "有可用更新") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

func TestInvalidReleaseMetadataIsDifferentFromDevelopmentBuild(t *testing.T) {
	app := NewBuildMode("broken", "abc123", "2026-07-19", BuildModeRelease)
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"upgrade", "--check"}, &stdout, &stderr)
	if code != 1 || !strings.Contains(stderr.String(), "版本信息无效") || !strings.Contains(stderr.String(), "重新安装 okit") {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	if strings.Contains(stderr.String(), "development build") || strings.Contains(stderr.String(), "SELF_VERSION_INVALID") {
		t.Fatalf("release diagnostic is not human-readable or was misclassified: %q", stderr.String())
	}
}

func TestJSONUsageErrorIsMachineReadable(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"--format", "json", "uninstall", "unexpected"}, &stdout, &stderr)
	if code != 2 || stdout.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	var diagnostic map[string]any
	if err := json.Unmarshal(stderr.Bytes(), &diagnostic); err != nil || diagnostic["level"] != "error" || diagnostic["code"] != "CLI_USAGE" {
		t.Fatalf("diagnostic=%v err=%v stderr=%q", diagnostic, err, stderr.String())
	}
}
