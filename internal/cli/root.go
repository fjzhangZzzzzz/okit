package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/appinfo"
	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/gitsync"
	hexdump "github.com/fjzhangZzzzzz/okit/internal/hex"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/theme"
	"github.com/fjzhangZzzzzz/okit/internal/peinspect"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
	shellcfg "github.com/fjzhangZzzzzz/okit/internal/shell"
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

func (a *App) Run(args []string, stdout, stderr io.Writer) int {
	global, remaining, err := parseGlobalOptions(args)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	args = remaining
	if global.quiet {
		stdout = io.Discard
	}
	if global.verbose && len(args) > 0 {
		fmt.Fprintf(stderr, "okit: command=%s\n", args[0])
	}
	if global.format != "" && global.format != "table" {
		if len(args) >= 2 && args[0] == "pe" && args[1] == "inspect" {
			args = append(args, "--format", global.format)
		} else if len(args) >= 1 && args[0] == "info" {
			// info receives the global format directly.
		} else {
			fmt.Fprintf(stderr, "--format %s is not supported by this command\n", global.format)
			return 2
		}
	}
	if len(args) == 0 || args[0] == "--help" || args[0] == "-h" || args[0] == "help" {
		printHelp(stdout)
		return 0
	}
	if args[0] == "--version" || args[0] == "version" {
		fmt.Fprintf(stdout, "okit %s\n", a.version)
		if a.commit != "" || a.date != "" {
			fmt.Fprintf(stdout, "commit %s\nbuilt %s\n", a.commit, a.date)
		}
		return 0
	}
	switch args[0] {
	case "info":
		return a.runInfo(args[1:], global.format, stdout, stderr)
	case "hex":
		return runHex(args[1:], stdout, stderr)
	case "pe":
		return runPE(args[1:], stdout, stderr)
	case "shell":
		return runShell(args[1:], a.stdin, stdout, stderr)
	case "git-sync":
		return a.runGitSync(args[1:], stdout, stderr)
	case "mobaxterm":
		return runMobaXterm(args[1:], a.stdin, stdout, stderr)
	case "self":
		return a.runSelf(args[1:], stdout, stderr)
	default:
		fmt.Fprintf(stderr, "unknown command %q\n", args[0])
		return 2
	}
}

func (a *App) runInfo(args []string, format string, stdout, stderr io.Writer) int {
	if format == "" {
		format = "table"
	}
	for index := 0; index < len(args); index++ {
		switch args[index] {
		case "--format":
			index++
			if index >= len(args) {
				fmt.Fprintln(stderr, "--format requires a value")
				return 2
			}
			format = args[index]
		case "--help", "-h":
			fmt.Fprintln(stdout, "Usage: okit info [--format table|json]")
			return 0
		default:
			fmt.Fprintf(stderr, "unknown info option %q\n", args[index])
			return 2
		}
	}
	if format != "table" && format != "json" {
		fmt.Fprintf(stderr, "--format %s is not supported by info\n", format)
		return 2
	}
	collector := appinfo.NewCollector(appinfo.Build{Version: a.version, Commit: a.commit, Built: a.date})
	info, err := collector.Collect()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	if format == "json" {
		if err := appinfo.WriteJSON(stdout, info); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		return 0
	}
	appinfo.WriteText(stdout, stderr, info)
	return 0
}

type globalOptions struct {
	format  string
	quiet   bool
	verbose bool
}

func parseGlobalOptions(args []string) (globalOptions, []string, error) {
	options := globalOptions{}
	index := 0
	for index < len(args) {
		switch args[index] {
		case "--no-color":
			index++
		case "--quiet":
			options.quiet = true
			index++
		case "--verbose":
			options.verbose = true
			index++
		case "--format":
			index++
			if index >= len(args) {
				return options, nil, fmt.Errorf("--format requires a value")
			}
			options.format = args[index]
			if options.format != "table" && options.format != "json" && options.format != "csv" {
				return options, nil, fmt.Errorf("unsupported format %q", options.format)
			}
			index++
		default:
			if options.quiet && options.verbose {
				return options, nil, fmt.Errorf("--quiet and --verbose are mutually exclusive")
			}
			return options, args[index:], nil
		}
	}
	if options.quiet && options.verbose {
		return options, nil, fmt.Errorf("--quiet and --verbose are mutually exclusive")
	}
	return options, nil, nil
}

