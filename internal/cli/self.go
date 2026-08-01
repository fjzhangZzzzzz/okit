package cli

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/installation"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/schollz/progressbar/v3"
	"github.com/spf13/cobra"
)

func (a *App) newUpgradeCommand(global *globalOptions) *cobra.Command {
	options := upgradeOptions{}
	command := &cobra.Command{
		Use:         "upgrade",
		Short:       "检查或安装 okit 更新",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			workflow := a.newUpgradeWorkflow(options, global.format, isTerminal(cmd.ErrOrStderr()), cmd.ErrOrStderr())
			result, err := workflow.Run(cmd.Context())
			if err != nil {
				return err
			}
			return newPresenter(cmd, global).Render(result.View())
		},
	}
	command.Flags().BoolVar(&options.check, "check", false, "仅检查是否有可用更新")
	command.Flags().StringVar(&options.version, "version", "", "安装指定版本")
	command.Flags().BoolVar(&options.prerelease, "prerelease", false, "包含预发布版本")
	command.Flags().BoolVar(&options.dryRun, "dry-run", false, "显示更新计划但不修改文件")
	return command
}

type terminalUpdateProgress struct {
	writer io.Writer
	stage  installation.ProgressStage
	bar    *progressbar.ProgressBar
	barMax int64
}

func (p *terminalUpdateProgress) ReportProgress(progress installation.Progress) {
	previousStage := p.stage
	switch progress.Stage {
	case installation.ProgressUpdateAvailable:
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	case installation.ProgressDownloadAsset, installation.ProgressDownloadChecksum:
		p.renderDownload(progress, previousStage)
	case installation.ProgressComplete:
		p.finishBar()
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	default:
		p.finishBar()
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	}
	p.stage = progress.Stage
}

func (p *terminalUpdateProgress) renderDownload(progress installation.Progress, previousStage installation.ProgressStage) {
	if p.bar == nil || previousStage != progress.Stage {
		p.finishBar()
		p.newDownloadBar(progress)
	} else if p.barMax <= 0 && progress.Total > 0 {
		_ = p.bar.Clear()
		p.newDownloadBar(progress)
	}
	if p.bar != nil {
		_ = p.bar.Set64(progress.Current)
	}
}

func (p *terminalUpdateProgress) newDownloadBar(progress installation.Progress) {
	maximum := progress.Total
	if maximum <= 0 {
		maximum = -1
	}
	p.barMax = maximum
	p.bar = progressbar.NewOptions64(maximum,
		progressbar.OptionSetWriter(p.writer),
		progressbar.OptionSetDescription(updateProgressMessage(progress)),
		progressbar.OptionShowBytes(true),
		progressbar.OptionSetWidth(16),
		progressbar.OptionThrottle(65*time.Millisecond),
	)
}

func (p *terminalUpdateProgress) finishBar() {
	if p.bar == nil {
		return
	}
	_ = p.bar.Finish()
	p.bar = nil
	p.barMax = 0
}

func updateProgressMessage(progress installation.Progress) string {
	switch progress.Stage {
	case installation.ProgressUpdateAvailable:
		return fmt.Sprintf("有可用更新：%s", progress.Version)
	case installation.ProgressDownloadAsset:
		return "正在下载更新"
	case installation.ProgressDownloadChecksum:
		return "正在下载校验和"
	case installation.ProgressVerifyChecksum:
		return "正在校验文件……"
	case installation.ProgressExtract:
		return "正在解压更新……"
	case installation.ProgressReplace:
		return "正在替换可执行文件……"
	case installation.ProgressComplete:
		if progress.Scheduled {
			return "已计划更新；当前进程退出后，新版本将生效。"
		}
		return "更新成功。"
	default:
		return "正在更新……"
	}
}

func isTerminal(writer io.Writer) bool {
	file, ok := writer.(*os.File)
	if !ok {
		return false
	}
	info, err := file.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}

func (a *App) newUninstallCommand(global *globalOptions) *cobra.Command {
	options := installation.UninstallOptions{}
	command := &cobra.Command{
		Use:         "uninstall",
		Short:       "卸载 okit",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			presenter := newPresenter(cmd, global)
			if options.Purge && !options.Yes && !options.DryRun {
				if err := presenter.Prompt("是否永久删除 OKIT_HOME 与全部用户数据？[y/N] "); err != nil {
					return runError(err)
				}
				answer, _ := bufio.NewReader(cmd.InOrStdin()).ReadString('\n')
				answer = strings.TrimSpace(strings.ToLower(answer))
				if answer != "y" && answer != "yes" {
					return presenter.Render(clioutput.View{
						Human:   clioutput.Document{Title: "已取消卸载", Summary: "未作任何更改。"},
						Machine: map[string]any{"status": "cancelled", "changed": false},
					})
				}
				options.Yes = true
			}
			uninstaller := a.selfUninstaller
			if uninstaller == nil {
				home, executable, err := selfPaths()
				if err != nil {
					return runError(err)
				}
				uninstaller = &installation.Uninstaller{OKITHome: home, Executable: executable}
			}
			result, err := uninstaller.Uninstall(options)
			if err != nil {
				return runError(err)
			}
			items := make([]clioutput.PlanItem, 0, len(result.Plan))
			for _, target := range result.Plan {
				items = append(items, clioutput.PlanItem{Action: uninstallAction(options.DryRun, result.Scheduled), Resource: uninstallResource(target), Target: target})
			}
			title := "okit 已成功卸载。"
			if result.Scheduled {
				title = "已计划卸载"
			} else if options.DryRun {
				title = "卸载计划"
			}
			summary := ""
			if options.DryRun {
				summary = "未作任何更改。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Plan: items, Summary: summary},
				Machine: map[string]any{"status": uninstallStatus(options.DryRun, result.Scheduled), "targets": result.Plan, "purge": options.Purge},
			})
		},
	}
	command.Flags().BoolVar(&options.Purge, "purge", false, "同时删除 OKIT_HOME 与用户数据")
	command.Flags().BoolVar(&options.Yes, "yes", false, "确认执行破坏性删除")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "显示卸载计划但不修改文件")
	return command
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

func selfPaths() (string, string, error) {
	home, err := config.Home()
	if err != nil {
		return "", "", err
	}
	executable, err := os.Executable()
	if err != nil {
		return "", "", err
	}
	executable, err = filepath.Abs(executable)
	if err != nil {
		return "", "", err
	}
	return home, executable, nil
}
