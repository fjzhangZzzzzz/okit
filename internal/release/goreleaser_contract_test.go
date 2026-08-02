package release

import (
	"strings"
	"testing"
)

func TestGoReleaserBuildsDocumentedMatrixAndPublishesInstallers(t *testing.T) {
	content := repositoryFile(t, ".goreleaser.yaml")
	for _, required := range []string{"linux", "windows", "amd64", "arm64", "okit-updater", "checksums.txt", "release-manifest.json", "install.sh", "install.ps1", "README.md", "LICENSE"} {
		if !strings.Contains(content, required) {
			t.Errorf("GoReleaser configuration does not contain %q", required)
		}
	}
	if !strings.Contains(content, "main.version={{.Tag}}") {
		t.Error("GoReleaser must inject the v-prefixed tag into the binary version")
	}
}
