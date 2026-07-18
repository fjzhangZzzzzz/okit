package config

import (
	"bufio"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func Home() (string, error) {
	if home := os.Getenv("OKIT_HOME"); home != "" {
		return normalizeHomeOverride(home)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve user home: %w", err)
	}
	return filepath.Join(home, ".okit"), nil
}

type Store struct {
	path string
}

func New(path string) *Store {
	return &Store{path: path}
}

func DefaultStore() (*Store, error) {
	home, err := Home()
	if err != nil {
		return nil, err
	}
	return New(filepath.Join(home, "config.yaml")), nil
}

func (s *Store) Get(key string) (string, bool, error) {
	values, err := s.List()
	if err != nil {
		return "", false, err
	}
	value, ok := values[key]
	return value, ok, nil
}

func (s *Store) Set(key, value string) error {
	if err := validateKey(key); err != nil {
		return err
	}
	values, err := s.List()
	if err != nil {
		return err
	}
	values[key] = value
	return s.write(values)
}

func (s *Store) List() (map[string]string, error) {
	values := make(map[string]string)
	f, err := os.Open(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return values, nil
	}
	if err != nil {
		return nil, fmt.Errorf("open config: %w", err)
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("invalid config line %q", line)
		}
		key := strings.TrimSpace(parts[0])
		if err := validateKey(key); err != nil {
			return nil, err
		}
		raw := strings.TrimSpace(parts[1])
		value, err := strconv.Unquote(raw)
		if err != nil {
			return nil, fmt.Errorf("invalid config value for %s: %w", key, err)
		}
		values[key] = value
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}
	return values, nil
}

func validateKey(key string) error {
	if key == "" {
		return errors.New("config key is empty")
	}
	for _, r := range key {
		if !(r == '-' || r == '.' || r == '_' || r >= 'a' && r <= 'z' || r >= '0' && r <= '9') {
			return fmt.Errorf("invalid config key %q", key)
		}
	}
	return nil
}

func (s *Store) write(values map[string]string) error {
	if err := os.MkdirAll(filepath.Dir(s.path), 0o700); err != nil {
		return fmt.Errorf("create config directory: %w", err)
	}
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	tmp, err := os.CreateTemp(filepath.Dir(s.path), ".config-*.tmp")
	if err != nil {
		return fmt.Errorf("create temporary config: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(0o600); err != nil {
		tmp.Close()
		return err
	}
	for _, key := range keys {
		if _, err := fmt.Fprintf(tmp, "%s: %s\n", key, strconv.Quote(values[key])); err != nil {
			tmp.Close()
			return err
		}
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmpName, s.path); err != nil {
		return fmt.Errorf("replace config: %w", err)
	}
	return nil
}
