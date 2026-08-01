package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/fjzhangZzzzzz/okit/internal/release"
)

func main() {
	version := flag.String("version", "", "带 v 前缀的发布版本")
	output := flag.String("output", "", "输出 JSON 路径")
	flag.Parse()
	if *output == "" {
		fmt.Fprintln(os.Stderr, "必须指定 --output")
		os.Exit(2)
	}
	manifest, err := release.NewManifest(*version)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := release.MarshalManifest(manifest)
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
