package release

import (
	"strings"
	"testing"
)

func TestNewManifestBuildsReleaseMatrix(t *testing.T) {
	manifest, err := NewManifest("v2.0.0")
	if err != nil {
		t.Fatal(err)
	}
	for target, expected := range map[string]string{"linux-amd64": "okit_2.0.0_linux_amd64.tar.gz", "linux-arm64": "okit_2.0.0_linux_arm64.tar.gz", "windows-amd64": "okit_2.0.0_windows_amd64.zip", "windows-arm64": "okit_2.0.0_windows_arm64.zip"} {
		if manifest.Assets[target] != expected {
			t.Errorf("asset %s=%q, want %q", target, manifest.Assets[target], expected)
		}
	}
}

func TestParseManifestRejectsInvalidManifest(t *testing.T) {
	for _, test := range []struct{ name, data, expected, message string }{
		{"schema", `{"schema":2,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"okit.zip"}}`, "", "schema"},
		{"version mismatch", `{"schema":1,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"okit.zip"}}`, "v2.0.1", "does not match"},
		{"unsafe asset", `{"schema":1,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"../okit.zip"}}`, "", "unsafe filename"},
	} {
		t.Run(test.name, func(t *testing.T) {
			_, err := ParseManifest([]byte(test.data), test.expected)
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("error=%v", err)
			}
		})
	}
}
