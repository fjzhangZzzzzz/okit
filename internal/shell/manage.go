package shell

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

const (
	beginMarker = "# >>> okit shell >>>"
	endMarker   = "# <<< okit shell <<<"
)

type Manager struct {
	OKITHome          string
	UserHome          string
	GOOS              string
	PowerShellProfile func() (string, error)
	Replace           func(path string, data []byte, mode os.FileMode) error
	RunGit            func(args ...string) error
	CmdAutoRun        CmdAutoRun
}

type CmdAutoRun interface {
	Get() (string, error)
	Set(string) error
}

func (m *Manager) Sync(shell, repositoryURL string, dryRun bool) (string, error) {
	if _, err := m.managedPath(shell); err != nil {
		return "", err
	}
	if strings.TrimSpace(repositoryURL) == "" {
		return "", errors.New("shell.repo-url is not configured")
	}
	repoDir := filepath.Join(m.OKITHome, "data", "shell", "repo")
	if dryRun {
		return fmt.Sprintf("would sync %s from %s", shell, repositoryURL), nil
	}
	runGit := m.RunGit
	if runGit == nil {
		runGit = func(args ...string) error {
			command := exec.Command("git", args...)
			if output, err := command.CombinedOutput(); err != nil {
				return fmt.Errorf("git %s: %w: %s", strings.Join(args, " "), err, strings.TrimSpace(string(output)))
			}
			return nil
		}
	}
	if _, err := os.Stat(repoDir); errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(filepath.Dir(repoDir), 0o700); err != nil {
			return "", err
		}
		if err := runGit("clone", "--depth", "1", repositoryURL, repoDir); err != nil {
			return "", err
		}
	} else if err != nil {
		return "", err
	} else if err := runGit("-C", repoDir, "pull", "--ff-only"); err != nil {
		return "", err
	}

	sourceName := map[string]string{"bash": "bash", "zsh": "zsh", "powershell": "powershell", "cmd": "cmd"}[shell]
	sourcePath := filepath.Join(repoDir, sourceName)
	data, err := os.ReadFile(sourcePath)
	if err != nil {
		return "", fmt.Errorf("read synchronized %s config: %w", shell, err)
	}
	target, _ := m.managedPath(shell)
	if err := m.replace(target, data, 0o600); err != nil {
		return "", err
	}
	return fmt.Sprintf("synchronized %s configuration", shell), nil
}

func New(okitHome, userHome string) *Manager {
	return &Manager{OKITHome: okitHome, UserHome: userHome, GOOS: runtime.GOOS}
}

