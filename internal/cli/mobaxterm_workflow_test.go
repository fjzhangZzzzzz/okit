package cli

import (
	"strings"
	"testing"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
)

func TestSelectedMobaInstallationUsesDefaultCandidate(t *testing.T) {
	service := mobaxterm.Service{GOOS: "windows", Candidates: func() ([]mobaxterm.Candidate, error) {
		return []mobaxterm.Candidate{{InstallPath: "first", ConfigPath: "first.ini", Default: true}, {InstallPath: "second", ConfigPath: "second.ini"}}, nil
	}}
	selected, err := selectDefaultMobaInstallation(service, "home")
	if err != nil || selected.candidate.InstallPath != "first" || selected.home != "home" {
		t.Fatalf("selected=%+v err=%v", selected, err)
	}
}

func TestSelectedMobaInstallationRejectsMissingInstallation(t *testing.T) {
	service := mobaxterm.Service{GOOS: "windows", Candidates: func() ([]mobaxterm.Candidate, error) { return nil, nil }}
	_, err := selectDefaultMobaInstallation(service, "home")
	if err == nil || !strings.Contains(err.Error(), "未找到 MobaXterm 安装") {
		t.Fatalf("err=%v", err)
	}
}

func TestMobaConfirmationOnlyAppliesToWrites(t *testing.T) {
	for input, want := range map[[2]bool]bool{{false, false}: true, {true, false}: false, {false, true}: false} {
		if got := needsMobaConfirmation(input[0], input[1]); got != want {
			t.Errorf("needsMobaConfirmation(%v)=%t, want %t", input, got, want)
		}
	}
}
