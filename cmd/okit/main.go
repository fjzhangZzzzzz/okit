package main

import (
	"os"

	"github.com/fjzhangZzzzzz/okit/internal/cli"
)

var version = "dev"
var commit = "unknown"
var date = "unknown"

func main() {
	os.Exit(cli.NewBuild(version, commit, date).Run(os.Args[1:], os.Stdout, os.Stderr))
}
