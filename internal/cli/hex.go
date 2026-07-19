package cli

import (
	"bytes"
	"os"

	hexdump "github.com/fjzhangZzzzzz/okit/internal/hex"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func newHexCommand(global *globalOptions) *cobra.Command {
	options := hexdump.Options{}
	command := &cobra.Command{
		Use:         "hex <file...>",
		Short:       "Display file bytes",
		Args:        cobra.MinimumNArgs(1),
		Annotations: map[string]string{"formats": "table,raw"},
		PreRunE: func(_ *cobra.Command, _ []string) error {
			if options.WordSize < 0 {
				return usageError("--word-size requires a non-negative integer")
			}
			if options.Skip < 0 {
				return usageError("--skip requires a non-negative integer")
			}
			if options.Length < 0 {
				return usageError("--length requires a non-negative integer")
			}
			return nil
		},
		RunE: func(cmd *cobra.Command, files []string) error {
			options.LengthSet = cmd.Flags().Changed("length")
			succeeded, failed := 0, 0
			presenter := newPresenter(cmd, global)
			for _, path := range files {
				file, err := os.Open(path)
				if err != nil {
					presenter.Error(clioutput.Diagnostic{Code: "HEX_FILE_OPEN_FAILED", Message: path + ": " + err.Error(), Action: "Check that the file exists and is readable."})
					failed++
					continue
				}
				var rendered bytes.Buffer
				err = hexdump.Dump(file, &rendered, options)
				closeErr := file.Close()
				if err == nil {
					err = closeErr
				}
				if err != nil {
					presenter.Error(clioutput.Diagnostic{Code: "HEX_FILE_READ_FAILED", Message: path + ": " + err.Error(), Action: "Check that the file can be read completely."})
					failed++
					continue
				}
				if len(files) > 1 {
					if err := presenter.Raw("==> " + path + " <==\n"); err != nil {
						return runError(err)
					}
				}
				if err := presenter.Raw(rendered.String()); err != nil {
					return runError(err)
				}
				succeeded++
			}
			if failed > 0 && succeeded > 0 {
				return exitCode(3)
			}
			if failed > 0 {
				return exitCode(1)
			}
			return nil
		},
	}
	command.Flags().StringVar(&options.Display, "display", "", "display mode: canonical, hex, octal, char, or decimal")
	command.Flags().IntVar(&options.WordSize, "word-size", 0, "word size: 1 or 2 bytes")
	command.Flags().Int64Var(&options.Skip, "skip", 0, "number of bytes to skip")
	command.Flags().Int64Var(&options.Length, "length", 0, "maximum number of bytes to display")
	command.Flags().BoolVar(&options.NoSqueeze, "no-squeeze", false, "do not collapse repeated lines")
	return command
}
