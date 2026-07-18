package releasemanifest

import (
	"strings"
	"testing"
)

func TestNewBuildsReleaseMatrix(t *testing.T) {
	manifest, err := New("v2.0.0")
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]string{
		"linux-amd64":   "okit_2.0.0_linux_amd64.tar.gz",
		"linux-arm64":   "okit_2.0.0_linux_arm64.tar.gz",
		"windows-amd64": "okit_2.0.0_windows_amd64.zip",
		"windows-arm64": "okit_2.0.0_windows_arm64.zip",
	}
	for target, expected := range want {
		if manifest.Assets[target] != expected {
			t.Errorf("asset %s=%q, want %q", target, manifest.Assets[target], expected)
		}
	}
}

func TestParseRejectsInvalidManifest(t *testing.T) {
	tests := []struct {
		name, data, expected, message string
	}{
		{"schema", `{"schema":2,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"okit.zip"}}`, "", "schema"},
		{"version mismatch", `{"schema":1,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"okit.zip"}}`, "v2.0.1", "does not match"},
		{"unsafe asset", `{"schema":1,"version":"v2.0.0","checksums":"checksums.txt","assets":{"windows-amd64":"../okit.zip"}}`, "", "unsafe filename"},
		{"missing assets", `{"schema":1,"version":"v2.0.0","checksums":"checksums.txt","assets":{}}`, "", "no assets"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := Parse([]byte(test.data), test.expected)
			if err == nil || !strings.Contains(err.Error(), test.message) {
				t.Fatalf("error=%v, want message containing %q", err, test.message)
			}
		})
	}
}

func TestAssetRejectsUnknownTarget(t *testing.T) {
	manifest, _ := New("v2.0.0")
	if _, err := manifest.Asset("darwin", "amd64"); err == nil {
		t.Fatal("expected unknown target error")
	}
}
