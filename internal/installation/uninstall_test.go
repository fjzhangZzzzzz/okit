package installation

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestUninstallJobRoundTripAndValidation(t *testing.T) {
	home := t.TempDir()
	jobPath := filepath.Join(home, ".uninstall-123", "uninstall.json")
	job := UninstallJob{
		Executable: filepath.Join(home, "okit.exe"),
		Updater:    filepath.Join(home, "okit-updater.exe"),
		Home:       home,
		WaitPID:    42,
	}
	data := `{"executable":"` + strings.ReplaceAll(job.Executable, `\`, `\\`) + `","updater":"` + strings.ReplaceAll(job.Updater, `\`, `\\`) + `","home":"` + strings.ReplaceAll(job.Home, `\`, `\\`) + `","wait_pid":42}`
	if err := os.MkdirAll(filepath.Dir(jobPath), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(jobPath, []byte(data), 0o600); err != nil {
		t.Fatal(err)
	}
	got, err := ReadUninstallJob(jobPath)
	if err != nil {
		t.Fatal(err)
	}
	if got != job {
		t.Fatalf("ReadUninstallJob() = %#v, want %#v", got, job)
	}
	if err := ValidateUninstallJob(jobPath, got); err != nil {
		t.Fatalf("ValidateUninstallJob() error = %v", err)
	}
	job.Home = filepath.Join(t.TempDir(), "outside")
	if err := ValidateUninstallJob(jobPath, job); err == nil || !strings.Contains(err.Error(), "outside OKIT_HOME") {
		t.Fatalf("ValidateUninstallJob() error = %v, want outside-home error", err)
	}
}

func TestExecuteUninstallJobPreservesHomeWithoutPurge(t *testing.T) {
	home := t.TempDir()
	executable := filepath.Join(home, "okit.exe")
	updater := filepath.Join(home, "okit-updater.exe")
	for _, path := range []string{executable, updater, metadataPath(home)} {
		if err := os.WriteFile(path, []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if err := ExecuteUninstallJob(UninstallJob{Executable: executable, Updater: updater, Home: home}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(home); err != nil {
		t.Fatalf("home removed: %v", err)
	}
	if _, err := os.Stat(metadataPath(home)); !os.IsNotExist(err) {
		t.Fatalf("install metadata still exists, err = %v", err)
	}
}

func TestExecuteUninstallJobPurgesHome(t *testing.T) {
	home := t.TempDir()
	if err := ExecuteUninstallJob(UninstallJob{Home: home, Purge: true}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("home still exists, err = %v", err)
	}
}

func TestExecuteUninstallJobReportsRemovalError(t *testing.T) {
	home := t.TempDir()
	executable := filepath.Join(home, "okit.exe")
	if err := os.Mkdir(executable, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(executable, "locked"), []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	err := ExecuteUninstallJob(UninstallJob{
		Executable: executable,
		Updater:    filepath.Join(home, "okit-updater.exe"),
		Home:       home,
	})
	if err == nil {
		t.Fatal("ExecuteUninstallJob() error = nil, want removal error")
	}
}
