//go:build windows

package installation

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"syscall"
)

func PlatformReplace(executable, staged string) (bool, error) {
	script := filepath.Join(filepath.Dir(staged), "replace.ps1")
	if err := os.WriteFile(script, []byte(replacementScriptContent), 0o600); err != nil {
		return false, err
	}
	command := exec.Command("powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script, strconv.Itoa(os.Getpid()), executable, staged)
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	if err := command.Start(); err != nil {
		return false, fmt.Errorf("start replacement helper: %w", err)
	}
	if err := command.Process.Release(); err != nil {
		return false, err
	}
	return true, nil
}

const replacementScriptContent = `param([int]$PidToWait,[string]$Current,[string]$Staged)
Wait-Process -Id $PidToWait -ErrorAction SilentlyContinue
$backup = "$Current.okit-old"
try {
  if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
  Move-Item -LiteralPath $Current -Destination $backup -Force
  Move-Item -LiteralPath $Staged -Destination $Current -Force
  Remove-Item -LiteralPath $backup -Force
} catch {
  if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $Current)) { Move-Item -LiteralPath $backup -Destination $Current -Force }
  exit 1
}
$helperDir = Split-Path -Parent $PSCommandPath
Remove-Item -LiteralPath $helperDir -Recurse -Force -ErrorAction SilentlyContinue
`
