package cli

import (
	"fmt"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
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