func (a *App) runSelf(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: okit self <update|uninstall>")
		return 2
	}
	switch args[0] {
	case "update":
		options := selfmanage.UpdateOptions{}
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--check":
				options.Check = true
			case "--dry-run":
				options.DryRun = true
			case "--prerelease":
				options.Prerelease = true
			case "--version":
				i++
				if i >= len(args) {
					fmt.Fprintln(stderr, "--version requires a value")
					return 2
				}
				options.Version = args[i]
			default:
				fmt.Fprintf(stderr, "unknown self update option %q\n", args[i])
				return 2
			}
		}
		updater := a.selfUpdater
		if updater == nil {
			home, executable, err := selfPaths()
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
			updater = &selfmanage.Updater{CurrentVersion: a.version, Executable: executable, OKITHome: home}
		}
		result, err := updater.Update(context.Background(), options)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintf(stdout, "current=%s available=%s updated=%t scheduled=%t\n", result.Current, result.Available, result.Updated, result.Scheduled)
		if options.DryRun && result.Plan != "" {
			fmt.Fprintln(stdout, result.Plan)
		}
		return 0
	case "uninstall":
		options := selfmanage.UninstallOptions{}
		for _, arg := range args[1:] {
			switch arg {
			case "--purge":
				options.Purge = true
			case "--yes":
				options.Yes = true
			case "--dry-run":
				options.DryRun = true
			default:
				fmt.Fprintf(stderr, "unknown self uninstall option %q\n", arg)
				return 2
			}
		}
		if options.Purge && !options.Yes && !options.DryRun {
			fmt.Fprint(stderr, "Permanently delete OKIT_HOME and all user data? [y/N] ")
			answer, _ := bufio.NewReader(a.stdin).ReadString('\n')
			answer = strings.TrimSpace(strings.ToLower(answer))
			if answer != "y" && answer != "yes" {
				fmt.Fprintln(stdout, "uninstall cancelled")
				return 0
			}
			options.Yes = true
		}
		uninstaller := a.selfUninstaller
		if uninstaller == nil {
			home, executable, err := selfPaths()
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
			uninstaller = &selfmanage.Uninstaller{OKITHome: home, Executable: executable}
		}
		result, err := uninstaller.Uninstall(options)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		for _, target := range result.Plan {
			fmt.Fprintln(stdout, target)
		}
		if result.Scheduled {
			fmt.Fprintln(stdout, "uninstall scheduled")
		}
		return 0
	default:
		fmt.Fprintf(stderr, "unknown self action %q\n", args[0])
		return 2
	}
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

func runMobaXterm(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if runtime.GOOS != "windows" {
		fmt.Fprintln(stderr, "mobaxterm is only supported on Windows")
		return 2
	}
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: okit mobaxterm <status|theme|license>")
		return 2
	}
	home, err := config.Home()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	service := mobaxterm.Service{GOOS: runtime.GOOS, OKITHome: home}
	if args[0] == "status" {
		candidates, err := service.Status()
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		data, _ := json.MarshalIndent(candidates, "", "  ")
		fmt.Fprintln(stdout, string(data))
		return 0
	}
	if args[0] == "theme" {
		return runMobaTheme(service, home, args[1:], stdin, stdout, stderr)
	}
	if args[0] == "license" {
		return runMobaLicense(service, args[1:], stdin, stdout, stderr)
	}
	fmt.Fprintf(stderr, "unknown mobaxterm action %q\n", args[0])
	return 2
}

