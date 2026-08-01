package cli

import (
	"context"
	"errors"
	"io"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
)

type upgradeOptions struct {
	check, dryRun, prerelease bool
	version                   string
}

// upgradeWorkflow 将用户的更新意图转换为稳定的升级结果。
// 它是 CLI 装配生命周期、选择进度 adapter 与生成输出的 seam。
type upgradeWorkflow struct {
	app      *App
	options  upgradeOptions
	format   string
	terminal bool
	stderr   io.Writer
}

type upgradeStatus string

const (
	upgradeStatusUpToDate            upgradeStatus = "up_to_date"
	upgradeStatusAvailable           upgradeStatus = "available"
	upgradeStatusPlanned             upgradeStatus = "planned"
	upgradeStatusApplied             upgradeStatus = "applied"
	upgradeStatusScheduled           upgradeStatus = "scheduled"
	upgradeStatusUnsupported         upgradeStatus = "unsupported"
	upgradeStatusInvalidInstallation upgradeStatus = "invalid_installation"
)

type upgradeNextAction struct {
	Kind    string   `json:"kind"`
	Command []string `json:"command,omitempty"`
}

type upgradeResult struct {
	Mode       string             `json:"mode"`
	Status     upgradeStatus      `json:"status"`
	Current    string             `json:"current,omitempty"`
	Target     string             `json:"target,omitempty"`
	Plan       string             `json:"plan,omitempty"`
	NextAction *upgradeNextAction `json:"next_action,omitempty"`
}

func (a *App) newUpgradeWorkflow(options upgradeOptions, format string, terminal bool, stderr io.Writer) upgradeWorkflow {
	return upgradeWorkflow{app: a, options: options, format: format, terminal: terminal, stderr: stderr}
}

func (w upgradeWorkflow) Run(ctx context.Context) (upgradeResult, error) {
	result := upgradeResult{Mode: w.mode()}
	if w.app.buildMode == BuildModeDevelopment {
		result.Status = upgradeStatusUnsupported
		result.NextAction = &upgradeNextAction{Kind: "install_released_build"}
		return result, nil
	}
	if installation.ValidateVersion(w.app.version) != nil {
		result.Status = upgradeStatusInvalidInstallation
		result.Current = w.app.version
		result.NextAction = &upgradeNextAction{Kind: "reinstall_released_build"}
		return result, nil
	}

	runner, err := w.runner()
	if err != nil {
		return upgradeResult{}, runError(err)
	}
	var progress installation.ProgressReporter
	if w.format != "json" && w.mode() == "apply" && w.terminal {
		progress = &terminalUpdateProgress{writer: w.stderr}
	}
	lifecycleResult, err := runner.Run(ctx, installation.Intent{
		Mode:              w.lifecycleMode(),
		Version:           w.options.version,
		IncludePrerelease: w.options.prerelease,
	}, progress)
	if err != nil {
		var failure *installation.Failure
		if errors.As(err, &failure) && failure.Kind == installation.FailureReleaseAccessDenied {
			return upgradeResult{}, domainError("SELF_RELEASE_ACCESS_DENIED", "发布服务拒绝了更新请求。", "请稍后重试；若触发服务限流，请配置 GH_TOKEN 或 GITHUB_TOKEN。")
		}
		return upgradeResult{}, runError(err)
	}
	return w.fromLifecycle(lifecycleResult), nil
}

func (w upgradeWorkflow) runner() (upgradeRunner, error) {
	return w.app.newInstallationRuntime().upgradeRunner(w.options)
}

func (w upgradeWorkflow) mode() string {
	if w.options.dryRun {
		return "dry_run"
	}
	if w.options.check {
		return "check"
	}
	return "apply"
}

func (w upgradeWorkflow) lifecycleMode() installation.Mode {
	switch w.mode() {
	case "dry_run":
		return installation.ModeDryRun
	case "check":
		return installation.ModeCheck
	default:
		return installation.ModeApply
	}
}

func (w upgradeWorkflow) fromLifecycle(lifecycle installation.Result) upgradeResult {
	result := upgradeResult{Mode: w.mode(), Current: lifecycle.Current, Target: lifecycle.Available, Plan: lifecycle.Plan}
	available := lifecycle.Available != "" && lifecycle.Available != lifecycle.Current
	switch {
	case !available:
		result.Status = upgradeStatusUpToDate
	case w.options.dryRun:
		result.Status = upgradeStatusPlanned
	case w.options.check:
		result.Status = upgradeStatusAvailable
		result.NextAction = &upgradeNextAction{Kind: "run_upgrade", Command: []string{"okit", "upgrade"}}
	case lifecycle.Scheduled:
		result.Status = upgradeStatusScheduled
	case lifecycle.Updated:
		result.Status = upgradeStatusApplied
	default:
		result.Status = upgradeStatusAvailable
	}
	return result
}

func (result upgradeResult) View() clioutput.View {
	return clioutput.View{Human: result.document(), Machine: upgradeMachineResult{
		SchemaVersion: 1, Mode: result.Mode, Status: result.Status, Current: result.Current,
		Target: result.Target, Plan: result.Plan, NextAction: result.NextAction,
	}}
}

type upgradeMachineResult struct {
	SchemaVersion int                `json:"schema_version"`
	Mode          string             `json:"mode"`
	Status        upgradeStatus      `json:"status"`
	Current       string             `json:"current,omitempty"`
	Target        string             `json:"target,omitempty"`
	Plan          string             `json:"plan,omitempty"`
	NextAction    *upgradeNextAction `json:"next_action,omitempty"`
}

func (result upgradeResult) document() clioutput.Document {
	document := clioutput.Document{}
	switch result.Status {
	case upgradeStatusUnsupported:
		document.Title, document.Hint = "开发构建不支持检查更新。", "请安装已发布的 okit 版本后重试。"
	case upgradeStatusInvalidInstallation:
		document.Title, document.Hint = "此 okit 安装的版本信息无效。", "请从正式发布版本重新安装 okit。"
	case upgradeStatusUpToDate:
		document.Title = "okit 已是最新版本。"
	case upgradeStatusAvailable:
		document.Title, document.Hint = "有可用更新", "运行 `okit upgrade` 安装。"
	case upgradeStatusPlanned:
		document.Title, document.Summary = "更新计划", "未作任何更改。"
	case upgradeStatusScheduled:
		document.Title, document.Hint = "已计划更新", "当前进程退出后，新版本将生效。"
	case upgradeStatusApplied:
		document.Title = "okit 更新成功。"
	}
	if result.Current != "" && (result.Status == upgradeStatusUpToDate || result.Status == upgradeStatusAvailable || result.Status == upgradeStatusPlanned) {
		document.Fields = []clioutput.Field{{Label: "当前版本", Value: result.Current}, {Label: "目标版本", Value: result.Target}}
	} else if result.Target != "" && (result.Status == upgradeStatusApplied || result.Status == upgradeStatusScheduled) {
		document.Fields = []clioutput.Field{{Label: "目标版本", Value: result.Target}}
	}
	if result.Status == upgradeStatusPlanned && result.Plan != "" {
		document.Lines = []string{updatePlanSummary(result.Current, result.Target)}
	}
	return document
}

func updatePlanSummary(current, target string) string {
	if target == "" || target == current {
		return "当前已是最新版本。"
	}
	return "将从 " + current + " 更新到 " + target + "。"
}
