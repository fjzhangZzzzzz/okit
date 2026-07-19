package cli

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"runtime"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	shellcfg "github.com/fjzhangZzzzzz/okit/internal/shell"
	"github.com/spf13/cobra"
)

func newShellCommand() *cobra.Command {
	command := commandGroup("shell", "Manage shell configuration")
	for _, action := range []string{"sync", "source", "enable", "disable", "status"} {
		command.AddCommand(newShellActionCommand(action))
	}
	command.AddCommand(newConfigCommand("shell"))
	return command
}

func newShellActionCommand(action string) *cobra.Command {
	var dryRun, force bool
	command := &cobra.Command{
		Use:   action + " <shell>",
		Short: shellActionDescription(action),
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			shellName := args[0]
			if !containsString([]string{"bash", "zsh", "powershell", "cmd"}, shellName) {
				return usageError("unsupported shell %q", shellName)
			}
			if runtime.GOOS != "windows" && (shellName == "cmd" || shellName == "powershell" && (action == "enable" || action == "disable" || action == "status")) {
				return usageError("shell %s %s is not supported on %s", action, shellName, runtime.GOOS)
			}
			home, err := config.Home()
			if err != nil {
				return runError(err)
			}
			userHome, err := os.UserHomeDir()
			if err != nil {
				return runError(err)
			}
			manager := shellcfg.New(home, userHome)
			if (action == "enable" || action == "disable") && !dryRun && !force {
				var preview string
				if action == "enable" {
					preview, err = manager.Enable(shellName, true)
				} else {
					preview, err = manager.Disable(shellName, true)
				}
				if err != nil {
					return runError(err)
				}
				fmt.Fprintln(cmd.OutOrStdout(), preview)
				if strings.HasPrefix(preview, "already ") {
					return nil
				}
				if !confirmAction(cmd.InOrStdin(), cmd.ErrOrStderr(), "Modify the shell startup configuration?") {
					fmt.Fprintln(cmd.OutOrStdout(), "shell configuration change cancelled")
					return nil
				}
			}
			var result string
			switch action {
			case "source":
				result, err = manager.Source(shellName)
			case "enable":
				result, err = manager.Enable(shellName, dryRun)
			case "disable":
				result, err = manager.Disable(shellName, dryRun)
			case "status":
				result, err = manager.Status(shellName)
			case "sync":
				store, storeErr := config.DefaultStore()
				if storeErr != nil {
					err = storeErr
					break
				}
				repositoryURL, ok, getErr := store.Get("shell.repo-url")
				if getErr != nil {
					err = getErr
				} else if !ok {
					err = fmt.Errorf("shell.repo-url is not configured")
				} else {
					result, err = manager.Sync(shellName, repositoryURL, dryRun)
				}
			}
			if err != nil {
				return runError(err)
			}
			fmt.Fprintln(cmd.OutOrStdout(), result)
			return nil
		},
	}
	if action == "sync" || action == "enable" || action == "disable" {
		command.Flags().BoolVar(&dryRun, "dry-run", false, "show the plan without changing files")
	}
	if action == "enable" || action == "disable" {
		command.Flags().BoolVar(&force, "force", false, "skip interactive confirmation")
	}
	return command
}

func shellActionDescription(action string) string {
	return map[string]string{
		"sync": "Synchronize shell configuration", "source": "Print shell source command",
		"enable": "Enable managed shell configuration", "disable": "Disable managed shell configuration",
		"status": "Display shell configuration status",
	}[action]
}

func confirmAction(stdin io.Reader, stderr io.Writer, prompt string) bool {
	fmt.Fprintf(stderr, "%s [y/N] ", prompt)
	answer, _ := bufio.NewReader(stdin).ReadString('\n')
	answer = strings.TrimSpace(strings.ToLower(answer))
	return answer == "y" || answer == "yes"
}
