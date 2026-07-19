package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	"github.com/spf13/cobra"
)

func (a *App) newGitSyncCommand() *cobra.Command {
	command := commandGroup("git-sync", "Synchronize Git changes")
	command.AddCommand(a.newGitSyncRunCommand(), newGitSyncStatusCommand(), newConfigCommand("git-sync"))
	return command
}

func (a *App) newGitSyncRunCommand() *cobra.Command {
	options := gitsync.Options{}
	command := &cobra.Command{
		Use:   "run <path...>",
		Short: "Synchronize one or more repositories",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, paths []string) error {
			if cmd.Flags().Changed("port") && options.Port == 0 {
				return usageError("--port must be between 1 and 65535")
			}
			store, err := config.DefaultStore()
			if err != nil {
				return runError(err)
			}
			for key, target := range map[string]*string{
				"host": &options.Host, "user": &options.User, "target-root": &options.TargetRoot, "transport": &options.Transport,
			} {
				if *target == "" {
					value, ok, getErr := store.Get("git-sync." + key)
					if getErr != nil {
						return runError(getErr)
					}
					if ok {
						*target = value
					}
				}
			}
			if options.Port == 0 {
				value, ok, getErr := store.Get("git-sync.port")
				if getErr != nil {
					return runError(getErr)
				}
				if ok {
					port, parseErr := strconv.Atoi(value)
					if parseErr != nil || port < 1 || port > 65535 {
						return runError(fmt.Errorf("git-sync.port must be an integer from 1 to 65535"))
					}
					options.Port = port
				} else {
					options.Port = 22
				}
			}
			if options.Port < 1 || options.Port > 65535 {
				return usageError("--port must be between 1 and 65535")
			}
			if options.Transport == "" {
				options.Transport = "auto"
			}
			if options.Host == "" || options.TargetRoot == "" {
				return usageError("git-sync run requires --host and --target-root")
			}
			results := a.gitSync.Run(context.Background(), paths, options)
			succeeded, failed := 0, 0
			for _, result := range results {
				if result.Err != nil {
					fmt.Fprintf(cmd.ErrOrStderr(), "%s: %v\n", result.Plan.Root, result.Err)
					failed++
					continue
				}
				encoded, _ := json.Marshal(result.Plan)
				fmt.Fprintln(cmd.OutOrStdout(), string(encoded))
				succeeded++
			}
			if failed > 0 && succeeded > 0 {
				return exitCode(3)
			}
			if failed > 0 {
				return exitCode(1)
			}
			return nil
		},
	}
	command.Flags().StringVar(&options.Host, "host", "", "remote host")
	command.Flags().StringVar(&options.User, "user", "", "remote user")
	command.Flags().StringVar(&options.TargetRoot, "target-root", "", "remote repository root")
	command.Flags().StringVar(&options.Transport, "transport", "", "transport: auto, rsync, or sftp")
	command.Flags().IntVar(&options.Port, "port", 0, "remote port")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "show the synchronization plan without changing files")
	return command
}

func newGitSyncStatusCommand() *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Display Git synchronization configuration",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			store, err := config.DefaultStore()
			if err != nil {
				return runError(err)
			}
			values, err := store.List()
			if err != nil {
				return runError(err)
			}
			keys := make([]string, 0)
			for key := range values {
				if strings.HasPrefix(key, "git-sync.") {
					keys = append(keys, key)
				}
			}
			sort.Strings(keys)
			for _, key := range keys {
				fmt.Fprintf(cmd.OutOrStdout(), "%s=%s\n", key, values[key])
			}
			return nil
		},
	}
}
