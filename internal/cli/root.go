package cli

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/spf13/cobra"
)

type App struct {
	version         string
	buildMode       string
	gitSync         gitSyncService
	selfUpdater     selfUpdater
	selfUninstaller selfUninstaller
	commit          string
	date            string
	stdin           io.Reader
}

const (
	BuildModeDevelopment = "development"
	BuildModeRelease     = "release"
)

func New(version string) *App {
	return &App{version: version, buildMode: inferBuildMode(version), gitSync: gitsync.NewService(nil, nil), stdin: os.Stdin}
}

func NewBuild(version, commit, date string) *App {
	app := New(version)
	app.commit, app.date = commit, date
	return app
}

func NewBuildMode(version, commit, date, buildMode string) *App {
	app := NewBuild(version, commit, date)
	if buildMode == BuildModeRelease {
		app.buildMode = BuildModeRelease
	} else {
		app.buildMode = BuildModeDevelopment
	}
	return app
}

func inferBuildMode(version string) string {
	if selfmanage.ValidateVersion(version) == nil {
		return BuildModeRelease
	}
	return BuildModeDevelopment
}

type gitSyncService interface {
	Run(context.Context, []string, gitsync.Options) []gitsync.Result
}

type selfUpdater interface {
	Update(context.Context, selfmanage.UpdateOptions) (selfmanage.UpdateResult, error)
}

type selfUninstaller interface {
	Uninstall(selfmanage.UninstallOptions) (selfmanage.UninstallResult, error)
}

type exitError struct {
	code       int
	diagnostic clioutput.Diagnostic
	cause      error
}

func (e *exitError) Error() string {
	if e.diagnostic.Message == "" {
		return ""
	}
	return e.diagnostic.Message
}

func usageError(format string, args ...any) error {
	message := fmt.Sprintf(format, args...)
	if strings.HasPrefix(message, "--") {
		message = "The " + message
	} else {
		message = upperFirstASCII(message)
	}
	return commandError(2, "CLI_USAGE", message, "Review this command's help and try again.")
}

func upperFirstASCII(value string) string {
	if value == "" || value[0] < 'a' || value[0] > 'z' {
		return value
	}
	return string(value[0]-('a'-'A')) + value[1:]
}

func runError(err error) error {
	diagnostic := runtimeDiagnostic(err)
	return &exitError{code: 1, diagnostic: diagnostic, cause: err}
}

func domainError(code, message, action string) error {
	return commandError(1, code, message, action)
}

func commandError(exitCode int, code, message, action string) error {
	return &exitError{code: exitCode, diagnostic: clioutput.Diagnostic{Code: code, Message: message, Action: action}}
}

func exitCode(code int) error {
	return &exitError{code: code}
}

func (a *App) Run(args []string, stdout, stderr io.Writer) int {
	options := &globalOptions{format: "table"}
	root := a.newRootCommandWithOptions(options)
	root.SetArgs(args)
	root.SetOut(stdout)
	root.SetErr(stderr)
	root.SetIn(a.stdin)
	executed, err := root.ExecuteC()
	if err != nil {
		commandPath := "okit"
		if executed != nil {
			commandPath = executed.CommandPath()
		}
		presenter := newPresenter(root, options)
		var coded *exitError
		if errors.As(err, &coded) {
			if coded.diagnostic.Message != "" {
				if coded.diagnostic.Fields == nil {
					coded.diagnostic.Fields = map[string]string{"command": commandPath}
				}
				if coded.cause != nil {
					presenter.Verbose("underlying failure", clioutput.Field{Label: "cause", Value: coded.cause.Error()})
				}
				if coded.code == 2 && coded.diagnostic.Code == "CLI_USAGE" {
					coded.diagnostic.Action = commandHelpAction(commandPath)
				}
				presenter.Error(coded.diagnostic)
			}
			return coded.code
		}
		diagnostic := cobraUsageDiagnostic(err, commandPath)
		presenter.Error(diagnostic)
		return 2
	}
	return 0
}

func cobraUsageDiagnostic(err error, commandPath string) clioutput.Diagnostic {
	raw := err.Error()
	message := "This command couldn't be used as written."
	switch {
	case strings.HasPrefix(raw, "unknown command "):
		message = strings.Replace(raw, "unknown command", "Unknown command", 1)
	case strings.HasPrefix(raw, "unknown flag: "):
		message = strings.Replace(raw, "unknown flag:", "Unknown option", 1)
	case strings.Contains(raw, "unknown shorthand flag"):
		message = strings.Replace(raw, "unknown shorthand flag", "Unknown short option", 1)
	case (strings.Contains(raw, "accepts ") || strings.Contains(raw, "requires at least")) && strings.Contains(raw, "received 0"):
		message = "This command is missing a required argument."
	case strings.Contains(raw, "accepts ") && strings.Contains(raw, "received"):
		message = "This command received the wrong number of arguments."
	case strings.Contains(raw, "required flag") && strings.Contains(raw, "not set"):
		message = "This command is missing a required option."
	}
	return clioutput.Diagnostic{
		Code: "CLI_USAGE", Message: message, Action: commandHelpAction(commandPath),
		Fields: map[string]string{"command": commandPath, "cause": raw},
	}
}

