package cli

import (
	"sort"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	clioutput "github.com/fjzhangZzzzzz/okit/internal/output"
	"github.com/spf13/cobra"
)

func newConfigCommand(namespace string, global *globalOptions) *cobra.Command {
	command := commandGroup("config", "Manage persistent configuration")
	command.AddCommand(
		&cobra.Command{
			Use:         "get <key>",
			Short:       "Read a configuration value",
			Args:        cobra.ExactArgs(1),
			Annotations: map[string]string{"formats": "table,json,raw"},
			RunE: func(cmd *cobra.Command, args []string) error {
				store, err := config.DefaultStore()
				if err != nil {
					return runError(err)
				}
				key := configKey(namespace, args[0])
				value, ok, err := store.Get(key)
				if err != nil {
					return runError(err)
				}
				if !ok {
					return domainError("CONFIG_KEY_NOT_SET", "configuration key "+quoteValue(key)+" is not set", "Set it with `okit "+namespace+" config set "+args[0]+" <value>`.")
				}
				presenter := newPresenter(cmd, global)
				if global.format == clioutput.FormatTable || global.format == clioutput.FormatRaw {
					return presenter.Raw(value + "\n")
				}
				return presenter.Render(clioutput.View{Machine: map[string]string{"key": key, "value": value}})
			},
		},
		&cobra.Command{
			Use:         "set <key> <value>",
			Short:       "Write a configuration value",
			Args:        cobra.ExactArgs(2),
			Annotations: map[string]string{"formats": "table,json"},
			RunE: func(cmd *cobra.Command, args []string) error {
				store, err := config.DefaultStore()
				if err != nil {
					return runError(err)
				}
				key := configKey(namespace, args[0])
				if err := store.Set(key, args[1]); err != nil {
					return runError(err)
				}
				return newPresenter(cmd, global).Render(clioutput.View{
					Human:   clioutput.Document{Title: "Configuration updated", Fields: []clioutput.Field{{Label: "Key", Value: key}}},
					Machine: map[string]any{"status": "updated", "key": key},
				})
			},
		},
		&cobra.Command{
			Use:         "list",
			Short:       "List configuration values",
			Args:        cobra.NoArgs,
			Annotations: map[string]string{"formats": "table,json"},
			RunE: func(cmd *cobra.Command, _ []string) error {
				store, err := config.DefaultStore()
				if err != nil {
					return runError(err)
				}
				values, err := store.List()
				if err != nil {
					return runError(err)
				}
				keys := make([]string, 0, len(values))
				for key := range values {
					if strings.HasPrefix(key, namespace+".") {
						keys = append(keys, key)
					}
				}
				sort.Strings(keys)
				document := clioutput.Document{Title: namespace + " configuration"}
				if len(keys) == 0 {
					document.Title = ""
					document.Empty = &clioutput.EmptyState{
						Message: "No " + namespace + " configuration found.",
						Hint:    "Configure a value with `okit " + namespace + " config set <key> <value>`.",
					}
				} else {
					table := &clioutput.Table{Headers: []string{"KEY", "VALUE"}}
					for _, key := range keys {
						table.Rows = append(table.Rows, []string{key, values[key]})
					}
					document.Table = table
				}
				machine := make(map[string]string, len(keys))
				for _, key := range keys {
					machine[key] = values[key]
				}
				return newPresenter(cmd, global).Render(clioutput.View{Human: document, Machine: machine})
			},
		},
	)
	return command
}

func quoteValue(value string) string { return `"` + value + `"` }

func configKey(namespace, key string) string {
	if strings.HasPrefix(key, namespace+".") {
		return key
	}
	return namespace + "." + key
}
