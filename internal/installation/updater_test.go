package installation

import (
	"os"
	"path/filepath"
	"testing"
)

func TestApplyUpdateJobCommitsBothBinariesAndMetadata(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	install := filepath.Join(root, "bin")
	staging := filepath.Join(root, "staging")
	if err := os.MkdirAll(staging, 0o700); err != nil {
		t.Fatal(err)
	}
	current, currentUpdater := filepath.Join(install, "okit.exe"), filepath.Join(install, "okit-updater.exe")
	staged, stagedUpdater := filepath.Join(staging, "okit.exe"), filepath.Join(staging, "okit-updater.exe")
	if err := os.MkdirAll(install, 0o700); err != nil {
		t.Fatal(err)
	}
	for path, data := range map[string]string{current: "old", currentUpdater: "old updater", staged: "new", stagedUpdater: "new updater"} {
		if err := os.WriteFile(path, []byte(data), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	job := UpdateJob{Current: current, CurrentUpdater: currentUpdater, Staged: staged, StagedUpdater: stagedUpdater, OKITHome: home, Metadata: Metadata{Method: "official", Version: "v1.1.0", Executable: current, ManagedFiles: []string{currentUpdater}}}
	if err := ApplyUpdateJob(job); err != nil {
		t.Fatal(err)
	}
	for path, want := range map[string]string{current: "new", currentUpdater: "new updater"} {
		got, err := os.ReadFile(path)
		if err != nil || string(got) != want {
			t.Fatalf("%s=%q err=%v", path, got, err)
		}
	}
	metadata, err := LoadMetadata(home)
	if err != nil || metadata.Version != "v1.1.0" {
		t.Fatalf("metadata=%+v err=%v", metadata, err)
	}
}

func TestApplyUpdateJobRollsBackBothBinariesWhenMetadataCommitFails(t *testing.T) {
	root := t.TempDir()
	current, currentUpdater := filepath.Join(root, "okit.exe"), filepath.Join(root, "okit-updater.exe")
	staged, stagedUpdater := filepath.Join(root, "new.exe"), filepath.Join(root, "new-updater.exe")
	for path, data := range map[string]string{current: "old", currentUpdater: "old updater", staged: "new", stagedUpdater: "new updater"} {
		if err := os.WriteFile(path, []byte(data), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	notDirectory := filepath.Join(root, "not-directory")
	if err := os.WriteFile(notDirectory, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	job := UpdateJob{Current: current, CurrentUpdater: currentUpdater, Staged: staged, StagedUpdater: stagedUpdater, OKITHome: filepath.Join(notDirectory, "home"), Metadata: Metadata{Method: "official", Executable: current}}
	if err := ApplyUpdateJob(job); err == nil {
		t.Fatal("metadata failure accepted")
	}
	for path, want := range map[string]string{current: "old", currentUpdater: "old updater"} {
		got, err := os.ReadFile(path)
		if err != nil || string(got) != want {
			t.Fatalf("%s=%q err=%v", path, got, err)
		}
	}
}
