package installation

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
	"strings"
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
type TransactionReplaceFunc func(UpdateTransaction) (scheduled bool, err error)

// Mode describes the requested upgrade lifecycle without exposing execution details.
type Mode uint8

const (
	ModeApply Mode = iota
	ModeCheck
	ModeDryRun
)

// Intent is the complete user intent accepted by the lifecycle module.
type Intent struct {
	Mode              Mode
	Version           string
	IncludePrerelease bool
}

type Status uint8

const (
	StatusUpToDate Status = iota
	StatusAvailable
	StatusPlanned
	StatusApplied
	StatusScheduled
)

// Result is the stable semantic outcome of an upgrade lifecycle.
type Result struct {
	Status    Status
	Current   string
	Available string
	Plan      string
}

// FailureKind classifies upgrade failures without leaking transport text to callers.
type FailureKind string

const (
	FailureReleaseAccessDenied FailureKind = "release_access_denied"
)

type Failure struct {
	Kind  FailureKind
	Cause error
}

func (f *Failure) Error() string { return f.Cause.Error() }
func (f *Failure) Unwrap() error { return f.Cause }

// Dependencies are chosen at the CLI composition seam. Each port has production and
// test adapters; the lifecycle owns every remaining execution detail.
type Dependencies struct {
	CurrentVersion     string
	Executable         string
	OKITHome           string
	Source             ReleaseSource
	Downloader         Downloader
	Replace            ReplaceFunc
	ReplaceTransaction TransactionReplaceFunc
	Metadata           *Metadata
}

// Lifecycle is the deep module behind the upgrade seam.
type Lifecycle struct{ Dependencies }

func NewLifecycle(deps Dependencies) *Lifecycle { return &Lifecycle{Dependencies: deps} }

type lifecyclePlan struct {
	result     Result
	release    Release
	managed    ManagedInstallation
	executable string
}

type preparedUpgrade struct {
	lock        *Lock
	stagingDir  string
	staged      string
	metadata    Metadata
	transaction *UpdateTransaction
}

// Run handles check, dry-run, and apply through one interface.
func (u *Lifecycle) Run(ctx context.Context, intent Intent, progress ProgressReporter) (Result, error) {
	plan, err := u.plan(ctx, intent)
	if err != nil {
		return Result{}, err
	}
	if plan.release.Version == "" || intent.Mode == ModeCheck || intent.Mode == ModeDryRun {
		return plan.result, nil
	}
	prepared, err := u.prepare(ctx, plan, progress)
	if err != nil {
		return Result{}, err
	}
	defer prepared.lock.Release()
	return u.apply(plan, prepared, progress)
}

func (u *Lifecycle) plan(ctx context.Context, intent Intent) (lifecyclePlan, error) {
	metadata, err := u.metadata()
	if err != nil {
		return lifecyclePlan{}, err
	}
	managed, err := NewManagedInstallation(metadata)
	if err != nil {
		return lifecyclePlan{}, err
	}
	current := u.CurrentVersion
	if current == "" {
		current = metadata.Version
	}
	executable := u.Executable
	if executable == "" {
		executable = metadata.Executable
	}
	if u.Source == nil {
		return lifecyclePlan{}, errors.New("upgrade lifecycle dependencies are incomplete")
	}
	releases, err := u.Source.Releases(ctx)
	if errors.Is(err, ErrNoPrerelease) {
		return lifecyclePlan{result: Result{Status: StatusUpToDate, Current: current, Available: current, Plan: "no prerelease is available"}}, nil
	}
	if err != nil {
		return lifecyclePlan{}, classifyFailure(err)
	}
	release, err := SelectRelease(current, releases, intent)
	if errors.Is(err, ErrNoUpdate) {
		return lifecyclePlan{result: Result{Status: StatusUpToDate, Current: current, Available: current, Plan: "already up to date"}}, nil
	}
	if err != nil {
		return lifecyclePlan{}, err
	}
	result := Result{Status: StatusAvailable, Current: current, Available: release.Version, Plan: fmt.Sprintf("would update %s to %s", current, release.Version)}
	if intent.Mode == ModeDryRun {
		result.Status = StatusPlanned
	}
	return lifecyclePlan{result: result, release: release, managed: managed, executable: executable}, nil
}

