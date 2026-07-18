package mobaxterm

import "testing"

type source struct {
	name       string
	candidates []Candidate
}

func (s source) Name() string                 { return s.name }
func (s source) Detect() ([]Candidate, error) { return s.candidates, nil }

func TestDetectionPriorityAndDedup_MOBA001(t *testing.T) {
	sources := []Source{
		source{name: "registry", candidates: []Candidate{{InstallPath: `C:\Moba`, Version: "25.2"}}},
		source{name: "package-manager", candidates: []Candidate{{InstallPath: `c:\moba`, ExePath: `C:\Moba\MobaXterm.exe`}, {InstallPath: `D:\Portable`}}},
	}
	got, err := DetectAll(sources)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].Source != "registry" || got[0].Version != "25.2" || got[0].ExePath == "" {
		t.Fatalf("candidates=%+v", got)
	}
	if !got[0].Default || got[1].Default {
		t.Fatalf("default target is not explicit: %+v", got)
	}
}
