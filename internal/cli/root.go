package cli

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/spf13/cobra"
)

type App struct {
	version         string
	gitSync         gitSyncService
	selfUpdater     selfUpdater
	selfUninstaller selfUninstaller
	commit          string
	date            string
	stdin           io.Reader
}

func New(version string) *App {
	return &App{version: version, gitSync: gitsync.NewService(nil, nil), stdin: os.Stdin}
}

func NewBuild(version, commit, date string) *App {
	app := New(version)
	app.commit, app.date = commit, date
	return app
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
	code int
	err  error
}

func (e *exitError) Error() string {
	if e.err == nil {
		return ""
	}
	return e.err.Error()
}

func usageError(format string, args ...any) error {
	return &exitError{code: 2, err: fmt.Errorf(format, args...)}
}

func runError(err error) error {
	return &exitError{code: 1, err: err}
}

func exitCode(code int) error {
	return &exitError{code: code}
}

func (a *App) Run(args []string, stdout, stderr io.Writer) int {
	root := a.newRootCommand()
	root.SetArgs(args)
	root.SetOut(stdout)
	root.SetErr(stderr)
	root.SetIn(a.stdin)
	if err := root.Execute(); err != nil {
		var coded *exitError
		if errors.As(err, &coded) {
			if coded.err != nil {
				fmt.Fprintln(stderr, coded.err)
			}
			return coded.code
		}
		fmt.Fprintln(stderr, err)
		return 2
	}
	return 0
}

type globalOptions struct {
	format  string
	noColor bool
	quiet   bool
	verbose bool
}

func (a *App) newRootCommand() *cobra.Command {
	options := &globalOptions{format: "table"}
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
			if !containsString([]string{"table", "json", "csv"}, options.format) {
				return usageError("unsupported format %q", options.format)
			}
			allowed := strings.Split(cmd.Annotations["formats"], ",")
			if len(allowed) == 1 && allowed[0] == "" {
				allowed = []string{"table"}
			}
			if !containsString(allowed, options.format) {
				return usageError("--format %s is not supported by this command", options.format)
			}
			if options.quiet {
				cmd.Root().SetOut(io.Discard)
			}
			if options.verbose {
				fmt.Fprintf(cmd.ErrOrStderr(), "okit: command=%s\n", cmd.CommandPath())
			}
			return nil
		},
	}
	root.SetVersionTemplate(a.versionOutput())
	root.CompletionOptions.DisableDefaultCmd = true
	root.PersistentFlags().StringVar(&options.format, "format", "table", "output format: table, json, or csv (where supported)")
	root.PersistentFlags().BoolVar(&options.noColor, "no-color", false, "disable ANSI colors")
	root.PersistentFlags().BoolVar(&options.quiet, "quiet", false, "suppress normal output")
	root.PersistentFlags().BoolVar(&options.verbose, "verbose", false, "enable diagnostic output")

	root.AddCommand(
		a.newInfoCommand(options),
		newHexCommand(),
		newPECommand(options),
		a.newGitSyncCommand(),
		newShellCommand(),
		newMobaXtermCommand(),
		a.newSelfCommand(),
	)
	root.AddCommand(&cobra.Command{
		Use:    "version",
		Short:  "Display version information",
		Hidden: true,
		Args:   cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			fmt.Fprint(cmd.OutOrStdout(), a.versionOutput())
			return nil
		},
	})
	return root
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