func (u *Lifecycle) prepare(ctx context.Context, plan lifecyclePlan, progress ProgressReporter) (*preparedUpgrade, error) {
	if u.Downloader == nil || u.Replace == nil {
		return nil, errors.New("upgrade lifecycle dependencies are incomplete")
	}
	reportProgress(progress, Progress{Stage: ProgressUpdateAvailable, Version: plan.release.Version})
	lock, err := AcquireLock(u.OKITHome)
	if err != nil {
		return nil, err
	}
	prepared := &preparedUpgrade{lock: lock}
	cleanup := func() {
		if prepared.stagingDir != "" {
			_ = os.RemoveAll(prepared.stagingDir)
		}
		_ = lock.Release()
	}
	archive, err := downloadWithProgress(ctx, u.Downloader, plan.release.AssetURL, progress, ProgressDownloadAsset, plan.release.Version)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("download release asset: %w", err)
	}
	checksums, err := downloadWithProgress(ctx, u.Downloader, plan.release.ChecksumsURL, progress, ProgressDownloadChecksum, plan.release.Version)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("download checksums: %w", err)
	}
	reportProgress(progress, Progress{Stage: ProgressVerifyChecksum, Version: plan.release.Version})
	if err := verifyChecksum(plan.release.AssetName, archive, checksums); err != nil {
		cleanup()
		return nil, err
	}
	stagingDir, err := os.MkdirTemp(u.OKITHome, ".update-*")
	if err != nil {
		cleanup()
		return nil, err
	}
	prepared.stagingDir = stagingDir
	reportProgress(progress, Progress{Stage: ProgressExtract, Version: plan.release.Version})
	staged, err := extractExecutable(plan.release.AssetName, archive, stagingDir)
	if err != nil {
		cleanup()
		return nil, err
	}
	metadata := plan.managed.WithRelease(plan.release.Version, releaseChannel(plan.release)).Metadata
	if metadata.Executable == "" {
		metadata.Executable = plan.executable
	}
	if u.ReplaceTransaction != nil {
		updaterPath := filepath.Join(filepath.Dir(plan.executable), "okit-updater.exe")
		found := false
		for _, file := range metadata.ManagedFiles {
			if filepath.Clean(file) == filepath.Clean(updaterPath) {
				found = true
				break
			}
		}
		if !found {
			metadata.ManagedFiles = append(metadata.ManagedFiles, updaterPath)
		}
	}
	prepared.staged, prepared.metadata = staged, metadata
	if u.ReplaceTransaction != nil {
		currentUpdater := filepath.Join(filepath.Dir(plan.executable), "okit-updater.exe")
		stagedUpdater := filepath.Join(filepath.Dir(staged), "okit-updater.exe")
		transaction := &UpdateTransaction{Schema: 1, State: TransactionPrepared, OKITHome: u.OKITHome,
			TransactionDir: filepath.Dir(staged), Current: plan.executable,
			CurrentUpdater: currentUpdater,
			Staged:         staged, StagedUpdater: stagedUpdater,
			Backup:        filepath.Join(filepath.Dir(staged), "okit.exe.old"),
			UpdaterBackup: filepath.Join(filepath.Dir(staged), "okit-updater.exe.old"),
			OldMetadata:   metadata, NewMetadata: metadata, WaitPID: os.Getpid()}
		if old, e := LoadMetadata(u.OKITHome); e == nil {
			transaction.OldMetadata = old
		}
		transaction.StagedSHA256, err = fileSHA256(staged)
		if err != nil {
			cleanup()
			return nil, err
		}
		transaction.UpdaterSHA256, err = fileSHA256(stagedUpdater)
		if err != nil {
			cleanup()
			return nil, err
		}
		prepared.transaction = transaction
	}
	return prepared, nil
}

func (u *Lifecycle) apply(plan lifecyclePlan, prepared *preparedUpgrade, progress ProgressReporter) (Result, error) {
	removeStaging := true
	defer func() {
		if removeStaging {
			_ = os.RemoveAll(prepared.stagingDir)
		}
	}()
	reportProgress(progress, Progress{Stage: ProgressReplace, Version: plan.release.Version})
	var scheduled bool
	var err error
	if u.ReplaceTransaction != nil {
		currentUpdater := filepath.Join(filepath.Dir(plan.executable), "okit-updater.exe")
		if _, statErr := os.Stat(currentUpdater); statErr != nil {
			return Result{}, fmt.Errorf("SELF_UPDATE_MIGRATION_REQUIRED: install the current release once with install.ps1 before upgrading")
		}
		scheduled, err = u.ReplaceTransaction(*prepared.transaction)
	} else {
		scheduled, err = u.Replace(plan.executable, prepared.staged)
	}
	if err != nil {
		return Result{}, err
	}
	removeStaging = !scheduled
	if !scheduled {
		if err := SaveMetadata(u.OKITHome, prepared.metadata); err != nil {
			return Result{}, err
		}
	}
	result := plan.result
	if scheduled {
		result.Status = StatusScheduled
	} else {
		result.Status = StatusApplied
	}
	reportProgress(progress, Progress{Stage: ProgressComplete, Version: plan.release.Version, Scheduled: scheduled})
	return result, nil
}

func classifyFailure(err error) error {
	if strings.Contains(err.Error(), "HTTP 403") {
		return &Failure{Kind: FailureReleaseAccessDenied, Cause: err}
	}
	return err
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

func (u *Lifecycle) metadata() (Metadata, error) {
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
		found := false
		for _, file := range reader.File {
			base := filepath.Base(file.Name)
			if base != executableName && base != "okit-updater.exe" {
				continue
			}
			found = found || base == executableName
			targetPath := filepath.Join(directory, base)
			stream, err := file.Open()
			if err != nil {
				return "", err
			}
			err = writeLimitedExecutable(targetPath, stream)
			stream.Close()
			if err != nil {
				return "", err
			}
		}
		if found {
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
