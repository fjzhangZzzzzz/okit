package cli

import (
	"fmt"
	"os"

	"github.com/fjzhangZzzzzz/okit/internal/peinspect"
	"github.com/spf13/cobra"
)

func newPECommand(options *globalOptions) *cobra.Command {
	command := commandGroup("pe", "Inspect PE files")
	inspect := &cobra.Command{
		Use:         "inspect <file...>",
		Short:       "Inspect PE file metadata",
		Args:        cobra.MinimumNArgs(1),
		Annotations: map[string]string{"formats": "table,json,csv"},
		RunE: func(cmd *cobra.Command, files []string) error {
			infos := make([]peinspect.Info, 0, len(files))
			failed := 0
			for _, path := range files {
				file, err := os.Open(path)
				if err != nil {
					fmt.Fprintf(cmd.ErrOrStderr(), "%s: %v\n", path, err)
					failed++
					continue
				}
				info, parseErr := peinspect.Parse(file, path)
				closeErr := file.Close()
				if parseErr == nil {
					parseErr = closeErr
				}
				if parseErr != nil {
					fmt.Fprintf(cmd.ErrOrStderr(), "%s: %v\n", path, parseErr)
					failed++
					continue
				}
				infos = append(infos, info)
			}
			if len(infos) > 0 {
				if err := peinspect.Write(cmd.OutOrStdout(), infos, options.format); err != nil {
					return runError(err)
				}
			}
			if failed > 0 && len(infos) > 0 {
				return exitCode(3)
			}
			if failed > 0 {
				return exitCode(1)
			}
			return nil
		},
	}
	command.AddCommand(inspect)
	return command
}
