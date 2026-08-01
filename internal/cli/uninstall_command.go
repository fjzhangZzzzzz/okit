package cli

import (
	"github.com/fjzhangZzzzzz/okit/internal/installation"
	"github.com/spf13/cobra"
)

func (a *App) newUninstallCommand(global *globalOptions) *cobra.Command {
	options := installation.UninstallOptions{}
	command := &cobra.Command{Use: "uninstall", Short: "卸载 okit", Args: cobra.NoArgs, Annotations: map[string]string{"formats": "table,json"}, RunE: func(cmd *cobra.Command, _ []string) error {
		presenter := newPresenter(cmd, global)
		view, err := a.newUninstallWorkflow(options).Run(cmd.InOrStdin(), presenter)
		if err != nil {
			return err
		}
		return presenter.Render(view)
	}}
	command.Flags().BoolVar(&options.Purge, "purge", false, "同时删除 OKIT_HOME 与用户数据")
	command.Flags().BoolVar(&options.Yes, "yes", false, "确认执行破坏性删除")
	command.Flags().BoolVar(&options.DryRun, "dry-run", false, "显示卸载计划但不修改文件")
	return command
}
