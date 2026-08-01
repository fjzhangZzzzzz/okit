package cli

import (
	"errors"
	"os"
	"path/filepath"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/theme"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

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
			selected, err := selectMobaInstallation()
			if err != nil {
				return err
			}
			home := selected.home
			scheme, err := theme.Resolve(mobaThemeCache(home), args[0])
			if err != nil {
				return runError(err)
			}
			presenter := newPresenter(cmd, global)
			if !confirmMobaAction(cmd.InOrStdin(), presenter, dryRun, force, mobaThemeApplyPrompt()) {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消应用主题", Summary: "未作任何更改。"}, Machine: mobaThemeApplyResult{mobaActionResult: newMobaActionResult("theme_apply", "cancelled", false, false), Theme: args[0], ConfigPath: selected.candidate.ConfigPath}})
			}
			var result theme.Result
			if noBackup {
				result, err = theme.ApplyWithoutBackup(selected.candidate.ConfigPath, scheme, dryRun, nil)
			} else {
				result, err = theme.Apply(selected.candidate.ConfigPath, scheme, mobaThemeBackups(home), dryRun, nil)
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
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "主题", Value: args[0]}, {Label: "配置文件", Value: selected.candidate.ConfigPath}, {Label: "备份", Value: result.BackupPath}}, Summary: summary},
				Machine: mobaThemeApplyResult{mobaActionResult: newMobaActionResult("theme_apply", themeStatus(dryRun, result.Changed), result.Changed, dryRun), Theme: args[0], ConfigPath: selected.candidate.ConfigPath, BackupPath: result.BackupPath},
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
			selectedInstallation, err := selectMobaInstallation()
			if err != nil {
				return err
			}
			selected := backup
			if selected == "" {
				selected, err = theme.LatestBackup(mobaThemeBackups(selectedInstallation.home))
				if err != nil {
					return runError(err)
				}
			}
			presenter := newPresenter(cmd, global)
			if !confirmMobaAction(cmd.InOrStdin(), presenter, dryRun, force, mobaThemeRestorePrompt()) {
				return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消还原主题", Summary: "未作任何更改。"}, Machine: mobaThemeRestoreResult{mobaActionResult: newMobaActionResult("theme_restore", "cancelled", false, false), BackupPath: selected, ConfigPath: selectedInstallation.candidate.ConfigPath}})
			}
			if err := theme.Restore(selectedInstallation.candidate.ConfigPath, selected, dryRun); err != nil {
				return runError(err)
			}
			title := "已还原 MobaXterm 配置"
			summary := ""
			if dryRun {
				title = "MobaXterm 配置还原计划"
				summary = "未作任何更改。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "备份", Value: selected}, {Label: "配置文件", Value: selectedInstallation.candidate.ConfigPath}}, Summary: summary},
				Machine: mobaThemeRestoreResult{mobaActionResult: newMobaActionResult("theme_restore", plannedOrCompleted(dryRun), !dryRun, dryRun), BackupPath: selected, ConfigPath: selectedInstallation.candidate.ConfigPath},
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
				return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: mobaCacheResult{SchemaVersion: 1, Path: cachePath, Exists: exists, Modified: modified}})
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
				Machine: mobaCacheResult{SchemaVersion: 1, Status: status, Path: cachePath},
			})
		},
	}
}

func mobaThemeCache(home string) string   { return filepath.Join(home, "cache", "mobaxterm", "themes") }
func mobaThemeBackups(home string) string { return filepath.Join(home, "backups", "mobaxterm") }

func themeStatus(dryRun, changed bool) string {
	if dryRun {
		return "planned"
	}
	if changed {
		return "updated"
	}
	return "unchanged"
}
func mobaThemeApplyPrompt() string   { return "要应用选定的 MobaXterm 主题吗？" }
func mobaThemeRestorePrompt() string { return "要还原 MobaXterm 配置备份吗？" }
