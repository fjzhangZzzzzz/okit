package release

import (
	"strings"
	"testing"
)

func TestWorkflowSeparatesRuntimeAndReleaseLifecycleSmokeTests(t *testing.T) {
	workflow := repositoryFile(t, ".github", "workflows", "release.yml")
	for _, required := range []string{"release:", "published, released", "cmd/release-manifest", "install.ps1", "install.sh", "gh release view", "直接发布正式版本", "GORELEASER_CURRENT_TAG", "release-publish"} {
		if !strings.Contains(workflow, required) {
			t.Errorf("发布工作流不包含 %q", required)
		}
	}
	for _, removed := range []string{"actions/upload-pages-artifact", "actions/deploy-pages", "pages: write", "id-token: write", "channels/prerelease", "CHANNEL_BASE"} {
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
