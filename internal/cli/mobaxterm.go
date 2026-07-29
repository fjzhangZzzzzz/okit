package cli

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
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
			document := clioutput.Document{Title: "Detected MobaXterm installations"}
			if len(candidates) == 0 {
				document.Title = ""
				document.Empty = &clioutput.EmptyState{Message: "No MobaXterm installation found."}
			} else {
				table := &clioutput.Table{Headers: []string{"DEFAULT", "VERSION", "SOURCE", "EXECUTABLE", "CONFIG"}}
				for _, candidate := range candidates {
					table.Rows = append(table.Rows, []string{boolText(candidate.Default), candidate.Version, candidate.Source, candidate.ExePath, candidate.ConfigPath})
				}
				document.Table = table
			}
			return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: candidates})
		},
	}
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
							Message: "No cached MobaXterm themes found.",
							Hint:    "Initialize the cache with `okit mobaxterm theme cache update`.",
						}},
						Machine: []string{},
					})
				}
				return runError(err)
			}
			document := clioutput.Document{Title: "Cached MobaXterm themes"}
			if len(schemes) == 0 {
				document.Title = ""
				document.Empty = &clioutput.EmptyState{Message: "No themes matched the current filter.", Hint: "Try a different --search value."}
			} else {
				table := &clioutput.Table{Headers: []string{"THEME"}}
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
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), presenter, "Apply the selected MobaXterm theme?") {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "Theme application cancelled", Summary: "No changes were made."}, Machine: map[string]any{"status": "cancelled", "changed": false}})
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
			title := "MobaXterm theme applied"
			summary := ""
			if dryRun {
				title = "MobaXterm theme application plan"
				summary = "No changes were made."
			} else if !result.Changed {
				title = "MobaXterm theme is unchanged."
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "Theme", Value: args[0]}, {Label: "Config", Value: candidates[0].ConfigPath}, {Label: "Backup", Value: result.BackupPath}}, Summary: summary},
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
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), presenter, "Restore the MobaXterm configuration backup?") {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "Theme restore cancelled", Summary: "No changes were made."}, Machine: map[string]any{"status": "cancelled", "changed": false}})
			}
			if err := theme.Restore(candidates[0].ConfigPath, selected, dryRun); err != nil {
				return runError(err)
			}
			title := "MobaXterm configuration restored"
			summary := ""
			if dryRun {
				title = "MobaXterm restore plan"
				summary = "No changes were made."
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "Backup", Value: selected}, {Label: "Config", Value: candidates[0].ConfigPath}}, Summary: summary},
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
				document := clioutput.Document{Title: "MobaXterm theme cache status", Fields: []clioutput.Field{{Label: "Exists", Value: boolText(exists)}, {Label: "Path", Value: cachePath}, {Label: "Modified", Value: modified}}}
				if !exists {
					document.Hint = "Initialize the cache with `okit mobaxterm theme cache update`."
				}
				return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: map[string]any{"exists": exists, "path": cachePath, "modified": modified}})
			}
			if err != nil {
				return runError(err)
			}
			title := "MobaXterm theme cache updated"
			status := "updated"
			if action == "clean" {
				title = "MobaXterm theme cache removed"
				status = "removed"
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "Path", Value: cachePath}}},
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
				Human:   clioutput.Document{Title: "MobaXterm license created", Fields: []clioutput.Field{{Label: "Output", Value: output}, {Label: "Username", Value: username}, {Label: "Version", Value: version}}},
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
				if !force && !confirmAction(cmd.InOrStdin(), presenter, "Deploy the MobaXterm license file? "+plan) {
					return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "License deployment cancelled", Summary: "No changes were made."}, Machine: map[string]any{"status": "cancelled", "changed": false}})
				}
			}
			result, err := service.DeployLicense(username, version, dryRun)
			if err != nil {
				return runError(err)
			}
			title := "MobaXterm license deployed"
			summary := ""
			if dryRun {
				title = "MobaXterm license deployment plan"
				summary = "No changes were made."
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "Username", Value: username}, {Label: "Version", Value: version}, {Label: "Result", Value: result}}, Summary: summary},
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
				Human: clioutput.Document{Title: "MobaXterm license", Fields: []clioutput.Field{
					{Label: "Username", Value: info.Username}, {Label: "Version", Value: info.Version},
					{Label: "License type", Value: info.LicenseType}, {Label: "User count", Value: strconv.Itoa(info.UserCount)},
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
				return domainError("MOBA_LICENSE_INVALID", "License verification failed.", "Check the expected username, version, and license input.")
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "MobaXterm license is valid.", Fields: []clioutput.Field{{Label: "Username", Value: username}, {Label: "Version", Value: version}}},
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
