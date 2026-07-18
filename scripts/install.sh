#!/bin/sh
set -eu

repo="fjzhangZzzzzz/okit"
okit_home="${OKIT_HOME:-$HOME/.okit}"
install_dir="${OKIT_INSTALL_DIR:-$HOME/.local/bin}"
version="${OKIT_VERSION:-}"

case "$(uname -s)" in
  Linux) os=linux ;;
  *) echo "okit supports Linux with this installer" >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo "unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

if [ -z "$version" ]; then
  version=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest" | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)
fi
if ! printf '%s\n' "$version" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$'; then
  echo "invalid OKIT_VERSION: $version" >&2
  exit 1
fi

plain_version=${version#v}
asset="okit_${plain_version}_${os}_${arch}.tar.gz"
base="https://github.com/$repo/releases/download/$version"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/okit-install.XXXXXX")
metadata_tmp=
binary_tmp=
trap 'rm -rf "$tmp"; [ -z "$metadata_tmp" ] || rm -f "$metadata_tmp"; [ -z "$binary_tmp" ] || rm -f "$binary_tmp"' EXIT HUP INT TERM

curl -fsSL "$base/$asset" -o "$tmp/$asset"
curl -fsSL "$base/checksums.txt" -o "$tmp/checksums.txt"
expected=$(awk -v name="$asset" '$2 == name || $2 == "*" name { print $1 }' "$tmp/checksums.txt")
[ -n "$expected" ] || { echo "checksum for $asset is missing" >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$tmp/$asset" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
else
  echo "sha256sum or shasum is required" >&2
  exit 1
fi
[ "$actual" = "$expected" ] || { echo "checksum mismatch for $asset" >&2; exit 1; }

tar -xzf "$tmp/$asset" -C "$tmp"
[ -f "$tmp/okit" ] || { echo "okit is missing from release archive" >&2; exit 1; }
mkdir -p "$install_dir" "$okit_home"
binary_tmp="$install_dir/.okit-install-$$"
install -m 0755 "$tmp/okit" "$binary_tmp"
mv -f "$binary_tmp" "$install_dir/okit"
binary_tmp=
metadata_executable=$(printf '%s' "$install_dir/okit" | sed 's/\\/\\\\/g; s/"/\\"/g')
metadata_tmp="$okit_home/.install-$$.tmp"
cat >"$metadata_tmp" <<EOF
{
  "method": "official",
  "version": "$version",
  "channel": "stable",
  "executable": "$metadata_executable",
  "path_entries": [],
  "managed_files": []
}
EOF
chmod 0600 "$metadata_tmp"
mv -f "$metadata_tmp" "$okit_home/install.json"
metadata_tmp=

echo "okit $version installed to $install_dir/okit"
case ":$PATH:" in
  *":$install_dir:"*) ;;
  *) echo "Add $install_dir to PATH to invoke okit directly." ;;
esac
