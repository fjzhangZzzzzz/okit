//go:build windows

package installation

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
)

func PlatformReplace(executable, staged, okitHome string, metadata Metadata) (bool, error) {
	stagedUpdater := filepath.Join(filepath.Dir(staged), "okit-updater.exe")
	if _, err := os.Stat(stagedUpdater); err != nil {
		return false, fmt.Errorf("staged updater is missing: %w", err)
	}
	jobPath := filepath.Join(filepath.Dir(staged), "update-job.json")
	job := UpdateJob{WaitPID: os.Getpid(), Current: executable, CurrentUpdater: filepath.Join(filepath.Dir(executable), "okit-updater.exe"), Staged: staged, StagedUpdater: stagedUpdater, OKITHome: okitHome, Metadata: metadata}
	if err := SaveUpdateJob(jobPath, job); err != nil {
		return false, err
	}
	command := exec.Command(stagedUpdater, "--job", jobPath)
	command.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x08000000}
	if err := command.Start(); err != nil {
		return false, fmt.Errorf("start native updater: %w", err)
	}
	if err := command.Process.Release(); err != nil {
		return false, err
	}
	return true, nil
}
