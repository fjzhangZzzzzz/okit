package appinfo

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"

	"github.com/fjzhangZzzzzz/okit/internal/config"
	"github.com/fjzhangZzzzzz/okit/internal/selfmanage"
)

type Build struct {
	Version string
	Commit  string
	Built   string
}

type Warning struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Info struct {
	Version          string    `json:"version"`
	Commit           string    `json:"commit"`
	Built            string    `json:"built"`
	Platform         string    `json:"platform"`
	Executable       string    `json:"executable"`
	InstallDir       string    `json:"install_dir"`
	Resolved         string    `json:"resolved"`
	PathStatus       string    `json:"path_status"`
	InstallDirInPath bool      `json:"install_dir_in_path"`
	DataDir          string    `json:"data_dir"`
	ConfigFile       string    `json:"config_file"`
	ConfigExists     bool      `json:"config_exists"`
	MetadataFile     string    `json:"metadata_file"`
	MetadataStatus   string    `json:"metadata_status"`
	InstallMethod    string    `json:"install_method"`
	InstallChannel   string    `json:"install_channel"`
	InstallVersion   string    `json:"install_version"`
	Warnings         []Warning `json:"warnings"`
}

type Collector struct {
	Build  Build
	system collectorSystem
}

type collectorSystem struct {
	Executable   func() (string, error)
	LookPath     func(string) (string, error)
	Home         func() (string, error)
	Getenv       func(string) string
	Stat         func(string) (os.FileInfo, error)
	LoadMetadata func(string) (selfmanage.Metadata, error)
	Canonicalize func(string) (string, error)
	SameFile     func(string, string) bool
}

type snapshot struct {
	Build              Build
	Platform           string
	Executable         string
	InstallDir         string
	Resolved           string
	PathLookupErr      error
	PathEntries        []string
	DataDir            string
	ConfigFile         string
	ConfigExists       bool
	ConfigError        error
	MetadataFile       string
	Metadata           selfmanage.Metadata
	MetadataExecutable string
	MetadataError      error
}

func NewCollector(build Build) Collector {
	return Collector{Build: build, system: nativeSystem()}
}

func (c Collector) Collect() (Info, error) {
	system := c.system
	if system.Executable == nil {
		system = nativeSystem()
	}

	executable, err := system.Executable()
	if err != nil {
		return Info{}, fmt.Errorf("resolve executable: %w", err)
	}
	executable, err = system.Canonicalize(executable)
	if err != nil {
		return Info{}, fmt.Errorf("resolve executable: %w", err)
	}
	home, err := system.Home()
	if err != nil {
		return Info{}, err
	}
	home, err = system.Canonicalize(home)
	if err != nil {
		return Info{}, fmt.Errorf("resolve data directory: %w", err)
	}

	pathEntries := filepath.SplitList(system.Getenv("PATH"))
	for index, entry := range pathEntries {
		pathEntries[index] = canonicalComparablePath(
			system.Canonicalize,
			system.SameFile,
			filepath.Dir(executable),
			entry,
		)
	}
	state := snapshot{
		Build:        c.Build,
		Platform:     runtime.GOOS + "/" + runtime.GOARCH,
		Executable:   executable,
		InstallDir:   filepath.Dir(executable),
		PathEntries:  pathEntries,
		DataDir:      home,
		ConfigFile:   filepath.Join(home, "config.yaml"),
		MetadataFile: filepath.Join(home, "install.json"),
	}

	for _, name := range executableNames() {
		state.Resolved, state.PathLookupErr = system.LookPath(name)
		if state.PathLookupErr == nil && state.Resolved != "" {
			break
		}
	}
	if state.Resolved != "" {
		state.Resolved = canonicalComparablePath(system.Canonicalize, system.SameFile, executable, state.Resolved)
	}
	if _, err := system.Stat(state.ConfigFile); err == nil {
		state.ConfigExists = true
	} else {
		state.ConfigError = err
	}
	state.Metadata, state.MetadataError = system.LoadMetadata(home)
	if state.MetadataError == nil {
		state.MetadataExecutable = canonicalComparablePath(
			system.Canonicalize,
			system.SameFile,
			executable,
			state.Metadata.Executable,
		)
	}
	return diagnose(state, sameNativePath), nil
}

