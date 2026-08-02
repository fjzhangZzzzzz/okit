//go:build windows

package installation

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWindowsNativeUpdaterCommitsPairedBinaries_SELF006(t *testing.T) {
	root := t.TempDir()
	install, staging, home := filepath.Join(root, "bin"), filepath.Join(root, "staging"), filepath.Join(root, "home")
	if err := os.MkdirAll(install, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(staging, 0o700); err != nil {
		t.Fatal(err)
	}
	current := filepath.Join(install, "okit.exe")
	currentUpdater := filepath.Join(install, "okit-updater.exe")
	staged := filepath.Join(staging, "okit.exe")
	stagedUpdater := filepath.Join(staging, "okit-updater.exe")
	for path, data := range map[string]string{current: "old", currentUpdater: "old updater", staged: "new", stagedUpdater: "new updater"} {
		if err := os.WriteFile(path, []byte(data), 0o700); err != nil {
			t.Fatal(err)
		}
	}
	if err := ApplyUpdateJob(UpdateJob{Current: current, CurrentUpdater: currentUpdater, Staged: staged, StagedUpdater: stagedUpdater, OKITHome: home, Metadata: Metadata{Method: "official", Executable: current}}); err != nil {
		t.Fatal(err)
	}
}
