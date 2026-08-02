package release

import (
	"strings"
	"testing"
)

func TestWorkflowSeparatesRuntimeAndReleaseLifecycleSmokeTests(t *testing.T) {
	workflow := repositoryFile(t, ".github", "workflows", "release.yml")
	for _, required := range []string{"release:", "published, released", "cmd/release-manifest", "actions/upload-pages-artifact@v4", "actions/deploy-pages@v4", "channels/prerelease"} {
		if !strings.Contains(workflow, required) {
			t.Errorf("发布工作流不包含 %q", required)
		}
	}
	for _, removed := range []string{"gh release create pre-release", "gh release upload pre-release", "releases/download/pre-release"} {
		if strings.Contains(workflow, removed) {
			t.Errorf("发布工作流不应再使用固定预发布 Release: %q", removed)
		}
	}
	for _, file := range []string{"smoke-runtime-linux.sh", "smoke-runtime-windows.ps1", "smoke-runtime-windows-git-bash.sh"} {
		if !strings.Contains(repositoryFile(t, ".github", "workflows", "ci.yml"), file) {
			t.Errorf("CI 工作流没有调用 %s", file)
		}
	}
}
