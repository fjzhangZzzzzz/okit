package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestHomeUsesTemporaryOKITHOME(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "okit-home")
	t.Setenv("OKIT_HOME", dir)
	got, err := Home()
	if err != nil {
		t.Fatal(err)
	}
	if got != dir {
		t.Fatalf("Home() = %q, want %q", got, dir)
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatalf("Home created directory before a write: %v", err)
	}
}

func TestStoreRoundTripDottedKeys(t *testing.T) {
	dir := t.TempDir()
	store := New(filepath.Join(dir, "config.yaml"))
	if err := store.Set("git-sync.host", "devbox"); err != nil {
		t.Fatal(err)
	}
	if err := store.Set("git-sync.host", "new-devbox"); err != nil {
		t.Fatalf("replace existing config: %v", err)
	}
	got, ok, err := store.Get("git-sync.host")
	if err != nil || !ok || got != "new-devbox" {
		t.Fatalf("Get = %q, %v, %v", got, ok, err)
	}
	all, err := store.List()
	if err != nil || all["git-sync.host"] != "new-devbox" {
		t.Fatalf("List = %#v, %v", all, err)
	}
}
