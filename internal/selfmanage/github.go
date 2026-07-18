package selfmanage

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

type GitHubSource struct {
	GOOS, GOARCH string
	Client       *http.Client
}

func (s GitHubSource) Releases(ctx context.Context) ([]Release, error) {
	if s.Client == nil {
		s.Client = http.DefaultClient
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://api.github.com/repos/fjzhangZzzzzz/okit/releases?per_page=100", nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("User-Agent", "okit-self-update")
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