func diagnose(state snapshot, equalPath func(string, string) bool) Info {
	info := Info{
		Version:        state.Build.Version,
		Commit:         state.Build.Commit,
		Built:          state.Build.Built,
		Platform:       state.Platform,
		Executable:     state.Executable,
		InstallDir:     state.InstallDir,
		Resolved:       state.Resolved,
		DataDir:        state.DataDir,
		ConfigFile:     state.ConfigFile,
		ConfigExists:   state.ConfigExists,
		MetadataFile:   state.MetadataFile,
		MetadataStatus: "missing",
		Warnings:       make([]Warning, 0),
	}

	if state.PathLookupErr != nil || state.Resolved == "" {
		info.PathStatus = "missing"
		info.addWarning("PATH_MISSING", "okit is not available through the current PATH")
	} else {
		if equalPath(state.Executable, state.Resolved) {
			info.PathStatus = "ok"
		} else {
			info.PathStatus = "shadowed"
			info.addWarning("PATH_SHADOWED", fmt.Sprintf("PATH resolves okit to %s instead of %s", state.Resolved, state.Executable))
		}
	}

	for _, entry := range state.PathEntries {
		if equalPath(info.InstallDir, entry) {
			info.InstallDirInPath = true
			break
		}
	}
	if !info.InstallDirInPath {
		info.addWarning("INSTALL_DIR_NOT_IN_PATH", fmt.Sprintf("install directory %s is not in the current PATH", info.InstallDir))
	}

	if state.ConfigError != nil && !errors.Is(state.ConfigError, os.ErrNotExist) {
		info.addWarning("CONFIG_UNREADABLE", fmt.Sprintf("cannot inspect config file %s", info.ConfigFile))
	}

	if state.MetadataError != nil {
		if errors.Is(state.MetadataError, os.ErrNotExist) {
			info.MetadataStatus = "missing"
			info.addWarning("METADATA_MISSING", fmt.Sprintf("install metadata is missing at %s", info.MetadataFile))
		} else {
			info.MetadataStatus = "invalid"
			info.addWarning("METADATA_INVALID", fmt.Sprintf("install metadata cannot be read at %s", info.MetadataFile))
		}
		return info
	}
	info.MetadataStatus = "ok"
	info.InstallMethod = state.Metadata.Method
	info.InstallChannel = state.Metadata.Channel
	info.InstallVersion = state.Metadata.Version
	if state.Metadata.Executable != "" && !equalPath(state.Executable, state.MetadataExecutable) {
		info.addWarning("METADATA_EXECUTABLE_MISMATCH", fmt.Sprintf("install metadata points to %s", state.Metadata.Executable))
	}
	if state.Metadata.Version != "" && state.Build.Version != "" && state.Metadata.Version != state.Build.Version {
		info.addWarning("METADATA_VERSION_MISMATCH", fmt.Sprintf("install metadata version %s differs from binary version %s", state.Metadata.Version, state.Build.Version))
	}
	return info
}

func nativeSystem() collectorSystem {
	return collectorSystem{
		Executable:   os.Executable,
		LookPath:     exec.LookPath,
		Home:         config.Home,
		Getenv:       os.Getenv,
		Stat:         os.Stat,
		LoadMetadata: selfmanage.LoadMetadata,
		Canonicalize: absolutePath,
		SameFile:     sameExistingFile,
	}
}

func WriteText(stdout, stderr io.Writer, info Info) {
	fields := [][2]string{
		{"version", info.Version},
		{"commit", info.Commit},
		{"built", info.Built},
		{"platform", info.Platform},
		{"executable", info.Executable},
		{"install-dir", info.InstallDir},
		{"resolved", valueOrDash(info.Resolved)},
		{"path-status", info.PathStatus},
		{"install-dir-in-path", fmt.Sprintf("%t", info.InstallDirInPath)},
		{"data-dir", info.DataDir},
		{"config-file", info.ConfigFile},
		{"config-exists", fmt.Sprintf("%t", info.ConfigExists)},
		{"metadata-file", info.MetadataFile},
		{"metadata-status", info.MetadataStatus},
		{"install-method", valueOrDash(info.InstallMethod)},
		{"install-channel", valueOrDash(info.InstallChannel)},
		{"install-version", valueOrDash(info.InstallVersion)},
	}
	for _, field := range fields {
		fmt.Fprintf(stdout, "%-20s %s\n", field[0], valueOrDash(field[1]))
	}
	for _, warning := range info.Warnings {
		fmt.Fprintf(stderr, "warning %s: %s\n", warning.Code, warning.Message)
	}
}

func WriteJSON(w io.Writer, info Info) error {
	encoder := json.NewEncoder(w)
	encoder.SetIndent("", "  ")
	return encoder.Encode(info)
}

func (i *Info) addWarning(code, message string) {
	i.Warnings = append(i.Warnings, Warning{Code: code, Message: message})
}

func absolutePath(path string) (string, error) {
	absolute, err := filepath.Abs(filepath.Clean(path))
	if err != nil {
		return "", err
	}
	if evaluated, err := filepath.EvalSymlinks(absolute); err == nil {
		return evaluated, nil
	}
	return absolute, nil
}

func canonicalPathBestEffort(canonicalize func(string) (string, error), path string) string {
	if path == "" {
		return ""
	}
	canonical, err := canonicalize(path)
	if err != nil {
		return path
	}
	return canonical
}

func canonicalComparablePath(canonicalize func(string) (string, error), sameFile func(string, string) bool, reference, path string) string {
	canonical := canonicalPathBestEffort(canonicalize, path)
	if reference != "" && canonical != "" && sameFile(reference, canonical) {
		return reference
	}
	return canonical
}

func sameExistingFile(left, right string) bool {
	leftInfo, err := os.Stat(left)
	if err != nil {
		return false
	}
	rightInfo, err := os.Stat(right)
	if err != nil {
		return false
	}
	return os.SameFile(leftInfo, rightInfo)
}

func valueOrDash(value string) string {
	if value == "" {
		return "-"
	}
	return value
}
