package gitsync

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type OperationKind string

const (
	Upsert OperationKind = "upsert"
	Delete OperationKind = "delete"
)

type Operation struct {
	Kind OperationKind `json:"kind"`
	Path string        `json:"path"`
}

type Plan struct {
	Repository string      `json:"repository"`
	Root       string      `json:"root"`
	RemoteRoot string      `json:"remote_root"`
	Operations []Operation `json:"operations"`
}

type Options struct {
	Host       string
	User       string
	Port       int
	TargetRoot string
	Transport  string
	DryRun     bool
}

type Result struct {
	Plan      Plan
	Transport string
	Err       error
}

type GitStatus interface {
	Status(ctx context.Context, root string) (string, error)
}

type Commands interface {
	LookPath(name string) bool
	Run(ctx context.Context, name string, args []string, stdin string) error
}

type Service struct {
	git      GitStatus
	commands Commands
}

func NewService(git GitStatus, commands Commands) *Service {
	if git == nil {
		git = execGit{}
	}
	if commands == nil {
		commands = execCommands{}
	}
	return &Service{git: git, commands: commands}
}

func (s *Service) Run(ctx context.Context, roots []string, options Options) []Result {
	results := make([]Result, 0, len(roots))
	for _, root := range roots {
		plan, err := s.plan(ctx, root, options.TargetRoot)
		result := Result{Plan: plan, Err: err}
		if err == nil && len(plan.Operations) > 0 && !options.DryRun {
			result.Transport, result.Err = s.execute(ctx, plan, options)
		}
		results = append(results, result)
	}
	return results
}

