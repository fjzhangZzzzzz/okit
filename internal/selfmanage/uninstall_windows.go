//go:build windows

package selfmanage

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

func removePathEntries(entries []string) error {
	if len(entries) == 0 {
		return nil
	}
	output, err := exec.Command("reg", "query", `HKCU\Environment`, "/v", "Path").CombinedOutput()
	if err != nil {
		return fmt.Errorf("read user PATH: %w: %s", err, strings.TrimSpace(string(output)))
	}
	line := ""
	for _, candidate := range strings.Split(string(output), "\n") {
		if strings.Contains(candidate, "REG_") {
			line = candidate
		}
	}
	fields := strings.Fields(line)
	if len(fields) < 3 {
		return fmt.Errorf("could not parse user PATH")
	}
	parts := strings.Split(strings.Join(fields[2:], " "), ";")
	kept := make([]string, 0, len(parts))
	for _, part := range parts {
		remove := false
		for _, entry := range entries {
			if strings.EqualFold(strings.TrimSpace(part), strings.TrimSpace(entry)) {
				remove = true
			}
		}
		if !remove && part != "" {
			kept = append(kept, part)
		}
	}
	command := exec.Command("reg", "add", `HKCU\Environment`, "/v", "Path", "/t", "REG_EXPAND_SZ", "/d", strings.Join(kept, ";"), "/f")
	if output, err := command.CombinedOutput(); err != nil {
		return fmt.Errorf("update user PATH: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func scheduleUninstall(executable, home string, purge bool) (bool, error) {
	dir, err := os.MkdirTemp("", "okit-uninstall-*")
	if err != nil {
		return false, err
	}
	script := filepath.Join(dir, "uninstall.ps1")
	if err := os.WriteFile(script, []byte(uninstallScriptContent), 0o600); err != nil {
		return false, err
	}
	command := exec.Command("powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script, strconv.Itoa(os.Getpid()), executable, home, strconv.FormatBool(purge))
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	if err := command.Start(); err != nil {
		return false, err
	}
	if err := command.Process.Release(); err != nil {
		return false, err
	}
	return true, nil
}

const uninstallScriptContent = `param([int]$PidToWait,[string]$Executable,[string]$OKITHome,[string]$Purge)
Wait-Process -Id $PidToWait -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $Executable -Force -ErrorAction SilentlyContinue
if ($Purge -eq 'true') { Remove-Item -LiteralPath $OKITHome -Recurse -Force -ErrorAction SilentlyContinue } else { Remove-Item -LiteralPath (Join-Path $OKITHome 'install.json') -Force -ErrorAction SilentlyContinue }
Remove-Item -LiteralPath (Split-Path -Parent $PSCommandPath) -Recurse -Force -ErrorAction SilentlyContinue
`
