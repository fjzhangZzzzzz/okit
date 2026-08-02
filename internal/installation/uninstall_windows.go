//go:build windows

package installation

import (
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
	parts, kept := strings.Split(strings.Join(fields[2:], " "), ";"), []string{}
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
	dir, err := os.MkdirTemp(home, ".uninstall-*")
	if err != nil {
		return false, err
	}
	installedUpdater := filepath.Join(filepath.Dir(executable), "okit-updater.exe")
	helper := filepath.Join(dir, "okit-updater.exe")
	if data, err := os.ReadFile(installedUpdater); err != nil {
		return false, fmt.Errorf("read installed updater: %w", err)
	} else if err := os.WriteFile(helper, data, 0o700); err != nil {
		return false, err
	}
	jobPath := filepath.Join(dir, "uninstall-job.json")
	if err := SaveUninstallJob(jobPath, UninstallJob{WaitPID: os.Getpid(), Executable: executable, InstalledUpdater: installedUpdater, OKITHome: home, Purge: purge}); err != nil {
		return false, err
	}
	command := exec.Command(helper, "--uninstall-job", jobPath)
	command.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x08000000}
	if err := command.Start(); err != nil {
		return false, err
	}
	if err := command.Process.Release(); err != nil {
		return false, err
	}
	return true, nil
}
