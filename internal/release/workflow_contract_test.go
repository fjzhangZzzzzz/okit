package release

import (
	"strings"
	"testing"
)

func TestWorkflowSeparatesRuntimeAndReleaseLifecycleSmokeTests(t *testing.T) {
	workflow := repositoryFile(t, ".github", "workflows", "release.yml")
	for _, required := range []string{"release:", "published, released", "cmd/release-manifest", "pre-release", "gh release upload", "delete-asset"} {
		if !strings.Contains(workflow, required) {
			t.Errorf("发布工作流不包含 %q", required)
		}
	}
	if verified, uploaded := strings.Index(workflow, "jq -e --arg version"), strings.Index(workflow, "gh release upload pre-release"); verified < 0 || uploaded < 0 || verified > uploaded {
		t.Error("预发布指针必须在验证 release-manifest 后更新")
	}
	for _, file := range []string{"smoke-runtime-linux.sh", "smoke-runtime-windows.ps1", "smoke-runtime-windows-git-bash.sh"} {
		if !strings.Contains(repositoryFile(t, ".github", "workflows", "ci.yml"), file) {
			t.Errorf("CI 工作流没有调用 %s", file)
		}
	}
}
