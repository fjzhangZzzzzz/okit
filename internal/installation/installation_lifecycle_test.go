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
	"testing"
)

type fakeSource struct {
	releases []Release
	err      error
	calls    int
}

func TestScheduledWindowsHelperKeepsStagedFiles_SELF006(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	var archive bytes.Buffer
	writer := zip.NewWriter(&archive)
	file, err := writer.Create("okit.exe")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = file.Write([]byte("new executable"))
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(archive.Bytes())
	var staged string
	lifecycle := NewLifecycle(Dependencies{
		CurrentVersion: "v1.0.0",
		Executable:     filepath.Join(root, "okit.exe"),
		OKITHome:       home,
		Metadata:       &Metadata{Method: "official", Executable: filepath.Join(root, "okit.exe")},
		Source:         &fakeSource{releases: []Release{{Version: "v1.1.0", AssetName: "okit.zip", AssetURL: "asset", ChecksumsURL: "sum"}}},
		Downloader: fakeDownload{data: map[string][]byte{
			"asset": archive.Bytes(), "sum": []byte(fmt.Sprintf("%x  okit.zip\n", digest)),
		}},
		Replace: func(_ string, candidate string) (bool, error) {
			staged = candidate
			return true, nil
		},
	})
	result, err := lifecycle.Run(context.Background(), Intent{}, nil)
	if err != nil || result.Status != StatusScheduled {
		t.Fatalf("result=%+v err=%v", result, err)
	}
	if _, err := os.Stat(staged); err != nil {
		t.Fatalf("scheduled replacement input was removed too early: %v", err)
	}
}

func (f *fakeSource) Releases(context.Context) ([]Release, error) {
	f.calls++
	return f.releases, f.err
}

type fakeDownload struct {
	data map[string][]byte
	err  map[string]error
}

func (f fakeDownload) Download(_ context.Context, url string) ([]byte, error) {
	if err := f.err[url]; err != nil {
		return nil, err
	}
	return f.data[url], nil
}

func TestReleaseSelection_SELF001_SELF002(t *testing.T) {
	releases := []Release{{Version: "v1.3.0", Prerelease: true}, {Version: "v1.2.0"}, {Version: "v1.1.0"}}
	selected, err := SelectRelease("v1.1.0", releases, Intent{})
	if err != nil || selected.Version != "v1.2.0" {
		t.Fatalf("selected=%+v err=%v", selected, err)
	}
	selected, err = SelectRelease("v1.2.0", releases, Intent{IncludePrerelease: true})
	if err != nil || selected.Version != "v1.3.0" {
		t.Fatalf("prerelease selected=%+v err=%v", selected, err)
	}
	if _, err := SelectRelease("v1.2.0", releases, Intent{Version: "v1.1.0"}); err != nil {
		t.Fatalf("explicit downgrade rejected: %v", err)
	}
	if _, err := SelectRelease("v1.2.0", []Release{{Version: "v1.1.0"}}, Intent{}); err == nil {
		t.Fatal("implicit downgrade accepted")
	}
	selected, err = SelectRelease("v1.2.0", []Release{{Version: "v1.3.0", Prerelease: true}, {Version: "v1.4.0", Prerelease: true}}, Intent{IncludePrerelease: true})
	if err != nil || selected.Version != "v1.4.0" {
		t.Fatalf("semantic ordering selected=%+v err=%v", selected, err)
	}
}

func TestReleaseChannel(t *testing.T) {
	for release, want := range map[Release]string{
		{Version: "v1.2.3"}:                   "stable",
		{Version: "v1.2.3", Prerelease: true}: "prerelease",
	} {
		if got := releaseChannel(release); got != want {
			t.Errorf("releaseChannel(%+v) = %q, want %q", release, got, want)
		}
	}
}

