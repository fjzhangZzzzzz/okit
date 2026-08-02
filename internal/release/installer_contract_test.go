package release

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func repositoryFile(t *testing.T, parts ...string) string {
	t.Helper()
	path := filepath.Join(append([]string{"..", ".."}, parts...)...)
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(data)
}

func TestInstallersVerifyReleaseAndWriteOfficialMetadata(t *testing.T) {
	for _, file := range []string{"install.sh", "install.ps1"} {
		content := repositoryFile(t, "scripts", file)
		for _, required := range []string{"checksums", "SHA256", "install.json", "official"} {
			if !strings.Contains(strings.ToUpper(content), strings.ToUpper(required)) {
				t.Errorf("%s does not contain %q", file, required)
			}
		}
	}
	if !strings.Contains(repositoryFile(t, "scripts", "install.sh"), "--version") {
		t.Error("install.sh must accept --version")
	}
	for _, file := range []string{"install.sh", "install.ps1"} {
		content := repositoryFile(t, "scripts", file)
		if !strings.Contains(content, "release-manifest.json") {
			t.Errorf("%s does not use the release manifest", file)
		}
		if strings.Contains(content, "api.github.com") {
			t.Errorf("%s must not use the rate-limited GitHub REST API", file)
		}
	}
	powerShell := repositoryFile(t, "scripts", "install.ps1")
	if !strings.Contains(powerShell, "param(") || !strings.Contains(powerShell, "[string]$Version") {
		t.Error("PowerShell installer must accept -Version instead of OKIT_VERSION")
	}
	if strings.Contains(repositoryFile(t, "scripts", "install.sh"), "OKIT_VERSION") || strings.Contains(powerShell, "OKIT_VERSION") {
		t.Error("installers must not require OKIT_VERSION to select a release")
	}
	if !strings.Contains(powerShell, "catch") || !strings.Contains(powerShell, "okit 安装失败") {
		t.Error("install.ps1 must convert failures into a friendly user-facing error")
	}
	installShell := repositoryFile(t, "scripts", "install.sh")
	if !strings.Contains(installShell, "安装失败") {
		t.Error("install.sh must convert failures into a friendly user-facing error")
	}
	if !strings.Contains(powerShell, "UTF8Encoding]::new($false)") {
		t.Error("PowerShell installer may write BOM-prefixed JSON that Go cannot decode")
	}
}
