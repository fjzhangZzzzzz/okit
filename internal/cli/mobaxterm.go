package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/theme"
	"github.com/spf13/cobra"
)

func newMobaXtermCommand() *cobra.Command {
	command := commandGroup("mobaxterm", "Manage MobaXterm")
	command.AddCommand(newMobaStatusCommand(), newMobaThemeCommand(), newMobaLicenseCommand())
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

func newMobaStatusCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Display detected MobaXterm installations",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			candidates, err := service.Status()
			if err != nil {
				return runError(err)
			}
			data, _ := json.MarshalIndent(candidates, "", "  ")
			fmt.Fprintln(cmd.OutOrStdout(), string(data))
			return nil
		},
	}
}

func newMobaThemeCommand() *cobra.Command {
	command := commandGroup("theme", "Manage MobaXterm terminal themes")
	command.AddCommand(newMobaThemeListCommand(), newMobaThemeApplyCommand(), newMobaThemeRestoreCommand(), newMobaThemeCacheCommand())
	return command
}

func newMobaThemeListCommand() *cobra.Command {
	search, limit := "", 20
	command := &cobra.Command{
		Use:   "list",
		Short: "List cached MobaXterm themes",
		Args:  cobra.NoArgs,
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
				return runError(err)
			}
			for _, scheme := range schemes {
				fmt.Fprintln(cmd.OutOrStdout(), scheme)
			}
			return nil
		},
	}
	command.Flags().StringVar(&search, "search", "", "filter themes by name")
	command.Flags().IntVar(&limit, "limit", 20, "maximum number of themes")
	return command
}

func newMobaThemeApplyCommand() *cobra.Command {
	var noBackup, force, dryRun bool
	command := &cobra.Command{
		Use:   "apply <name>",
		Short: "Apply a MobaXterm theme",
		Args:  cobra.ExactArgs(1),
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
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), cmd.ErrOrStderr(), "Apply the selected MobaXterm theme?") {
				fmt.Fprintln(cmd.OutOrStdout(), "theme apply cancelled")
				return nil
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
			fmt.Fprintf(cmd.OutOrStdout(), "changed=%t backup=%s\n", result.Changed, result.BackupPath)
			return nil
		},
	}
	command.Flags().BoolVar(&noBackup, "no-backup", false, "do not create a configuration backup")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the plan without changing files")
	return command
}

func newMobaThemeRestoreCommand() *cobra.Command {
	backup := ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:   "restore",
		Short: "Restore a MobaXterm configuration backup",
		Args:  cobra.NoArgs,
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
			if !dryRun && !force && !confirmAction(cmd.InOrStdin(), cmd.ErrOrStderr(), "Restore the MobaXterm configuration backup?") {
				fmt.Fprintln(cmd.OutOrStdout(), "theme restore cancelled")
				return nil
			}
			if err := theme.Restore(candidates[0].ConfigPath, selected, dryRun); err != nil {
				return runError(err)
			}
			fmt.Fprintf(cmd.OutOrStdout(), "restored=%s\n", selected)
			return nil
		},
	}
	command.Flags().StringVar(&backup, "backup", "", "backup file to restore (defaults to latest)")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the plan without changing files")
	return command
}

func newMobaThemeCacheCommand() *cobra.Command {
	command := commandGroup("cache", "Manage the local theme cache")
	command.AddCommand(
		newMobaThemeCacheAction("update", "Update the local theme cache"),
		newMobaThemeCacheAction("clean", "Remove the local theme cache"),
		newMobaThemeCacheAction("status", "Display local theme cache status"),
	)
	return command
}

func newMobaThemeCacheAction(action, description string) *cobra.Command {
	return &cobra.Command{
		Use: action, Short: description, Args: cobra.NoArgs,
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
				if statErr != nil {
					fmt.Fprintf(cmd.OutOrStdout(), "cache_exists=false path=%s\n", cachePath)
				} else {
					fmt.Fprintf(cmd.OutOrStdout(), "cache_exists=true modified=%s path=%s\n", info.ModTime().UTC().Format(time.RFC3339), cachePath)
				}
			}
			if err != nil {
				return runError(err)
			}
			return nil
		},
	}
}

func mobaThemeCache(home string) string   { return filepath.Join(home, "cache", "mobaxterm", "themes") }
func mobaThemeBackups(home string) string { return filepath.Join(home, "backups", "mobaxterm") }

func newMobaLicenseCommand() *cobra.Command {
	command := commandGroup("license", "Manage MobaXterm Pro licenses")
	command.AddCommand(newMobaLicenseGenerateCommand(), newMobaLicenseDeployCommand(), newMobaLicenseInspectCommand(), newMobaLicenseVerifyCommand())
	return command
}

func newMobaLicenseGenerateCommand() *cobra.Command {
	username, version, output := "", "", ""
	command := &cobra.Command{
		Use:   "generate",
		Short: "Generate a MobaXterm license file",
		Args:  cobra.NoArgs,
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
			fmt.Fprintln(cmd.OutOrStdout(), output)
			return nil
		},
	}
	command.Flags().StringVar(&username, "username", "", "licensed username")
	command.Flags().StringVar(&version, "version", "", "MobaXterm version")
	command.Flags().StringVar(&output, "output", "", "output license file")
	return command
}

func newMobaLicenseDeployCommand() *cobra.Command {
	username, version := "", ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:   "deploy",
		Short: "Deploy a MobaXterm license",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			if username == "" {
				return usageError("deploy requires --username")
			}
			if !dryRun {
				plan, err := service.DeployLicense(username, version, true)
				if err != nil {
					return runError(err)
				}
				fmt.Fprintln(cmd.OutOrStdout(), plan)
				if !force && !confirmAction(cmd.InOrStdin(), cmd.ErrOrStderr(), "Deploy the MobaXterm license file?") {
					fmt.Fprintln(cmd.OutOrStdout(), "license deploy cancelled")
					return nil
				}
			}
			result, err := service.DeployLicense(username, version, dryRun)
			if err != nil {
				return runError(err)
			}
			fmt.Fprintln(cmd.OutOrStdout(), result)
			return nil
		},
	}
	command.Flags().StringVar(&username, "username", "", "licensed username")
	command.Flags().StringVar(&version, "version", "", "MobaXterm version")
	command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "show the deployment plan without changing files")
	return command
}

func newMobaLicenseInspectCommand() *cobra.Command {
	return &cobra.Command{
		Use: "inspect <file-or-key>", Short: "Inspect a MobaXterm license", Args: cobra.ExactArgs(1),
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
			data, _ := json.MarshalIndent(info, "", "  ")
			fmt.Fprintln(cmd.OutOrStdout(), string(data))
			return nil
		},
	}
}

func newMobaLicenseVerifyCommand() *cobra.Command {
	username, version := "", ""
	command := &cobra.Command{
		Use: "verify <file-or-key>", Short: "Verify a MobaXterm license", Args: cobra.ExactArgs(1),
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
				return runError(fmt.Errorf("license verification failed"))
			}
			fmt.Fprintln(cmd.OutOrStdout(), "valid")
			return nil
		},
	}
	command.Flags().StringVar(&username, "username", "", "expected licensed username")
	command.Flags().StringVar(&version, "version", "", "expected MobaXterm version")
	return command
}

func readLicenseArgument(value string) (string, error) {
	if info, err := os.Stat(value); err == nil && !info.IsDir() {
		return license.ReadFile(value)
	}
	return value, nil
}
