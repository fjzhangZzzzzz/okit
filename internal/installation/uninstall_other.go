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
