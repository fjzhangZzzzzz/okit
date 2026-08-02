package installation

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/release"
)

const (
	defaultReleaseBaseURL = "https://github.com/fjzhangZzzzzz/okit/releases"
	defaultChannelBaseURL = "https://fjzhangzzzzzz.github.io/okit"
)

type ManifestSource struct {
	GOOS, GOARCH string
	Version      string
	Prerelease   bool
	Client       *http.Client
	ReleaseBase  string
	ChannelBase  string
}

func (s ManifestSource) Releases(ctx context.Context) ([]Release, error) {
	if s.Client == nil {
		s.Client = http.DefaultClient
	}
	base := strings.TrimRight(s.ReleaseBase, "/")
	if base == "" {
		base = defaultReleaseBaseURL
	}
	if s.Version != "" {
		if err := release.ValidateVersion(s.Version); err != nil {
			return nil, err
		}
	}
	manifestURL := s.manifestURL(base)
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
	if response.StatusCode == http.StatusNotFound && s.Prerelease && s.Version == "" {
		return nil, ErrNoPrerelease
	}
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("release manifest: HTTP %s", response.Status)
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	manifest, err := release.ParseManifest(data, s.Version)
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
		Prerelease:   s.Prerelease,
		AssetName:    asset,
		AssetURL:     downloadBase + "/" + asset,
		ChecksumsURL: downloadBase + "/" + manifest.Checksums,
	}}, nil
}

func (s ManifestSource) manifestURL(base string) string {
	if s.Version != "" {
		return base + "/download/" + s.Version + "/release-manifest.json"
	}
	if s.Prerelease {
		channelBase := strings.TrimRight(s.ChannelBase, "/")
		if channelBase == "" {
			channelBase = defaultChannelBaseURL
		}
		return channelBase + "/channels/prerelease/release-manifest.json"
	}
	return base + "/latest/download/release-manifest.json"
}
