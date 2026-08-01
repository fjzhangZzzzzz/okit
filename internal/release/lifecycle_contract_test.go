package release

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestMain(m *testing.M) {
	if os.Getenv("OKIT_LIFECYCLE_HELPER") == "1" {
		os.Exit(runLifecycleHelper(os.Args[1:]))
	}
	os.Exit(m.Run())
}

func TestLifecycleSmokeRejectsUnsupportedUpgradeSourceBeforeUpgrade(t *testing.T) {
	t.Parallel()

	tempDir := t.TempDir()
	scriptDir := filepath.Join(tempDir, "scripts")
	binDir := filepath.Join(tempDir, "bin")
	homeDir := filepath.Join(tempDir, "home")
	installDir := filepath.Join(tempDir, "install")
	marker := filepath.Join(tempDir, "upgrade-called")
	for _, dir := range []string{scriptDir, binDir} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
	}

	repoRoot, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}

	var command *exec.Cmd
	if runtime.GOOS == "windows" {
		copyFile(t, filepath.Join(repoRoot, "scripts", "smoke-release-lifecycle.ps1"), filepath.Join(scriptDir, "smoke-release-lifecycle.ps1"))
		writeFile(t, filepath.Join(scriptDir, "install.ps1"), `
New-Item -ItemType Directory -Force -Path $env:OKIT_INSTALL_DIR | Out-Null
Copy-Item -LiteralPath $env:OKIT_TEST_HELPER -Destination (Join-Path $env:OKIT_INSTALL_DIR 'okit.exe')
`)
		writeFile(t, filepath.Join(binDir, "gh.cmd"), `@echo off
echo [{"draft":false,"prerelease":false,"tag_name":"v2.2.1"}]
`)
		command = exec.Command("pwsh", "-NoProfile", "-File", filepath.Join(scriptDir, "smoke-release-lifecycle.ps1"), "-Mode", "release", "-Version", "v2.2.3-rc.1", "-Repository", "owner/repo")
	} else {
		copyFile(t, filepath.Join(repoRoot, "scripts", "smoke-release-lifecycle.sh"), filepath.Join(scriptDir, "smoke-release-lifecycle.sh"))
		writeFile(t, filepath.Join(scriptDir, "install.sh"), `#!/bin/sh
set -eu
mkdir -p "$OKIT_INSTALL_DIR"
cp "$OKIT_TEST_HELPER" "$OKIT_INSTALL_DIR/okit"
chmod 0755 "$OKIT_INSTALL_DIR/okit"
`)
		writeFile(t, filepath.Join(binDir, "gh"), `#!/bin/sh
printf '%s\n' v2.2.1
`)
		if err := os.Chmod(filepath.Join(scriptDir, "install.sh"), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(filepath.Join(binDir, "gh"), 0o755); err != nil {
			t.Fatal(err)
		}
		command = exec.Command("sh", filepath.Join(scriptDir, "smoke-release-lifecycle.sh"), "--release", "--version", "v2.2.3-rc.1", "--repository", "owner/repo")
	}

	command.Env = append(os.Environ(),
		"OKIT_HOME="+homeDir,
		"OKIT_INSTALL_DIR="+installDir,
		"OKIT_TEST_HELPER="+os.Args[0],
		"OKIT_LIFECYCLE_HELPER=1",
		"OKIT_UPGRADE_MARKER="+marker,
		"PATH="+binDir+string(os.PathListSeparator)+os.Getenv("PATH"),
	)
	output, err := command.CombinedOutput()
	if err == nil {
		t.Fatalf("不支持的升级源应失败，实际成功：\n%s", output)
	}
	if !strings.Contains(string(output), "v2.2.1 不支持 upgrade 命令") {
		t.Fatalf("错误信息未说明不支持的升级源：\n%s", output)
	}
	if _, statErr := os.Stat(marker); !os.IsNotExist(statErr) {
		t.Fatalf("识别到不支持的升级源后仍调用了 upgrade")
	}
}

func runLifecycleHelper(args []string) int {
	if len(args) > 0 && args[0] == "--help" {
		fmt.Println("可用命令：")
		fmt.Println("  self        管理当前安装")
		fmt.Println("  uninstall   卸载 okit")
		return 0
	}
	if len(args) > 0 && args[0] == "upgrade" {
		if marker := os.Getenv("OKIT_UPGRADE_MARKER"); marker != "" {
			_ = os.WriteFile(marker, []byte("called"), 0o600)
		}
		fmt.Println("okit v2.2.1")
		return 0
	}
	if len(args) > 0 && args[0] == "--version" {
		fmt.Println("okit v2.2.1")
		return 0
	}
	return 0
}

func copyFile(t *testing.T, source, destination string) {
	t.Helper()
	content, err := os.ReadFile(source)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(destination, content, 0o755); err != nil {
		t.Fatal(err)
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(strings.TrimSpace(content)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}
