package cli

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/schollz/progressbar/v3"
	"github.com/spf13/cobra"
)

func (a *App) newSelfCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("self", "Update or uninstall okit")
	command.AddCommand(a.newSelfUpdateCommand(global), a.newSelfUninstallCommand(global))
	return command
}

func (a *App) newSelfUpdateCommand(global *globalOptions) *cobra.Command {
	options := selfmanage.UpdateOptions{}
	command := &cobra.Command{
		Use:         "update",
		Short:       "Check for or install an okit update",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			if a.buildMode == BuildModeDevelopment {
				return newPresenter(cmd, global).Render(clioutput.View{
					Human: clioutput.Document{
						Title: "Update checks aren't available for development builds.",
						Hint:  "Install a released version of okit, then run this command again.",
					},
					Machine: map[string]any{
						"update_supported": false,
						"reason":           "development_build",
						"action":           "Install a released version of okit, then run this command again.",
					},
				})
			}
			if err := selfmanage.ValidateVersion(a.version); err != nil {
				return domainError(
					"SELF_VERSION_INVALID",
					"This okit installation has invalid version information.",
					"Reinstall okit from an official release.",
				)
			}
			updater := a.selfUpdater
			if updater == nil {
				home, executable, err := selfPaths()
				if err != nil {
					return runError(err)
				}
				updater = &selfmanage.Updater{CurrentVersion: a.version, Executable: executable, OKITHome: home}
			}
			if global.format != "json" && !options.Check && !options.DryRun && isTerminal(cmd.ErrOrStderr()) {
				options.Progress = &terminalUpdateProgress{writer: cmd.ErrOrStderr()}
			}
			result, err := updater.Update(context.Background(), options)
			if err != nil {
				if strings.Contains(err.Error(), "403") {
					return domainError("SELF_RELEASE_ACCESS_DENIED", "The release service denied the update request.", "Retry later or configure GH_TOKEN/GITHUB_TOKEN if the service rate limit was reached.")
				}
				return runError(err)
			}
			available := result.Available != "" && result.Available != result.Current
			title := "okit is up to date."
			hint := ""
			if options.Check && available {
				title = "Update available"
				hint = "Run `okit self update` to install."
			} else if options.DryRun {
				title = "Update plan"
			} else if result.Scheduled {
				title = "Update scheduled"
			} else if result.Updated {
				title = "okit updated successfully."
			} else if available {
				title = "Update selected"
			}
			document := clioutput.Document{
				Title:  title,
				Fields: []clioutput.Field{{Label: "Current", Value: result.Current}, {Label: "Available", Value: result.Available}},
				Hint:   hint,
			}
			if options.DryRun {
				if result.Plan != "" {
					document.Lines = []string{result.Plan}
				}
				document.Summary = "No changes were made."
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
	command.Flags().BoolVar(&options.Check, "check", false, "only check whether an update is available")
	command.Flags().StringVar(&options.Version, "version", "", "install a specific version")
	command.Flags().BoolVar(&options.Prerelease, "prerelease", false, "include prerelease versions")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "show the update plan without changing files")
	return command
}

type terminalUpdateProgress struct {
	writer io.Writer
	stage  selfmanage.ProgressStage
	bar    *progressbar.ProgressBar
	barMax int64
}

func (p *terminalUpdateProgress) ReportProgress(progress selfmanage.Progress) {
	previousStage := p.stage
	switch progress.Stage {
	case selfmanage.ProgressUpdateAvailable:
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	case selfmanage.ProgressDownloadAsset, selfmanage.ProgressDownloadChecksum:
		p.renderDownload(progress, previousStage)
	case selfmanage.ProgressComplete:
		p.finishBar()
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	default:
		p.finishBar()
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	}
	p.stage = progress.Stage
}

func (p *terminalUpdateProgress) renderDownload(progress selfmanage.Progress, previousStage selfmanage.ProgressStage) {
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

func (p *terminalUpdateProgress) newDownloadBar(progress selfmanage.Progress) {
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

func updateProgressMessage(progress selfmanage.Progress) string {
	switch progress.Stage {
	case selfmanage.ProgressUpdateAvailable:
		return fmt.Sprintf("Update available: %s", progress.Version)
	case selfmanage.ProgressDownloadAsset:
		return downloadProgressMessage("Downloading update", progress)
	case selfmanage.ProgressDownloadChecksum:
		return downloadProgressMessage("Downloading checksums", progress)
	case selfmanage.ProgressVerifyChecksum:
		return "Verifying checksum..."
	case selfmanage.ProgressExtract:
		return "Extracting update..."
	case selfmanage.ProgressReplace:
		return "Replacing executable..."
	case selfmanage.ProgressComplete:
		return "Update completed successfully."
	default:
		return "Updating..."
	}
}

func downloadProgressMessage(prefix string, progress selfmanage.Progress) string {
	if progress.Total > 0 {
		return fmt.Sprintf("%s... %d%% (%d/%d bytes)", prefix, progress.Current*100/progress.Total, progress.Current, progress.Total)
	}
	if progress.Current > 0 {
		return fmt.Sprintf("%s... %d bytes", prefix, progress.Current)
	}
	return prefix + "..."
}

func isTerminal(writer io.Writer) bool {
	file, ok := writer.(*os.File)
	if !ok {
		return false
	}
	info, err := file.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}

func (a *App) newSelfUninstallCommand(global *globalOptions) *cobra.Command {
	options := selfmanage.UninstallOptions{}
	command := &cobra.Command{
		Use:         "uninstall",
		Short:       "Uninstall okit",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			presenter := newPresenter(cmd, global)
			if options.Purge && !options.Yes && !options.DryRun {
				if err := presenter.Prompt("Permanently delete OKIT_HOME and all user data? [y/N] "); err != nil {
					return runError(err)
				}
				answer, _ := bufio.NewReader(cmd.InOrStdin()).ReadString('\n')
				answer = strings.TrimSpace(strings.ToLower(answer))
				if answer != "y" && answer != "yes" {
					return presenter.Render(clioutput.View{
						Human:   clioutput.Document{Title: "Uninstall cancelled", Summary: "No changes were made."},
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
				uninstaller = &selfmanage.Uninstaller{OKITHome: home, Executable: executable}
			}
			result, err := uninstaller.Uninstall(options)
			if err != nil {
				return runError(err)
			}
			items := make([]clioutput.PlanItem, 0, len(result.Plan))
			for _, target := range result.Plan {
				items = append(items, clioutput.PlanItem{Action: uninstallAction(options.DryRun, result.Scheduled), Resource: uninstallResource(target), Target: target})
			}
			title := "okit uninstalled successfully."
			if result.Scheduled {
				title = "Uninstall scheduled"
			} else if options.DryRun {
				title = "Uninstall plan"
			}
			summary := ""
			if options.DryRun {
				summary = "No changes were made."
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Plan: items, Summary: summary},
				Machine: map[string]any{"status": uninstallStatus(options.DryRun, result.Scheduled), "targets": result.Plan, "purge": options.Purge},
			})
		},
	}
	command.Flags().BoolVar(&options.Purge, "purge", false, "also remove OKIT_HOME and user data")
	command.Flags().BoolVar(&options.Yes, "yes", false, "confirm destructive removal")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "show the uninstall plan without changing files")
	return command
}

func uninstallAction(dryRun, scheduled bool) string {
	if dryRun {
		return "Would remove"
	}
	if scheduled {
		return "Schedule removal"
	}
	return "Removed"
}

func uninstallResource(target string) string {
	if filepath.Base(target) == "install.json" {
		return "metadata"
	}
	if strings.HasSuffix(strings.ToLower(target), ".exe") || filepath.Base(target) == "okit" {
		return "executable"
	}
	return "managed resource"
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
