#!/bin/sh
set -eu

repo="fjzhangZzzzzz/okit"
okit_home="${OKIT_HOME:-$HOME/.okit}"
install_dir="${OKIT_INSTALL_DIR:-$HOME/.local/bin}"
release_root="${OKIT_RELEASE_BASE_URL:-https://github.com/$repo/releases}"
release_root=${release_root%/}

status() {
  printf '==> %s\n' "$*" >&2
}

usage() {
  cat <<'EOF'
Usage: install.sh [--version vMAJOR.MINOR.PATCH[-rc.N]]
EOF
}

requested_version=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) [ "$#" -ge 2 ] || { usage >&2; exit 1; }; requested_version=$2; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 1 ;;
  esac
done

case "$(uname -s)" in
  Linux) os=linux ;;
  *) echo "okit supports Linux with this installer" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

if [ -n "$requested_version" ] && ! printf '%s\n' "$requested_version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[1-9][0-9]*)?$'; then
  echo "invalid --version: $requested_version" >&2
  exit 1
fi

tmp=$(mktemp -d "${TMPDIR:-/tmp}/okit-install.XXXXXX")
metadata_tmp=
binary_tmp=
cleanup() {
  rm -rf "$tmp"
  [ -z "$metadata_tmp" ] || rm -f "$metadata_tmp"
  [ -z "$binary_tmp" ] || rm -f "$binary_tmp"
}
on_exit() {
  status=$?
  cleanup
  if [ "$status" -ne 0 ]; then
    echo "okit 安装失败：安装过程未完成。" >&2
    echo "请检查网络、Release 制品和安装目录权限后重试。" >&2
  fi
  exit "$status"
}
trap on_exit 0 1 2 15

if [ -n "$requested_version" ]; then
  manifest_url="$release_root/download/$requested_version/release-manifest.json"
else
  manifest_url="$release_root/latest/download/release-manifest.json"
fi
if [ -n "$requested_version" ]; then
  status "正在获取 $requested_version 版本信息"
else
  status "正在获取最新版本信息"
fi
if ! curl -fsSL "$manifest_url" -o "$tmp/release-manifest.json" 2>/dev/null; then
  echo "okit 安装失败：无法下载发布清单。" >&2
  exit 1
fi

json_string() {
  sed -n "s/^[[:space:]]*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\"[[:space:]]*,*[[:space:]]*$/\1/p" "$tmp/release-manifest.json" | head -n 1
}
schema=$(sed -n 's/^[[:space:]]*"schema"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\)[[:space:]]*,*[[:space:]]*$/\1/p' "$tmp/release-manifest.json" | head -n 1)
[ "$schema" = 1 ] || { echo "unsupported release manifest schema: $schema" >&2; exit 1; }
version=$(json_string version)
if ! printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[1-9][0-9]*)?$'; then
  echo "invalid version in release manifest: $version" >&2
  exit 1
fi
if [ -n "$requested_version" ] && [ "$version" != "$requested_version" ]; then
  echo "release manifest version $version does not match requested version $requested_version" >&2
  exit 1
fi
case "$version" in
  *-*) channel=prerelease ;;
  *) channel=stable ;;
esac
target="$os-$arch"
asset=$(json_string "$target")
checksums_name=$(json_string checksums)
if [ "$channel" = stable ]; then channel_name=稳定版; else channel_name=预发布版; fi
status "目标版本：$version（$channel_name）"
case "$asset" in [0-9A-Za-z]* ) ;; *) echo "invalid or missing asset for $target" >&2; exit 1 ;; esac
case "$asset" in *[!0-9A-Za-z._-]* ) echo "invalid asset filename: $asset" >&2; exit 1 ;; esac
case "$checksums_name" in [0-9A-Za-z]* ) ;; *) echo "invalid checksums filename: $checksums_name" >&2; exit 1 ;; esac
case "$checksums_name" in *[!0-9A-Za-z._-]* ) echo "invalid checksums filename: $checksums_name" >&2; exit 1 ;; esac
base="$release_root/download/$version"

status "正在下载 Linux $arch 制品"
if ! curl -fsSL "$base/$asset" -o "$tmp/$asset" 2>/dev/null; then
  echo "okit 安装失败：无法下载 Linux 制品。" >&2
  exit 1
fi
status '正在下载校验文件'
if ! curl -fsSL "$base/$checksums_name" -o "$tmp/$checksums_name" 2>/dev/null; then
  echo "okit 安装失败：无法下载校验文件。" >&2
  exit 1
fi
expected=$(awk -v name="$asset" '$2 == name || $2 == "*" name { print $1 }' "$tmp/$checksums_name")
[ -n "$expected" ] || { echo "checksum for $asset is missing" >&2; exit 1; }
status '正在校验制品完整性'
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$tmp/$asset" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
else
  echo "sha256sum or shasum is required" >&2
  exit 1
fi
[ "$actual" = "$expected" ] || { echo "checksum mismatch for $asset" >&2; exit 1; }

status '正在解压安装包'
tar -xzf "$tmp/$asset" -C "$tmp"
[ -f "$tmp/okit" ] || { echo "okit is missing from release archive" >&2; exit 1; }
status '正在准备安装目录'
mkdir -p "$install_dir" "$okit_home"
binary_tmp="$install_dir/.okit-install-$$"
status '正在替换可执行文件'
install -m 0755 "$tmp/okit" "$binary_tmp"
mv -f "$binary_tmp" "$install_dir/okit"
binary_tmp=
metadata_executable=$(printf '%s' "$install_dir/okit" | sed 's/\\/\\\\/g; s/"/\\"/g')
metadata_tmp="$okit_home/.install-$$.tmp"
status '正在写入安装元数据'
cat >"$metadata_tmp" <<EOF
{
  "method": "official",
  "version": "$version",
  "channel": "$channel",
  "executable": "$metadata_executable",
  "path_entries": [],
  "managed_files": []
}
EOF
chmod 0600 "$metadata_tmp"
mv -f "$metadata_tmp" "$okit_home/install.json"
metadata_tmp=

case ":$PATH:" in
  *":$install_dir:"*) ;;
  *) status '正在配置 PATH'; echo "Add $install_dir to PATH to invoke okit directly." ;;
esac
status '安装完成'
echo "okit $version installed to $install_dir/okit"
