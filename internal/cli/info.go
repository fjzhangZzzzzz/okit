package cli

import (
	"github.com/fjzhangZzzzzz/okit/internal/appinfo"
	"github.com/spf13/cobra"
)

func (a *App) newInfoCommand(options *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use:         "info",
		Short:       "Display runtime and installation status",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			collector := appinfo.NewCollector(appinfo.Build{Version: a.version, Commit: a.commit, Built: a.date})
			info, err := collector.Collect()
			if err != nil {
				return runError(err)
			}
			if options.format == "json" {
				if err := appinfo.WriteJSON(cmd.OutOrStdout(), info); err != nil {
					return runError(err)
				}
				return nil
			}
			appinfo.WriteText(cmd.OutOrStdout(), cmd.ErrOrStderr(), info)
			return nil
		},
	}
}
