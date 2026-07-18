package theme

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestApplyPreservesUnrelatedContent_MOBA002(t *testing.T) {
	dir := t.TempDir()
	config := filepath.Join(dir, "MobaXterm.ini")
	scheme := filepath.Join(dir, "Solarized.ini")
	original := "; keep comment\r\n[Colors]\r\nBlack=0,0,0\r\nCustomKey=yes\r\nForegroundColour=1,2,3\r\n"
	if err := os.WriteFile(config, []byte(original), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(scheme, []byte("Black=10,20,30\nForegroundColour=200,210,220\nUnknown=9,9,9\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	result, err := Apply(config, scheme, filepath.Join(dir, "backups"), false, nil)
	if err != nil || result.BackupPath == "" {
		t.Fatalf("result=%+v err=%v", result, err)
	}
	data, _ := os.ReadFile(config)
	text := string(data)
	for _, expected := range []string{"; keep comment\r\n", "Black=10,20,30\r\n", "CustomKey=yes\r\n", "ForegroundColour=200,210,220\r\n"} {
		if !strings.Contains(text, expected) {
			t.Fatalf("missing %q in %q", expected, text)
		}
	}
	if strings.Contains(text, "Unknown") {
		t.Fatalf("unknown key added: %q", text)
	}
}

func TestApplyFailureLeavesConfigRecoverable_MOBA003(t *testing.T) {
	dir := t.TempDir()
	config := filepath.Join(dir, "MobaXterm.ini")
	scheme := filepath.Join(dir, "theme.ini")
	original := []byte("Black=0,0,0\n")
	_ = os.WriteFile(config, original, 0o600)
	_ = os.WriteFile(scheme, []byte("Black=1,2,3\n"), 0o600)
	replace := func(string, []byte, os.FileMode) error { return errors.New("failure") }
	result, err := Apply(config, scheme, filepath.Join(dir, "backups"), false, replace)
	if err == nil || result.BackupPath == "" {
		t.Fatalf("result=%+v err=%v", result, err)
	}
	data, _ := os.ReadFile(config)
	if string(data) != string(original) {
		t.Fatalf("config changed: %q", data)
	}
	backup, readErr := os.ReadFile(result.BackupPath)
	if readErr != nil || string(backup) != string(original) {
		t.Fatalf("backup=%q err=%v", backup, readErr)
	}
}

func TestCleanCacheIsScoped_MOBA004(t *testing.T) {
	home := t.TempDir()
	cache := filepath.Join(home, "cache", "mobaxterm", "themes")
	if err := os.MkdirAll(cache, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := CleanCache(home, cache, false); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(cache); !os.IsNotExist(err) {
		t.Fatalf("cache remains: %v", err)
	}
	outside := filepath.Join(home, "data")
	if err := CleanCache(home, outside, false); err == nil {
		t.Fatal("unsafe cache path accepted")
	}
}
