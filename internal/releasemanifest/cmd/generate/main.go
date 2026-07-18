package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/fjzhangZzzzzz/okit/internal/releasemanifest"
)

func main() {
	version := flag.String("version", "", "v-prefixed release version")
	output := flag.String("output", "", "output JSON path")
	flag.Parse()
	if *output == "" {
		fmt.Fprintln(os.Stderr, "--output is required")
		os.Exit(2)
	}
	manifest, err := releasemanifest.New(*version)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := releasemanifest.Marshal(manifest)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.MkdirAll(filepath.Dir(*output), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	temporary := *output + ".tmp"
	if err := os.WriteFile(temporary, data, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.Rename(temporary, *output); err != nil {
		_ = os.Remove(temporary)
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