func (m *Manager) managedPath(shell string) (string, error) {
	name := map[string]string{"bash": "bash.rc", "zsh": "zsh.rc", "powershell": "powershell.ps1", "cmd": "cmd.cmd"}[shell]
	if name == "" {
		return "", fmt.Errorf("unsupported shell %q", shell)
	}
	if m.GOOS == "windows" {
		return strings.TrimRight(m.OKITHome, `\/`) + `\data\shell\` + name, nil
	}
	return filepath.Join(m.OKITHome, "data", "shell", name), nil
}

func (m *Manager) ProfilePath(shell string) (string, error) {
	switch shell {
	case "bash":
		return filepath.Join(m.UserHome, ".bashrc"), nil
	case "zsh":
		return filepath.Join(m.UserHome, ".zshrc"), nil
	case "powershell":
		if m.GOOS != "windows" {
			return "", errors.New("powershell profile management is only supported on Windows")
		}
		if m.PowerShellProfile != nil {
			return m.PowerShellProfile()
		}
		output, err := exec.Command("powershell", "-NoProfile", "-Command", "$PROFILE").Output()
		if err == nil && strings.TrimSpace(string(output)) != "" {
			return strings.TrimSpace(string(output)), nil
		}
		return filepath.Join(m.UserHome, "Documents", "PowerShell", "Microsoft.PowerShell_profile.ps1"), nil
	case "cmd":
		if m.GOOS != "windows" {
			return "", errors.New("cmd profile management is only supported on Windows")
		}
		return filepath.Join(m.OKITHome, "data", "shell", "cmd-autorun.cmd"), nil
	default:
		return "", fmt.Errorf("unsupported shell %q", shell)
	}
}

func (m *Manager) Source(shell string) (string, error) {
	path, err := m.managedPath(shell)
	if err != nil {
		return "", err
	}
	switch shell {
	case "bash", "zsh":
		if m.GOOS == "windows" {
			path = gitBashPath(path)
		}
		return fmt.Sprintf("[ -f %q ] && . %q", path, path), nil
	case "powershell":
		return fmt.Sprintf("if (Test-Path -LiteralPath '%s') { . '%s' }", strings.ReplaceAll(path, "'", "''"), strings.ReplaceAll(path, "'", "''")), nil
	case "cmd":
		return fmt.Sprintf("if exist \"%s\" call \"%s\"", path, path), nil
	default:
		return "", fmt.Errorf("unsupported shell %q", shell)
	}
}

func gitBashPath(path string) string {
	path = strings.ReplaceAll(path, `\`, "/")
	if len(path) >= 3 && path[1] == ':' && path[2] == '/' {
		drive := strings.ToLower(path[:1])
		return "/" + drive + path[2:]
	}
	return path
}

func (m *Manager) Enable(shell string, dryRun bool) (string, error) {
	if shell == "cmd" {
		return m.enableCMD(dryRun)
	}
	profile, err := m.ProfilePath(shell)
	if err != nil {
		return "", err
	}
	source, err := m.Source(shell)
	if err != nil {
		return "", err
	}
	block := beginMarker + "\n" + source + "\n" + endMarker + "\n"
	current, mode, err := readOptional(profile)
	if err != nil {
		return "", err
	}
	start, end, err := managedRange(string(current))
	if err != nil {
		return "", err
	}
	var next string
	if start >= 0 {
		next = string(current[:start]) + block + string(current[end:])
	} else {
		next = string(current)
		if next != "" && !strings.HasSuffix(next, "\n") {
			next += "\n"
		}
		next += block
	}
	if next == string(current) {
		return "already enabled", nil
	}
	if dryRun {
		return fmt.Sprintf("would enable %s in %s", shell, profile), nil
	}
	if err := m.backup(profile, current); err != nil {
		return "", err
	}
	if mode == 0 {
		mode = 0o600
	}
	if err := m.replace(profile, []byte(next), mode); err != nil {
		return "", err
	}
	return fmt.Sprintf("enabled %s in %s", shell, profile), nil
}

func (m *Manager) Disable(shell string, dryRun bool) (string, error) {
	if shell == "cmd" {
		return m.disableCMD(dryRun)
	}
	profile, err := m.ProfilePath(shell)
	if err != nil {
		return "", err
	}
	current, mode, err := readOptional(profile)
	if err != nil {
		return "", err
	}
	start, end, err := managedRange(string(current))
	if err != nil {
		return "", err
	}
	if start < 0 {
		return "already disabled", nil
	}
	next := append(append([]byte(nil), current[:start]...), current[end:]...)
	if dryRun {
		return fmt.Sprintf("would disable %s in %s", shell, profile), nil
	}
	if err := m.backup(profile, current); err != nil {
		return "", err
	}
	if err := m.replace(profile, next, mode); err != nil {
		return "", err
	}
	return fmt.Sprintf("disabled %s in %s", shell, profile), nil
}

func (m *Manager) Status(shell string) (string, error) {
	if shell == "cmd" {
		registry, err := m.cmdAutoRun()
		if err != nil {
			return "", err
		}
		current, err := registry.Get()
		if err != nil {
			return "", err
		}
		source, _ := m.Source("cmd")
		managed, _ := m.managedPath("cmd")
		_, managedErr := os.Stat(managed)
		_, repoErr := os.Stat(filepath.Join(m.OKITHome, "data", "shell", "repo", ".git"))
		return fmt.Sprintf("shell=cmd enabled=%t profile=HKCU\\Software\\Microsoft\\Command Processor\\AutoRun config=%s config_exists=%t repo_exists=%t", strings.Contains(current, source), managed, managedErr == nil, repoErr == nil), nil
	}
	profile, err := m.ProfilePath(shell)
	if err != nil {
		return "", err
	}
	current, _, err := readOptional(profile)
	if err != nil {
		return "", err
	}
	start, _, err := managedRange(string(current))
	if err != nil {
		return "", err
	}
	managed, _ := m.managedPath(shell)
	_, managedErr := os.Stat(managed)
	_, repoErr := os.Stat(filepath.Join(m.OKITHome, "data", "shell", "repo", ".git"))
	return fmt.Sprintf("shell=%s enabled=%t profile=%s config=%s config_exists=%t repo_exists=%t", shell, start >= 0, profile, managed, managedErr == nil, repoErr == nil), nil
}

func (m *Manager) cmdAutoRun() (CmdAutoRun, error) {
	if m.GOOS != "windows" {
		return nil, errors.New("cmd profile management is only supported on Windows")
	}
	if m.CmdAutoRun != nil {
		return m.CmdAutoRun, nil
	}
	return platformCmdAutoRun(), nil
}

func (m *Manager) enableCMD(dryRun bool) (string, error) {
	registry, err := m.cmdAutoRun()
	if err != nil {
		return "", err
	}
	current, err := registry.Get()
	if err != nil {
		return "", err
	}
	source, err := m.Source("cmd")
	if err != nil {
		return "", err
	}
	if strings.Contains(current, source) {
		return "already enabled", nil
	}
	next := strings.TrimSpace(current)
	if next != "" {
		next += " & "
	}
	next += source
	if dryRun {
		return "would enable cmd in AutoRun", nil
	}
	if err := m.backup("cmd-autorun.registry", []byte(current)); err != nil {
		return "", err
	}
	if err := registry.Set(next); err != nil {
		return "", err
	}
	return "enabled cmd in AutoRun", nil
}

func (m *Manager) disableCMD(dryRun bool) (string, error) {
	registry, err := m.cmdAutoRun()
	if err != nil {
		return "", err
	}
	current, err := registry.Get()
	if err != nil {
		return "", err
	}
	source, _ := m.Source("cmd")
	if !strings.Contains(current, source) {
		return "already disabled", nil
	}
	next := strings.Replace(current, " & "+source, "", 1)
	if next == current {
		next = strings.Replace(current, source+" & ", "", 1)
	}
	if next == current {
		next = strings.Replace(current, source, "", 1)
	}
	if dryRun {
		return "would disable cmd in AutoRun", nil
	}
	if err := m.backup("cmd-autorun.registry", []byte(current)); err != nil {
		return "", err
	}
	if err := registry.Set(strings.TrimSpace(next)); err != nil {
		return "", err
	}
	return "disabled cmd in AutoRun", nil
}

func managedRange(content string) (int, int, error) {
	start := strings.Index(content, beginMarker)
	endMarkerStart := strings.Index(content, endMarker)
	if (start >= 0) != (endMarkerStart >= 0) || endMarkerStart >= 0 && endMarkerStart < start {
		return -1, -1, errors.New("malformed okit managed block")
	}
	if start < 0 {
		return -1, -1, nil
	}
	end := endMarkerStart + len(endMarker)
	if end < len(content) && content[end] == '\r' {
		end++
	}
	if end < len(content) && content[end] == '\n' {
		end++
	}
	return start, end, nil
}

func readOptional(path string) ([]byte, os.FileMode, error) {
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, 0, nil
	}
	if err != nil {
		return nil, 0, err
	}
	info, err := os.Stat(path)
	if err != nil {
		return nil, 0, err
	}
	return data, info.Mode().Perm(), nil
}

func (m *Manager) backup(path string, content []byte) error {
	if len(content) == 0 {
		return nil
	}
	backupDir := filepath.Join(m.OKITHome, "backups", "shell")
	if err := os.MkdirAll(backupDir, 0o700); err != nil {
		return err
	}
	name := filepath.Base(path) + "." + time.Now().UTC().Format("20060102T150405.000000000Z") + ".bak"
	return os.WriteFile(filepath.Join(backupDir, name), content, 0o600)
}

func (m *Manager) replace(path string, data []byte, mode os.FileMode) error {
	if m.Replace != nil {
		return m.Replace(path, data, mode)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".okit-profile-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(mode); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	swap := path + ".okit-swap"
	hadOriginal := false
	if _, err := os.Stat(path); err == nil {
		if err := os.Rename(path, swap); err != nil {
			return err
		}
		hadOriginal = true
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	if err := os.Rename(tmpName, path); err != nil {
		if hadOriginal {
			_ = os.Rename(swap, path)
		}
		return err
	}
	if hadOriginal {
		_ = os.Remove(swap)
	}
	return nil
}
