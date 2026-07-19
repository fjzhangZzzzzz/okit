package main

import (
	"os"

	"github.com/fjzhangZzzzzz/okit/internal/cli"
)

var version = "dev"
var commit = "unknown"
var date = "unknown"
var buildMode = cli.BuildModeDevelopment

func main() {
	os.Exit(cli.NewBuildMode(version, commit, date, buildMode).Run(os.Args[1:], os.Stdout, os.Stderr))
}