func runMobaTheme(service mobaxterm.Service, home string, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "theme requires list, apply, restore, or cache")
		return 2
	}
	cachePath := filepath.Join(home, "cache", "mobaxterm", "themes")
	backupDir := filepath.Join(home, "backups", "mobaxterm")
	switch args[0] {
	case "list":
		search, limit := "", 20
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--search":
				i++
				if i >= len(args) {
					fmt.Fprintln(stderr, "--search requires a value")
					return 2
				}
				search = args[i]
			case "--limit":
				i++
				value, ok := parseNonNegative(args, i, "--limit", stderr)
				if !ok || value == 0 {
					return 2
				}
				limit = int(value)
			default:
				fmt.Fprintf(stderr, "unknown theme list option %q\n", args[i])
				return 2
			}
		}
		schemes, err := theme.List(cachePath, search, limit)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		for _, scheme := range schemes {
			fmt.Fprintln(stdout, scheme)
		}
		return 0
	case "cache":
		if len(args) != 2 {
			fmt.Fprintln(stderr, "theme cache requires update, clean, or status")
			return 2
		}
		switch args[1] {
		case "update":
			if err := theme.UpdateCache(cachePath); err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
		case "clean":
			if err := theme.CleanCache(home, cachePath, false); err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
		case "status":
			info, err := os.Stat(cachePath)
			if err != nil {
				fmt.Fprintf(stdout, "cache_exists=false path=%s\n", cachePath)
			} else {
				fmt.Fprintf(stdout, "cache_exists=true modified=%s path=%s\n", info.ModTime().UTC().Format(time.RFC3339), cachePath)
			}
		default:
			fmt.Fprintf(stderr, "unknown cache action %q\n", args[1])
			return 2
		}
		return 0
	case "apply":
		if len(args) < 2 {
			fmt.Fprintln(stderr, "theme apply requires a name")
			return 2
		}
		name, dryRun, noBackup, force := args[1], false, false, false
		for _, arg := range args[2:] {
			switch arg {
			case "--dry-run":
				dryRun = true
			case "--no-backup":
				noBackup = true
			case "--force":
				force = true
			default:
				fmt.Fprintf(stderr, "unknown theme apply option %q\n", arg)
				return 2
			}
		}
		scheme, err := theme.Resolve(cachePath, name)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		candidates, err := service.Status()
		if err != nil || len(candidates) == 0 {
			fmt.Fprintln(stderr, "MobaXterm installation was not found")
			return 1
		}
		if !dryRun && !force && !confirmAction(stdin, stderr, "Apply the selected MobaXterm theme?") {
			fmt.Fprintln(stdout, "theme apply cancelled")
			return 0
		}
		var result theme.Result
		if noBackup {
			result, err = theme.ApplyWithoutBackup(candidates[0].ConfigPath, scheme, dryRun, nil)
		} else {
			result, err = theme.Apply(candidates[0].ConfigPath, scheme, backupDir, dryRun, nil)
		}
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintf(stdout, "changed=%t backup=%s\n", result.Changed, result.BackupPath)
		return 0
	case "restore":
		backup, dryRun, force := "", false, false
		var err error
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--backup":
				i++
				if i >= len(args) {
					fmt.Fprintln(stderr, "--backup requires a value")
					return 2
				}
				backup = args[i]
			case "--dry-run":
				dryRun = true
			case "--force":
				force = true
			default:
				fmt.Fprintf(stderr, "unknown restore option %q\n", args[i])
				return 2
			}
		}
		if backup == "" {
			backup, err = theme.LatestBackup(backupDir)
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
		}
		candidates, err := service.Status()
		if err != nil || len(candidates) == 0 {
			fmt.Fprintln(stderr, "MobaXterm installation was not found")
			return 1
		}
		if !dryRun && !force && !confirmAction(stdin, stderr, "Restore the MobaXterm configuration backup?") {
			fmt.Fprintln(stdout, "theme restore cancelled")
			return 0
		}
		if err := theme.Restore(candidates[0].ConfigPath, backup, dryRun); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintf(stdout, "restored=%s\n", backup)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown theme action %q\n", args[0])
		return 2
	}
}

