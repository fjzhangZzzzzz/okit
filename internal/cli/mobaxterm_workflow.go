package cli

import (
	"fmt"
	"io"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
)

// selectedMobaInstallation is the CLI workflow module for every mutating action.
// It preserves the existing default-candidate policy in one place.
type selectedMobaInstallation struct {
	service   mobaxterm.Service
	home      string
	candidate mobaxterm.Candidate
}

func selectMobaInstallation() (selectedMobaInstallation, error) {
	service, home, err := mobaContext()
	if err != nil {
		return selectedMobaInstallation{}, err
	}
	return selectDefaultMobaInstallation(service, home)
}

func selectDefaultMobaInstallation(service mobaxterm.Service, home string) (selectedMobaInstallation, error) {
	candidates, err := service.Status()
	if err != nil {
		return selectedMobaInstallation{}, runError(err)
	}
	if len(candidates) == 0 {
		return selectedMobaInstallation{}, runError(fmt.Errorf("MobaXterm installation was not found"))
	}
	return selectedMobaInstallation{service: service, home: home, candidate: candidates[0]}, nil
}

func needsMobaConfirmation(dryRun, force bool) bool { return !dryRun && !force }

// confirmMobaAction is the CLI adapter for terminal confirmation. MobaXterm
// action modules receive only an already-confirmed intent and never read a terminal.
func confirmMobaAction(stdin io.Reader, presenter *clioutput.Presenter, dryRun, force bool, prompt string) bool {
	return !needsMobaConfirmation(dryRun, force) || confirmAction(stdin, presenter, prompt)
}