func TestChecksumOrDownloadFailureDoesNotReplace_SELF003(t *testing.T) {
	dir := t.TempDir()
	executable := filepath.Join(dir, "okit")
	if err := os.WriteFile(executable, []byte("old"), 0o700); err != nil {
		t.Fatal(err)
	}
	source := &fakeSource{releases: []Release{{Version: "v1.1.0", AssetName: "okit.zip", AssetURL: "asset", ChecksumsURL: "sum"}}}
	replaced := false
	lifecycle := NewLifecycle(Dependencies{CurrentVersion: "v1.0.0", Executable: executable, OKITHome: filepath.Join(dir, "home"), Source: source,
		Metadata:   &Metadata{Method: "official", Executable: executable},
		Downloader: fakeDownload{data: map[string][]byte{"asset": []byte("broken"), "sum": []byte("deadbeef  okit.zip\n")}},
		Replace:    func(string, string) (bool, error) { replaced = true; return false, nil },
	})
	if _, err := lifecycle.Run(context.Background(), Intent{}, nil); err == nil {
		t.Fatal("checksum failure accepted")
	}
	if replaced {
		t.Fatal("replace called after checksum failure")
	}
	data, _ := os.ReadFile(executable)
	if string(data) != "old" {
		t.Fatalf("executable changed: %q", data)
	}
}

func TestReplacementFailureRollsBack_SELF004(t *testing.T) {
	dir := t.TempDir()
	executable := filepath.Join(dir, "okit")
	staged := filepath.Join(dir, "new")
	_ = os.WriteFile(executable, []byte("old"), 0o700)
	_ = os.WriteFile(staged, []byte("new"), 0o700)
	calls := 0
	err := CompleteReplacement(executable, staged, func(from, to string) error {
		calls++
		if calls == 2 {
			return fmt.Errorf("injected install rename failure")
		}
		return os.Rename(from, to)
	})
	if err == nil {
		t.Fatal("expected failure")
	}
	data, _ := os.ReadFile(executable)
	if string(data) != "old" {
		t.Fatalf("rollback failed: %q", data)
	}
}

func TestConcurrentUpdateLock_SELF005(t *testing.T) {
	home := t.TempDir()
	first, err := AcquireLock(home)
	if err != nil {
		t.Fatal(err)
	}
	defer first.Release()
	if _, err := AcquireLock(home); err == nil {
		t.Fatal("second lock acquired")
	}
}

func TestInstallMetadataCanBeUpdatedAtomically(t *testing.T) {
	home := t.TempDir()
	metadata := Metadata{Method: "official", Version: "v1.0.0"}
	if err := SaveMetadata(home, metadata); err != nil {
		t.Fatal(err)
	}
	metadata.Version = "v1.1.0"
	if err := SaveMetadata(home, metadata); err != nil {
		t.Fatal(err)
	}
	loaded, err := LoadMetadata(home)
	if err != nil || loaded.Version != "v1.1.0" {
		t.Fatalf("metadata=%+v err=%v", loaded, err)
	}
}

func TestManagedInstallationOwnsSafetyAndResourcePlan(t *testing.T) {
	metadata := Metadata{Method: "official", Executable: "okit", ManagedFiles: []string{"managed"}}
	managed, err := NewManagedInstallation(metadata)
	if err != nil {
		t.Fatal(err)
	}
	if got := managed.UninstallPlan("home", true); len(got) != 4 {
		t.Fatalf("plan=%v", got)
	}
	if got := managed.WithRelease("v1.2.0", "prerelease").Metadata; got.Version != "v1.2.0" || got.Channel != "prerelease" {
		t.Fatalf("metadata=%+v", got)
	}
	if _, err := NewManagedInstallation(Metadata{Method: "scoop"}); err == nil {
		t.Fatal("package-managed installation accepted")
	}
}

