package selfmanage

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/releasemanifest"
)

const (
	defaultReleaseBaseURL = "https://github.com/fjzhangZzzzzz/okit/releases"
	defaultReleaseAPIURL  = "https://api.github.com/repos/fjzhangZzzzzz/okit/releases?per_page=100"
)

type GitHubSource struct {
	GOOS, GOARCH string
	Client       *http.Client
	APIURL       string
}

func (s GitHubSource) Releases(ctx context.Context) ([]Release, error) {
	if s.Client == nil {
		s.Client = http.DefaultClient
	}
	apiURL := s.APIURL
	if apiURL == "" {
		apiURL = defaultReleaseAPIURL
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, apiURL, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("User-Agent", "okit-self-update")
	if token := firstNonEmpty(os.Getenv("GH_TOKEN"), os.Getenv("GITHUB_TOKEN")); token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response, err := s.Client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub releases: HTTP %s", response.Status)
	}
	var payload []struct {
		Tag        string `json:"tag_name"`
		Draft      bool   `json:"draft"`
		Prerelease bool   `json:"prerelease"`
		Assets     []struct {
			Name string `json:"name"`
			URL  string `json:"browser_download_url"`
		} `json:"assets"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return nil, err
	}
	suffix := "_" + s.GOOS + "_" + s.GOARCH
	extension := ".tar.gz"
	if s.GOOS == "windows" {
		extension = ".zip"
	}
	result := make([]Release, 0)
	for _, item := range payload {
		if item.Draft {
			continue
		}
		release := Release{Version: item.Tag, Prerelease: item.Prerelease}
		for _, asset := range item.Assets {
			if strings.Contains(asset.Name, suffix) && strings.HasSuffix(asset.Name, extension) {
				release.AssetName, release.AssetURL = asset.Name, asset.URL
			}
			if asset.Name == "checksums.txt" {
				release.ChecksumsURL = asset.URL
			}
		}
		if release.AssetURL != "" && release.ChecksumsURL != "" {
			result = append(result, release)
		}
	}
	return result, nil
}

type ManifestSource struct {
	GOOS, GOARCH string
	Version      string
	Client       *http.Client
	ReleaseBase  string
}

func (s ManifestSource) Releases(ctx context.Context) ([]Release, error) {
	if s.Client == nil {
		s.Client = http.DefaultClient
	}
	base := strings.TrimRight(s.ReleaseBase, "/")
	if base == "" {
		base = defaultReleaseBaseURL
	}
	manifestURL := base + "/latest/download/release-manifest.json"
	if s.Version != "" {
		if err := releasemanifest.ValidateVersion(s.Version); err != nil {
			return nil, err
		}
		manifestURL = base + "/download/" + s.Version + "/release-manifest.json"
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, manifestURL, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("User-Agent", "okit-self-update")
	response, err := s.Client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("release manifest: HTTP %s", response.Status)
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	manifest, err := releasemanifest.Parse(data, s.Version)
	if err != nil {
		return nil, err
	}
	asset, err := manifest.Asset(s.GOOS, s.GOARCH)
	if err != nil {
		return nil, err
	}
	downloadBase := base + "/download/" + manifest.Version
	return []Release{{
		Version:      manifest.Version,
		Prerelease:   strings.Contains(manifest.Version, "-"),
		AssetName:    asset,
		AssetURL:     downloadBase + "/" + asset,
		ChecksumsURL: downloadBase + "/" + manifest.Checksums,
	}}, nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