func runMobaLicense(service mobaxterm.Service, args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "license requires generate, deploy, inspect, or verify")
		return 2
	}
	switch args[0] {
	case "generate":
		username, version, output := flagValue(args[1:], "--username"), flagValue(args[1:], "--version"), flagValue(args[1:], "--output")
		if username == "" || version == "" || output == "" {
			fmt.Fprintln(stderr, "generate requires --username, --version, and --output")
			return 2
		}
		key, err := license.Generate(username, version)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		if err := license.CreateFile(output, key); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintln(stdout, output)
		return 0
	case "deploy":
		username, version := flagValue(args[1:], "--username"), flagValue(args[1:], "--version")
		if username == "" {
			fmt.Fprintln(stderr, "deploy requires --username")
			return 2
		}
		dryRun := contains(args[1:], "--dry-run")
		if !dryRun {
			plan, err := service.DeployLicense(username, version, true)
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
			fmt.Fprintln(stdout, plan)
			if !contains(args[1:], "--force") && !confirmAction(stdin, stderr, "Deploy the MobaXterm license file?") {
				fmt.Fprintln(stdout, "license deploy cancelled")
				return 0
			}
		}
		result, err := service.DeployLicense(username, version, dryRun)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintln(stdout, result)
		return 0
	case "inspect", "verify":
		if len(args) < 2 {
			fmt.Fprintf(stderr, "%s requires a file or key\n", args[0])
			return 2
		}
		key := args[1]
		if info, err := os.Stat(key); err == nil && !info.IsDir() {
			key, err = license.ReadFile(key)
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
		}
		if args[0] == "inspect" {
			info, err := license.InspectKey(key)
			if err != nil {
				fmt.Fprintln(stderr, err)
				return 1
			}
			data, _ := json.MarshalIndent(info, "", "  ")
			fmt.Fprintln(stdout, string(data))
			return 0
		}
		username, version := flagValue(args[2:], "--username"), flagValue(args[2:], "--version")
		if username == "" || version == "" {
			fmt.Fprintln(stderr, "verify requires --username and --version")
			return 2
		}
		ok, err := license.Verify(key, username, version)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		if !ok {
			fmt.Fprintln(stderr, "license verification failed")
			return 1
		}
		fmt.Fprintln(stdout, "valid")
		return 0
	default:
		fmt.Fprintf(stderr, "unknown license action %q\n", args[0])
		return 2
	}
}

func flagValue(args []string, name string) string {
	for i := 0; i+1 < len(args); i++ {
		if args[i] == name {
			return args[i+1]
		}
	}
	return ""
}
func contains(args []string, value string) bool {
	for _, arg := range args {
		if arg == value {
			return true
		}
	}
	return false
}