func TestUninstallPreservePurgeAndManagedResources_SELF007_SELF008_SELF009(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, ".okit")
	executable := filepath.Join(root, "bin", "okit")
	managed := filepath.Join(root, "bin", "managed.txt")
	_ = os.MkdirAll(filepath.Join(home, "data"), 0o700)
	_ = os.MkdirAll(filepath.Dir(executable), 0o700)
	_ = os.WriteFile(executable, []byte("bin"), 0o700)
	_ = os.WriteFile(managed, []byte("managed"), 0o600)
	_ = os.WriteFile(filepath.Join(home, "data", "user.txt"), []byte("keep"), 0o600)
	metadata := Metadata{Method: "official", Executable: executable, ManagedFiles: []string{managed}}
	if err := SaveMetadata(home, metadata); err != nil {
		t.Fatal(err)
	}
	manager := Uninstaller{OKITHome: home, Executable: filepath.Join(root, "not-running")}
	if _, err := manager.Uninstall(UninstallOptions{Yes: true}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(home, "data", "user.txt")); err != nil {
		t.Fatalf("user data removed: %v", err)
	}
	if _, err := os.Stat(managed); !os.IsNotExist(err) {
		t.Fatalf("managed file remains: %v", err)
	}
	if err := SaveMetadata(home, metadata); err != nil {
		t.Fatal(err)
	}
	if _, err := manager.Uninstall(UninstallOptions{Purge: true, Yes: true}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("purge did not remove home: %v", err)
	}
	unsafe := Uninstaller{OKITHome: root, Executable: manager.Executable}
	if _, err := unsafe.Uninstall(UninstallOptions{Purge: true, Yes: true, Metadata: &metadata}); err == nil {
		t.Fatal("unsafe purge root accepted")
	}
}

func TestPackageManagerRefused_SELF010(t *testing.T) {
	home := t.TempDir()
	metadata := Metadata{Method: "scoop", Executable: filepath.Join(home, "okit.exe")}
	if err := SaveMetadata(home, metadata); err != nil {
		t.Fatal(err)
	}
	if _, err := NewLifecycle(Dependencies{OKITHome: home}).Run(context.Background(), Intent{}, nil); err == nil {
		t.Fatal("package manager update accepted")
	}
	if _, err := (&Uninstaller{OKITHome: home}).Uninstall(UninstallOptions{Yes: true}); err == nil {
		t.Fatal("package manager uninstall accepted")
	}
}

func TestCheckAndDryRunHaveNoSideEffects_SELF011(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "missing-home")
	archive := []byte("archive")
	hash := sha256.Sum256(archive)
	source := &fakeSource{releases: []Release{{Version: "v1.1.0", AssetName: "okit.zip", AssetURL: "asset", ChecksumsURL: "sum"}}}
	lifecycle := NewLifecycle(Dependencies{CurrentVersion: "v1.0.0", OKITHome: home, Source: source, Metadata: &Metadata{Method: "official"}, Downloader: fakeDownload{data: map[string][]byte{
		"asset": archive, "sum": []byte(fmt.Sprintf("%x  okit.zip\n", hash)),
	}}})
	if _, err := lifecycle.Run(context.Background(), Intent{Mode: ModeCheck}, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := lifecycle.Run(context.Background(), Intent{Mode: ModeDryRun}, nil); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("check/dry-run created home: %v", err)
	}
}

func TestLifecycleCheckHasNoSideEffects(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "missing-home")
	lifecycle := NewLifecycle(Dependencies{
		CurrentVersion: "v1.0.0",
		OKITHome:       home,
		Metadata:       &Metadata{Method: "official"},
		Source:         &fakeSource{releases: []Release{{Version: "v1.1.0"}}},
		Downloader:     fakeDownload{},
		Replace: func(string, string) (bool, error) {
			t.Fatal("check must not replace the executable")
			return false, nil
		},
	})

	result, err := lifecycle.Run(context.Background(), Intent{Mode: ModeCheck}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if result.Status != StatusAvailable || result.Current != "v1.0.0" || result.Available != "v1.1.0" {
		t.Fatalf("result=%+v", result)
	}
	if _, err := os.Stat(home); !os.IsNotExist(err) {
		t.Fatalf("check created home: %v", err)
	}
}

