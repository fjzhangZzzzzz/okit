package releasechannel

import "testing"

func TestManifestPathAndPrereleaseAdvance(t *testing.T) {
	for request, want := range map[Request]string{
		{}:                        "/latest/download/release-manifest.json",
		{IncludePrerelease: true}: "/download/pre-release/release-manifest.json",
		{Version: "v1.2.3"}:       "/download/v1.2.3/release-manifest.json",
	} {
		if got := ManifestPath(request); got != want {
			t.Errorf("ManifestPath(%+v)=%q, want %q", request, got, want)
		}
	}
	if CanAdvancePrerelease(false) {
		t.Fatal("unverified manifest advanced prerelease pointer")
	}
	if !CanAdvancePrerelease(true) {
		t.Fatal("verified manifest did not advance prerelease pointer")
	}
}
