package cli

import (
	"github.com/fjzhangZzzzzz/okit/internal/mobaxterm"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func newMobaStatusCommand(global *globalOptions) *cobra.Command {
	return &cobra.Command{
		Use:         "status",
		Short:       "显示已检测到的 MobaXterm 安装",
		Args:        cobra.NoArgs,
		Annotations: map[string]string{"formats": "table,json"},
		RunE: func(cmd *cobra.Command, _ []string) error {
			service, _, err := mobaContext()
			if err != nil {
				return err
			}
			candidates, err := service.Status()
			if err != nil {
				return runError(err)
			}
			document := mobaStatusDocument(candidates)
			return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: candidates})
		},
	}
}

func mobaStatusDocument(candidates []mobaxterm.Candidate) clioutput.Document {
	document := clioutput.Document{Title: "已检测到的 MobaXterm 安装"}
	if len(candidates) == 0 {
		document.Title = ""
		document.Empty = &clioutput.EmptyState{Message: "未找到 MobaXterm 安装。"}
		return document
	}
	table := &clioutput.Table{Headers: []string{"默认", "版本", "来源", "可执行文件", "配置文件"}}
	for _, candidate := range candidates {
		table.Rows = append(table.Rows, []string{boolText(candidate.Default), candidate.Version, candidate.Source, candidate.ExePath, candidate.ConfigPath})
	}
	document.Table = table
	return document
}

func boolText(value bool) string {
	if value {
		return "是"
	}
	return "否"
}
