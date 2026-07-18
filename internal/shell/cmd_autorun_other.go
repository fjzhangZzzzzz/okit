//go:build !windows

package shell

type unavailableCmdAutoRun struct{}

func platformCmdAutoRun() CmdAutoRun               { return unavailableCmdAutoRun{} }
func (unavailableCmdAutoRun) Get() (string, error) { return "", nil }
func (unavailableCmdAutoRun) Set(string) error     { return nil }
