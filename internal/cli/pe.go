package cli

import (
	"bytes"
	"os"

	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
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
			presenter := newPresenter(cmd, options)
			for _, path := range files {
				file, err := os.Open(path)
				if err != nil {
					presenter.Error(clioutput.Diagnostic{Code: "PE_FILE_OPEN_FAILED", Message: path + ": " + err.Error(), Action: "Check that the file exists and is readable."})
					failed++
					continue
				}
				info, parseErr := peinspect.Parse(file, path)
				closeErr := file.Close()
				if parseErr == nil {
					parseErr = closeErr
				}
				if parseErr != nil {
					presenter.Error(clioutput.Diagnostic{Code: "PE_PARSE_FAILED", Message: path + ": " + parseErr.Error(), Action: "Confirm that the input is a valid PE file."})
					failed++
					continue
				}
				infos = append(infos, info)
			}
			if len(infos) > 0 {
				if options.format == clioutput.FormatJSON {
					if err := presenter.Render(clioutput.View{Machine: infos}); err != nil {
						return runError(err)
					}
				} else {
					var rendered bytes.Buffer
					if err := peinspect.Write(&rendered, infos, options.format); err != nil {
						return runError(err)
					}
					if err := presenter.Raw(rendered.String()); err != nil {
						return runError(err)
					}
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
