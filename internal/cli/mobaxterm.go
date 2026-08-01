package cli

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/theme"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func newMobaXtermCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("mobaxterm", "管理 MobaXterm")
	command.AddCommand(newMobaStatusCommand(global), newMobaThemeCommand(global), newMobaLicenseCommand(global))
	return command
}

func mobaContext() (mobaxterm.Service, string, error) {
	if runtime.GOOS != "windows" {
		return mobaxterm.Service{}, "", usageError("MobaXterm 仅支持 Windows")
	}
	home, err := config.Home()
	if err != nil {
		return mobaxterm.Service{}, "", runError(err)
	}
	return mobaxterm.Service{GOOS: runtime.GOOS, OKITHome: home}, home, nil
}

func newMobaStatusCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use:         "status",
		Short:       "显示已检测到的 MobaXterm 安装",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			candidates, err := service.Status()
			if err != nil {
				return runError(err)
			}
			document := mobaStatusDocument(candidates)
			return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: candidates})
		},
	}
}

func mobaStatusDocument(candidates []mobaxterm.Candidate) clioutput.Document {
	document := clioutput.Document{Title: "已检测到的 MobaXterm 安装"}
	if len(candidates) == 0 {
		document.Title = ""
		document.Empty = &clioutput.EmptyState{Message: "未找到 MobaXterm 安装。"}
		return document
	}
	table := &clioutput.Table{Headers: []string{"默认", "版本", "来源", "可执行文件", "配置文件"}}
	for _, candidate := range candidates {
		table.Rows = append(table.Rows, []string{boolText(candidate.Default), candidate.Version, candidate.Source, candidate.ExePath, candidate.ConfigPath})
	}
	document.Table = table
	return document
}

func newMobaThemeCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("theme", "管理 MobaXterm 终端主题")
	command.AddCommand(newMobaThemeListCommand(global), newMobaThemeApplyCommand(global), newMobaThemeRestoreCommand(global), newMobaThemeCacheCommand(global))
	return command
}

func newMobaThemeListCommand(global *globalOptions) *cobra.Command {
	search, limit := "", 20
	command := &cobra.Command{
		Use:         "list",
		Short:       "列出已缓存的 MobaXterm 主题",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			_, home, err := mobaContext()
			if err != nil {
				return err
			}
			if limit < 1 {
				return usageError("--limit 必须大于零")
			}
			schemes, err := theme.List(mobaThemeCache(home), search, limit)
			if err != nil {
				if errors.Is(err, os.ErrNotExist) {
					return newPresenter(cmd, global).Render(clioutput.View{
						Human: clioutput.Document{Empty: &clioutput.EmptyState{
							Message: "未找到缓存的 MobaXterm 主题。",
							Hint:    "请运行 `okit mobaxterm theme cache update` 初始化缓存。",
						}},
						Machine: []string{},
					})
				}
				return runError(err)
			}
			document := clioutput.Document{Title: "已缓存的 MobaXterm 主题"}
			if len(schemes) == 0 {
				document.Title = ""
				document.Empty = &clioutput.EmptyState{Message: "没有主题匹配当前筛选条件。", Hint: "请尝试其他 --search 值。"}
			} else {
				table := &clioutput.Table{Headers: []string{"主题"}}
				for _, scheme := range schemes {
					table.Rows = append(table.Rows, []string{scheme})
				}
				document.Table = table
			}
			return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: schemes})
		},
	}
	command.Flags().StringVar(&search, "search", "", "按名称筛选主题")
	command.Flags().IntVar(&limit, "limit", 20, "主题数量上限")
	return command
}

func newMobaThemeApplyCommand(global *globalOptions) *cobra.Command {
	var noBackup, force, dryRun bool
	command := &cobra.Command{
		Use:         "apply <名称>",
		Short:       "应用 MobaXterm 主题",
		Args:        cobra.ExactArgs(1),
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			service, home, err := mobaContext()
			if err != nil {
				return err
			}
			scheme, err := theme.Resolve(mobaThemeCache(home), args[0])
			if err != nil {
				return runError(err)
			}
			candidates, err := service.Status()
			if err != nil || len(candidates) == 0 {
				return runError(fmt.Errorf("MobaXterm installation was not found"))
			}
			presenter := newPresenter(cmd, global)
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), presenter, mobaThemeApplyPrompt()) {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消应用主题", Summary: "未作任何更改。"}, Machine: map[string]any{"status": "cancelled", "changed": false}})
			}
			var result theme.Result
			if noBackup {
				result, err = theme.ApplyWithoutBackup(candidates[0].ConfigPath, scheme, dryRun, nil)
			} else {
				result, err = theme.Apply(candidates[0].ConfigPath, scheme, mobaThemeBackups(home), dryRun, nil)
			}
			if err != nil {
				return runError(err)
			}
			title := "已应用 MobaXterm 主题"
			summary := ""
			if dryRun {
				title = "MobaXterm 主题应用计划"
				summary = "未作任何更改。"
			} else if !result.Changed {
				title = "MobaXterm 主题未发生变化。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "主题", Value: args[0]}, {Label: "配置文件", Value: candidates[0].ConfigPath}, {Label: "备份", Value: result.BackupPath}}, Summary: summary},
				Machine: map[string]any{"status": themeStatus(dryRun, result.Changed), "theme": args[0], "config_path": candidates[0].ConfigPath, "backup_path": result.BackupPath, "changed": result.Changed},
			})
		},
	}
	command.Flags().BoolVar(&noBackup, "no-backup", false, "不创建配置备份")
	command.Flags().BoolVar(&force, "force", false, "跳过交互确认")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "显示计划但不修改文件")
	return command
}

