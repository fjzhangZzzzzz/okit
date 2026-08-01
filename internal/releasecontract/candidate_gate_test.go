package releasecontract

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestFormalReleaseAcceptsValidatedCandidateFromSameCommit(t *testing.T) {
	result := runCandidateVerification(t, "abc123", true, true, `{"version":"v2.2.3-rc.1","commit":"abc123","linux":true,"windows":true}`)
	if result.err != nil {
		t.Fatalf("已验证且提交一致的 RC 应允许正式发布：%v\n%s", result.err, result.output)
	}
	if !strings.Contains(result.output, "v2.2.3-rc.1 已通过发布验证") {
		t.Fatalf("成功输出缺少已验证的 RC：\n%s", result.output)
	}
}

func TestFormalReleaseRejectsUnvalidatedCandidate(t *testing.T) {
	result := runCandidateVerification(t, "abc123", true, false, "")
	if result.err == nil {
		t.Fatalf("没有验证标记的 RC 不应允许正式发布：\n%s", result.output)
	}
	if !strings.Contains(result.output, "尚未完成 Linux/Windows 发布冒烟验证") {
		t.Fatalf("失败信息没有说明缺少验证标记：\n%s", result.output)
	}
}

func TestFormalReleaseRejectsCandidateFromDifferentCommit(t *testing.T) {
	result := runCandidateVerification(t, "def456", true, true, `{"version":"v2.2.3-rc.1","commit":"def456","linux":true,"windows":true}`)
	if result.err == nil {
		t.Fatalf("提交不一致的 RC 不应允许正式发布：\n%s", result.output)
	}
	if !strings.Contains(result.output, "与正式发布不在同一提交") {
		t.Fatalf("失败信息没有说明提交不一致：\n%s", result.output)
	}
}

func TestFormalReleaseRejectsIncompleteValidationMarker(t *testing.T) {
	result := runCandidateVerification(t, "abc123", true, true, `{"version":"v2.2.3-rc.1","commit":"abc123","linux":true,"windows":false}`)
	if result.err == nil {
		t.Fatalf("平台结果不完整的 RC 不应允许正式发布：\n%s", result.output)
	}
	if !strings.Contains(result.output, "验证标记与版本、提交或平台结果不一致") {
		t.Fatalf("失败信息没有说明验证标记无效：\n%s", result.output)
	}
}

type verificationResult struct {
	output string
	err    error
}

func runCandidateVerification(t *testing.T, candidateCommit string, published, markerAvailable bool, marker string) verificationResult {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("正式发布门禁在 Ubuntu runner 上执行")
	}

	tempDir := t.TempDir()
	binDir := filepath.Join(tempDir, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatal(err)
	}
	writeExecutable(t, filepath.Join(binDir, "git"), `#!/bin/sh
if [ "$1" = tag ]; then
  printf '%s\n' v2.2.3-rc.1
else
  printf '%s\n' "$OKIT_TEST_CANDIDATE_COMMIT"
fi
`)
	writeExecutable(t, filepath.Join(binDir, "gh"), `#!/bin/sh
if [ "$2" = view ]; then
  printf '%s\n' "$OKIT_TEST_PUBLISHED"
  exit 0
fi
if [ "$OKIT_TEST_MARKER_AVAILABLE" != true ]; then
  exit 1
fi
while [ "$#" -gt 0 ]; do
  if [ "$1" = --dir ]; then
    printf '%s\n' "$OKIT_TEST_MARKER" > "$2/release-validation.json"
    exit 0
  fi
  shift
done
exit 1
`)

	repoRoot, err := filepath.Abs(filepath.Join("..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	command := exec.Command("sh", "scripts/verify-release-candidate.sh",
		"--version", "v2.2.3",
		"--repository", "owner/repo",
		"--commit", "abc123",
	)
	command.Dir = repoRoot
	command.Env = withPath(os.Environ(), binDir+string(os.PathListSeparator)+os.Getenv("PATH"))
	command.Env = append(command.Env,
		"OKIT_TEST_CANDIDATE_COMMIT="+candidateCommit,
		"OKIT_TEST_PUBLISHED="+map[bool]string{true: "true", false: "false"}[published],
		"OKIT_TEST_MARKER_AVAILABLE="+map[bool]string{true: "true", false: "false"}[markerAvailable],
		"OKIT_TEST_MARKER="+marker,
	)
	output, commandErr := command.CombinedOutput()
	return verificationResult{output: string(output), err: commandErr}
}

func withPath(environment []string, pathValue string) []string {
	result := make([]string, 0, len(environment)+1)
	for _, entry := range environment {
		if strings.EqualFold(strings.SplitN(entry, "=", 2)[0], "PATH") {
			continue
		}
		result = append(result, entry)
	}
	return append(result, "PATH="+pathValue)
}

func writeExecutable(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o755); err != nil {
		t.Fatal(err)
	}
}
