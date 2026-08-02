//go:build windows

package installation

import (
	"fmt"
	"os/exec"
	"syscall"
)

func PlatformReplace(executable, staged string) (bool, error) {
	return false, fmt.Errorf("native transaction metadata is required for Windows replacement")
}

func PlatformReplaceTransaction(t UpdateTransaction) (bool, error) {
	if err := SaveTransaction(t); err != nil {
		return false, err
	}
	command := exec.Command(t.StagedUpdater, "--transaction", TransactionPath(t.OKITHome))
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if err := command.Start(); err != nil {
		return false, fmt.Errorf("start native updater: %w", err)
	}
	_ = command.Process.Release()
	return true, nil
}

func NativeTransactionReplace() TransactionReplaceFunc { return PlatformReplaceTransaction }

// Kept for compatibility with the legacy helper test; production upgrades use
// PlatformReplaceTransaction and never launch this script.
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
}`