func TestLifecyclePlanDoesNotMutateDependencies(t *testing.T) {
	lifecycle := NewLifecycle(Dependencies{
		OKITHome: t.TempDir(),
		Metadata: &Metadata{Method: "official", Version: "v1.0.0", Executable: "okit"},
		Source:   &fakeSource{releases: []Release{{Version: "v1.1.0"}}},
	})
	for _, mode := range []Mode{ModeCheck, ModeDryRun} {
		if _, err := lifecycle.Run(context.Background(), Intent{Mode: mode}, nil); err != nil {
			t.Fatalf("mode=%v: %v", mode, err)
		}
	}
	if lifecycle.CurrentVersion != "" || lifecycle.Executable != "" {
		t.Fatalf("planning mutated dependencies: current=%q executable=%q", lifecycle.CurrentVersion, lifecycle.Executable)
	}
}

func TestUpToDateCheckIsSuccessful_SELF001(t *testing.T) {
	lifecycle := NewLifecycle(Dependencies{
		CurrentVersion: "v1.0.0",
		Metadata:       &Metadata{Method: "official"},
		Source:         &fakeSource{releases: []Release{{Version: "v1.0.0"}}},
	})
	result, err := lifecycle.Run(context.Background(), Intent{Mode: ModeCheck}, nil)
	if err != nil || result.Current != "v1.0.0" || result.Available != "v1.0.0" || result.Status != StatusUpToDate {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}

func TestHTTPDownloaderReportsProgress(t *testing.T) {
	payload := bytes.Repeat([]byte("x"), 64*1024)
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Length", fmt.Sprint(len(payload)))
		_, _ = writer.Write(payload)
	}))
	defer server.Close()

	var updates []Progress
	data, err := (HTTPDownloader{Client: server.Client()}).DownloadWithProgress(context.Background(), server.URL, func(current, total int64) {
		updates = append(updates, Progress{Current: current, Total: total})
	})
	if err != nil || !bytes.Equal(data, payload) {
		t.Fatalf("err=%v bytes=%d", err, len(data))
	}
	if len(updates) < 2 || updates[0].Current != 0 || updates[0].Total != int64(len(payload)) {
		t.Fatalf("initial progress=%+v", updates)
	}
	last := updates[len(updates)-1]
	if last.Current != int64(len(payload)) || last.Total != int64(len(payload)) {
		t.Fatalf("final progress=%+v", last)
	}
}

func TestLifecycleReportsProgressStages(t *testing.T) {
	root := t.TempDir()
	archive := bytes.NewBuffer(nil)
	zipWriter := zip.NewWriter(archive)
	file, err := zipWriter.Create("okit.exe")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = file.Write([]byte("new executable"))
	if err := zipWriter.Close(); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(archive.Bytes())
	var stages []ProgressStage
	lifecycle := NewLifecycle(Dependencies{
		CurrentVersion: "v1.0.0", Executable: filepath.Join(root, "okit.exe"), OKITHome: filepath.Join(root, "home"),
		Metadata: &Metadata{Method: "official"},
		Source:   &fakeSource{releases: []Release{{Version: "v1.1.0", Prerelease: true, AssetName: "okit.zip", AssetURL: "asset", ChecksumsURL: "sum"}}},
		Downloader: fakeDownload{data: map[string][]byte{
			"asset": archive.Bytes(), "sum": []byte(fmt.Sprintf("%x  okit.zip\n", digest)),
		}},
		Replace: func(_, _ string) (bool, error) { return false, nil },
	})
	_, err = lifecycle.Run(context.Background(), Intent{IncludePrerelease: true}, ProgressFunc(func(progress Progress) {
		stages = append(stages, progress.Stage)
	}))
	if err != nil {
		t.Fatal(err)
	}
	metadata, err := LoadMetadata(filepath.Join(root, "home"))
	if err != nil || metadata.Channel != "prerelease" {
		t.Fatalf("metadata=%+v err=%v", metadata, err)
	}
	want := []ProgressStage{ProgressUpdateAvailable, ProgressDownloadAsset, ProgressDownloadChecksum, ProgressVerifyChecksum, ProgressExtract, ProgressReplace, ProgressComplete}
	if len(stages) != len(want) {
		t.Fatalf("stages=%v want=%v", stages, want)
	}
	for index := range want {
		if stages[index] != want[index] {
			t.Fatalf("stages=%v want=%v", stages, want)
		}
	}
}