func (a *App) runGitSync(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: okit git-sync <run|status|config>")
		return 2
	}
	store, err := config.DefaultStore()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	switch args[0] {
	case "config":
		return runConfig(store, "git-sync", args[1:], stdout, stderr)
	case "status":
		values, listErr := store.List()
		if listErr != nil {
			fmt.Fprintln(stderr, listErr)
			return 1
		}
		keys := make([]string, 0)
		for key := range values {
			if strings.HasPrefix(key, "git-sync.") {
				keys = append(keys, key)
			}
		}
		sort.Strings(keys)
		for _, key := range keys {
			fmt.Fprintf(stdout, "%s=%s\n", key, values[key])
		}
		return 0
	case "run":
		// Continue below.
	default:
		fmt.Fprintf(stderr, "unknown git-sync action %q\n", args[0])
		return 2
	}

	options := gitsync.Options{}
	paths := make([]string, 0)
	for i := 1; i < len(args); i++ {
		var target *string
		switch args[i] {
		case "--host":
			target = &options.Host
		case "--user":
			target = &options.User
		case "--target-root":
			target = &options.TargetRoot
		case "--transport":
			target = &options.Transport
		case "--port":
			name := args[i]
			i++
			value, ok := parseNonNegative(args, i, name, stderr)
			if !ok || value == 0 {
				if ok {
					fmt.Fprintf(stderr, "%s must be greater than zero\n", name)
				}
				return 2
			}
			options.Port = int(value)
			continue
		case "--dry-run":
			options.DryRun = true
			continue
		default:
			if strings.HasPrefix(args[i], "-") {
				fmt.Fprintf(stderr, "unknown git-sync option %q\n", args[i])
				return 2
			}
			paths = append(paths, args[i])
			continue
		}
		i++
		if i >= len(args) {
			fmt.Fprintf(stderr, "%s requires a value\n", args[i-1])
			return 2
		}
		*target = args[i]
	}
	for key, target := range map[string]*string{
		"host": &options.Host, "user": &options.User, "target-root": &options.TargetRoot, "transport": &options.Transport,
	} {
		if *target == "" {
			value, ok, getErr := store.Get("git-sync." + key)
			if getErr != nil {
				fmt.Fprintln(stderr, getErr)
				return 1
			}
			if ok {
				*target = value
			}
		}
	}
	if options.Port == 0 {
		value, ok, getErr := store.Get("git-sync.port")
		if getErr != nil {
			fmt.Fprintln(stderr, getErr)
			return 1
		}
		if ok {
			port, parseErr := strconv.Atoi(value)
			if parseErr != nil || port < 1 || port > 65535 {
				fmt.Fprintln(stderr, "git-sync.port must be an integer from 1 to 65535")
				return 1
			}
			options.Port = port
		} else {
			options.Port = 22
		}
	}
	if options.Port > 65535 {
		fmt.Fprintln(stderr, "--port must be between 1 and 65535")
		return 2
	}
	if options.Transport == "" {
		options.Transport = "auto"
	}
	if len(paths) == 0 || options.Host == "" || options.TargetRoot == "" {
		fmt.Fprintln(stderr, "git-sync run requires paths, --host, and --target-root")
		return 2
	}
	results := a.gitSync.Run(context.Background(), paths, options)
	succeeded, failed := 0, 0
	for _, result := range results {
		if result.Err != nil {
			fmt.Fprintf(stderr, "%s: %v\n", result.Plan.Root, result.Err)
			failed++
			continue
		}
		encoded, _ := json.Marshal(result.Plan)
		fmt.Fprintln(stdout, string(encoded))
		succeeded++
	}
	if failed > 0 && succeeded > 0 {
		return 3
	}
	if failed > 0 {
		return 1
	}
	return 0
}

