//go:build windows

package installation

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
)

func removePathEntries(entries []string) error {
	if len(entries) == 0 {
		return nil
	}
	out, err := exec.Command("reg", "query", `HKCU\Environment`, "/v", "Path").CombinedOutput()
	if err != nil {
		return fmt.Errorf("read user PATH: %w: %s", err, strings.TrimSpace(string(out)))
	}
	line := ""
	for _, candidate := range strings.Split(string(out), "\n") {
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
	cmd := exec.Command("reg", "add", `HKCU\Environment`, "/v", "Path", "/t", "REG_EXPAND_SZ", "/d", strings.Join(kept, ";"), "/f")
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("update user PATH: %w: %s", err, strings.TrimSpace(string(out)))
	}
	return nil
}

func scheduleUninstall(executable, home string, purge bool) (bool, error) {
	updater := filepath.Join(filepath.Dir(executable), "okit-updater.exe")
	if _, err := os.Stat(updater); err != nil {
		return false, fmt.Errorf("okit-updater.exe is required for Windows uninstall: %w", err)
	}
	dir, err := os.MkdirTemp(home, ".uninstall-*")
	if err != nil {
		return false, err
	}
	copy := filepath.Join(dir, "okit-updater.exe")
	if err := copyFile(updater, copy); err != nil {
		return false, err
	}
	job := filepath.Join(dir, "uninstall.json")
	data, err := json.Marshal(UninstallJob{Executable: executable, Updater: updater, Home: home, Purge: purge, WaitPID: os.Getpid()})
	if err != nil {
		return false, err
	}
	if err := os.WriteFile(job, data, 0o600); err != nil {
		return false, err
	}
	command := exec.Command(copy, "--uninstall", job)
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if err := command.Start(); err != nil {
		return false, err
	}
	_ = command.Process.Release()
	return true, nil
}

func executeUninstallJob(job UninstallJob) error {
	if err := os.Remove(job.Executable); err != nil && !os.IsNotExist(err) {
		return err
	}
	if err := os.Remove(job.Updater); err != nil && !os.IsNotExist(err) {
		return err
	}
	if job.Purge {
		return os.RemoveAll(job.Home)
	}
	if err := os.Remove(metadataPath(job.Home)); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err = out.ReadFrom(in); err != nil {
		_ = out.Close()
		return err
	}
	return out.Close()
}

const uninstallScriptContent = `param([int]$PidToWait,[string]$Executable,[string]$OKITHome,[string]$Purge)
Wait-Process -Id $PidToWait -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $Executable -Force -ErrorAction SilentlyContinue
if ($Purge -eq 'true') { Remove-Item -LiteralPath $OKITHome -Recurse -Force -ErrorAction SilentlyContinue } else { Remove-Item -LiteralPath (Join-Path $OKITHome 'install.json') -Force -ErrorAction SilentlyContinue }`
