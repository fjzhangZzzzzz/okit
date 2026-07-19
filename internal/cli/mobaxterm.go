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
	command := commandGroup("mobaxterm", "Manage MobaXterm")
	command.AddCommand(newMobaStatusCommand(global), newMobaThemeCommand(global), newMobaLicenseCommand(global))
	return command
}

func mobaContext() (mobaxterm.Service, string, error) {
	if runtime.GOOS != "windows" {
		return mobaxterm.Service{}, "", usageError("mobaxterm is only supported on Windows")
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
		Short:       "Display detected MobaXterm installations",
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
	command := commandGroup("theme", "Manage MobaXterm terminal themes")
	command.AddCommand(newMobaThemeListCommand(global), newMobaThemeApplyCommand(global), newMobaThemeRestoreCommand(global), newMobaThemeCacheCommand(global))
	return command
}

func newMobaThemeListCommand(global *globalOptions) *cobra.Command {
	search, limit := "", 20
	command := &cobra.Command{
		Use:         "list",
		Short:       "List cached MobaXterm themes",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			_, home, err := mobaContext()
			if err != nil {
				return err
			}
			if limit < 1 {
				return usageError("--limit must be greater than zero")
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
	command.Flags().StringVar(&search, "search", "", "filter themes by name")
	command.Flags().IntVar(&limit, "limit", 20, "maximum number of themes")
	return command
}

func newMobaThemeApplyCommand(global *globalOptions) *cobra.Command {
	var noBackup, force, dryRun bool
	command := &cobra.Command{
		Use:         "apply <name>",
		Short:       "Apply a MobaXterm theme",
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
	command.Flags().BoolVar(&noBackup, "no-backup", false, "do not create a configuration backup")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the plan without changing files")
	return command
}

func newMobaThemeRestoreCommand(global *globalOptions) *cobra.Command {
	backup := ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:         "restore",
		Short:       "Restore a MobaXterm configuration backup",
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
	command.Flags().StringVar(&backup, "backup", "", "backup file to restore (defaults to latest)")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the plan without changing files")
	return command
}

func newMobaThemeCacheCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("cache", "Manage the local theme cache")
	command.AddCommand(
		newMobaThemeCacheAction("update", "Update the local theme cache", global),
		newMobaThemeCacheAction("clean", "Remove the local theme cache", global),
		newMobaThemeCacheAction("status", "Display local theme cache status", global),
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
	command := commandGroup("license", "Manage MobaXterm Pro licenses")
	command.AddCommand(newMobaLicenseGenerateCommand(global), newMobaLicenseDeployCommand(global), newMobaLicenseInspectCommand(global), newMobaLicenseVerifyCommand(global))
	return command
}

func newMobaLicenseGenerateCommand(global *globalOptions) *cobra.Command {
	username, version, output := "", "", ""
	command := &cobra.Command{
		Use:         "generate",
		Short:       "Generate a MobaXterm license file",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" || output == "" {
				return usageError("generate requires --username, --version, and --output")
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
	command.Flags().StringVar(&username, "username", "", "licensed username")
	command.Flags().StringVar(&version, "version", "", "MobaXterm version")
	command.Flags().StringVar(&output, "output", "", "output license file")
	return command
}

func newMobaLicenseDeployCommand(global *globalOptions) *cobra.Command {
	username, version := "", ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:         "deploy",
		Short:       "Deploy a MobaXterm license",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			if username == "" {
				return usageError("deploy requires --username")
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
	command.Flags().StringVar(&username, "username", "", "licensed username")
	command.Flags().StringVar(&version, "version", "", "MobaXterm version")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the deployment plan without changing files")
	return command
}

func newMobaLicenseInspectCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use: "inspect <file-or-key>", Short: "Inspect a MobaXterm license", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
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
		Use: "verify <file-or-key>", Short: "Verify a MobaXterm license", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" {
				return usageError("verify requires --username and --version")
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
				return domainError("MOBA_LICENSE_INVALID", "license verification failed", "Check the expected username, version, and license input.")
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "MobaXterm license is valid.", Fields: []clioutput.Field{{Label: "Username", Value: username}, {Label: "Version", Value: version}}},
				Machine: map[string]any{"valid": true, "username": username, "version": version},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "expected licensed username")
	command.Flags().StringVar(&version, "version", "", "expected MobaXterm version")
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
