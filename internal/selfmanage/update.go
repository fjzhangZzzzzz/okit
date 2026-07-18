package selfmanage

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type Release struct {
	Version      string
	Prerelease   bool
	AssetName    string
	AssetURL     string
	ChecksumsURL string
}

type ReleaseSource interface {
	Releases(context.Context) ([]Release, error)
}
type Downloader interface {
	Download(context.Context, string) ([]byte, error)
}
type ReplaceFunc func(executable, staged string) (scheduled bool, err error)

type UpdateOptions struct {
	Check      bool
	DryRun     bool
	Version    string
	Prerelease bool
}

type UpdateResult struct {
	Current   string
	Available string
	Updated   bool
	Scheduled bool
	Plan      string
}

type Updater struct {
	CurrentVersion string
	Executable     string
	OKITHome       string
	GOOS           string
	GOARCH         string
	Source         ReleaseSource
	Downloader     Downloader
	Replace        ReplaceFunc
	Metadata       *Metadata
}

func (u *Updater) Update(ctx context.Context, options UpdateOptions) (UpdateResult, error) {
	metadata, err := u.metadata()
	if err != nil {
		return UpdateResult{}, err
	}
	if err := requireOfficial(metadata); err != nil {
		return UpdateResult{}, err
	}
	if u.CurrentVersion == "" {
		u.CurrentVersion = metadata.Version
	}
	if u.Executable == "" {
		u.Executable = metadata.Executable
	}
	if u.Source == nil {
		goos, arch := u.GOOS, u.GOARCH
		if goos == "" {
			goos = runtime.GOOS
		}
		if arch == "" {
			arch = runtime.GOARCH
		}
		client := &http.Client{Timeout: 30 * time.Second}
		u.Source = defaultReleaseSource(options, goos, arch, client)
	}
	releases, err := u.Source.Releases(ctx)
	if err != nil {
		return UpdateResult{}, err
	}
	release, err := SelectRelease(u.CurrentVersion, releases, options)
	if errors.Is(err, ErrNoUpdate) {
		return UpdateResult{Current: u.CurrentVersion, Available: u.CurrentVersion, Plan: "already up to date"}, nil
	}
	if err != nil {
		return UpdateResult{}, err
	}
	result := UpdateResult{Current: u.CurrentVersion, Available: release.Version, Plan: fmt.Sprintf("would update %s to %s", u.CurrentVersion, release.Version)}
	if options.Check || options.DryRun {
		return result, nil
	}
	lock, err := AcquireLock(u.OKITHome)
	if err != nil {
		return UpdateResult{}, err
	}
	defer lock.Release()
	if u.Downloader == nil {
		u.Downloader = HTTPDownloader{Client: &http.Client{Timeout: 2 * time.Minute}}
	}
	archive, err := u.Downloader.Download(ctx, release.AssetURL)
	if err != nil {
		return UpdateResult{}, fmt.Errorf("download release asset: %w", err)
	}
	checksums, err := u.Downloader.Download(ctx, release.ChecksumsURL)
	if err != nil {
		return UpdateResult{}, fmt.Errorf("download checksums: %w", err)
	}
	if err := verifyChecksum(release.AssetName, archive, checksums); err != nil {
		return UpdateResult{}, err
	}
	stagingDir, err := os.MkdirTemp(u.OKITHome, ".update-*")
	if err != nil {
		return UpdateResult{}, err
	}
	removeStaging := true
	defer func() {
		if removeStaging {
			_ = os.RemoveAll(stagingDir)
		}
	}()
	staged, err := extractExecutable(release.AssetName, archive, stagingDir)
	if err != nil {
		return UpdateResult{}, err
	}
	replace := u.Replace
	if replace == nil {
		replace = PlatformReplace
	}
	scheduled, err := replace(u.Executable, staged)
	if err != nil {
		return UpdateResult{}, err
	}
	metadata.Version = release.Version
	removeStaging = !scheduled
	if !scheduled {
		if err := SaveMetadata(u.OKITHome, metadata); err != nil {
			return UpdateResult{}, err
		}
	}
	result.Updated, result.Scheduled = true, scheduled
	return result, nil
}

func defaultReleaseSource(options UpdateOptions, goos, goarch string, client *http.Client) ReleaseSource {
	if options.Prerelease && options.Version == "" {
		return GitHubSource{GOOS: goos, GOARCH: goarch, Client: client}
	}
	return ManifestSource{GOOS: goos, GOARCH: goarch, Version: options.Version, Client: client}
}

func (u *Updater) metadata() (Metadata, error) {
	if u.Metadata != nil {
		return *u.Metadata, nil
	}
	return LoadMetadata(u.OKITHome)
}

func verifyChecksum(name string, data, checksumFile []byte) error {
	want := ""
	for _, line := range strings.Split(string(checksumFile), "\n") {
		fields := strings.Fields(line)
		if len(fields) >= 2 && strings.TrimPrefix(fields[len(fields)-1], "*") == name {
			want = fields[0]
			break
		}
	}
	if want == "" {
		return fmt.Errorf("checksum for %s is missing", name)
	}
	digest := sha256.Sum256(data)
	if !strings.EqualFold(want, hex.EncodeToString(digest[:])) {
		return fmt.Errorf("checksum mismatch for %s", name)
	}
	return nil
}

func extractExecutable(name string, data []byte, directory string) (string, error) {
	executableName := "okit"
	if strings.HasSuffix(strings.ToLower(name), ".zip") {
		executableName += ".exe"
	}
	target := filepath.Join(directory, executableName)
	if strings.HasSuffix(strings.ToLower(name), ".zip") {
		reader, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
		if err != nil {
			return "", err
		}
		for _, file := range reader.File {
			if filepath.Base(file.Name) != executableName {
				continue
			}
			stream, err := file.Open()
			if err != nil {
				return "", err
			}
			err = writeLimitedExecutable(target, stream)
			stream.Close()
			if err != nil {
				return "", err
			}
			return target, nil
		}
		return "", errors.New("okit executable is missing from archive")
	}
	gzipReader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	defer gzipReader.Close()
	tarReader := tar.NewReader(gzipReader)
	for {
		header, err := tarReader.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return "", err
		}
		if filepath.Base(header.Name) == executableName {
			if err := writeLimitedExecutable(target, tarReader); err != nil {
				return "", err
			}
			return target, nil
		}
	}
	return "", errors.New("okit executable is missing from archive")
}

func writeLimitedExecutable(path string, reader io.Reader) error {
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o700)
	if err != nil {
		return err
	}
	_, copyErr := io.Copy(file, io.LimitReader(reader, 256<<20))
	syncErr := file.Sync()
	closeErr := file.Close()
	if copyErr != nil {
		return copyErr
	}
	if syncErr != nil {
		return syncErr
	}
	return closeErr
}

type HTTPDownloader struct{ Client *http.Client }

func (d HTTPDownloader) Download(ctx context.Context, url string) ([]byte, error) {
	if d.Client == nil {
		d.Client = http.DefaultClient
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	response, err := d.Client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %s", response.Status)
	}
	return io.ReadAll(io.LimitReader(response.Body, 300<<20))
}
