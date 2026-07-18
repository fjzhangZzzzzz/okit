//go:build windows

package mobaxterm

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

func DefaultSources() []Source {
	userProfile := os.Getenv("USERPROFILE")
	programFiles := os.Getenv("ProgramFiles")
	programFilesX86 := os.Getenv("ProgramFiles(x86)")
	return []Source{
		registrySource{},
		pathListSource{name: "package-manager", paths: []string{
			filepath.Join(userProfile, "scoop", "apps", "mobaxterm", "current", "MobaXterm.exe"),
			filepath.Join(os.Getenv("LOCALAPPDATA"), "Microsoft", "WinGet", "Packages", "MobaXterm", "MobaXterm.exe"),
		}},
		pathListSource{name: "common-path", paths: []string{
			filepath.Join(programFiles, "Mobatek", "MobaXterm", "MobaXterm.exe"),
			filepath.Join(programFilesX86, "Mobatek", "MobaXterm", "MobaXterm.exe"),
			filepath.Join(userProfile, "Documents", "MobaXterm", "MobaXterm.exe"),
		}},
		pathEnvironmentSource{},
	}
}

type pathListSource struct {
	name  string
	paths []string
}

func (s pathListSource) Name() string { return s.name }
func (s pathListSource) Detect() ([]Candidate, error) {
	result := make([]Candidate, 0)
	for _, path := range s.paths {
		if path == "" {
			continue
		}
		if info, err := os.Stat(path); err == nil && !info.IsDir() {
			result = append(result, candidateFromExecutable(path, ""))
		}
	}
	return result, nil
}

type pathEnvironmentSource struct{}

func (pathEnvironmentSource) Name() string { return "PATH" }
func (pathEnvironmentSource) Detect() ([]Candidate, error) {
	path, err := exec.LookPath("MobaXterm.exe")
	if err != nil {
		return nil, nil
	}
	return []Candidate{candidateFromExecutable(path, "")}, nil
}

type registrySource struct{}

func (registrySource) Name() string { return "registry" }
func (registrySource) Detect() ([]Candidate, error) {
	contexts := []string{
		`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
		`HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
		`HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
	}
	var result []Candidate
	for _, root := range contexts {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		output, err := exec.CommandContext(ctx, "reg", "query", root, "/s", "/f", "MobaXterm").CombinedOutput()
		cancel()
		if err != nil {
			continue
		}
		var installPath, version string
		for _, line := range strings.Split(string(output), "\n") {
			fields := strings.Fields(strings.TrimSpace(line))
			if len(fields) < 3 {
				continue
			}
			value := strings.Join(fields[2:], " ")
			switch fields[0] {
			case "InstallLocation":
				installPath = value
			case "DisplayVersion":
				version = value
			}
			if installPath != "" && version != "" {
				exe := filepath.Join(installPath, "MobaXterm.exe")
				result = append(result, candidateFromExecutable(exe, version))
				installPath, version = "", ""
			}
		}
	}
	return result, nil
}

func candidateFromExecutable(executable, version string) Candidate {
	if version == "" {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		output, err := exec.CommandContext(ctx, "powershell", "-NoProfile", "-Command", "(Get-Item -LiteralPath '"+strings.ReplaceAll(executable, "'", "''")+"').VersionInfo.ProductVersion").Output()
		cancel()
		if err == nil {
			version = strings.TrimSpace(string(output))
		}
	}
	return Candidate{InstallPath: filepath.Dir(executable), ExePath: executable, Version: version}
}
