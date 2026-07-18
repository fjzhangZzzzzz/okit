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
	"strings"

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
	Build        Build
	GOOS         string
	GOARCH       string
	Executable   func() (string, error)
	LookPath     func(string) (string, error)
	Home         func() (string, error)
	Getenv       func(string) string
	Stat         func(string) (os.FileInfo, error)
	LoadMetadata func(string) (selfmanage.Metadata, error)
}

func NewCollector(build Build) Collector {
	return Collector{Build: build}
}

func (c Collector) Collect() (Info, error) {
	if c.GOOS == "" {
		c.GOOS = runtime.GOOS
	}
	if c.GOARCH == "" {
		c.GOARCH = runtime.GOARCH
	}
	if c.Executable == nil {
		c.Executable = os.Executable
	}
	if c.LookPath == nil {
		c.LookPath = exec.LookPath
	}
	if c.Home == nil {
		c.Home = config.Home
	}
	if c.Getenv == nil {
		c.Getenv = os.Getenv
	}
	if c.Stat == nil {
		c.Stat = os.Stat
	}
	if c.LoadMetadata == nil {
		c.LoadMetadata = selfmanage.LoadMetadata
	}

	executable, err := c.Executable()
	if err != nil {
		return Info{}, fmt.Errorf("resolve executable: %w", err)
	}
	executable, err = absolutePath(executable)
	if err != nil {
		return Info{}, fmt.Errorf("resolve executable: %w", err)
	}
	home, err := c.Home()
	if err != nil {
		return Info{}, err
	}
	home, err = absolutePath(home)
	if err != nil {
		return Info{}, fmt.Errorf("resolve data directory: %w", err)
	}

	info := Info{
		Version:        c.Build.Version,
		Commit:         c.Build.Commit,
		Built:          c.Build.Built,
		Platform:       c.GOOS + "/" + c.GOARCH,
		Executable:     executable,
		InstallDir:     filepath.Dir(executable),
		DataDir:        home,
		ConfigFile:     filepath.Join(home, "config.yaml"),
		MetadataFile:   filepath.Join(home, "install.json"),
		MetadataStatus: "missing",
		Warnings:       make([]Warning, 0),
	}

	resolved, lookErr := c.LookPath("okit")
	if c.GOOS == "windows" && (lookErr != nil || resolved == "") {
		resolved, lookErr = c.LookPath("okit.exe")
	}
	if lookErr != nil || resolved == "" {
		info.PathStatus = "missing"
		info.addWarning("PATH_MISSING", "okit is not available through the current PATH")
	} else {
		if absolute, err := absolutePath(resolved); err == nil {
			resolved = absolute
		}
		info.Resolved = resolved
		if samePath(c.GOOS, executable, resolved) {
			info.PathStatus = "ok"
		} else {
			info.PathStatus = "shadowed"
			info.addWarning("PATH_SHADOWED", fmt.Sprintf("PATH resolves okit to %s instead of %s", resolved, executable))
		}
	}

	for _, entry := range filepath.SplitList(c.Getenv("PATH")) {
		if samePath(c.GOOS, info.InstallDir, entry) {
			info.InstallDirInPath = true
			break
		}
	}
	if !info.InstallDirInPath {
		info.addWarning("INSTALL_DIR_NOT_IN_PATH", fmt.Sprintf("install directory %s is not in the current PATH", info.InstallDir))
	}

	if _, err := c.Stat(info.ConfigFile); err == nil {
		info.ConfigExists = true
	} else if !errors.Is(err, os.ErrNotExist) {
		info.addWarning("CONFIG_UNREADABLE", fmt.Sprintf("cannot inspect config file %s", info.ConfigFile))
	}

	metadata, err := c.LoadMetadata(home)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			info.MetadataStatus = "missing"
			info.addWarning("METADATA_MISSING", fmt.Sprintf("install metadata is missing at %s", info.MetadataFile))
		} else {
			info.MetadataStatus = "invalid"
			info.addWarning("METADATA_INVALID", fmt.Sprintf("install metadata cannot be read at %s", info.MetadataFile))
		}
		return info, nil
	}
	info.MetadataStatus = "ok"
	info.InstallMethod = metadata.Method
	info.InstallChannel = metadata.Channel
	info.InstallVersion = metadata.Version
	if metadata.Executable != "" && !samePath(c.GOOS, executable, metadata.Executable) {
		info.addWarning("METADATA_EXECUTABLE_MISMATCH", fmt.Sprintf("install metadata points to %s", metadata.Executable))
	}
	if metadata.Version != "" && c.Build.Version != "" && metadata.Version != c.Build.Version {
		info.addWarning("METADATA_VERSION_MISMATCH", fmt.Sprintf("install metadata version %s differs from binary version %s", metadata.Version, c.Build.Version))
	}
	return info, nil
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

func samePath(goos, left, right string) bool {
	if left == "" || right == "" {
		return false
	}
	left = filepath.Clean(left)
	right = filepath.Clean(right)
	if goos == "windows" {
		return strings.EqualFold(left, right)
	}
	return left == right
}

func valueOrDash(value string) string {
	if value == "" {
		return "-"
	}
	return value
}
