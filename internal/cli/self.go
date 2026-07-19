package cli

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/spf13/cobra"
)

func (a *App) newSelfCommand() *cobra.Command {
	command := commandGroup("self", "Update or uninstall okit")
	command.AddCommand(a.newSelfUpdateCommand(), a.newSelfUninstallCommand())
	return command
}

func (a *App) newSelfUpdateCommand() *cobra.Command {
	options := selfmanage.UpdateOptions{}
	command := &cobra.Command{
		Use:   "update",
		Short: "Check for or install an okit update",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			updater := a.selfUpdater
			if updater == nil {
				home, executable, err := selfPaths()
				if err != nil {
					return runError(err)
				}
				updater = &selfmanage.Updater{CurrentVersion: a.version, Executable: executable, OKITHome: home}
			}
			result, err := updater.Update(context.Background(), options)
			if err != nil {
				return runError(err)
			}
			fmt.Fprintf(cmd.OutOrStdout(), "current=%s available=%s updated=%t scheduled=%t\n", result.Current, result.Available, result.Updated, result.Scheduled)
			if options.DryRun && result.Plan != "" {
				fmt.Fprintln(cmd.OutOrStdout(), result.Plan)
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

func (a *App) newSelfUninstallCommand() *cobra.Command {
	options := selfmanage.UninstallOptions{}
	command := &cobra.Command{
		Use:   "uninstall",
		Short: "Uninstall okit",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			if options.Purge && !options.Yes && !options.DryRun {
				fmt.Fprint(cmd.ErrOrStderr(), "Permanently delete OKIT_HOME and all user data? [y/N] ")
				answer, _ := bufio.NewReader(cmd.InOrStdin()).ReadString('\n')
				answer = strings.TrimSpace(strings.ToLower(answer))
				if answer != "y" && answer != "yes" {
					fmt.Fprintln(cmd.OutOrStdout(), "uninstall cancelled")
					return nil
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
			for _, target := range result.Plan {
				fmt.Fprintln(cmd.OutOrStdout(), target)
			}
			if result.Scheduled {
				fmt.Fprintln(cmd.OutOrStdout(), "uninstall scheduled")
			}
			return nil
		},
	}
	command.Flags().BoolVar(&options.Purge, "purge", false, "also remove OKIT_HOME and user data")
	command.Flags().BoolVar(&options.Yes, "yes", false, "confirm destructive removal")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "show the uninstall plan without changing files")
	return command
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
