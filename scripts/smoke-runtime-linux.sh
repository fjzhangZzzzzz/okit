#!/bin/sh
set -eu

usage() {
  printf '%s\n' 'Usage: scripts/smoke-runtime-linux.sh --executable PATH --version VERSION'
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

executable=
version=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --executable) [ "$#" -ge 2 ] || fail "--executable requires a path"; executable=$2; shift 2 ;;
    --version) [ "$#" -ge 2 ] || fail "--version requires a value"; version=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; fail "unknown option: $1" ;;
  esac
done

[ -n "$executable" ] || fail "--executable is required"
[ -n "$version" ] || fail "--version is required"
[ -f "$executable" ] || fail "executable does not exist: $executable"

executable_dir=$(CDPATH= cd -- "$(dirname -- "$executable")" && pwd)
smoke_root=$(mktemp -d "${TMPDIR:-/tmp}/okit-runtime-linux.XXXXXX")
cleanup() { rm -rf "$smoke_root"; }
trap cleanup EXIT HUP INT TERM

export PATH=$executable_dir:$PATH
export OKIT_HOME=$smoke_root/okit-home

actual=$(okit --version)
printf '%s\n' "$actual" | grep -Fx "okit $version" >/dev/null || fail "version output does not contain okit $version"
okit --help >/dev/null
info=$(okit info --format json)
printf '%s\n' "$info" | grep -F '"platform": "linux/' >/dev/null || fail "info did not report Linux"
printf '%s\n' "$info" | grep -F '"path_status": "ok"' >/dev/null || fail "PATH did not resolve to the tested executable"
printf '%s\n' "$info" | grep -F '"install_dir_in_path": true' >/dev/null || fail "install directory was not detected in PATH"
printf '%s\n' "$info" | grep -F "\"data_dir\": \"$OKIT_HOME\"" >/dev/null || fail "OKIT_HOME was not preserved"

printf '%s\n' 'Linux runtime smoke test passed'
