package installation

import (
	"fmt"
	"os"
	"path/filepath"
)

type Lock struct {
	path string
	file *os.File
}

func AcquireLock(home string) (*Lock, error) {
	if err := os.MkdirAll(home, 0o700); err != nil {
		return nil, err
	}
	path := filepath.Join(home, "install.lock")
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, fmt.Errorf("another update is in progress: %w", err)
	}
	fmt.Fprintln(file, os.Getpid())
	return &Lock{path: path, file: file}, nil
}

func (l *Lock) Release() error {
	if l == nil {
		return nil
	}
	if l.file != nil {
		_ = l.file.Close()
	}
	return os.Remove(l.path)
}
