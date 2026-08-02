package installation

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/release"
)

func TestManifestSourceResolvesLatestWithoutAPI(t *testing.T) {
	manifest, _ := release.NewManifest("v2.0.0")
	data, _ := release.MarshalManifest(manifest)
	var requested string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requested = r.URL.Path
		_, _ = w.Write(data)
	}))
	defer server.Close()

	source := ManifestSource{GOOS: "windows", GOARCH: "amd64", Client: server.Client(), ReleaseBase: server.URL + "/releases"}
	releases, err := source.Releases(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if requested != "/releases/latest/download/release-manifest.json" {
		t.Fatalf("requested %q", requested)
	}
	if len(releases) != 1 {
		t.Fatalf("releases=%v", releases)
	}
	release := releases[0]
	if release.Version != "v2.0.0" || release.AssetName != "okit_2.0.0_windows_amd64.zip" || release.Prerelease {
		t.Fatalf("release=%+v", release)
	}
}

func TestManifestSourceUsesAndValidatesExplicitVersion(t *testing.T) {
	manifest, _ := release.NewManifest("v2.0.1-rc.2")
	data, _ := release.MarshalManifest(manifest)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/releases/download/v2.0.0-rc.2/release-manifest.json" {
			t.Errorf("requested %q", r.URL.Path)
		}
		_, _ = w.Write(data)
	}))
	defer server.Close()

	source := ManifestSource{GOOS: "linux", GOARCH: "amd64", Version: "v2.0.0-rc.2", Client: server.Client(), ReleaseBase: server.URL + "/releases"}
	_, err := source.Releases(context.Background())
	if err == nil || !strings.Contains(err.Error(), "does not match requested version") {
		t.Fatalf("error=%v", err)
	}
}

func TestManifestSourceResolvesExplicitPrereleaseWithoutAPI(t *testing.T) {
	manifest, _ := release.NewManifest("v2.0.1-rc.2")
	data, _ := release.MarshalManifest(manifest)
	var requested string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requested = r.URL.Path
		_, _ = w.Write(data)
	}))
	defer server.Close()

	releases, err := (ManifestSource{GOOS: "linux", GOARCH: "amd64", Version: "v2.0.1-rc.2", Client: server.Client(), ReleaseBase: server.URL + "/releases"}).Releases(context.Background())
	if err != nil || requested != "/releases/download/v2.0.1-rc.2/release-manifest.json" || !releases[0].Prerelease {
		t.Fatalf("releases=%+v requested=%q err=%v", releases, requested, err)
	}
}

func TestLifecycleDownloadsManifestAssetAndChecksums(t *testing.T) {
	var archive bytes.Buffer
	zipWriter := zip.NewWriter(&archive)
	file, err := zipWriter.Create("okit.exe")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = file.Write([]byte("new executable"))
	if err := zipWriter.Close(); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(archive.Bytes())
	manifest, _ := release.NewManifest("v2.0.0")
	manifestData, _ := release.MarshalManifest(manifest)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/releases/latest/download/release-manifest.json":
			_, _ = w.Write(manifestData)
		case "/releases/download/v2.0.0/okit_2.0.0_windows_amd64.zip":
			_, _ = w.Write(archive.Bytes())
		case "/releases/download/v2.0.0/checksums.txt":
			_, _ = fmt.Fprintf(w, "%x  okit_2.0.0_windows_amd64.zip\n", digest)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	root := t.TempDir()
	home := filepath.Join(root, "home")
	if err := os.MkdirAll(home, 0o700); err != nil {
		t.Fatal(err)
	}
	executable := filepath.Join(root, "okit.exe")
	replaced := false
	lifecycle := NewLifecycle(Dependencies{
		CurrentVersion: "v1.0.0",
		Executable:     executable,
		OKITHome:       home,
		Metadata:       &Metadata{Method: "official", Version: "v1.0.0", Executable: executable},
		Source: ManifestSource{
			GOOS: "windows", GOARCH: "amd64", Client: server.Client(), ReleaseBase: server.URL + "/releases",
		},
		Downloader: HTTPDownloader{Client: server.Client()},
		Replace: func(_, staged string) (bool, error) {
			data, err := os.ReadFile(staged)
			if err != nil {
				return false, err
			}
			if string(data) != "new executable" {
				return false, fmt.Errorf("staged content %q", data)
			}
			replaced = true
			return false, nil
		},
	})
	result, err := lifecycle.Run(context.Background(), Intent{}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusApplied || result.Available != "v2.0.0" || !replaced {
		t.Fatalf("result=%+v replaced=%t", result, replaced)
	}
}
