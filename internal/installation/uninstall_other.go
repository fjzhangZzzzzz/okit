//go:build !windows

package installation

import "os"

func removePathEntries([]string) error { return nil }
func scheduleUninstall(executable, home string, purge bool) (bool, error) {
	if err := os.Remove(executable); err != nil && !os.IsNotExist(err) {
		return false, err
	}
	return false, nil
}
