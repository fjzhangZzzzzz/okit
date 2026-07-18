package mobaxterm

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
)

func TestDeployDryRunAndPlatformBoundary_MOBA006_MOBA007(t *testing.T) {
	dir := t.TempDir()
	service := Service{GOOS: "windows", Candidates: func() ([]Candidate, error) {
		return []Candidate{{InstallPath: dir, Version: "25.2"}}, nil
	}}
	result, err := service.DeployLicense("alice", "", true)
	if err != nil || result == "" {
		t.Fatalf("result=%q err=%v", result, err)
	}
	if _, err := os.Stat(filepath.Join(dir, "Custom.mxtpro")); !os.IsNotExist(err) {
		t.Fatalf("dry-run wrote license: %v", err)
	}

	nonWindowsHome := filepath.Join(t.TempDir(), "okit")
	nonWindows := Service{GOOS: "linux", OKITHome: nonWindowsHome}
	if _, err := nonWindows.Status(); err == nil {
		t.Fatal("non-Windows status succeeded")
	}
	if _, err := os.Stat(nonWindowsHome); !os.IsNotExist(err) {
		t.Fatalf("non-Windows call created files: %v", err)
	}
}

func TestDeployBacksUpExistingValidLicense(t *testing.T) {
	root := t.TempDir()
	licensePath := filepath.Join(root, "install", "Custom.mxtpro")
	key, err := license.Generate("old-user", "25.2")
	if err != nil {
		t.Fatal(err)
	}
	if err := license.CreateFile(licensePath, key); err != nil {
		t.Fatal(err)
	}
	service := Service{
		GOOS:     "windows",
		OKITHome: filepath.Join(root, "home"),
		Candidates: func() ([]Candidate, error) {
			return []Candidate{{InstallPath: filepath.Dir(licensePath), LicensePath: licensePath, Version: "25.2"}}, nil
		},
	}
	if _, err := service.DeployLicense("new-user", "25.2", false); err != nil {
		t.Fatal(err)
	}
	backups, err := os.ReadDir(filepath.Join(service.OKITHome, "backups", "mobaxterm"))
	if err != nil || len(backups) != 1 {
		t.Fatalf("backups=%v err=%v", backups, err)
	}
	deployed, err := license.ReadFile(licensePath)
	if err != nil {
		t.Fatal(err)
	}
	valid, err := license.Verify(deployed, "new-user", "25.2")
	if err != nil || !valid {
		t.Fatalf("valid=%v err=%v", valid, err)
	}
}
