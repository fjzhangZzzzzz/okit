package cli

import (
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/installation"
)

// installationRuntime owns production adapter assembly for the installation lifecycle.
type installationRuntime struct{ app *App }

func (a *App) newInstallationRuntime() installationRuntime { return installationRuntime{app: a} }
func (r installationRuntime) upgradeRunner(options upgradeOptions) (upgradeRunner, error) {
	if r.app.upgradeRunner != nil {
		return r.app.upgradeRunner, nil
	}
	home, executable, err := installationPaths()
	if err != nil {
		return nil, err
	}
	return installation.NewLifecycle(installation.Dependencies{CurrentVersion: r.app.version, Executable: executable, OKITHome: home,
		Source:     installation.ManifestSource{GOOS: runtime.GOOS, GOARCH: runtime.GOARCH, Version: options.version, Prerelease: options.prerelease && options.version == "", Client: &http.Client{Timeout: 30 * time.Second}},
		Downloader: installation.HTTPDownloader{Client: &http.Client{Timeout: 2 * time.Minute}}, Replace: installation.PlatformReplace, ReplaceTransaction: installation.NativeTransactionReplace()}), nil
}
func (r installationRuntime) uninstaller() (selfUninstaller, error) {
	if r.app.selfUninstaller != nil {
		return r.app.selfUninstaller, nil
	}
	home, executable, err := installationPaths()
	if err != nil {
		return nil, err
	}
	return &installation.Uninstaller{OKITHome: home, Executable: executable}, nil
}
func installationPaths() (string, string, error) {
	home, err := config.Home()
	if err != nil {
		return "", "", err
	}
	executable, err := os.Executable()
	if err != nil {
		return "", "", err
	}
	executable, err = filepath.Abs(executable)
	if err != nil {
		return "", "", err
	}
	return home, executable, nil
}
