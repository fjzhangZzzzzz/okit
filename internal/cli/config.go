package cli

import (
	"fmt"
	"sort"
	"strings"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/spf13/cobra"
)

func newConfigCommand(namespace string) *cobra.Command {
	command := commandGroup("config", "Manage persistent configuration")
	command.AddCommand(
		&cobra.Command{
			Use:   "get <key>",
			Short: "Read a configuration value",
			Args:  cobra.ExactArgs(1),
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
					return runError(fmt.Errorf("config key %q is not set", key))
				}
				fmt.Fprintln(cmd.OutOrStdout(), value)
				return nil
			},
		},
		&cobra.Command{
			Use:   "set <key> <value>",
			Short: "Write a configuration value",
			Args:  cobra.ExactArgs(2),
			RunE: func(_ *cobra.Command, args []string) error {
				store, err := config.DefaultStore()
				if err != nil {
					return runError(err)
				}
				if err := store.Set(configKey(namespace, args[0]), args[1]); err != nil {
					return runError(err)
				}
				return nil
			},
		},
		&cobra.Command{
			Use:   "list",
			Short: "List configuration values",
			Args:  cobra.NoArgs,
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
				for _, key := range keys {
					fmt.Fprintf(cmd.OutOrStdout(), "%s=%s\n", key, values[key])
				}
				return nil
			},
		},
	)
	return command
}

func configKey(namespace, key string) string {
	if strings.HasPrefix(key, namespace+".") {
		return key
	}
	return namespace + "." + key
}
