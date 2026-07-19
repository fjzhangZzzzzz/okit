package cli

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"runtime"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	shellcfg "github.com/fjzhangZzzzzz/okit/internal/shell"
	"github.com/spf13/cobra"
)

func newShellCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("shell", "Manage shell configuration")
	for _, action := range []string{"sync", "source", "enable", "disable", "status"} {
		command.AddCommand(newShellActionCommand(action, global))
	}
	command.AddCommand(newConfigCommand("shell", global))
	return command
}

func newShellActionCommand(action string, global *globalOptions) *cobra.Command {
	var dryRun, force bool
	command := &cobra.Command{
		Use:         action + " <shell>",
		Short:       shellActionDescription(action),
		Args:        cobra.ExactArgs(1),
		Annotations: map[string]string{"formats": shellFormats(action)},
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
			presenter := newPresenter(cmd, global)
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
				if strings.HasPrefix(preview, "already ") {
					return presenter.Render(shellResultView(action, shellName, preview, dryRun))
				}
				if !confirmAction(cmd.InOrStdin(), presenter, "Modify the shell startup configuration?") {
					return presenter.Render(clioutput.View{
						Human:   clioutput.Document{Title: "Shell configuration change cancelled", Summary: "No changes were made."},
						Machine: map[string]any{"status": "cancelled", "shell": shellName, "changed": false},
					})
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
			if action == "source" {
				return presenter.Raw(result + "\n")
			}
			return presenter.Render(shellResultView(action, shellName, result, dryRun))
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

func confirmAction(stdin interface{ Read([]byte) (int, error) }, presenter *clioutput.Presenter, prompt string) bool {
	if err := presenter.Prompt(prompt + " [y/N] "); err != nil {
		return false
	}
	answer, _ := bufio.NewReader(stdin).ReadString('\n')
	answer = strings.TrimSpace(strings.ToLower(answer))
	return answer == "y" || answer == "yes"
}

func shellFormats(action string) string {
	if action == "source" {
		return "table,raw"
	}
	return "table,json"
}

func shellResultView(action, shellName, result string, dryRun bool) clioutput.View {
	if action == "status" {
		values := parseAssignments(result)
		fields := []clioutput.Field{
			{Label: "Shell", Value: values["shell"]},
			{Label: "Enabled", Value: yesNo(values["enabled"])},
			{Label: "Profile", Value: values["profile"]},
			{Label: "Managed config", Value: values["config"]},
			{Label: "Managed config exists", Value: yesNo(values["config_exists"])},
			{Label: "Repository data exists", Value: yesNo(values["repo_exists"])},
		}
		return clioutput.View{Human: clioutput.Document{Title: "Shell configuration status", Fields: fields}, Machine: values}
	}
	status := "completed"
	if strings.HasPrefix(result, "already ") {
		status = "unchanged"
	} else if dryRun {
		status = "planned"
	}
	title := "Shell " + action + " completed"
	if status == "unchanged" {
		title = "Shell configuration is unchanged."
	} else if dryRun {
		title = "Shell " + action + " plan"
	}
	summary := ""
	if dryRun {
		summary = "No changes were made."
	}
	return clioutput.View{
		Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "Shell", Value: shellName}, {Label: "Result", Value: result}}, Summary: summary},
		Machine: map[string]any{"action": action, "shell": shellName, "status": status, "result": result},
	}
}

var assignmentPattern = regexp.MustCompile(`(?:^| )(shell|enabled|profile|config|config_exists|repo_exists)=`)

func parseAssignments(value string) map[string]string {
	matches := assignmentPattern.FindAllStringSubmatchIndex(value, -1)
	result := make(map[string]string, len(matches))
	for index, match := range matches {
		start := match[1]
		if index+1 < len(matches) {
			start = matches[index][1]
		}
		end := len(value)
		if index+1 < len(matches) {
			end = matches[index+1][0]
		}
		result[value[match[2]:match[3]]] = strings.TrimSpace(value[start:end])
	}
	return result
}

func yesNo(value string) string {
	if value == "true" {
		return "yes"
	}
	if value == "false" {
		return "no"
	}
	return value
}
