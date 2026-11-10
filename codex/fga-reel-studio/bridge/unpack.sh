#!/bin/bash
# Compatibility entry point. The library now ships as ordinary files.
set -eu
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$STUDIO/bridge/library-files.txt"
[ -f "$MANIFEST" ] || { echo "MISS library manifest. Download the complete package again."; exit 1; }
missing=0
while IFS= read -r relative; do
  [ -f "$STUDIO/engine/kit/$relative" ] || { printf 'MISS library %s\n' "$relative"; missing=1; }
done < "$MANIFEST"
[ "$missing" -eq 0 ] || exit 1
echo "OK    library       all bundled library files are present"
