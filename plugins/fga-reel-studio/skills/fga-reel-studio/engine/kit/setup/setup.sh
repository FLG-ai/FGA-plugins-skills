#!/bin/sh
# Setup, step one: find a Python 3.12+ on this computer, or fetch one into the kit's home (no admin password, no
# Homebrew, nothing installed system-wide), then run setup.py with it. setup.py fetches ffmpeg and Node the same way.
# Run: sh setup/setup.sh [--check] [--matte]          (the same flags as setup.py)
set -e
KIT_DIR=$(cd "$(dirname "$0")/.." && pwd)
RK_HOME="${REEL_KIT_HOME:-$HOME/reel-kit}"
case "$RK_HOME" in "~"*) RK_HOME="$HOME${RK_HOME#"~"}" ;; esac
TOOLS="$RK_HOME/tools"
UV_VERSION=0.12.8

good() {   # a Python 3.12+ that can make a virtual environment with pip in it
  "$1" -c 'import sys, venv, ensurepip; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1
}

pick() {
  for c in "$TOOLS/bin/python3" python3.13 python3.12 python3; do
    p=$(command -v "$c" 2>/dev/null) || continue
    # macOS's /usr/bin/python3 is 3.9, and on a Mac without Apple's developer tools it opens an install prompt
    [ "$(uname -s)" = Darwin ] && [ "$p" = /usr/bin/python3 ] && continue
    good "$p" && { echo "$p"; return 0; }
  done
  return 1
}

PY=$(pick) || PY=""
if [ -z "$PY" ]; then
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) T=aarch64-apple-darwin; SUM=8ce083658dbff20143607ca7af8e0c1d64b6fd7bf03a5cdcb62bf3d47d991b5f ;;
    Darwin-x86_64) T=x86_64-apple-darwin; SUM=bfcd4407de99e0a2c1904df0902fa1795653d4edd145358e6561527e746a4f16 ;;
    Linux-aarch64|Linux-arm64) T=aarch64-unknown-linux-gnu; SUM=ba8661f4fd207c8e94814191598e619b355ac10d5014e851e21eb800f9ef2b00 ;;
    Linux-x86_64) T=x86_64-unknown-linux-gnu; SUM=2e2b37e9811e17675a9e70bed5e1a58fc8c0388be63d751d72cc735188c149ff ;;
    *) echo "reel-kit needs Python 3.12 or newer, and can't fetch one for $(uname -s) $(uname -m). Install it from python.org, then run this again."; exit 1 ;;
  esac
  if [ "$1" = "--check" ]; then
    echo "STATUS python     MISSING no Python 3.12+ yet"; echo "           fix: sh $KIT_DIR/setup/setup.sh"; exit 1
  fi
  echo "fetching Python 3.12 into $TOOLS (about 40 MB, once) ..."
  mkdir -p "$TOOLS/uv" "$TOOLS/bin"
  TMP=$(mktemp -d)
  curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$T.tar.gz" -o "$TMP/uv.tar.gz"
  GOT=$( (shasum -a 256 "$TMP/uv.tar.gz" 2>/dev/null || sha256sum "$TMP/uv.tar.gz") | awk '{print $1}')
  [ "$GOT" = "$SUM" ] || { echo "the Python installer download didn't match its checksum; check your internet connection and run this again"; exit 1; }
  tar -xzf "$TMP/uv.tar.gz" -C "$TMP"
  mv "$TMP/uv-$T/uv" "$TOOLS/uv/uv"
  rm -rf "$TMP"
  UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PYTHON_PREFERENCE=only-managed "$TOOLS/uv/uv" python install 3.12 --quiet
  P=$(UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PYTHON_PREFERENCE=only-managed "$TOOLS/uv/uv" python find 3.12)
  ln -sf "$P" "$TOOLS/bin/python3"
  PY="$TOOLS/bin/python3"
  good "$PY" || { echo "the fetched Python didn't start; run this again, and if it fails twice install Python 3.12 from python.org"; exit 1; }
fi

exec "$PY" "$KIT_DIR/setup/setup.py" "$@"
