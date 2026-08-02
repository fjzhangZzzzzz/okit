package cli

import "github.com/spf13/cobra"

func (a *App) newUpgradeCommand(global *globalOptions) *cobra.Command {
	options := upgradeOptions{}
	command := &cobra.Command{Use: "upgrade", Short: "检查或安装 okit 更新", Args: cobra.NoArgs, Annotations: map[string]string{"formats": "table,json"}, RunE: func(cmd *cobra.Command, _ []string) error {
		workflow := a.newUpgradeWorkflow(options, global.format, isTerminal(cmd.ErrOrStderr()), cmd.ErrOrStderr())
		result, err := workflow.Run(cmd.Context())
		if err != nil {
			return err
		}
		return newPresenter(cmd, global).Render(result.View())
	}}
	command.Flags().BoolVar(&options.check, "check", false, "仅检查是否有可用更新")
	command.Flags().StringVar(&options.version, "version", "", "安装指定版本")
	command.Flags().BoolVar(&options.dryRun, "dry-run", false, "显示更新计划但不修改文件")
	return command
}
