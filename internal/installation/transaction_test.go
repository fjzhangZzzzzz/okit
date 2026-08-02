package installation

import (
	"os"
	"path/filepath"
	"testing"
)

func TestTransactionPersistsItsRecoveryState(t *testing.T) {
	home := t.TempDir()
	dir := filepath.Join(home, "staging")
	current := filepath.Join(home, "okit.exe")
	updater := filepath.Join(home, "okit-updater.exe")
	tx := UpdateTransaction{Schema: 1, State: TransactionBackedUp, OKITHome: home,
		TransactionDir: dir, Current: current, CurrentUpdater: updater,
		Staged: filepath.Join(dir, "okit.exe"), StagedUpdater: filepath.Join(dir, "okit-updater.exe"),
		Backup: filepath.Join(dir, "okit.exe.old"), UpdaterBackup: filepath.Join(dir, "okit-updater.exe.old"),
		NewMetadata: Metadata{Executable: current, Version: "v1.1.0"}}
	if err := SaveTransaction(tx); err != nil {
		t.Fatal(err)
	}
	loaded, err := LoadTransaction(home)
	if err != nil || loaded.State != TransactionBackedUp || loaded.NewMetadata.Version != "v1.1.0" {
		t.Fatalf("transaction=%+v err=%v", loaded, err)
	}
}

func TestApplyTransactionReplacesPairAndMetadata(t *testing.T) {
	home := t.TempDir()
	dir := filepath.Join(home, "staging")
	_ = os.MkdirAll(dir, 0o700)
	current := filepath.Join(home, "okit.exe")
	updater := filepath.Join(home, "okit-updater.exe")
	staged := filepath.Join(dir, "okit.exe")
	stagedUpdater := filepath.Join(dir, "okit-updater.exe")
	for path, data := range map[string]string{current: "old", updater: "old-updater", staged: "new", stagedUpdater: "new-updater"} {
		if err := os.WriteFile(path, []byte(data), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	tx := UpdateTransaction{Schema: 1, State: TransactionPrepared, OKITHome: home, TransactionDir: dir, Current: current, CurrentUpdater: updater, Staged: staged, StagedUpdater: stagedUpdater, Backup: filepath.Join(dir, "okit.exe.old"), UpdaterBackup: filepath.Join(dir, "okit-updater.exe.old"), NewMetadata: Metadata{Method: "official", Version: "v2", Executable: current}}
	var err error
	tx.StagedSHA256, err = fileSHA256(staged)
	if err != nil {
		t.Fatal(err)
	}
	tx.UpdaterSHA256, err = fileSHA256(stagedUpdater)
	if err != nil {
		t.Fatal(err)
	}
	if err := ApplyTransaction(tx); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(current)
	if string(got) != "new" {
		t.Fatalf("current=%q", got)
	}
	got, _ = os.ReadFile(updater)
	if string(got) != "new-updater" {
		t.Fatalf("updater=%q", got)
	}
	if _, err := LoadMetadata(home); err != nil {
		t.Fatal(err)
	}
}
