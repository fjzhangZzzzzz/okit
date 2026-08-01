package releasecontract

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

func TestWorkflowsSeparateRuntimeAndReleaseLifecycleSmokeTests(t *testing.T) {
	releaseWorkflow := repositoryFile(t, ".github", "workflows", "release.yml")
	for _, required := range []string{"release:", "published, released", "github.event.release.prerelease", "GORELEASER_CURRENT_TAG", "cmd/releasemanifest", "pre-release", "gh release edit", "gh release upload", "delete-asset"} {
		if !strings.Contains(releaseWorkflow, required) {
			t.Errorf("发布工作流不包含 %q", required)
		}
	}
	verified := strings.Index(releaseWorkflow, "jq -e --arg version")
	uploaded := strings.Index(releaseWorkflow, "gh release upload pre-release")
	if verified < 0 || uploaded < 0 || verified > uploaded {
		t.Error("预发布指针必须在验证 release-manifest 后更新")
	}
	if !strings.Contains(repositoryFile(t, ".goreleaser.yaml"), "release:") {
		t.Error("GoReleaser 必须发布 Release 制品")
	}
	for _, file := range []string{"smoke-release-lifecycle.sh", "smoke-release-lifecycle.ps1"} {
		smoke := repositoryFile(t, "scripts", file)
		for _, required := range []string{"binary", "release", "upgrade", "uninstall", "smoke-runtime-", "--dry-run", "实际输出"} {
			if !strings.Contains(smoke, required) {
				t.Errorf("%s 不包含 %q", file, required)
			}
		}
	}

	ciWorkflow := repositoryFile(t, ".github", "workflows", "ci.yml")
	for _, file := range []string{"smoke-runtime-linux.sh", "smoke-runtime-windows.ps1", "smoke-runtime-windows-git-bash.sh"} {
		if !strings.Contains(ciWorkflow, file) {
			t.Errorf("CI 工作流没有调用 %s", file)
		}
		smoke := repositoryFile(t, "scripts", file)
		for _, required := range []string{"--version", "--help", "upgrade", "uninstall"} {
			if !strings.Contains(smoke, required) {
				t.Errorf("%s 不包含 %q", file, required)
			}
		}
	}
}
