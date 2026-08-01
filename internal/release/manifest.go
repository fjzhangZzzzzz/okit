package release

import (
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
)

const Schema = 1

var (
	versionPattern = regexp.MustCompile(`^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$`)
	assetPattern   = regexp.MustCompile(`^[0-9A-Za-z][0-9A-Za-z._-]*$`)
)

type Manifest struct {
	Schema    int               `json:"schema"`
	Version   string            `json:"version"`
	Checksums string            `json:"checksums"`
	Assets    map[string]string `json:"assets"`
}

func NewManifest(version string) (Manifest, error) {
	if err := ValidateVersion(version); err != nil {
		return Manifest{}, err
	}
	plain := strings.TrimPrefix(version, "v")
	return Manifest{Schema: Schema, Version: version, Checksums: "checksums.txt", Assets: map[string]string{
		"linux-amd64": fmt.Sprintf("okit_%s_linux_amd64.tar.gz", plain), "linux-arm64": fmt.Sprintf("okit_%s_linux_arm64.tar.gz", plain),
		"windows-amd64": fmt.Sprintf("okit_%s_windows_amd64.zip", plain), "windows-arm64": fmt.Sprintf("okit_%s_windows_arm64.zip", plain),
	}}, nil
}

func ValidateVersion(version string) error {
	if !versionPattern.MatchString(version) {
		return fmt.Errorf("invalid release version %q", version)
	}
	return nil
}
func ParseManifest(data []byte, expectedVersion string) (Manifest, error) {
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return Manifest{}, fmt.Errorf("parse release manifest: %w", err)
	}
	if err := manifest.Validate(expectedVersion); err != nil {
		return Manifest{}, err
	}
	return manifest, nil
}
func (m Manifest) Validate(expectedVersion string) error {
	if m.Schema != Schema {
		return fmt.Errorf("unsupported release manifest schema %d", m.Schema)
	}
	if !versionPattern.MatchString(m.Version) {
		return fmt.Errorf("invalid release manifest version %q", m.Version)
	}
	if expectedVersion != "" && m.Version != expectedVersion {
		return fmt.Errorf("release manifest version %s does not match requested version %s", m.Version, expectedVersion)
	}
	if err := validateFilename(m.Checksums); err != nil {
		return fmt.Errorf("invalid checksums filename: %w", err)
	}
	if len(m.Assets) == 0 {
		return errors.New("release manifest has no assets")
	}
	for target, name := range m.Assets {
		if target == "" {
			return errors.New("release manifest has an empty target")
		}
		if err := validateFilename(name); err != nil {
			return fmt.Errorf("invalid asset for %s: %w", target, err)
		}
	}
	return nil
}
func (m Manifest) Asset(goos, goarch string) (string, error) {
	target := goos + "-" + goarch
	if name := m.Assets[target]; name != "" {
		return name, nil
	}
	return "", fmt.Errorf("release manifest has no asset for %s", target)
}
func MarshalManifest(manifest Manifest) ([]byte, error) {
	if err := manifest.Validate(""); err != nil {
		return nil, err
	}
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}
func validateFilename(name string) error {
	if !assetPattern.MatchString(name) || filepath.Base(name) != name || strings.ContainsAny(name, `/\\`) {
		return fmt.Errorf("unsafe filename %q", name)
	}
	return nil
}
