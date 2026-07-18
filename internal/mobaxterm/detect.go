package mobaxterm

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
)

type Candidate struct {
	InstallPath string `json:"install_path"`
	ExePath     string `json:"exe_path"`
	Version     string `json:"version"`
	Source      string `json:"source"`
	ConfigPath  string `json:"config_path"`
	LicensePath string `json:"license_path"`
	Default     bool   `json:"default"`
}

type Source interface {
	Name() string
	Detect() ([]Candidate, error)
}

func DetectAll(sources []Source) ([]Candidate, error) {
	result := make([]Candidate, 0)
	indexes := make(map[string]int)
	for _, source := range sources {
		candidates, err := source.Detect()
		if err != nil {
			continue
		}
		for _, candidate := range candidates {
			if candidate.InstallPath == "" && candidate.ExePath != "" {
				candidate.InstallPath = filepath.Dir(candidate.ExePath)
			}
			if candidate.InstallPath == "" {
				continue
			}
			candidate.Source = source.Name()
			if candidate.ConfigPath == "" {
				candidate.ConfigPath = filepath.Join(candidate.InstallPath, "MobaXterm.ini")
			}
			if candidate.LicensePath == "" {
				candidate.LicensePath = filepath.Join(candidate.InstallPath, "Custom.mxtpro")
			}
			key := strings.ToLower(filepath.Clean(candidate.InstallPath))
			if index, ok := indexes[key]; ok {
				existing := &result[index]
				if existing.ExePath == "" {
					existing.ExePath = candidate.ExePath
				}
				if existing.Version == "" {
					existing.Version = candidate.Version
				}
				continue
			}
			indexes[key] = len(result)
			result = append(result, candidate)
		}
	}
	if len(result) > 0 {
		result[0].Default = true
	}
	return result, nil
}

type Service struct {
	GOOS       string
	OKITHome   string
	Candidates func() ([]Candidate, error)
}

func (s Service) candidates() ([]Candidate, error) {
	goos := s.GOOS
	if goos == "" {
		goos = runtime.GOOS
	}
	if goos != "windows" {
		return nil, errorsUnsupported()
	}
	if s.Candidates != nil {
		return s.Candidates()
	}
	return DetectAll(DefaultSources())
}

func errorsUnsupported() error {
	return fmt.Errorf("mobaxterm is only supported on Windows")
}

func (s Service) Status() ([]Candidate, error) {
	return s.candidates()
}

func (s Service) DeployLicense(username, version string, dryRun bool) (string, error) {
	candidates, err := s.candidates()
	if err != nil {
		return "", err
	}
	if len(candidates) == 0 {
		return "", fmt.Errorf("MobaXterm installation was not found")
	}
	target := candidates[0]
	if version == "" {
		version = target.Version
	}
	if version == "" {
		return "", fmt.Errorf("MobaXterm version could not be detected; specify --version")
	}
	key, err := license.Generate(username, version)
	if err != nil {
		return "", err
	}
	path := target.LicensePath
	if path == "" {
		path = filepath.Join(target.InstallPath, "Custom.mxtpro")
	}
	if dryRun {
		return fmt.Sprintf("would deploy license to %s", path), nil
	}
	if existing, readErr := os.ReadFile(path); readErr == nil {
		if _, parseErr := license.ReadFile(path); parseErr != nil {
			return "", fmt.Errorf("refusing to overwrite an invalid existing license: %w", parseErr)
		}
		backupDir := filepath.Join(s.OKITHome, "backups", "mobaxterm")
		if err := os.MkdirAll(backupDir, 0o700); err != nil {
			return "", err
		}
		backup := filepath.Join(backupDir, filepath.Base(path)+"."+time.Now().UTC().Format("20060102T150405.000000000Z")+".bak")
		if err := os.WriteFile(backup, existing, 0o600); err != nil {
			return "", err
		}
	} else if !os.IsNotExist(readErr) {
		return "", readErr
	}
	if err := license.CreateFile(path, key); err != nil {
		return "", err
	}
	return fmt.Sprintf("deployed license to %s", path), nil
}
