#!/bin/bash
# Reel autopilot: renders a reel without Claude in the loop once its builders have written their files.
# Waits for work/sfx/<sb>.txt and work/edit_<sb>.json from every builder, then: apply edits, fix sparse keyframes,
# merge sound, force-align captions (sfx move with them), mix, render in a retry loop, copy to the delivery folder (REEL_OUT).
# Run: autopilot_reel.sh <project> "<sb1 sb2 ...>" "<delivered title>"
P="$(cd "$1" 2>/dev/null && pwd)" || { echo "autopilot_reel.sh: project folder not found: $1" >&2; exit 1; }; SBS="$2"; TITLE="$3"; N=$(basename "$P")
HERE="$(cd "$(dirname "$0")" && pwd)"
RK="$(cd "$HERE/../gates" && pwd)"; KIT="$(cd "$HERE/../kit" && pwd)"
HOME_RK="${REEL_KIT_HOME:-$HOME/reel-kit}"; PY="$HOME_RK/.venv/bin/python"
log() { echo "$(date '+%H:%M:%S') $*"; }
log "waiting for: $SBS"
for i in $(seq 1 1440); do
  miss=""; for s in $SBS; do [ -f "$P/work/sfx/$s.txt" ] && [ -f "$P/work/edit_$s.json" ] || miss="$miss $s"; done
  [ -z "$miss" ] && break; sleep 20
done
[ -n "$miss" ] && { log "gave up waiting for:$miss"; exit 1; }
log "all builders in"; sleep 60
python3 "$RK/apply_changes.py" "$P" || { log "apply_changes failed"; exit 1; }
for f in "$P"/fx/*/*.mp4; do
  [ -f "$f" ] || continue
  k=$(ffprobe -v error -select_streams v:0 -skip_frame nokey -show_entries frame=pts_time -of csv=p=0 "$f" | awk 'NR>1{d=$1-p; if(d>m)m=d} {p=$1} END{print (NR<2)?99:m+0}')
  if awk "BEGIN{exit !($k > 1.0)}"; then
    "$HERE/heavy.sh" ffmpeg -v error -y -i "$f" -c:v libx264 -g 10 -crf 16 -pix_fmt yuv420p -movflags +faststart -an "${f%.mp4}.kf.mp4" && mv "${f%.mp4}.kf.mp4" "$f" && log "re-keyed $f"
  fi
done
python3 "$RK/merge_sound.py" "$P" || { log "merge failed"; exit 1; }
if [ -z "$NOALIGN" ]; then "$HERE/heavy.sh" "$PY" "$RK/align.py" "$P" --write 2>&1 | grep -E "aligned|moved" ; log "aligned"; fi
python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" "$P/edit.py" || { log "edit.py broken"; exit 1; }
"$HERE/heavy.sh" "$PY" "$KIT/pipeline/mix.py" "$P" | tail -1
echo "$N" > "$HOME_RK/PRIORITY"
"$HERE/heavy.sh" "$HERE/render_retry.sh" "$P" "$N-${VER:-v1}" "$TITLE"
log "AUTOPILOT END"
