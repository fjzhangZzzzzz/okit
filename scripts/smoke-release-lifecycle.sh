#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
用法：
  scripts/smoke-release-lifecycle.sh --release --version vMAJOR.MINOR.PATCH
  scripts/smoke-release-lifecycle.sh --binary PATH --version vMAJOR.MINOR.PATCH

环境变量：
  OKIT_HOME, OKIT_INSTALL_DIR  覆盖隔离测试目录
  OKIT_REPOSITORY              覆盖 GitHub owner/repository
EOF
}

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\n错误：%s\n' "$*" >&2; exit 1; }

mode=release
binary=
version=${OKIT_VERSION:-}
repository=${OKIT_REPOSITORY:-fjzhangZzzzzz/okit}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --release) mode=release; shift ;;
    --binary) [ "$#" -ge 2 ] || fail "--binary 需要路径"; mode=binary; binary=$2; shift 2 ;;
    --version) [ "$#" -ge 2 ] || fail "--version 需要版本号"; version=$2; shift 2 ;;
    --repository) [ "$#" -ge 2 ] || fail "--repository 需要 owner/repository"; repository=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; fail "未知选项：$1" ;;
  esac
done

printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$' || fail "版本号无效：$version"
[ "$mode" != binary ] || [ -n "$binary" ] || fail "binary 模式需要 --binary PATH"

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
smoke_root=
if [ -z "${OKIT_HOME:-}" ] || [ -z "${OKIT_INSTALL_DIR:-}" ]; then
  smoke_root=$(mktemp -d "${TMPDIR:-/tmp}/okit-smoke.XXXXXX")
fi
okit_home=${OKIT_HOME:-$smoke_root/okit-home}
install_dir=${OKIT_INSTALL_DIR:-$smoke_root/okit-bin}
executable=$install_dir/okit
cleanup() { [ -z "$smoke_root" ] || rm -rf "$smoke_root"; }
trap cleanup EXIT HUP INT TERM

export OKIT_HOME=$okit_home
export OKIT_INSTALL_DIR=$install_dir

stage_binary() {
  [ -f "$binary" ] || fail "二进制文件不存在：$binary"
  mkdir -p "$install_dir" "$okit_home"
  cp "$binary" "$executable"
  chmod 0755 "$executable"
  escaped_executable=$(printf '%s' "$executable" | sed 's/\\/\\\\/g; s/"/\\"/g')
  cat >"$okit_home/install.json" <<EOF
{
  "method": "official",
  "version": "$version",
  "channel": "$(case "$version" in *-*) printf prerelease ;; *) printf stable ;; esac)",
  "executable": "$escaped_executable",
  "path_entries": [],
  "managed_files": []
}
EOF
}

assert_version() {
  log "验证已安装版本"
  set +e
  actual=$($executable --version 2>&1)
  status=$?
  set -e
  printf '二进制：%s\n期望：okit %s\n实际输出：\n%s\n' "$executable" "$version" "$actual"
  [ "$status" -eq 0 ] || fail "版本命令退出码为 $status"
  printf '%s\n' "$actual" | grep -Fx "okit $version" >/dev/null || fail "已安装版本与 tag $version 不一致"
}

log "准备 $version 的 $mode 冒烟测试"
if [ "$mode" = binary ]; then
  stage_binary
else
  command -v gh >/dev/null 2>&1 || fail "release 模式需要 gh"
  previous=$(gh api "repos/$repository/releases" --jq '.[] | select(.draft == false and .prerelease == false) | .tag_name' | grep -vx "$version" | head -n 1 || true)
  if [ -n "$previous" ]; then
    log "安装上一正式版本 $previous"
    sh "$script_dir/install.sh" --version "$previous"
    previous_help=$("$executable" --help 2>&1)
    printf '%s\n' "$previous_help" | grep -Eq '^[[:space:]]+upgrade[[:space:]]' ||
      fail "$previous 不支持 upgrade 命令，不能作为 $version 的升级源"
    log "从 $previous 升级到 $version"
    "$executable" upgrade --version "$version"
  else
    log "安装首个版本 $version"
    sh "$script_dir/install.sh" --version "$version"
  fi
fi

assert_version

log "运行已安装二进制的运行时冒烟测试"
sh "$script_dir/smoke-runtime-linux.sh" --executable "$executable" --version "$version"

log "检查发布生命周期命令"
"$executable" upgrade --help

log "验证默认卸载保留用户数据"
touch "$okit_home/user-data"
"$executable" uninstall --dry-run
"$executable" uninstall
[ ! -e "$executable" ] || fail "未卸载可执行文件：$executable"
[ -e "$okit_home/user-data" ] || fail "默认卸载删除了用户数据"

log "发布生命周期冒烟测试通过"
