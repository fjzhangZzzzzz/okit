#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' 'Usage: scripts/smoke-runtime-windows-git-bash.sh --executable PATH --version VERSION'
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

executable=
version=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --executable) [[ "$#" -ge 2 ]] || fail "--executable requires a path"; executable=$2; shift 2 ;;
    --version) [[ "$#" -ge 2 ]] || fail "--version requires a value"; version=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; fail "unknown option: $1" ;;
  esac
done

[[ -n "$executable" ]] || fail "--executable is required"
[[ -n "$version" ]] || fail "--version is required"
executable=$(cygpath -u "$executable")
[[ -f "$executable" ]] || fail "executable does not exist: $executable"

executable_dir=$(cd -- "$(dirname -- "$executable")" && pwd)
temp_windows=$(cygpath -m "${RUNNER_TEMP:-${TEMP:-${TMP:-C:/Windows/Temp}}}")
[[ "$temp_windows" =~ ^([A-Za-z]):(/.*)?$ ]] || fail "temporary directory is not drive-qualified: $temp_windows"
drive=$(tr '[:upper:]' '[:lower:]' <<<"${BASH_REMATCH[1]}")
temp_path=${BASH_REMATCH[2]:-/}
temp_root="/$drive$temp_path"
smoke_root=$(mktemp -d "$temp_root/okit-runtime-git-bash.XXXXXX")
cleanup() { rm -rf "$smoke_root"; }
trap cleanup EXIT HUP INT TERM

export PATH="$executable_dir:$PATH"
export OKIT_HOME="$smoke_root/okit-home"
export MSYS2_ENV_CONV_EXCL=OKIT_HOME

actual=$(okit --version)
grep -Fx "okit $version" <<<"$actual" >/dev/null || fail "version output does not contain okit $version"
okit --help >/dev/null
okit upgrade --help >/dev/null
okit uninstall --help >/dev/null

printf '%s\n' 'Windows Git Bash runtime smoke test passed'
