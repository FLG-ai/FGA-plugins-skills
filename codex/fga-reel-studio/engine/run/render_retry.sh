#!/bin/bash
# Render a reel-kit project in segments with retries (a stalled capture only redoes its segment), then mux, QA, copy.
# Run: render_retry.sh <project> <name> "<delivered file title>"   (REEL_OUT=<folder> sets where the copy goes)
P="$(cd "$1" 2>/dev/null && pwd)" || { echo "render_retry.sh: project folder not found: $1" >&2; exit 1; }; NAME="$2"; TITLE="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT="$(cd "$HERE/../kit" && pwd)"                       # the kit that sits beside this script
HOME_RK="${REEL_KIT_HOME:-$HOME/reel-kit}"
PY="$HOME_RK/.venv/bin/python"
OUT="${REEL_OUT:-$(dirname "$P")/delivered}"            # set REEL_OUT to the folder to deliver into
log() { echo "$(date '+%H:%M:%S') $*"; }
cd "$P/public" || exit 1
"$PY" "$KIT/pipeline/build.py" "$P" | tail -1
F="$P/renders/$NAME.mp4"; rm -f "$F"
ok=0
for try in 1 2 3 4 5 6; do
  extra=""; [ $try -ge 3 ] && extra="--debug"   # plain capture recovers from a stall itself (it did at frame 422); --debug keeps diagnostics
  log "render try $try"
  mode=""   # the low-memory profile (the default, and the safe one on a laptop with 8 GB); --no-low-memory-mode hung at frame 0
  npx -y hyperframes@0.8.139 render -q delivery --quiet $mode $extra -o "../renders/$NAME.mp4" 2>&1 | grep -vE "^\[INFO\]" | tail -6
  if [ -f "$F" ] && ffprobe -v error -show_entries format=duration -of csv=p=0 "$F" >/dev/null 2>&1; then ok=1; break; fi
done
[ $ok -eq 1 ] || { log "RENDER FAILED after $try tries"; exit 1; }
rm -rf "$P/public/snapshots"
ffmpeg -v error -y -i "$F" -i "$P/public/master.wav" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -ar 48000 -shortest -movflags +faststart "${F%.mp4}.mix.mp4" && mv "${F%.mp4}.mix.mp4" "$F"
log "rendered $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$F") s"
"$PY" "$KIT/pipeline/qa.py" "$P" "renders/$NAME.mp4" --phone 2>&1 | tail -25; rc=${PIPESTATUS[0]}
tag=""; [ "$rc" -ne 0 ] && tag=" (QA flagged)"
mkdir -p "$OUT"
cp "$F" "$OUT/$TITLE$tag.mp4" && log "copied: $TITLE$tag.mp4"
[ -f "${F%.mp4}-phone.mp4" ] && cp "${F%.mp4}-phone.mp4" "$OUT/$TITLE$tag (phone).mp4" && log "copied phone copy"
log "RENDER_RETRY DONE rc=$rc"
