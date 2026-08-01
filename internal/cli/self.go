package cli

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/installation"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/schollz/progressbar/v3"
	"github.com/spf13/cobra"
)

type upgradeOptions struct {
	check, dryRun, prerelease bool
	version                   string
}

func (a *App) newUpgradeCommand(global *globalOptions) *cobra.Command {
	options := upgradeOptions{}
	command := &cobra.Command{
		Use:         "upgrade",
		Short:       "检查或安装 okit 更新",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			if a.buildMode == BuildModeDevelopment {
				return newPresenter(cmd, global).Render(clioutput.View{
					Human: clioutput.Document{
						Title: "开发构建不支持检查更新。",
						Hint:  "请安装已发布的 okit 版本后重试。",
					},
					Machine: map[string]any{
						"update_supported": false,
						"reason":           "development_build",
						"action":           "请安装已发布的 okit 版本后重试。",
					},
				})
			}
			if err := installation.ValidateVersion(a.version); err != nil {
				return domainError(
					"SELF_VERSION_INVALID",
					"此 okit 安装的版本信息无效。",
					"请从正式发布版本重新安装 okit。",
				)
			}
			runner := a.upgradeRunner
			if runner == nil {
				home, executable, err := selfPaths()
				if err != nil {
					return runError(err)
				}
				releaseClient := &http.Client{Timeout: 30 * time.Second}
				runner = installation.NewLifecycle(installation.Dependencies{
					CurrentVersion: a.version,
					Executable:     executable,
					OKITHome:       home,
					Source: installation.ManifestSource{
						GOOS: runtime.GOOS, GOARCH: runtime.GOARCH,
						Version: options.version, Prerelease: options.prerelease && options.version == "", Client: releaseClient,
					},
					Downloader: installation.HTTPDownloader{Client: &http.Client{Timeout: 2 * time.Minute}},
					Replace:    installation.PlatformReplace,
				})
			}
			mode := installation.ModeApply
			if options.dryRun {
				mode = installation.ModeDryRun
			} else if options.check {
				mode = installation.ModeCheck
			}
			var progress installation.ProgressReporter
			if global.format != "json" && !options.check && !options.dryRun && isTerminal(cmd.ErrOrStderr()) {
				progress = &terminalUpdateProgress{writer: cmd.ErrOrStderr()}
			}
			result, err := runner.Run(context.Background(), installation.Intent{Mode: mode, Version: options.version, IncludePrerelease: options.prerelease}, progress)
			if err != nil {
				var failure *installation.Failure
				if errors.As(err, &failure) && failure.Kind == installation.FailureReleaseAccessDenied {
					return domainError("SELF_RELEASE_ACCESS_DENIED", "发布服务拒绝了更新请求。", "请稍后重试；若触发服务限流，请配置 GH_TOKEN 或 GITHUB_TOKEN。")
				}
				return runError(err)
			}
			available := result.Available != "" && result.Available != result.Current
			title := "okit 已是最新版本。"
			hint := ""
			if options.check && available {
				title = "有可用更新"
				hint = "运行 `okit upgrade` 安装。"
			} else if options.dryRun {
				title = "更新计划"
			} else if result.Scheduled {
				title = "已计划更新"
				hint = "当前进程退出后，新版本将生效。"
			} else if result.Updated {
				title = "okit 更新成功。"
			} else if available {
				title = "已选择更新版本"
			}
			document := clioutput.Document{Title: title, Hint: hint}
			if options.check || options.dryRun {
				document.Fields = []clioutput.Field{{Label: "当前版本", Value: result.Current}, {Label: "可用版本", Value: result.Available}}
			} else if result.Updated {
				label := "已更新至"
				if result.Scheduled {
					label = "目标版本"
				}
				document.Fields = []clioutput.Field{{Label: label, Value: result.Available}}
			}
			if options.dryRun {
				if result.Plan != "" {
					document.Lines = []string{updatePlanSummary(result)}
				}
				document.Summary = "未作任何更改。"
			}
			machine := map[string]any{
				"current_version": result.Current, "available_version": result.Available,
				"update_available": available, "updated": result.Updated, "scheduled": result.Scheduled,
			}
			if result.Plan != "" {
				machine["plan"] = result.Plan
			}
			if err := newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: machine}); err != nil {
				return runError(err)
			}
			return nil
		},
	}
	command.Flags().BoolVar(&options.check, "check", false, "仅检查是否有可用更新")
	command.Flags().StringVar(&options.version, "version", "", "安装指定版本")
	command.Flags().BoolVar(&options.prerelease, "prerelease", false, "包含预发布版本")
	command.Flags().BoolVar(&options.dryRun, "dry-run", false, "显示更新计划但不修改文件")
	return command
}

func updatePlanSummary(result installation.Result) string {
	if result.Available == "" || result.Available == result.Current {
		return "当前已是最新版本。"
	}
	return fmt.Sprintf("将从 %s 更新到 %s。", result.Current, result.Available)
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
