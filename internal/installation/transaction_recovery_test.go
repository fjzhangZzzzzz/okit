package installation

import (
	"os"
	"path/filepath"
	"testing"
)

func TestRecoverTransactionRestoresBackupPairAndOldMetadata(t *testing.T) {
	home := t.TempDir()
	dir := filepath.Join(home, "staging")
	_ = os.MkdirAll(dir, 0o700)
	current := filepath.Join(home, "okit.exe")
	updater := filepath.Join(home, "okit-updater.exe")
	backup := filepath.Join(dir, "okit.exe.old")
	updaterBackup := filepath.Join(dir, "okit-updater.exe.old")
	for path, data := range map[string]string{current: "new", updater: "new-updater", backup: "old", updaterBackup: "old-updater"} {
		if err := os.WriteFile(path, []byte(data), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	old := Metadata{Method: "official", Version: "v1.0.0", Executable: current}
	tx := UpdateTransaction{Schema: 1, State: TransactionBinariesInstalled, TransactionDir: dir, OKITHome: home, Current: current, CurrentUpdater: updater, Staged: filepath.Join(dir, "okit.exe.staged"), StagedUpdater: filepath.Join(dir, "okit-updater.exe.staged"), Backup: backup, UpdaterBackup: updaterBackup, OldMetadata: old, NewMetadata: Metadata{Executable: current, Version: "v2"}}
	if err := SaveTransaction(tx); err != nil {
		t.Fatal(err)
	}
	if recovered, err := RecoverTransaction(home); err != nil || !recovered {
		t.Fatalf("recovered=%v err=%v", recovered, err)
	}
	data, _ := os.ReadFile(current)
	if string(data) != "old" {
		t.Fatalf("current=%q", data)
	}
	data, _ = os.ReadFile(updater)
	if string(data) != "old-updater" {
		t.Fatalf("updater=%q", data)
	}
	if _, err := LoadMetadata(home); err != nil {
		t.Fatal(err)
	}
}
