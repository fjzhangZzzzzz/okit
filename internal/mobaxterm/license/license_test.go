package license

import (
	"archive/zip"
	"os"
	"path/filepath"
	"testing"
)

func TestCompatibilityVectorAndFileRoundTrip_MOBA005(t *testing.T) {
	const expected = "2sWKkEyKtQje9p3a5tme9tne+p3a4tGerh3a"
	key, err := Generate("alice", "25.2")
	if err != nil || key != expected {
		t.Fatalf("key=%q err=%v", key, err)
	}
	info, err := InspectKey(key)
	if err != nil || info.Username != "alice" || info.Version != "25.2" || info.UserCount != 1 {
		t.Fatalf("info=%+v err=%v", info, err)
	}
	path := filepath.Join(t.TempDir(), "Custom.mxtpro")
	if err := CreateFile(path, key); err != nil {
		t.Fatal(err)
	}
	reader, err := zip.OpenReader(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if len(reader.File) != 1 || reader.File[0].Name != "Pro.key" {
		t.Fatalf("zip entries=%+v", reader.File)
	}
	read, err := ReadFile(path)
	if err != nil || read != key {
		t.Fatalf("key=%q err=%v", read, err)
	}
	if ok, err := Verify(key, "alice", "25.2"); err != nil || !ok {
		t.Fatalf("verify=%v err=%v", ok, err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatal(err)
	}
}
