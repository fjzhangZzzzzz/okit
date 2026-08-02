package installation

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type UninstallOptions struct {
	Purge, Yes, DryRun bool
	Metadata           *Metadata
}
type UninstallResult struct {
	Plan      []string
	Scheduled bool
}
type UninstallJob struct {
	Executable string `json:"executable"`
	Updater    string `json:"updater"`
	Home       string `json:"home"`
	Purge      bool   `json:"purge"`
	WaitPID    int    `json:"wait_pid"`
}
type Uninstaller struct{ OKITHome, Executable string }

func ValidateUninstallJob(jobPath string, job UninstallJob) error {
	if job.Home == "" || filepath.Base(job.Executable) != "okit.exe" || filepath.Base(job.Updater) != "okit-updater.exe" {
		return fmt.Errorf("invalid uninstall job")
	}
	root, err := filepath.Abs(job.Home)
	if err != nil {
		return fmt.Errorf("invalid uninstall home: %w", err)
	}
	dir, err := filepath.Abs(filepath.Dir(jobPath))
	if err != nil {
		return fmt.Errorf("invalid uninstall job path: %w", err)
	}
	rel, err := filepath.Rel(root, dir)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return fmt.Errorf("uninstall job is outside OKIT_HOME")
	}
	if filepath.Clean(job.Updater) != filepath.Join(filepath.Dir(job.Executable), "okit-updater.exe") {
		return fmt.Errorf("uninstall files are not paired")
	}
	return nil
}

func ExecuteUninstallJob(job UninstallJob) error {
	return executeUninstallJob(job)
}

func ReadUninstallJob(path string) (UninstallJob, error) {
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

func (u *Uninstaller) Uninstall(options UninstallOptions) (UninstallResult, error) {
	metadata := Metadata{}
	var err error
	if options.Metadata != nil {
		metadata = *options.Metadata
	} else {
		metadata, err = LoadMetadata(u.OKITHome)
		if err != nil {
			return UninstallResult{}, err
		}
	}
	managed, err := NewManagedInstallation(metadata)
	if err != nil {
		return UninstallResult{}, err
	}
	plan := managed.UninstallPlan(u.OKITHome, options.Purge)
	result := UninstallResult{Plan: plan}
	if options.DryRun {
		return result, nil
	}
	if options.Purge && !options.Yes {
		return result, errors.New("--purge requires confirmation or --yes")
	}
	if options.Purge {
		if err := validatePurgeHome(u.OKITHome); err != nil {
			return result, err
		}
		if _, err := os.Stat(metadataPath(u.OKITHome)); err != nil {
			return result, errors.New("refusing purge without install metadata in OKIT_HOME")
		}
	}
	if err := removePathEntries(metadata.PathEntries); err != nil {
		return result, err
	}
	for _, file := range metadata.ManagedFiles {
		if metadata.Executable != "" && filepath.Clean(file) == filepath.Clean(filepath.Join(filepath.Dir(metadata.Executable), "okit-updater.exe")) {
			continue // the native updater removes itself after the process exits
		}
		if err := os.Remove(file); err != nil && !os.IsNotExist(err) {
			return result, err
		}
	}
	if metadata.Executable != "" {
		if filepath.Clean(metadata.Executable) == filepath.Clean(u.Executable) && u.Executable != "" {
			scheduled, err := scheduleUninstall(metadata.Executable, u.OKITHome, options.Purge)
			if err != nil {
				return result, err
			}
			result.Scheduled = scheduled
			if scheduled {
				return result, nil
			}
		} else if err := os.Remove(metadata.Executable); err != nil && !os.IsNotExist(err) {
			return result, err
		}
	}
	if options.Purge {
		return result, os.RemoveAll(u.OKITHome)
	}
	if err := os.Remove(metadataPath(u.OKITHome)); err != nil && !os.IsNotExist(err) {
		return result, err
	}
	return result, nil
}

func validatePurgeHome(home string) error {
	clean := filepath.Clean(home)
	volume := filepath.VolumeName(clean)
	root := string(os.PathSeparator)
	if volume != "" {
		root = volume + string(os.PathSeparator)
	}
	if clean == "." || clean == root || clean == volume || filepath.Dir(clean) == clean || strings.TrimSpace(clean) == "" {
		return fmt.Errorf("unsafe OKIT_HOME %q", home)
	}
	return nil
}
