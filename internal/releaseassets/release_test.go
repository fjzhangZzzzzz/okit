package releaseassets

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
		for _, required := range []string{"checksums", "SHA256", "install.json", "official", "OKIT_VERSION"} {
			if !strings.Contains(strings.ToUpper(content), strings.ToUpper(required)) {
				t.Errorf("%s does not contain %q", file, required)
			}
		}
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
	if !strings.Contains(powerShell, "UTF8Encoding]::new($false)") {
		t.Error("PowerShell installer may write BOM-prefixed JSON that Go cannot decode")
	}
}

func TestGoReleaserBuildsDocumentedMatrixAndPublishesInstallers(t *testing.T) {
	content := repositoryFile(t, ".goreleaser.yaml")
	for _, required := range []string{"linux", "windows", "amd64", "arm64", "checksums.txt", "release-manifest.json", "install.sh", "install.ps1", "README.md", "LICENSE"} {
		if !strings.Contains(content, required) {
			t.Errorf("GoReleaser configuration does not contain %q", required)
		}
	}
	if !strings.Contains(content, "main.version={{.Tag}}") {
		t.Error("GoReleaser must inject the v-prefixed tag into the binary version")
	}
}

func TestReleaseWorkflowRunsInstallUpdateAndUninstallSmokeTests(t *testing.T) {
	content := repositoryFile(t, ".github", "workflows", "release.yml")
	for _, required := range []string{"smoke-linux", "smoke-windows", "smoke-release.sh", "smoke-release.ps1", "--release", "internal/releasemanifest/cmd/generate"} {
		if !strings.Contains(content, required) {
			t.Errorf("release workflow does not contain %q", required)
		}
	}
	for _, file := range []string{"smoke-release.sh", "smoke-release.ps1"} {
		smoke := repositoryFile(t, "scripts", file)
		for _, required := range []string{"binary", "release", "self update", "self uninstall", "--dry-run", "actual output"} {
			if !strings.Contains(smoke, required) {
				t.Errorf("%s does not contain %q", file, required)
			}
		}
	}
}
