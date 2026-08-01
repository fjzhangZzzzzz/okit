package cli

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
	"github.com/spf13/cobra"
)

func TestRootHelpListsRetainedCommands(t *testing.T) {
	var stdout, stderr bytes.Buffer
	if code := New("v0.0.0-test").Run([]string{"--help"}, &stdout, &stderr); code != 0 || stderr.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for _, command := range []string{"mobaxterm", "upgrade", "uninstall"} {
		if !strings.Contains(stdout.String(), command) {
			t.Errorf("帮助中缺少 %q：%s", command, stdout.String())
		}
	}
}

func TestHelpUsesChineseCommonLabelsAndArgumentPlaceholders(t *testing.T) {
	for _, testCase := range []struct {
		name string
		args []string
		want []string
	}{
		{
			name: "root",
			args: []string{"--help"},
			want: []string{"用法:", "可用命令:", "选项:", "获取命令更多信息"},
		},
		{
			name: "command with positional argument",
			args: []string{"mobaxterm", "theme", "apply", "--help"},
			want: []string{"用法:", "选项:", "全局选项:", "apply <名称>", "应用 MobaXterm 主题"},
		},
	} {
		t.Run(testCase.name, func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			if code := New("dev").Run(testCase.args, &stdout, &stderr); code != 0 || stderr.Len() != 0 {
				t.Fatalf("args=%v code=%d stdout=%q stderr=%q", testCase.args, code, stdout.String(), stderr.String())
			}
			for _, want := range testCase.want {
				if !strings.Contains(stdout.String(), want) {
					t.Errorf("args=%v help lacks %q: %q", testCase.args, want, stdout.String())
				}
			}
		})
	}
}

func TestUsageErrorsUseChineseHumanGuidance(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("dev").Run([]string{"unknown"}, &stdout, &stderr)
	if code != 2 || stdout.Len() != 0 {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
	for _, want := range []string{"未知命令", "请运行 `okit --help` 查看可用的位置参数和选项。"} {
		if !strings.Contains(stderr.String(), want) {
			t.Errorf("usage error lacks %q: %q", want, stderr.String())
		}
	}
}

func TestEveryRetainedCommandHasContextualHelp(t *testing.T) {
	commands := [][]string{
		{"mobaxterm"}, {"mobaxterm", "status"}, {"mobaxterm", "theme"},
		{"mobaxterm", "theme", "list"}, {"mobaxterm", "theme", "apply"}, {"mobaxterm", "theme", "restore"},
		{"mobaxterm", "theme", "cache"}, {"mobaxterm", "theme", "cache", "update"},
		{"mobaxterm", "theme", "cache", "clean"}, {"mobaxterm", "theme", "cache", "status"},
		{"mobaxterm", "license"}, {"mobaxterm", "license", "generate"}, {"mobaxterm", "license", "deploy"},
		{"mobaxterm", "license", "inspect"}, {"mobaxterm", "license", "verify"},
		{"upgrade"}, {"uninstall"},
	}
	for _, command := range commands {
		command := command
		t.Run(strings.Join(command, "_"), func(t *testing.T) {
			var stdout, stderr bytes.Buffer
			args := append(append([]string{}, command...), "--help")
			if code := New("dev").Run(args, &stdout, &stderr); code != 0 || stderr.Len() != 0 {
				t.Fatalf("args=%v code=%d stdout=%q stderr=%q", args, code, stdout.String(), stderr.String())
			}
			if !strings.Contains(stdout.String(), "用法:") || !strings.Contains(stdout.String(), strings.Join(command, " ")) {
				t.Fatalf("args=%v help=%q", args, stdout.String())
			}
		})
	}
}

func TestPublicCommandHelpUsesChineseLabelsAndDescriptions(t *testing.T) {
	root := New("dev").newRootCommand()
	var verify func(*cobra.Command)
	verify = func(command *cobra.Command) {
		if command.Hidden || command.Name() == "help" {
			return
		}
		var stdout, stderr bytes.Buffer
		args := append(commandPathArguments(command), "--help")
		if code := New("dev").Run(args, &stdout, &stderr); code != 0 || stderr.Len() != 0 {
			t.Fatalf("args=%v code=%d stdout=%q stderr=%q", args, code, stdout.String(), stderr.String())
		}
		if !strings.Contains(stdout.String(), "用法:") || !containsChinese(command.Short) {
			t.Errorf("args=%v help or description is not Chinese: %q", args, stdout.String())
		}
		for _, english := range []string{"Usage:", "Available Commands:", "Flags:", "Global Flags:", "help for"} {
			if strings.Contains(stdout.String(), english) {
				t.Errorf("args=%v help contains untranslated text %q: %q", args, english, stdout.String())
			}
		}
		for _, child := range command.Commands() {
			verify(child)
		}
	}
	verify(root)
}

func commandPathArguments(command *cobra.Command) []string {
	path := strings.Fields(command.CommandPath())
	if len(path) > 0 && path[0] == "okit" {
		return path[1:]
	}
	return path
}

func TestRemovedTopLevelCommandsAreUsageErrors(t *testing.T) {
	for _, command := range []string{"info", "hex", "pe", "git-sync", "shell", "self", "config"} {
		var stdout, stderr bytes.Buffer
		code := New("dev").Run([]string{command}, &stdout, &stderr)
		if code != 2 || stdout.Len() != 0 || !strings.Contains(stderr.String(), "未知命令") {
			t.Errorf("command=%q code=%d stdout=%q stderr=%q", command, code, stdout.String(), stderr.String())
		}
	}
}

func TestUpgradeParsesDocumentedOptions(t *testing.T) {
	runner := &fakeUpgradeRunner{}
	app := New("v1.0.0")
	app.upgradeRunner = runner
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"upgrade", "--check", "--version", "v1.1.0", "--prerelease", "--dry-run"}, &stdout, &stderr)
	if code != 0 || runner.intent.Mode != installation.ModeDryRun || !runner.intent.IncludePrerelease || runner.intent.Version != "v1.1.0" {
		t.Fatalf("code=%d intent=%+v stdout=%q stderr=%q", code, runner.intent, stdout.String(), stderr.String())
	}
}

