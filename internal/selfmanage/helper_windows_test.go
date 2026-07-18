//go:build windows

package selfmanage

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestWindowsHelpersCompleteReplacementAndUninstall_SELF006(t *testing.T) {
	root := t.TempDir()
	current := filepath.Join(root, "okit.exe")
	staging := filepath.Join(root, "staging")
	if err := os.MkdirAll(staging, 0o700); err != nil {
		t.Fatal(err)
	}
	staged := filepath.Join(staging, "okit.exe")
	script := filepath.Join(staging, "replace.ps1")
	_ = os.WriteFile(current, []byte("old"), 0o700)
	_ = os.WriteFile(staged, []byte("new"), 0o700)
	_ = os.WriteFile(script, []byte(replacementScriptContent), 0o600)
	if output, err := exec.Command("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "2147483647", current, staged).CombinedOutput(); err != nil {
		t.Fatalf("replace helper: %v: %s", err, output)
	}
	data, err := os.ReadFile(current)
	if err != nil || string(data) != "new" {
		t.Fatalf("replacement data=%q err=%v", data, err)
	}

	home := filepath.Join(root, "home")
	helper := filepath.Join(root, "uninstall-helper")
	if err := os.MkdirAll(home, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(helper, 0o700); err != nil {
		t.Fatal(err)
	}
	metadata := filepath.Join(home, "install.json")
	uninstallScript := filepath.Join(helper, "uninstall.ps1")
	_ = os.WriteFile(metadata, []byte("{}"), 0o600)
	_ = os.WriteFile(uninstallScript, []byte(uninstallScriptContent), 0o600)
	if output, err := exec.Command("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", uninstallScript, "2147483647", current, home, "False").CombinedOutput(); err != nil {
		t.Fatalf("uninstall helper: %v: %s", err, output)
	}
	if _, err := os.Stat(current); !os.IsNotExist(err) {
		t.Fatalf("executable was not removed: %v", err)
	}
	if _, err := os.Stat(metadata); !os.IsNotExist(err) {
		t.Fatalf("metadata was not removed: %v", err)
	}
}
