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

// ProgressStage identifies an observable step in a self-update.
type ProgressStage string

const (
	ProgressUpdateAvailable  ProgressStage = "update_available"
	ProgressDownloadAsset    ProgressStage = "download_asset"
	ProgressDownloadChecksum ProgressStage = "download_checksum"
	ProgressVerifyChecksum   ProgressStage = "verify_checksum"
	ProgressExtract          ProgressStage = "extract"
	ProgressReplace          ProgressStage = "replace"
	ProgressComplete         ProgressStage = "complete"
)

// Progress reports a self-update stage. Total is zero when the download size is unknown.
type Progress struct {
	Stage     ProgressStage
	Current   int64
	Total     int64
	Version   string
	Scheduled bool
}

// ProgressReporter receives optional, best-effort update progress notifications.
type ProgressReporter interface {
	ReportProgress(Progress)
}

type ProgressFunc func(Progress)

func (f ProgressFunc) ReportProgress(progress Progress) { f(progress) }

type progressDownloader interface {
	DownloadWithProgress(context.Context, string, func(current, total int64)) ([]byte, error)
}
type ReplaceFunc func(executable, staged string) (scheduled bool, err error)

type UpdateOptions struct {
	Check      bool
	DryRun     bool
	Version    string
	Prerelease bool
	Progress   ProgressReporter
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
	if errors.Is(err, ErrNoPrerelease) {
		return UpdateResult{Current: u.CurrentVersion, Available: u.CurrentVersion, Plan: "no prerelease is available"}, nil
	}
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
	reportProgress(options.Progress, Progress{Stage: ProgressUpdateAvailable, Version: release.Version})
	lock, err := AcquireLock(u.OKITHome)
	if err != nil {
		return UpdateResult{}, err
	}
	defer lock.Release()
	if u.Downloader == nil {
		u.Downloader = HTTPDownloader{Client: &http.Client{Timeout: 2 * time.Minute}}
	}
	archive, err := downloadWithProgress(ctx, u.Downloader, release.AssetURL, options.Progress, ProgressDownloadAsset, release.Version)
	if err != nil {
		return UpdateResult{}, fmt.Errorf("download release asset: %w", err)
	}
	checksums, err := downloadWithProgress(ctx, u.Downloader, release.ChecksumsURL, options.Progress, ProgressDownloadChecksum, release.Version)
	if err != nil {
		return UpdateResult{}, fmt.Errorf("download checksums: %w", err)
	}
	reportProgress(options.Progress, Progress{Stage: ProgressVerifyChecksum, Version: release.Version})
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
	reportProgress(options.Progress, Progress{Stage: ProgressExtract, Version: release.Version})
	staged, err := extractExecutable(release.AssetName, archive, stagingDir)
	if err != nil {
		return UpdateResult{}, err
	}
	replace := u.Replace
	if replace == nil {
		replace = PlatformReplace
	}
	reportProgress(options.Progress, Progress{Stage: ProgressReplace, Version: release.Version})
	scheduled, err := replace(u.Executable, staged)
	if err != nil {
		return UpdateResult{}, err
	}
	metadata.Version = release.Version
	metadata.Channel = releaseChannel(release)
	removeStaging = !scheduled
	if !scheduled {
		if err := SaveMetadata(u.OKITHome, metadata); err != nil {
			return UpdateResult{}, err
		}
	}
	result.Updated, result.Scheduled = true, scheduled
	reportProgress(options.Progress, Progress{Stage: ProgressComplete, Version: release.Version, Scheduled: scheduled})
	return result, nil
}

func releaseChannel(release Release) string {
	if release.Prerelease {
		return "prerelease"
	}
	return "stable"
}

func reportProgress(reporter ProgressReporter, progress Progress) {
	if reporter != nil {
		reporter.ReportProgress(progress)
	}
}

func downloadWithProgress(ctx context.Context, downloader Downloader, url string, reporter ProgressReporter, stage ProgressStage, version string) ([]byte, error) {
	reportProgress(reporter, Progress{Stage: stage, Version: version})
	if downloader, ok := downloader.(progressDownloader); ok {
		return downloader.DownloadWithProgress(ctx, url, func(current, total int64) {
			reportProgress(reporter, Progress{Stage: stage, Current: current, Total: total, Version: version})
		})
	}
	return downloader.Download(ctx, url)
}

func defaultReleaseSource(options UpdateOptions, goos, goarch string, client *http.Client) ReleaseSource {
	return ManifestSource{GOOS: goos, GOARCH: goarch, Version: options.Version, Prerelease: options.Prerelease && options.Version == "", Client: client}
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
	return d.DownloadWithProgress(ctx, url, nil)
}

func (d HTTPDownloader) DownloadWithProgress(ctx context.Context, url string, report func(current, total int64)) ([]byte, error) {
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
	const maxDownloadSize = 300 << 20
	if response.ContentLength > maxDownloadSize {
		return nil, fmt.Errorf("download exceeds %d byte limit", maxDownloadSize)
	}
	total := response.ContentLength
	if total < 0 {
		total = 0
	}
	if report != nil {
		report(0, total)
	}
	reader := io.LimitReader(response.Body, maxDownloadSize+1)
	var data bytes.Buffer
	buffer := make([]byte, 32*1024)
	for {
		count, readErr := reader.Read(buffer)
		if count > 0 {
			_, _ = data.Write(buffer[:count])
			if int64(data.Len()) > maxDownloadSize {
				return nil, fmt.Errorf("download exceeds %d byte limit", maxDownloadSize)
			}
			if report != nil {
				report(int64(data.Len()), total)
			}
		}
		if errors.Is(readErr, io.EOF) {
			return data.Bytes(), nil
		}
		if readErr != nil {
			return nil, readErr
		}
	}
}