func TestUninstallRetainsSafetyOptions(t *testing.T) {
	uninstaller := &fakeSelfUninstaller{}
	app := New("v1.0.0")
	app.selfUninstaller = uninstaller
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"uninstall", "--purge", "--yes", "--dry-run"}, &stdout, &stderr)
	if code != 0 || !uninstaller.options.Purge || !uninstaller.options.Yes || !uninstaller.options.DryRun || !strings.Contains(stdout.String(), "卸载计划") || !strings.Contains(stdout.String(), "未作任何更改") {
		t.Fatalf("code=%d options=%+v stdout=%q stderr=%q", code, uninstaller.options, stdout.String(), stderr.String())
	}
}

func TestUninstallPurgeRequiresConfirmation(t *testing.T) {
	uninstaller := &fakeSelfUninstaller{}
	app := New("v1.0.0")
	app.selfUninstaller = uninstaller
	app.stdin = strings.NewReader("y\n")
	var stdout, stderr bytes.Buffer
	code := app.Run([]string{"uninstall", "--purge"}, &stdout, &stderr)
	if code != 0 || !uninstaller.options.Yes || !strings.Contains(stderr.String(), "永久删除") || !strings.Contains(stdout.String(), "已成功卸载") {
		t.Fatalf("code=%d options=%+v stdout=%q stderr=%q", code, uninstaller.options, stdout.String(), stderr.String())
	}
}

func TestVersion(t *testing.T) {
	var stdout, stderr bytes.Buffer
	code := New("v1.2.3").Run([]string{"--version"}, &stdout, &stderr)
	if code != 0 || strings.TrimSpace(stdout.String()) != "okit v1.2.3" {
		t.Fatalf("code=%d stdout=%q stderr=%q", code, stdout.String(), stderr.String())
	}
}

type fakeUpgradeRunner struct {
	intent installation.Intent
	result installation.Result
}

func (f *fakeUpgradeRunner) Run(_ context.Context, intent installation.Intent, _ installation.ProgressReporter) (installation.Result, error) {
	f.intent = intent
	if f.result.Available != "" {
		return f.result, nil
	}
	return installation.Result{Status: installation.StatusAvailable, Current: "v1.0.0", Available: "v1.1.0", Plan: "would update v1.0.0 to v1.1.0"}, nil
}

type fakeSelfUninstaller struct{ options installation.UninstallOptions }

func (f *fakeSelfUninstaller) Uninstall(options installation.UninstallOptions) (installation.UninstallResult, error) {
	f.options = options
	return installation.UninstallResult{Plan: []string{"okit", "install.json"}}, nil
}
