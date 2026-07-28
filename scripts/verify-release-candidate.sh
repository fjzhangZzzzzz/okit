#!/bin/sh
set -eu

fail() { printf '错误：%s\n' "$*" >&2; exit 1; }

version=
repository=
commit=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) [ "$#" -ge 2 ] || fail "--version 需要版本号"; version=$2; shift 2 ;;
    --repository) [ "$#" -ge 2 ] || fail "--repository 需要 owner/repository"; repository=$2; shift 2 ;;
    --commit) [ "$#" -ge 2 ] || fail "--commit 需要提交号"; commit=$2; shift 2 ;;
    *) fail "未知选项：$1" ;;
  esac
done

printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$' ||
  fail "正式版本号无效：$version"
[ -n "$repository" ] || fail "缺少 --repository"
[ -n "$commit" ] || fail "缺少 --commit"

candidate=$(git tag --list "$version-rc.*" --points-at "$commit" --sort=-v:refname | head -n 1)
[ -n "$candidate" ] || fail "$version 的正式发布提交上不存在 RC tag"

candidate_commit=$(git rev-list -n 1 "$candidate")
[ "$candidate_commit" = "$commit" ] ||
  fail "$candidate 与正式发布不在同一提交"

candidate_state=$(gh release view "$candidate" \
  --repo "$repository" \
  --json isDraft,isPrerelease \
  --jq '(.isDraft == false and .isPrerelease == true)')
[ "$candidate_state" = true ] ||
  fail "$candidate 不是已发布的 GitHub Pre-release"

validation_dir=$(mktemp -d "${TMPDIR:-/tmp}/okit-release-validation.XXXXXX")
cleanup() { rm -rf "$validation_dir"; }
trap cleanup EXIT HUP INT TERM
gh release download "$candidate" \
  --repo "$repository" \
  --pattern release-validation.json \
  --dir "$validation_dir" >/dev/null 2>&1 ||
  fail "$candidate 尚未完成 Linux/Windows 发布冒烟验证"

jq -e \
  --arg version "$candidate" \
  --arg commit "$commit" \
  '.version == $version and .commit == $commit and .linux == true and .windows == true' \
  "$validation_dir/release-validation.json" >/dev/null ||
  fail "$candidate 的发布验证标记与版本、提交或平台结果不一致"

printf '%s\n' "$candidate 已通过发布验证，可以发布 $version"
