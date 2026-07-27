#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  scripts/smoke-release-lifecycle.sh --release --version vMAJOR.MINOR.PATCH
  scripts/smoke-release-lifecycle.sh --binary PATH --version vMAJOR.MINOR.PATCH

Environment:
  OKIT_HOME, OKIT_INSTALL_DIR  override the isolated test directories
  OKIT_REPOSITORY              override the GitHub owner/repository
EOF
}

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

mode=release
binary=
version=${OKIT_VERSION:-}
repository=${OKIT_REPOSITORY:-fjzhangZzzzzz/okit}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --release) mode=release; shift ;;
    --binary) [ "$#" -ge 2 ] || fail "--binary requires a path"; mode=binary; binary=$2; shift 2 ;;
    --version) [ "$#" -ge 2 ] || fail "--version requires a value"; version=$2; shift 2 ;;
    --repository) [ "$#" -ge 2 ] || fail "--repository requires owner/repository"; repository=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; fail "unknown option: $1" ;;
  esac
done

printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$' || fail "invalid version: $version"
[ "$mode" != binary ] || [ -n "$binary" ] || fail "binary mode requires --binary PATH"

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
  [ -f "$binary" ] || fail "binary does not exist: $binary"
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
  log "Verify installed version"
  set +e
  actual=$($executable --version 2>&1)
  status=$?
  set -e
  printf 'binary: %s\nexpected: okit %s\nactual output:\n%s\n' "$executable" "$version" "$actual"
  [ "$status" -eq 0 ] || fail "version command exited with status $status"
  printf '%s\n' "$actual" | grep -Fx "okit $version" >/dev/null || fail "installed version does not match tag $version"
}

log "Prepare $mode smoke test for $version"
if [ "$mode" = binary ]; then
  stage_binary
else
  command -v gh >/dev/null 2>&1 || fail "gh is required for release mode"
  previous=$(gh api "repos/$repository/releases" --jq '.[] | select(.draft == false and .prerelease == false) | .tag_name' | grep -vx "$version" | head -n 1 || true)
  if [ -n "$previous" ]; then
    log "Install previous release $previous"
    sh "$script_dir/install.sh" --version "$previous"
    log "Update $previous to $version"
    "$executable" upgrade --version "$version"
  else
    log "Install first release $version"
    sh "$script_dir/install.sh" --version "$version"
  fi
fi

assert_version

log "Run installed binary runtime smoke"
sh "$script_dir/smoke-runtime-linux.sh" --executable "$executable" --version "$version"

log "Run release lifecycle command checks"
"$executable" upgrade --help

log "Verify uninstall preserves user data"
touch "$okit_home/user-data"
"$executable" uninstall --dry-run
"$executable" uninstall
[ ! -e "$executable" ] || fail "executable was not uninstalled: $executable"
[ -e "$okit_home/user-data" ] || fail "default uninstall removed user data"

log "Release lifecycle smoke test passed"
