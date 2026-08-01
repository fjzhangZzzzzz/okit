package cli

import (
	"bufio"
	"strings"

	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
)

func confirmAction(stdin interface{ Read([]byte) (int, error) }, presenter *clioutput.Presenter, prompt string) bool {
	if err := presenter.Prompt(prompt + " [y/N] "); err != nil {
		return false
	}
	answer, _ := bufio.NewReader(stdin).ReadString('\n')
	answer = strings.TrimSpace(strings.ToLower(answer))
	return answer == "y" || answer == "yes"
}