func newMobaThemeRestoreCommand(global *globalOptions) *cobra.Command {
	backup := ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:         "restore",
		Short:       "还原 MobaXterm 配置备份",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, home, err := mobaContext()
			if err != nil {
				return err
			}
			selected := backup
			if selected == "" {
				selected, err = theme.LatestBackup(mobaThemeBackups(home))
				if err != nil {
					return runError(err)
				}
			}
			candidates, err := service.Status()
			if err != nil || len(candidates) == 0 {
				return runError(fmt.Errorf("MobaXterm installation was not found"))
			}
			presenter := newPresenter(cmd, global)
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), presenter, mobaThemeRestorePrompt()) {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消还原主题", Summary: "未作任何更改。"}, Machine: map[string]any{"status": "cancelled", "changed": false}})
			}
			if err := theme.Restore(candidates[0].ConfigPath, selected, dryRun); err != nil {
				return runError(err)
			}
			title := "已还原 MobaXterm 配置"
			summary := ""
			if dryRun {
				title = "MobaXterm 配置还原计划"
				summary = "未作任何更改。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "备份", Value: selected}, {Label: "配置文件", Value: candidates[0].ConfigPath}}, Summary: summary},
				Machine: map[string]any{"status": plannedOrCompleted(dryRun), "backup_path": selected, "config_path": candidates[0].ConfigPath},
			})
		},
	}
	command.Flags().StringVar(&backup, "backup", "", "要还原的备份文件（默认为最新备份）")
	command.Flags().BoolVar(&force, "force", false, "跳过交互确认")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "显示计划但不修改文件")
	return command
}

func newMobaThemeCacheCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("cache", "管理本地主题缓存")
	command.AddCommand(
		newMobaThemeCacheAction("update", "更新本地主题缓存", global),
		newMobaThemeCacheAction("clean", "删除本地主题缓存", global),
		newMobaThemeCacheAction("status", "显示本地主题缓存状态", global),
	)
	return command
}

func newMobaThemeCacheAction(action, description string, global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use: action, Short: description, Args: cobra.NoArgs, Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			_, home, err := mobaContext()
			if err != nil {
				return err
			}
			cachePath := mobaThemeCache(home)
			switch action {
			case "update":
				err = theme.UpdateCache(cachePath)
			case "clean":
				err = theme.CleanCache(home, cachePath, false)
			case "status":
				info, statErr := os.Stat(cachePath)
				if statErr != nil && !errors.Is(statErr, os.ErrNotExist) {
					return runError(statErr)
				}
				exists := statErr == nil
				modified := ""
				if exists {
					modified = info.ModTime().UTC().Format(time.RFC3339)
				}
				document := clioutput.Document{Title: "MobaXterm 主题缓存状态", Fields: []clioutput.Field{{Label: "是否存在", Value: boolText(exists)}, {Label: "路径", Value: cachePath}, {Label: "修改时间", Value: modified}}}
				if !exists {
					document.Hint = "请运行 `okit mobaxterm theme cache update` 初始化缓存。"
				}
				return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: map[string]any{"exists": exists, "path": cachePath, "modified": modified}})
			}
			if err != nil {
				return runError(err)
			}
			title := "已更新 MobaXterm 主题缓存"
			status := "updated"
			if action == "clean" {
				title = "已删除 MobaXterm 主题缓存"
				status = "removed"
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "路径", Value: cachePath}}},
				Machine: map[string]any{"status": status, "path": cachePath},
			})
		},
	}
}

func mobaThemeCache(home string) string   { return filepath.Join(home, "cache", "mobaxterm", "themes") }
func mobaThemeBackups(home string) string { return filepath.Join(home, "backups", "mobaxterm") }

func newMobaLicenseCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("license", "管理 MobaXterm Pro 许可证")
	command.AddCommand(newMobaLicenseGenerateCommand(global), newMobaLicenseDeployCommand(global), newMobaLicenseInspectCommand(global), newMobaLicenseVerifyCommand(global))
	return command
}