func commandHelpAction(commandPath string) string {
	return "Run `" + commandPath + " --help` to review the available arguments and options."
}

func runtimeDiagnostic(err error) clioutput.Diagnostic {
	message := err.Error()
	switch {
	case strings.Contains(message, "shell.repo-url is not configured"):
		return clioutput.Diagnostic{
			Code: "SHELL_REPOSITORY_NOT_CONFIGURED", Message: "The shell configuration repository isn't configured.",
			Action: "Set it with `okit shell config set repo-url <url>`.",
		}
	case strings.Contains(message, "MobaXterm installation was not found"):
		return clioutput.Diagnostic{
			Code: "MOBA_INSTALLATION_NOT_FOUND", Message: "MobaXterm installation was not found",
			Action: "Run `okit mobaxterm status` to inspect detected installations.",
		}
	default:
		return clioutput.Diagnostic{
			Code: "CLI_RUNTIME", Message: "The command couldn't be completed.",
			Action: "Re-run with --verbose for the underlying diagnostic context.",
		}
	}
}

type globalOptions struct {
	format  string
	noColor bool
	quiet   bool
	verbose bool
}

func (a *App) newRootCommand() *cobra.Command {
	return a.newRootCommandWithOptions(&globalOptions{format: "table"})
}

func (a *App) newRootCommandWithOptions(options *globalOptions) *cobra.Command {
	root := &cobra.Command{
		Use:           "okit",
		Short:         "Cross-platform developer toolkit",
		SilenceErrors: true,
		SilenceUsage:  true,
		Version:       a.version,
		Args:          cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
		PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
			if options.quiet && options.verbose {
				return usageError("--quiet and --verbose are mutually exclusive")
			}
			if !containsString([]string{"table", "json", "jsonl", "csv", "raw"}, options.format) {
				return usageError("unsupported format %q", options.format)
			}
			allowed := commandFormats(cmd)
			if !containsString(allowed, options.format) {
				return usageError("--format %s is not supported by this command", options.format)
			}
			newPresenter(cmd, options).Verbose("executing command", clioutput.Field{Label: "command", Value: cmd.CommandPath()})
			return nil
		},
	}
	root.SetVersionTemplate(a.versionOutput())
	root.CompletionOptions.DisableDefaultCmd = true
	root.PersistentFlags().StringVar(&options.format, "format", "table", "output format (where supported)")
	root.PersistentFlags().BoolVar(&options.noColor, "no-color", false, "disable ANSI colors")
	root.PersistentFlags().BoolVar(&options.quiet, "quiet", false, "hide progress and nonessential hints")
	root.PersistentFlags().BoolVar(&options.verbose, "verbose", false, "show additional diagnostic context")
	defaultHelp := root.HelpFunc()
	root.SetHelpFunc(func(cmd *cobra.Command, args []string) {
		formatFlag := root.PersistentFlags().Lookup("format")
		originalUsage := formatFlag.Usage
		formatFlag.Usage = "output format: " + strings.Join(commandFormats(cmd), ", ")
		defer func() { formatFlag.Usage = originalUsage }()
		defaultHelp(cmd, args)
	})

	root.AddCommand(
		a.newInfoCommand(options),
		newHexCommand(options),
		newPECommand(options),
		a.newGitSyncCommand(options),
		newShellCommand(options),
		newMobaXtermCommand(options),
		a.newSelfCommand(options),
	)
	root.AddCommand(&cobra.Command{
		Use:    "version",
		Short:  "Display version information",
		Hidden: true,
		Args:   cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return newPresenter(cmd, options).Raw(a.versionOutput())
		},
	})
	return root
}

func commandFormats(cmd *cobra.Command) []string {
	allowed := strings.Split(cmd.Annotations["formats"], ",")
	if len(allowed) == 1 && allowed[0] == "" {
		return []string{"table"}
	}
	return allowed
}

func newPresenter(cmd *cobra.Command, options *globalOptions) *clioutput.Presenter {
	return clioutput.New(cmd.OutOrStdout(), cmd.ErrOrStderr(), clioutput.Policy{
		Format: options.format, Quiet: options.quiet, Verbose: options.verbose, NoColor: options.noColor,
	})
}

func commandGroup(use, short string) *cobra.Command {
	return &cobra.Command{
		Use:   use,
		Short: short,
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}
}

func (a *App) versionOutput() string {
	output := fmt.Sprintf("okit %s\n", a.version)
	if a.commit != "" || a.date != "" {
		output += fmt.Sprintf("commit %s\nbuilt %s\n", a.commit, a.date)
	}
	return output
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
