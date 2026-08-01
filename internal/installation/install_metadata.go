package installation

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

type Metadata struct {
	Method       string   `json:"method"`
	Version      string   `json:"version"`
	Channel      string   `json:"channel"`
	Executable   string   `json:"executable"`
	PathEntries  []string `json:"path_entries,omitempty"`
	ManagedFiles []string `json:"managed_files,omitempty"`
}

func metadataPath(home string) string { return filepath.Join(home, "install.json") }

func SaveMetadata(home string, metadata Metadata) error {
	if metadata.Method == "" {
		return errors.New("install method is required")
	}
	if err := os.MkdirAll(home, 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(metadata, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	tmp, err := os.CreateTemp(home, ".install-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpName, metadataPath(home)); err != nil {
		return fmt.Errorf("replace install metadata: %w", err)
	}
	return nil
}

func LoadMetadata(home string) (Metadata, error) {
	data, err := os.ReadFile(metadataPath(home))
	if err != nil {
		return Metadata{}, fmt.Errorf("read install metadata: %w", err)
	}
	var metadata Metadata
	if err := json.Unmarshal(data, &metadata); err != nil {
		return Metadata{}, fmt.Errorf("parse install metadata: %w", err)
	}
	if metadata.Method == "" {
		return Metadata{}, errors.New("install metadata has no method")
	}
	return metadata, nil
}

func requireOfficial(metadata Metadata) error {
	if metadata.Method != "official" {
		return fmt.Errorf("installation is managed by %s; use that package manager", metadata.Method)
	}
	return nil
}
