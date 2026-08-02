package installation

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// UpdateJob is the verified, persisted instruction consumed by the detached
// Windows updater. All paths are absolute and supplied by the lifecycle.
type UpdateJob struct {
	WaitPID        int      `json:"wait_pid"`
	Current        string   `json:"current"`
	CurrentUpdater string   `json:"current_updater"`
	Staged         string   `json:"staged"`
	StagedUpdater  string   `json:"staged_updater"`
	OKITHome       string   `json:"okit_home"`
	Metadata       Metadata `json:"metadata"`
}

type UninstallJob struct {
	WaitPID          int    `json:"wait_pid"`
	Executable       string `json:"executable"`
	InstalledUpdater string `json:"installed_updater"`
	OKITHome         string `json:"okit_home"`
	Purge            bool   `json:"purge"`
}

func ApplyUninstallJob(job UninstallJob) error {
	for _, path := range []string{job.Executable, job.InstalledUpdater, job.OKITHome} {
		if path == "" || !filepath.IsAbs(path) {
			return errors.New("uninstall job contains an unsafe path")
		}
	}
	for _, path := range []string{job.Executable, job.InstalledUpdater} {
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	if job.Purge {
		return os.RemoveAll(job.OKITHome)
	}
	if err := os.Remove(metadataPath(job.OKITHome)); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

func SaveUninstallJob(path string, job UninstallJob) error {
	data, err := json.Marshal(job)
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o600)
}
func LoadUninstallJob(path string) (UninstallJob, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return UninstallJob{}, err
	}
	var job UninstallJob
	if err := json.Unmarshal(data, &job); err != nil {
		return UninstallJob{}, err
	}
	return job, nil
}

func SaveUpdateJob(path string, job UpdateJob) error {
	data, err := json.Marshal(job)
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o600)
}

func LoadUpdateJob(path string) (UpdateJob, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return UpdateJob{}, err
	}
	var job UpdateJob
	if err := json.Unmarshal(data, &job); err != nil {
		return UpdateJob{}, err
	}
	return job, nil
}

func ApplyUpdateJob(job UpdateJob) error {
	if err := job.Validate(); err != nil {
		return err
	}
	pairs := []replacementPair{{current: job.Current, staged: job.Staged}, {current: job.CurrentUpdater, staged: job.StagedUpdater}}
	committed := make([]replacementPair, 0, len(pairs))
	for _, pair := range pairs {
		if err := pair.backup(); err != nil {
			rollbackPairs(committed)
			return err
		}
		committed = append(committed, pair)
		if err := os.Rename(pair.staged, pair.current); err != nil {
			rollbackPairs(committed)
			return fmt.Errorf("install %s: %w", filepath.Base(pair.current), err)
		}
	}
	if err := SaveMetadata(job.OKITHome, job.Metadata); err != nil {
		rollbackPairs(committed)
		return err
	}
	for _, pair := range committed {
		_ = os.Remove(pair.backupPath())
	}
	return nil
}

func (job UpdateJob) Validate() error {
	for _, path := range []string{job.Current, job.CurrentUpdater, job.Staged, job.StagedUpdater, job.OKITHome} {
		if path == "" || !filepath.IsAbs(path) {
			return errors.New("update job contains an unsafe path")
		}
	}
	if filepath.Dir(job.Current) != filepath.Dir(job.CurrentUpdater) || filepath.Dir(job.Staged) != filepath.Dir(job.StagedUpdater) {
		return errors.New("update job binaries are not paired")
	}
	if filepath.Clean(job.Metadata.Executable) != filepath.Clean(job.Current) {
		return errors.New("update job metadata executable does not match current binary")
	}
	return nil
}

type replacementPair struct{ current, staged string }

func (pair replacementPair) backupPath() string { return pair.current + ".okit-old" }
func (pair replacementPair) backup() error {
	_ = os.Remove(pair.backupPath())
	if err := os.Rename(pair.current, pair.backupPath()); err != nil {
		return fmt.Errorf("save %s: %w", filepath.Base(pair.current), err)
	}
	return nil
}
func rollbackPairs(pairs []replacementPair) {
	for index := len(pairs) - 1; index >= 0; index-- {
		pair := pairs[index]
		_ = os.Remove(pair.current)
		_ = os.Rename(pair.backupPath(), pair.current)
	}
}