func newMobaLicenseGenerateCommand(global *globalOptions) *cobra.Command {
	username, version, output := "", "", ""
	command := &cobra.Command{
		Use:         "generate",
		Short:       "生成 MobaXterm 许可证文件",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" || output == "" {
				return usageError("generate 需要 --username、--version 和 --output")
			}
			key, err := license.Generate(username, version)
			if err != nil {
				return runError(err)
			}
			if err := license.CreateFile(output, key); err != nil {
				return runError(err)
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "已生成 MobaXterm 许可证", Fields: []clioutput.Field{{Label: "输出文件", Value: output}, {Label: "用户名", Value: username}, {Label: "版本", Value: version}}},
				Machine: map[string]any{"status": "created", "output": output, "username": username, "version": version},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "授权用户名")
	command.Flags().StringVar(&version, "version", "", "MobaXterm 版本")
	command.Flags().StringVar(&output, "output", "", "输出许可证文件")
	return command
}

func newMobaLicenseDeployCommand(global *globalOptions) *cobra.Command {
	username, version := "", ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:         "deploy",
		Short:       "部署 MobaXterm 许可证",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			if username == "" {
				return usageError("deploy 需要 --username")
			}
			presenter := newPresenter(cmd, global)
			if !dryRun {
				plan, err := service.DeployLicense(username, version, true)
				if err != nil {
					return runError(err)
				}
				if !force && !confirmAction(cmd.InOrStdin(), presenter, mobaLicenseDeployPrompt(plan)) {
					return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消部署许可证", Summary: "未作任何更改。"}, Machine: map[string]any{"status": "cancelled", "changed": false}})
				}
			}
			result, err := service.DeployLicense(username, version, dryRun)
			if err != nil {
				return runError(err)
			}
			title := "已部署 MobaXterm 许可证"
			summary := ""
			if dryRun {
				title = "MobaXterm 许可证部署计划"
				summary = "未作任何更改。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "用户名", Value: username}, {Label: "版本", Value: version}, {Label: "结果", Value: mobaLicenseDeploymentSummary(result)}}, Summary: summary},
				Machine: map[string]any{"status": plannedOrCompleted(dryRun), "username": username, "version": version, "result": result},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "授权用户名")
	command.Flags().StringVar(&version, "version", "", "MobaXterm 版本")
	command.Flags().BoolVar(&force, "force", false, "跳过交互确认")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "显示部署计划但不修改文件")
	return command
}

func newMobaLicenseInspectCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use: "inspect <文件或密钥>", Short: "检查 MobaXterm 许可证", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			key, err := readLicenseArgument(args[0])
			if err != nil {
				return runError(err)
			}
			info, err := license.InspectKey(key)
			if err != nil {
				return runError(err)
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human: clioutput.Document{Title: "MobaXterm 许可证", Fields: []clioutput.Field{
					{Label: "用户名", Value: info.Username}, {Label: "版本", Value: info.Version},
					{Label: "许可证类型", Value: info.LicenseType}, {Label: "用户数量", Value: strconv.Itoa(info.UserCount)},
				}},
				Machine: info,
			})
		},
	}
}

func newMobaLicenseVerifyCommand(global *globalOptions) *cobra.Command {
	username, version := "", ""
	command := &cobra.Command{
		Use: "verify <文件或密钥>", Short: "验证 MobaXterm 许可证", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" {
				return usageError("verify 需要 --username 和 --version")
			}
			key, err := readLicenseArgument(args[0])
			if err != nil {
				return runError(err)
			}
			valid, err := license.Verify(key, username, version)
			if err != nil {
				return runError(err)
			}
			if !valid {
				return domainError("MOBA_LICENSE_INVALID", "许可证验证失败。", "请检查预期的用户名、版本和许可证输入。")
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "MobaXterm 许可证有效。", Fields: []clioutput.Field{{Label: "用户名", Value: username}, {Label: "版本", Value: version}}},
				Machine: map[string]any{"valid": true, "username": username, "version": version},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "预期的授权用户名")
	command.Flags().StringVar(&version, "version", "", "预期的 MobaXterm 版本")
	return command
}

func themeStatus(dryRun, changed bool) string {
	if dryRun {
		return "planned"
	}
	if changed {
		return "updated"
	}
	return "unchanged"
}

func plannedOrCompleted(dryRun bool) string {
	if dryRun {
		return "planned"
	}
	return "completed"
}

func readLicenseArgument(value string) (string, error) {
	if info, err := os.Stat(value); err == nil && !info.IsDir() {
		return license.ReadFile(value)
	}
	return value, nil
}

func mobaThemeApplyPrompt() string { return "要应用选定的 MobaXterm 主题吗？" }

func mobaThemeRestorePrompt() string { return "要还原 MobaXterm 配置备份吗？" }

func mobaLicenseDeployPrompt(plan string) string {
	return "要部署 MobaXterm 许可证文件吗？ " + mobaLicenseDeploymentSummary(plan)
}

func mobaLicenseDeploymentSummary(result string) string {
	if path, ok := strings.CutPrefix(result, "would deploy license to "); ok {
		return "将把许可证部署到 " + path
	}
	if path, ok := strings.CutPrefix(result, "deployed license to "); ok {
		return "已将许可证部署到 " + path
	}
	return "许可证部署已完成。"
}
