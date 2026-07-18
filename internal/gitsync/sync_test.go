package gitsync

import (
	"context"
	"errors"
	"path/filepath"
	"strings"
	"testing"
)

type fakeGit struct {
	status map[string]string
}

func (f fakeGit) Status(_ context.Context, root string) (string, error) {
	value, ok := f.status[root]
	if !ok {
		return "", errors.New("not a git repository")
	}
	return value, nil
}

type fakeCommands struct {
	calls []commandCall
}

type commandCall struct {
	name string
	args []string
}

func (f *fakeCommands) LookPath(name string) bool { return name == "rsync" }
func (f *fakeCommands) Run(_ context.Context, name string, args []string, _ string) error {
	f.calls = append(f.calls, commandCall{name: name, args: append([]string(nil), args...)})
	return nil
}

func TestTargetRootSemantics_GITSYNC001(t *testing.T) {
	root := filepath.Join(t.TempDir(), "service-a")
	service := NewService(fakeGit{status: map[string]string{root: "?? main.go\x00"}}, &fakeCommands{})
	results := service.Run(context.Background(), []string{root}, Options{Host: "dev", TargetRoot: "/srv/src", DryRun: true})
	if len(results) != 1 || results[0].Err != nil || results[0].Plan.RemoteRoot != "/srv/src/service-a" {
		t.Fatalf("results=%+v", results)
	}
}

func TestStatusOperations_GITSYNC002(t *testing.T) {
	status := " M modified.txt\x00?? new.txt\x00 D removed.txt\x00R  renamed.txt\x00old.txt\x00"
	operations, err := ParseStatus(status)
	if err != nil {
		t.Fatal(err)
	}
	want := []Operation{
		{Kind: Upsert, Path: "modified.txt"},
		{Kind: Upsert, Path: "new.txt"},
		{Kind: Delete, Path: "removed.txt"},
		{Kind: Delete, Path: "old.txt"},
		{Kind: Upsert, Path: "renamed.txt"},
	}
	if len(operations) != len(want) {
		t.Fatalf("operations=%+v", operations)
	}
	for i := range want {
		if operations[i] != want[i] {
			t.Fatalf("operation[%d]=%+v want %+v", i, operations[i], want[i])
		}
	}
}

func TestDryRunDoesNotExecute_GITSYNC003(t *testing.T) {
	root := filepath.Join(t.TempDir(), "repo")
	commands := &fakeCommands{}
	service := NewService(fakeGit{status: map[string]string{root: "?? file.txt\x00"}}, commands)
	results := service.Run(context.Background(), []string{root}, Options{Host: "dev", TargetRoot: "/srv", DryRun: true})
	if results[0].Err != nil || len(commands.calls) != 0 {
		t.Fatalf("results=%+v calls=%+v", results, commands.calls)
	}
}

func TestTransportSelection_GITSYNC004(t *testing.T) {
	for _, test := range []struct {
		mode      string
		rsync     bool
		want      string
		wantError bool
	}{{"auto", true, "rsync", false}, {"auto", false, "sftp", false}, {"rsync", false, "", true}, {"sftp", true, "sftp", false}} {
		got, err := SelectTransport(test.mode, test.rsync)
		if got != test.want || (err != nil) != test.wantError {
			t.Fatalf("SelectTransport(%q,%v)=%q,%v", test.mode, test.rsync, got, err)
		}
	}
}

func TestTraversalRejectedAndStrictHostChecking_GITSYNC005(t *testing.T) {
	if _, err := ParseStatus("?? ../escape\x00"); err == nil {
		t.Fatal("path traversal accepted")
	}
	if _, err := ParseStatus("?? tab\tname\x00"); err == nil {
		t.Fatal("control character accepted")
	}
	root := filepath.Join(t.TempDir(), "repo")
	commands := &fakeCommands{}
	service := NewService(fakeGit{status: map[string]string{root: "?? file.txt\x00"}}, commands)
	results := service.Run(context.Background(), []string{root}, Options{Host: "dev", User: "alice", TargetRoot: "/srv", Transport: "rsync"})
	if results[0].Err != nil {
		t.Fatal(results[0].Err)
	}
	joined := ""
	for _, call := range commands.calls {
		joined += call.name + " " + strings.Join(call.args, " ") + "\n"
	}
	if !strings.Contains(joined, "StrictHostKeyChecking=yes") {
		t.Fatalf("strict host checking absent: %s", joined)
	}
}
