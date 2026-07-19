package cli

import (
	"github.com/fjzhangZzzzzz/okit/internal/appinfo"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
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
			presenter := newPresenter(cmd, options)
			view := clioutput.View{Human: clioutput.Document{
				Title: "okit information",
				Fields: []clioutput.Field{
					{Label: "version", Value: info.Version},
					{Label: "commit", Value: info.Commit},
					{Label: "built", Value: info.Built},
					{Label: "platform", Value: info.Platform},
					{Label: "executable", Value: info.Executable},
					{Label: "install-dir", Value: info.InstallDir},
					{Label: "resolved", Value: info.Resolved},
					{Label: "path-status", Value: info.PathStatus},
					{Label: "install-dir-in-path", Value: boolText(info.InstallDirInPath)},
					{Label: "data-dir", Value: info.DataDir},
					{Label: "config-file", Value: info.ConfigFile},
					{Label: "config-exists", Value: boolText(info.ConfigExists)},
					{Label: "metadata-file", Value: info.MetadataFile},
					{Label: "metadata-status", Value: info.MetadataStatus},
					{Label: "install-method", Value: info.InstallMethod},
					{Label: "install-channel", Value: info.InstallChannel},
					{Label: "install-version", Value: info.InstallVersion},
				},
			}, Machine: info}
			if err := presenter.Render(view); err != nil {
				return runError(err)
			}
			if options.format == clioutput.FormatTable {
				for _, warning := range info.Warnings {
					presenter.Warning(clioutput.Diagnostic{Code: warning.Code, Message: warning.Message})
				}
			}
			return nil
		},
	}
}

func boolText(value bool) string {
	if value {
		return "yes"
	}
	return "no"
}
