package cli

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) newGitSyncCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("git-sync", "Synchronize Git changes")
	command.AddCommand(a.newGitSyncRunCommand(global), newGitSyncStatusCommand(global), newConfigCommand("git-sync", global))
	return command
}

func (a *App) newGitSyncRunCommand(global *globalOptions) *cobra.Command {
	options := gitsync.Options{}
	command := &cobra.Command{
		Use:         "run <path...>",
		Short:       "Synchronize one or more repositories",
		Args:        cobra.MinimumNArgs(1),
		Annotations: map[string]string{"formats": "table,json,jsonl"},
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
			presenter := newPresenter(cmd, global)
			table := &clioutput.Table{Headers: []string{"REPOSITORY", "STATUS", "REMOTE", "OPERATIONS"}}
			machine := make([]any, 0, len(results))
			for _, result := range results {
				if result.Err != nil {
					presenter.Error(clioutput.Diagnostic{
						Code: "GITSYNC_REPOSITORY_FAILED", Message: result.Plan.Root + ": " + result.Err.Error(),
						Hint: "Re-run with --verbose after checking the repository and remote configuration.",
					})
					table.Rows = append(table.Rows, []string{gitRepositoryName(result.Plan), "failed", result.Plan.RemoteRoot, "-"})
					machine = append(machine, map[string]any{"status": "error", "plan": result.Plan, "error": result.Err.Error()})
					failed++
					continue
				}
				status := "synchronized"
				if options.DryRun {
					status = "planned"
				} else if len(result.Plan.Operations) == 0 {
					status = "unchanged"
				}
				table.Rows = append(table.Rows, []string{gitRepositoryName(result.Plan), status, result.Plan.RemoteRoot, strconv.Itoa(len(result.Plan.Operations))})
				machine = append(machine, map[string]any{"status": status, "plan": result.Plan, "transport": result.Transport})
				succeeded++
			}
			summary := fmt.Sprintf("%d succeeded, %d failed.", succeeded, failed)
			if options.DryRun {
				summary += " No changes were made."
			}
			if err := presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: gitSyncTitle(options.DryRun), Table: table, Summary: summary},
				Machine: machine,
			}); err != nil {
				return runError(err)
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

func newGitSyncStatusCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use:         "status",
		Short:       "Display Git synchronization configuration",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
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
			document := clioutput.Document{Title: "Git synchronization configuration"}
			if len(keys) == 0 {
				document.Title = ""
				document.Empty = &clioutput.EmptyState{
					Message: "No git-sync configuration found.",
					Hint:    "Configure it with `okit git-sync config set <key> <value>`.",
				}
			} else {
				table := &clioutput.Table{Headers: []string{"KEY", "VALUE"}}
				for _, key := range keys {
					table.Rows = append(table.Rows, []string{key, values[key]})
				}
				document.Table = table
			}
			machine := make(map[string]string, len(keys))
			for _, key := range keys {
				machine[key] = values[key]
			}
			return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: machine})
		},
	}
}

func gitRepositoryName(plan gitsync.Plan) string {
	if plan.Repository != "" {
		return plan.Repository
	}
	if plan.Root != "" {
		return plan.Root
	}
	return "unknown"
}

func gitSyncTitle(dryRun bool) string {
	if dryRun {
		return "Git synchronization plan"
	}
	return "Git synchronization result"
}
