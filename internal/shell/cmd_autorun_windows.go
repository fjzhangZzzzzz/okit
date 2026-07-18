//go:build windows

package shell

import (
	"errors"
	"fmt"
	"os/exec"
	"strings"
)

type windowsCmdAutoRun struct{}

func platformCmdAutoRun() CmdAutoRun { return windowsCmdAutoRun{} }

func (windowsCmdAutoRun) Get() (string, error) {
	output, err := exec.Command("reg", "query", `HKCU\Software\Microsoft\Command Processor`, "/v", "AutoRun").CombinedOutput()
	if err != nil {
		if strings.Contains(strings.ToLower(string(output)), "unable to find") || strings.Contains(strings.ToLower(string(output)), "not find") {
			return "", nil
		}
		return "", fmt.Errorf("read CMD AutoRun: %w: %s", err, strings.TrimSpace(string(output)))
	}
	for _, line := range strings.Split(string(output), "\n") {
		fields := strings.Fields(line)
		if len(fields) >= 3 && strings.EqualFold(fields[0], "AutoRun") {
			return strings.Join(fields[2:], " "), nil
		}
	}
	return "", nil
}

func (windowsCmdAutoRun) Set(value string) error {
	if strings.ContainsAny(value, "\r\n\x00") {
		return errors.New("CMD AutoRun contains a control character")
	}
	if value == "" {
		output, err := exec.Command("reg", "delete", `HKCU\Software\Microsoft\Command Processor`, "/v", "AutoRun", "/f").CombinedOutput()
		if err != nil && !strings.Contains(strings.ToLower(string(output)), "unable to find") {
			return fmt.Errorf("remove CMD AutoRun: %w: %s", err, strings.TrimSpace(string(output)))
		}
		return nil
	}
	output, err := exec.Command("reg", "add", `HKCU\Software\Microsoft\Command Processor`, "/v", "AutoRun", "/t", "REG_SZ", "/d", value, "/f").CombinedOutput()
	if err != nil {
		return fmt.Errorf("write CMD AutoRun: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return nil
}
