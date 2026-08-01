package cli

import (
	"os"
	"strconv"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm/license"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func newMobaLicenseCommand(global *globalOptions) *cobra.Command {
	command := commandGroup("license", "管理 MobaXterm Pro 许可证")
	command.AddCommand(newMobaLicenseGenerateCommand(global), newMobaLicenseDeployCommand(global), newMobaLicenseInspectCommand(global), newMobaLicenseVerifyCommand(global))
	return command
}

func newMobaLicenseGenerateCommand(global *globalOptions) *cobra.Command {
	username, version, output := "", "", ""
	command := &cobra.Command{
		Use:         "generate",
		Short:       "生成 MobaXterm 许可证文件",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" || output == "" {
				return usageError("generate 需要 --username、--version 和 --output")
			}
			key, err := license.Generate(username, version)
			if err != nil {
				return runError(err)
			}
			if err := license.CreateFile(output, key); err != nil {
				return runError(err)
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "已生成 MobaXterm 许可证", Fields: []clioutput.Field{{Label: "输出文件", Value: output}, {Label: "用户名", Value: username}, {Label: "版本", Value: version}}},
				Machine: map[string]any{"status": "created", "output": output, "username": username, "version": version},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "授权用户名")
	command.Flags().StringVar(&version, "version", "", "MobaXterm 版本")
	command.Flags().StringVar(&output, "output", "", "输出许可证文件")
	return command
}

func newMobaLicenseDeployCommand(global *globalOptions) *cobra.Command {
	username, version := "", ""
	var force, dryRun bool
	command := &cobra.Command{
		Use:         "deploy",
		Short:       "部署 MobaXterm 许可证",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			selected, err := selectMobaInstallation()
			if err != nil {
				return err
			}
			if username == "" {
				return usageError("deploy 需要 --username")
			}
			presenter := newPresenter(cmd, global)
			if needsMobaConfirmation(dryRun, force) {
				plan, err := selected.service.DeployLicenseTo(selected.candidate, username, version, true)
				if err != nil {
					return runError(err)
				}
				if !confirmAction(cmd.InOrStdin(), presenter, mobaLicenseDeployPrompt(plan)) {
					return presenter.Render(clioutput.View{Human: clioutput.Document{Title: "已取消部署许可证", Summary: "未作任何更改。"}, Machine: map[string]any{"status": "cancelled", "changed": false}})
				}
			}
			result, err := selected.service.DeployLicenseTo(selected.candidate, username, version, dryRun)
			if err != nil {
				return runError(err)
			}
			title := "已部署 MobaXterm 许可证"
			summary := ""
			if dryRun {
				title = "MobaXterm 许可证部署计划"
				summary = "未作任何更改。"
			}
			return presenter.Render(clioutput.View{
				Human:   clioutput.Document{Title: title, Fields: []clioutput.Field{{Label: "用户名", Value: username}, {Label: "版本", Value: version}, {Label: "结果", Value: mobaLicenseDeploymentSummary(result)}}, Summary: summary},
				Machine: map[string]any{"status": plannedOrCompleted(dryRun), "username": username, "version": version, "result": result},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "授权用户名")
	command.Flags().StringVar(&version, "version", "", "MobaXterm 版本")
	command.Flags().BoolVar(&force, "force", false, "跳过交互确认")
	command.Flags().BoolVar(&dryRun, "dry-run", false, "显示部署计划但不修改文件")
	return command
}

func newMobaLicenseInspectCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use: "inspect <文件或密钥>", Short: "检查 MobaXterm 许可证", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			key, err := readLicenseArgument(args[0])
			if err != nil {
				return runError(err)
			}
			info, err := license.InspectKey(key)
			if err != nil {
				return runError(err)
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human: clioutput.Document{Title: "MobaXterm 许可证", Fields: []clioutput.Field{
					{Label: "用户名", Value: info.Username}, {Label: "版本", Value: info.Version},
					{Label: "许可证类型", Value: info.LicenseType}, {Label: "用户数量", Value: strconv.Itoa(info.UserCount)},
				}},
				Machine: info,
			})
		},
	}
}

func newMobaLicenseVerifyCommand(global *globalOptions) *cobra.Command {
	username, version := "", ""
	command := &cobra.Command{
		Use: "verify <文件或密钥>", Short: "验证 MobaXterm 许可证", Args: cobra.ExactArgs(1), Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, args []string) error {
			if _, _, err := mobaContext(); err != nil {
				return err
			}
			if username == "" || version == "" {
				return usageError("verify 需要 --username 和 --version")
			}
			key, err := readLicenseArgument(args[0])
			if err != nil {
				return runError(err)
			}
			valid, err := license.Verify(key, username, version)
			if err != nil {
				return runError(err)
			}
			if !valid {
				return domainError("MOBA_LICENSE_INVALID", "许可证验证失败。", "请检查预期的用户名、版本和许可证输入。")
			}
			return newPresenter(cmd, global).Render(clioutput.View{
				Human:   clioutput.Document{Title: "MobaXterm 许可证有效。", Fields: []clioutput.Field{{Label: "用户名", Value: username}, {Label: "版本", Value: version}}},
				Machine: map[string]any{"valid": true, "username": username, "version": version},
			})
		},
	}
	command.Flags().StringVar(&username, "username", "", "预期的授权用户名")
	command.Flags().StringVar(&version, "version", "", "预期的 MobaXterm 版本")
	return command
}

func themeStatus(dryRun, changed bool) string {
	if dryRun {
		return "planned"
	}
	if changed {
		return "updated"
	}
	return "unchanged"
}

func plannedOrCompleted(dryRun bool) string {
	if dryRun {
		return "planned"
	}
	return "completed"
}

func readLicenseArgument(value string) (string, error) {
	if info, err := os.Stat(value); err == nil && !info.IsDir() {
		return license.ReadFile(value)
	}
	return value, nil
}

func mobaThemeApplyPrompt() string { return "要应用选定的 MobaXterm 主题吗？" }

func mobaThemeRestorePrompt() string { return "要还原 MobaXterm 配置备份吗？" }

func mobaLicenseDeployPrompt(plan string) string {
	return "要部署 MobaXterm 许可证文件吗？ " + mobaLicenseDeploymentSummary(plan)
}

func mobaLicenseDeploymentSummary(result string) string {
	if path, ok := strings.CutPrefix(result, "would deploy license to "); ok {
		return "将把许可证部署到 " + path
	}
	if path, ok := strings.CutPrefix(result, "deployed license to "); ok {
		return "已将许可证部署到 " + path
	}
	return "许可证部署已完成。"
}
