package cli

import (
	"runtime"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	"github.com/spf13/cobra"
)

func newMobaXtermCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("mobaxterm", "管理 MobaXterm")
	command.AddCommand(newMobaStatusCommand(global), newMobaThemeCommand(global), newMobaLicenseCommand(global))
	return command
}

func mobaContext() (mobaxterm.Service, string, error) {
	if runtime.GOOS != "windows" {
		return mobaxterm.Service{}, "", usageError("MobaXterm 仅支持 Windows")
	}
	home, err := config.Home()
	if err != nil {
		return mobaxterm.Service{}, "", runError(err)
	}
	return mobaxterm.Service{GOOS: runtime.GOOS, OKITHome: home}, home, nil
}