func runShell(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: okit shell <sync|source|enable|disable|status|config>")
		return 2
	}
	store, err := config.DefaultStore()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	if args[0] == "config" {
		return runConfig(store, "shell", args[1:], stdout, stderr)
	}
	if len(args) < 2 {
		fmt.Fprintf(stderr, "shell %s requires a shell name\n", args[0])
		return 2
	}
	shellName := args[1]
	if shellName != "bash" && shellName != "zsh" && shellName != "powershell" && shellName != "cmd" {
		fmt.Fprintf(stderr, "unsupported shell %q\n", shellName)
		return 2
	}
	if runtime.GOOS != "windows" && (shellName == "cmd" || shellName == "powershell" && (args[0] == "enable" || args[0] == "disable" || args[0] == "status")) {
		fmt.Fprintf(stderr, "shell %s %s is not supported on %s\n", args[0], shellName, runtime.GOOS)
		return 2
	}
	dryRun, force := false, false
	for _, arg := range args[2:] {
		switch arg {
		case "--dry-run":
			dryRun = true
		case "--force":
			force = true
		default:
			fmt.Fprintf(stderr, "unknown shell option %q\n", arg)
			return 2
		}
	}
	home, err := config.Home()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	userHome, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	manager := shellcfg.New(home, userHome)
	action := args[0]
	if (action == "enable" || action == "disable") && !dryRun && !force {
		var preview string
		if action == "enable" {
			preview, err = manager.Enable(shellName, true)
		} else {
			preview, err = manager.Disable(shellName, true)
		}
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		fmt.Fprintln(stdout, preview)
		if strings.HasPrefix(preview, "already ") {
			return 0
		}
		if !confirmAction(stdin, stderr, "Modify the shell startup configuration?") {
			fmt.Fprintln(stdout, "shell configuration change cancelled")
			return 0
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
		repositoryURL, ok, getErr := store.Get("shell.repo-url")
		if getErr != nil {
			err = getErr
		} else if !ok {
			err = fmt.Errorf("shell.repo-url is not configured")
		} else {
			result, err = manager.Sync(shellName, repositoryURL, dryRun)
		}
	default:
		fmt.Fprintf(stderr, "unknown shell action %q\n", action)
		return 2
	}
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	fmt.Fprintln(stdout, result)
	return 0
}

func confirmAction(stdin io.Reader, stderr io.Writer, prompt string) bool {
	fmt.Fprintf(stderr, "%s [y/N] ", prompt)
	answer, _ := bufio.NewReader(stdin).ReadString('\n')
	answer = strings.TrimSpace(strings.ToLower(answer))
	return answer == "y" || answer == "yes"
}

func runConfig(store *config.Store, namespace string, args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "config requires get, set, or list")
		return 2
	}
	switch args[0] {
	case "get":
		if len(args) != 2 {
			fmt.Fprintln(stderr, "config get requires a key")
			return 2
		}
		key := configKey(namespace, args[1])
		value, ok, err := store.Get(key)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		if !ok {
			fmt.Fprintf(stderr, "config key %q is not set\n", key)
			return 1
		}
		fmt.Fprintln(stdout, value)
		return 0
	case "set":
		if len(args) != 3 {
			fmt.Fprintln(stderr, "config set requires a key and value")
			return 2
		}
		if err := store.Set(configKey(namespace, args[1]), args[2]); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		return 0
	case "list":
		if len(args) != 1 {
			fmt.Fprintln(stderr, "config list takes no arguments")
			return 2
		}
		values, err := store.List()
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
		keys := make([]string, 0, len(values))
		for key := range values {
			if strings.HasPrefix(key, namespace+".") {
				keys = append(keys, key)
			}
		}
		sort.Strings(keys)
		for _, key := range keys {
			fmt.Fprintf(stdout, "%s=%s\n", key, values[key])
		}
		return 0
	default:
		fmt.Fprintf(stderr, "unknown config action %q\n", args[0])
		return 2
	}
}

func configKey(namespace, key string) string {
	if strings.HasPrefix(key, namespace+".") {
		return key
	}
	return namespace + "." + key
}

