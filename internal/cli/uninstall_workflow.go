package cli

import (
	"bufio"
	"io"
	"path/filepath"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/installation"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
)

type uninstallWorkflow struct {
	runtime installationRuntime
	options installation.UninstallOptions
}

func (a *App) newUninstallWorkflow(options installation.UninstallOptions) uninstallWorkflow {
	return uninstallWorkflow{runtime: a.newInstallationRuntime(), options: options}
}
func (w uninstallWorkflow) Run(stdin io.Reader, presenter *clioutput.Presenter) (clioutput.View, error) {
	if w.options.Purge && !w.options.Yes && !w.options.DryRun {
		if err := presenter.Prompt("是否永久删除 OKIT_HOME 与全部用户数据？[y/N] "); err != nil {
			return clioutput.View{}, runError(err)
		}
		answer, _ := bufio.NewReader(stdin).ReadString('\n')
		if answer = strings.TrimSpace(strings.ToLower(answer)); answer != "y" && answer != "yes" {
			return clioutput.View{Human: clioutput.Document{Title: "已取消卸载", Summary: "未作任何更改。"}, Machine: map[string]any{"status": "cancelled", "changed": false}}, nil
		}
		w.options.Yes = true
	}
	uninstaller, err := w.runtime.uninstaller()
	if err != nil {
		return clioutput.View{}, runError(err)
	}
	result, err := uninstaller.Uninstall(w.options)
	if err != nil {
		return clioutput.View{}, runError(err)
	}
	items := make([]clioutput.PlanItem, 0, len(result.Plan))
	for _, target := range result.Plan {
		items = append(items, clioutput.PlanItem{Action: uninstallAction(w.options.DryRun, result.Scheduled), Resource: uninstallResource(target), Target: target})
	}
	title, summary := "okit 已成功卸载。", ""
	if result.Scheduled {
		title = "已计划卸载"
	} else if w.options.DryRun {
		title = "卸载计划"
		summary = "未作任何更改。"
	}
	return clioutput.View{Human: clioutput.Document{Title: title, Plan: items, Summary: summary}, Machine: map[string]any{"status": uninstallStatus(w.options.DryRun, result.Scheduled), "targets": result.Plan, "purge": w.options.Purge}}, nil
}
func uninstallAction(dryRun, scheduled bool) string {
	if dryRun {
		return "将删除"
	}
	if scheduled {
		return "计划删除"
	}
	return "已删除"
}
func uninstallResource(target string) string {
	if filepath.Base(target) == "install.json" {
		return "元数据"
	}
	if strings.HasSuffix(strings.ToLower(target), ".exe") || filepath.Base(target) == "okit" {
		return "可执行文件"
	}
	return "受管理资源"
}
func uninstallStatus(dryRun, scheduled bool) string {
	if dryRun {
		return "planned"
	}
	if scheduled {
		return "scheduled"
	}
	return "removed"
}
