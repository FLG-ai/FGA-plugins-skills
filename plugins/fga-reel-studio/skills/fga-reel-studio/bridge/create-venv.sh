#!/bin/bash
set -eu
HOME_RK="${REEL_KIT_HOME:-$HOME/reel-kit}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
TARGET="$HOME_RK/.venv"
if [ -x "$TARGET/bin/python" ]; then
  if "$TARGET/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'; then
    echo "Python environment is ready."
    exit 0
  fi
fi
BASE=""
for candidate in python3.12 python3.13 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 python3; do
  resolved="$(command -v "$candidate" 2>/dev/null || true)"
  [ -n "$resolved" ] || continue
  if [ "$resolved" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
  if "$resolved" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then BASE="$resolved"; break; fi
done
[ -n "$BASE" ] || { echo "Install Python 3.12 first, then retry."; exit 1; }
mkdir -p "$HOME_RK"
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  BACKUP="$(mktemp -d "$HOME_RK/python-backup.XXXXXX")"
  mv "$TARGET" "$BACKUP/.venv"
  printf 'Previous environment saved at %s\n' "$BACKUP/.venv"
fi
"$BASE" -m venv "$TARGET"
"$TARGET/bin/python" -c 'import sys; assert sys.version_info >= (3,12)'
echo "Python environment is ready. Packages will be installed here."
