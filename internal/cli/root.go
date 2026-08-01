package cli

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	"github.com/spf13/cobra"
)

type App struct {
	version         string
	buildMode       string
	upgradeRunner   upgradeRunner
	selfUninstaller selfUninstaller
	commit          string
	date            string
	stdin           io.Reader
}

const (
	BuildModeDevelopment = "development"
	BuildModeRelease     = "release"
)

const chineseHelpTemplate = `{{with (or .Long .Short)}}{{. | trimTrailingWhitespaces}}

{{end}}用法:
  {{.UseLine}}{{if .HasAvailableSubCommands}}
  {{.CommandPath}} [command]{{end}}{{if .HasAvailableSubCommands}}

可用命令:{{range .Commands}}{{if (or .IsAvailableCommand (eq .Name "help"))}}
  {{rpad .Name .NamePadding }} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableLocalFlags}}

选项:
{{.LocalFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasAvailableInheritedFlags}}

全局选项:
{{.InheritedFlags.FlagUsages | trimTrailingWhitespaces}}{{end}}{{if .HasHelpSubCommands}}

其他帮助主题:{{range .Commands}}{{if .IsAdditionalHelpTopicCommand}}
  {{rpad .CommandPath .CommandPathPadding}} {{.Short}}{{end}}{{end}}{{end}}{{if .HasAvailableSubCommands}}

使用 "{{.CommandPath}} [command] --help" 获取命令更多信息。{{end}}
`

func New(version string) *App {
	return &App{version: version, buildMode: inferBuildMode(version), stdin: os.Stdin}
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

type upgradeRunner interface {
	Run(context.Context, selfmanage.Intent, selfmanage.ProgressReporter) (selfmanage.Result, error)
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
	return commandError(2, "CLI_USAGE", message, "请查看此命令的帮助后重试。")
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
	message := "此命令的用法不正确。"
	switch {
	case strings.HasPrefix(raw, "unknown command "):
		message = strings.Replace(raw, "unknown command", "未知命令", 1)
	case strings.HasPrefix(raw, "unknown flag: "):
		message = strings.Replace(raw, "unknown flag:", "未知选项", 1)
	case strings.Contains(raw, "unknown shorthand flag"):
		message = strings.Replace(raw, "unknown shorthand flag", "未知短选项", 1)
	case (strings.Contains(raw, "accepts ") || strings.Contains(raw, "requires at least")) && strings.Contains(raw, "received 0"):
		message = "此命令缺少必需的位置参数。"
	case strings.Contains(raw, "accepts ") && strings.Contains(raw, "received"):
		message = "此命令的位置参数数量不正确。"
	case strings.Contains(raw, "required flag") && strings.Contains(raw, "not set"):
		message = "此命令缺少必需的选项。"
	}
	return clioutput.Diagnostic{
		Code: "CLI_USAGE", Message: message, Action: commandHelpAction(commandPath),
		Fields: map[string]string{"command": commandPath, "cause": raw},
	}
}

func commandHelpAction(commandPath string) string {
	return "请运行 `" + commandPath + " --help` 查看可用的位置参数和选项。"
}

func runtimeDiagnostic(err error) clioutput.Diagnostic {
	message := err.Error()
	switch {
	case strings.Contains(message, "MobaXterm installation was not found"):
		return clioutput.Diagnostic{
			Code: "MOBA_INSTALLATION_NOT_FOUND", Message: "未找到 MobaXterm 安装。",
			Action: "请运行 `okit mobaxterm status` 查看已检测到的安装。",
		}
	default:
		return clioutput.Diagnostic{
			Code: "CLI_RUNTIME", Message: "命令未能完成。",
			Action: "请使用 --verbose 重新运行以查看带标签的技术详情。",
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
		Short:         "MobaXterm 维护与 okit 安装生命周期工具",
		SilenceErrors: true,
		SilenceUsage:  true,
		Version:       a.version,
		Args:          cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
		PersistentPreRunE: func(cmd *cobra.Command, _ []string) error {
			if options.quiet && options.verbose {
				return usageError("不能同时使用 --quiet 与 --verbose")
			}
			if !containsString([]string{"table", "json", "jsonl", "csv", "raw"}, options.format) {
				return usageError("不支持输出格式 %q", options.format)
			}
			allowed := commandFormats(cmd)
			if !containsString(allowed, options.format) {
				return usageError("此命令不支持 --format %s", options.format)
			}
			newPresenter(cmd, options).Verbose("executing command", clioutput.Field{Label: "command", Value: cmd.CommandPath()})
			return nil
		},
	}
	root.SetVersionTemplate(a.versionOutput())
	root.SetHelpTemplate(chineseHelpTemplate)
	root.SetHelpCommand(&cobra.Command{Use: "help [命令]", Short: "显示任意命令的帮助"})
	root.CompletionOptions.DisableDefaultCmd = true
	root.PersistentFlags().StringVar(&options.format, "format", "table", "输出格式（按命令支持情况而定）")
	root.PersistentFlags().BoolVar(&options.noColor, "no-color", false, "禁用 ANSI 颜色")
	root.PersistentFlags().BoolVar(&options.quiet, "quiet", false, "隐藏进度与非必要提示")
	root.PersistentFlags().BoolVar(&options.verbose, "verbose", false, "显示额外诊断上下文")
	defaultHelp := root.HelpFunc()
	root.SetHelpFunc(func(cmd *cobra.Command, args []string) {
		if helpFlag := cmd.Flags().Lookup("help"); helpFlag != nil {
			helpFlag.Usage = "显示此命令的帮助"
		}
		if cmd == root {
			versionFlag := cmd.Flags().Lookup("version")
			if versionFlag != nil {
				versionFlag.Usage = "显示版本信息"
			}
		}
		formatFlag := root.PersistentFlags().Lookup("format")
		originalUsage := formatFlag.Usage
		formatFlag.Usage = "输出格式：" + strings.Join(commandFormats(cmd), ", ")
		defer func() { formatFlag.Usage = originalUsage }()
		defaultHelp(cmd, args)
	})

	root.AddCommand(
		newMobaXtermCommand(options),
		a.newUpgradeCommand(options),
		a.newUninstallCommand(options),
	)
	root.AddCommand(&cobra.Command{
		Use:    "version",
		Short:  "显示版本信息",
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
