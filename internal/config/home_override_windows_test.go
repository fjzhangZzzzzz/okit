package config

import "testing"

func TestHomeConvertsExplicitMSYSDrivePath(t *testing.T) {
	t.Setenv("OKIT_HOME", `/c/Users/test/.okit`)
	home, err := Home()
	if err != nil {
		t.Fatal(err)
	}
	if home != `C:\Users\test\.okit` {
		t.Fatalf("Home() = %q", home)
	}
}

func TestNormalizeHomeOverrideConvertsMSYSDriveRoot(t *testing.T) {
	home, err := normalizeHomeOverride(`/d`)
	if err != nil {
		t.Fatal(err)
	}
	if home != `D:\` {
		t.Fatalf("normalizeHomeOverride() = %q", home)
	}
}

func TestHomeRejectsAmbiguousPOSIXPathOnWindows(t *testing.T) {
	t.Setenv("OKIT_HOME", `/home/test/.okit`)
	if _, err := Home(); err == nil {
		t.Fatal("Home() should reject a POSIX path without an MSYS drive prefix")
	}
}

func TestMSYSDrivePathDetectionIsStrict(t *testing.T) {
	for _, path := range []string{`/home/test`, `/cc/test`, `relative/path`, `C:/Users/test`} {
		if isMSYSDrivePath(path) {
			t.Fatalf("isMSYSDrivePath(%q) = true", path)
		}
	}
}