func runPE(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 || args[0] != "inspect" {
		fmt.Fprintln(stderr, "usage: okit pe inspect <file...> [--format table|json|csv]")
		return 2
	}
	format := "table"
	files := make([]string, 0)
	for i := 1; i < len(args); i++ {
		if args[i] == "--format" {
			i++
			if i >= len(args) {
				fmt.Fprintln(stderr, "--format requires a value")
				return 2
			}
			format = args[i]
			continue
		}
		if len(args[i]) > 0 && args[i][0] == '-' {
			fmt.Fprintf(stderr, "unknown pe option %q\n", args[i])
			return 2
		}
		files = append(files, args[i])
	}
	if format != "table" && format != "json" && format != "csv" {
		fmt.Fprintf(stderr, "unsupported format %q\n", format)
		return 2
	}
	if len(files) == 0 {
		fmt.Fprintln(stderr, "pe inspect requires at least one file")
		return 2
	}
	infos := make([]peinspect.Info, 0, len(files))
	failed := 0
	for _, path := range files {
		f, err := os.Open(path)
		if err != nil {
			fmt.Fprintf(stderr, "%s: %v\n", path, err)
			failed++
			continue
		}
		info, parseErr := peinspect.Parse(f, path)
		closeErr := f.Close()
		if parseErr == nil {
			parseErr = closeErr
		}
		if parseErr != nil {
			fmt.Fprintf(stderr, "%s: %v\n", path, parseErr)
			failed++
			continue
		}
		infos = append(infos, info)
	}
	if len(infos) > 0 {
		if err := peinspect.Write(stdout, infos, format); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
	}
	if failed > 0 && len(infos) > 0 {
		return 3
	}
	if failed > 0 {
		return 1
	}
	return 0
}

func runHex(args []string, stdout, stderr io.Writer) int {
	options := hexdump.Options{}
	files := make([]string, 0)
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--display":
			i++
			if i >= len(args) {
				fmt.Fprintln(stderr, "--display requires a value")
				return 2
			}
			options.Display = args[i]
		case "--word-size":
			i++
			value, ok := parseNonNegative(args, i, "--word-size", stderr)
			if !ok {
				return 2
			}
			options.WordSize = int(value)
		case "--skip":
			i++
			value, ok := parseNonNegative(args, i, "--skip", stderr)
			if !ok {
				return 2
			}
			options.Skip = value
		case "--length":
			i++
			value, ok := parseNonNegative(args, i, "--length", stderr)
			if !ok {
				return 2
			}
			options.Length, options.LengthSet = value, true
		case "--no-squeeze":
			options.NoSqueeze = true
		default:
			if len(args[i]) > 0 && args[i][0] == '-' {
				fmt.Fprintf(stderr, "unknown hex option %q\n", args[i])
				return 2
			}
			files = append(files, args[i])
		}
	}
	if len(files) == 0 {
		fmt.Fprintln(stderr, "hex requires at least one file")
		return 2
	}
	succeeded, failed := 0, 0
	for _, path := range files {
		f, err := os.Open(path)
		if err != nil {
			fmt.Fprintf(stderr, "%s: %v\n", path, err)
			failed++
			continue
		}
		err = hexdump.Dump(f, stdout, options)
		closeErr := f.Close()
		if err == nil {
			err = closeErr
		}
		if err != nil {
			fmt.Fprintf(stderr, "%s: %v\n", path, err)
			failed++
			continue
		}
		succeeded++
	}
	if failed > 0 && succeeded > 0 {
		return 3
	}
	if failed > 0 {
		return 1
	}
	return 0
}

func parseNonNegative(args []string, index int, name string, stderr io.Writer) (int64, bool) {
	if index >= len(args) {
		fmt.Fprintf(stderr, "%s requires a value\n", name)
		return 0, false
	}
	value, err := strconv.ParseInt(args[index], 10, 64)
	if err != nil || value < 0 {
		fmt.Fprintf(stderr, "%s requires a non-negative integer\n", name)
		return 0, false
	}
	return value, true
}

func printHelp(w io.Writer) {
	fmt.Fprintln(w, `okit - cross-platform developer toolkit

Usage:
  okit <command> [options]

Commands:
  info         display runtime and installation status
  hex          display file bytes
  pe           inspect PE files
  git-sync     synchronize Git changes
  shell        manage shell configuration
  mobaxterm    manage MobaXterm
  self         update or uninstall okit

Global options:
  --format     select table, json, or csv output where supported
  --no-color   disable ANSI colors
  --quiet      suppress normal output
  --verbose    enable diagnostic output
  --help       show help
  --version    show version`)
}