func (s *Service) plan(ctx context.Context, root, targetRoot string) (Plan, error) {
	if strings.TrimSpace(targetRoot) == "" {
		return Plan{}, errors.New("target root is required")
	}
	absRoot, err := filepath.Abs(root)
	if err != nil {
		return Plan{}, err
	}
	status, err := s.git.Status(ctx, absRoot)
	if err != nil {
		return Plan{Root: absRoot}, fmt.Errorf("git status %s: %w", absRoot, err)
	}
	operations, err := ParseStatus(status)
	if err != nil {
		return Plan{Root: absRoot}, err
	}
	repository := filepath.Base(filepath.Clean(absRoot))
	remoteRoot := path.Join(strings.ReplaceAll(targetRoot, `\`, "/"), repository)
	return Plan{Repository: repository, Root: absRoot, RemoteRoot: remoteRoot, Operations: operations}, nil
}

func ParseStatus(status string) ([]Operation, error) {
	records := strings.Split(status, "\x00")
	operations := make([]Operation, 0, len(records))
	for i := 0; i < len(records); i++ {
		record := records[i]
		if record == "" {
			continue
		}
		if len(record) < 4 || record[2] != ' ' {
			return nil, fmt.Errorf("invalid git status record %q", record)
		}
		x, y := record[0], record[1]
		current, err := cleanRelative(record[3:])
		if err != nil {
			return nil, err
		}
		if x == 'R' || y == 'R' || x == 'C' || y == 'C' {
			i++
			if i >= len(records) || records[i] == "" {
				return nil, errors.New("rename record is missing original path")
			}
			old, err := cleanRelative(records[i])
			if err != nil {
				return nil, err
			}
			if x == 'R' || y == 'R' {
				operations = append(operations, Operation{Kind: Delete, Path: old})
			}
			operations = append(operations, Operation{Kind: Upsert, Path: current})
			continue
		}
		kind := Upsert
		if x == 'D' || y == 'D' {
			kind = Delete
		}
		operations = append(operations, Operation{Kind: kind, Path: current})
	}
	return operations, nil
}

func cleanRelative(value string) (string, error) {
	value = strings.ReplaceAll(value, `\`, "/")
	if strings.IndexFunc(value, func(r rune) bool { return r < 0x20 || r == 0x7f }) >= 0 {
		return "", errors.New("path contains a control character")
	}
	cleaned := path.Clean(value)
	if cleaned == "." || strings.HasPrefix(cleaned, "../") || cleaned == ".." || path.IsAbs(cleaned) {
		return "", fmt.Errorf("path escapes repository root: %q", value)
	}
	return cleaned, nil
}

func SelectTransport(mode string, rsyncAvailable bool) (string, error) {
	if mode == "" {
		mode = "auto"
	}
	switch mode {
	case "auto":
		if rsyncAvailable {
			return "rsync", nil
		}
		return "sftp", nil
	case "rsync":
		if !rsyncAvailable {
			return "", errors.New("rsync transport requested but rsync is unavailable")
		}
		return "rsync", nil
	case "sftp":
		return "sftp", nil
	default:
		return "", fmt.Errorf("unsupported transport %q", mode)
	}
}

func (s *Service) execute(ctx context.Context, plan Plan, options Options) (string, error) {
	if strings.TrimSpace(options.Host) == "" {
		return "", errors.New("host is required")
	}
	if options.Port == 0 {
		options.Port = 22
	}
	transport, err := SelectTransport(options.Transport, s.commands.LookPath("rsync"))
	if err != nil {
		return "", err
	}
	if transport == "sftp" && !s.commands.LookPath("sftp") {
		return "", errors.New("sftp transport is unavailable")
	}
	if transport == "rsync" {
		return transport, s.executeRsync(ctx, plan, options)
	}
	return transport, s.executeSFTP(ctx, plan, options)
}

func destination(options Options, remoteRoot string) string {
	host := options.Host
	if options.User != "" {
		host = options.User + "@" + host
	}
	return host + ":" + remoteRoot
}

func (s *Service) executeRsync(ctx context.Context, plan Plan, options Options) error {
	list, err := os.CreateTemp("", "okit-rsync-*.files")
	if err != nil {
		return err
	}
	listName := list.Name()
	defer os.Remove(listName)
	for _, operation := range plan.Operations {
		if _, err := fmt.Fprintln(list, operation.Path); err != nil {
			list.Close()
			return err
		}
	}
	if err := list.Close(); err != nil {
		return err
	}
	sshCommand := "ssh -p " + strconv.Itoa(options.Port) + " -o StrictHostKeyChecking=yes"
	args := []string{"-azR", "--delete-missing-args", "--files-from=" + listName, "-e", sshCommand, filepath.Clean(plan.Root) + string(os.PathSeparator), destination(options, plan.RemoteRoot) + "/"}
	return s.commands.Run(ctx, "rsync", args, "")
}

func (s *Service) executeSFTP(ctx context.Context, plan Plan, options Options) error {
	dirs := map[string]bool{plan.RemoteRoot: true}
	for _, operation := range plan.Operations {
		if parent := path.Dir(path.Join(plan.RemoteRoot, operation.Path)); parent != "." {
			for current := parent; current != "." && current != "/"; current = path.Dir(current) {
				dirs[current] = true
				if current == plan.RemoteRoot {
					break
				}
			}
		}
	}
	directoryList := make([]string, 0, len(dirs))
	for directory := range dirs {
		directoryList = append(directoryList, directory)
	}
	sort.Slice(directoryList, func(i, j int) bool {
		return strings.Count(directoryList[i], "/") < strings.Count(directoryList[j], "/")
	})
	var batch strings.Builder
	for _, directory := range directoryList {
		fmt.Fprintf(&batch, "-mkdir %s\n", sftpQuote(directory))
	}
	for _, operation := range plan.Operations {
		remote := path.Join(plan.RemoteRoot, operation.Path)
		if operation.Kind == Delete {
			fmt.Fprintf(&batch, "-rm %s\n", sftpQuote(remote))
		} else {
			local := filepath.Join(plan.Root, filepath.FromSlash(operation.Path))
			fmt.Fprintf(&batch, "put %s %s\n", sftpQuote(local), sftpQuote(remote))
		}
	}
	host := options.Host
	if options.User != "" {
		host = options.User + "@" + host
	}
	args := []string{"-o", "StrictHostKeyChecking=yes", "-P", strconv.Itoa(options.Port), "-b", "-", host}
	return s.commands.Run(ctx, "sftp", args, batch.String())
}

func sftpQuote(value string) string {
	return `"` + strings.ReplaceAll(value, `"`, `\"`) + `"`
}

type execGit struct{}

func (execGit) Status(ctx context.Context, root string) (string, error) {
	command := exec.CommandContext(ctx, "git", "-C", root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
	output, err := command.Output()
	return string(output), err
}

type execCommands struct{}

func (execCommands) LookPath(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

func (execCommands) Run(ctx context.Context, name string, args []string, stdin string) error {
	command := exec.CommandContext(ctx, name, args...)
	command.Stdin = strings.NewReader(stdin)
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s failed: %w: %s", name, err, strings.TrimSpace(string(output)))
	}
	return nil
}
