package installation

import (
	"fmt"
	"os"
)

func CompleteReplacement(executable, staged string, rename func(string, string) error) error {
	backup := executable + ".okit-old"
	_ = os.Remove(backup)
	if err := rename(executable, backup); err != nil {
		return fmt.Errorf("save current executable: %w", err)
	}
	if err := rename(staged, executable); err != nil {
		if rollbackErr := rename(backup, executable); rollbackErr != nil {
			return fmt.Errorf("install update: %v; rollback failed: %v", err, rollbackErr)
		}
		return fmt.Errorf("install update: %w", err)
	}
	if err := os.Remove(backup); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}
