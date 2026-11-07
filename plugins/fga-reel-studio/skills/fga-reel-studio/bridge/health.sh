#!/bin/bash
# fga-reel-studio health check. It only reads: it never installs, downloads or starts a job.
# Prints OK / MISS / NOTE / BUSY lines and exits 1 if anything the chosen lane needs is MISS.
# Run: bash health.sh [quick|full|all]      (default all)
LANE="${1:-all}"
STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
KIT="$STUDIO/engine/kit"
HOME_RK="${REEL_KIT_HOME:-$HOME/reel-kit}"
PY="$HOME_RK/.venv/bin/python"
BAD=0
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"
# without Apple's command line tools, python3 and swiftc are stubs that pop up an install window: never run them then
realpy() { [ "$(command -v python3)" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; }
ok()   { printf "OK    %-16s %s\n" "$1" "$2"; }
note() { printf "NOTE  %-16s %s\n" "$1" "$2"; }
busy() { printf "BUSY  %-16s %s\n" "$1" "$2"; }
miss() { printf "MISS  %-16s %s\n      fix: %s\n" "$1" "$2" "$3"; BAD=1; }

realpy || miss "Apple tools" "Apple's command line tools are not installed (python3 and the Swift compiler need them)" "bash \"$STUDIO/bridge/install.sh\" run xcode-clt (a window opens, the person clicks Install)"

# machine
MEM=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
if [ "$MEM" -gt 0 ] && [ "$MEM" -lt 12 ]; then
  note machine "${MEM} GB: the laptop profile. One heavy job at a time, render in segments, keep small work files in a folder that survives a restart (references/machine.md)"
else
  ok machine "${MEM} GB: render in segments still, a little parallel work is fine"
fi

# Check every bundled library file.
if bash "$STUDIO/bridge/unpack.sh"; then :; else
  miss library "bundled files are missing" "download and install the complete package again"
fi
if [ ! -x "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
  miss "Python environment" "Python 3.12+ environment needed for both lanes" "bash \"$STUDIO/bridge/install.sh\" run venv"
fi

# anything heavy already running?
# real processes only: a shell started with -c (an agent's own command) can contain these words without running anything
RUN=$(ps -axo pid=,command= 2>/dev/null | grep -E "hyperframes|render_retry|autopilot_reel|fxsandbox|pipeline/(render|cut|cutout)\.py|matte\.py" | grep -vE " -c |health\.sh|^ *[0-9]+ +(/[^ ]*/)?(ugrep|egrep|grep|ps)( |$)" | head -3)
[ -n "$RUN" ] && busy running "a reel job is already running. Do not start another heavy job:" && echo "$RUN" | sed 's/^/      /'
if [ "$LANE" = "full" ] || [ "$LANE" = "all" ]; then
  if [ ! -x "$PY" ]; then
    miss "venv python" "$PY not found" "bash \"$STUDIO/bridge/install.sh\" run kit (ask first: it installs)"
  elif "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    ok "venv python" "$("$PY" --version 2>&1)"
  else
    miss "venv python" "Python 3.12+ needed" "bash \"$STUDIO/bridge/install.sh\" run venv (keeps the previous environment as a backup)"
  fi
  command -v ffmpeg >/dev/null && ok ffmpeg "$(ffmpeg -version 2>/dev/null | head -1 | cut -c1-40)" || miss ffmpeg "not on PATH" "brew install ffmpeg"
  NV=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
  [ -n "$NV" ] && [ "$NV" -ge 22 ] && ok node "v$(node -v | sed 's/v//')" || miss node "Node 22+ needed (found: ${NV:-none})" "brew install node"
  [ -f "$HOME_RK/vendor/gsap.min.js" ] && ok "render vendor" "GSAP present" || miss "render vendor" "no gsap.min.js in $HOME_RK/vendor" "bash \"$STUDIO/bridge/install.sh\" run kit (ask first)"
  [ -d "$HOME_RK/models" ] && ok models "$(du -sh "$HOME_RK/models" 2>/dev/null | cut -f1) in $HOME_RK/models" || note models "none yet: the first transcription downloads the speech model"
  if [ -f "$HOME_RK/style/style.json" ]; then
    ok "style pack" "$(readlink "$HOME_RK/style" 2>/dev/null || echo "$HOME_RK/style")"
  elif [ -f "$HOME_RK/style/design-system.json" ]; then
    note "style pack" "a Quick-lane design system exists but no style.json yet. Convert it: python3 \"$STUDIO/bridge/design_system_to_pack.py\" \"$HOME_RK/style/design-system.json\" --out \"$HOME_RK/style\""
  else
    note "style" "no style folder yet at $HOME_RK/style. That is expected for a new person: step 1 asks for their example reels and builds it"
  fi
fi

if [ "$LANE" = "quick" ] || [ "$LANE" = "all" ]; then
  echo "--- Quick lane"
  QP=python3; [ -x "$PY" ] && QP="$PY"
  if [ "$QP" = python3 ] && ! realpy; then note "quick lane" "skipped the Python checks: install Apple's command line tools first"; else
  REEL_PY="$QP" bash "$STUDIO/engine/quick/reel-studio/scripts/check_all.sh" | grep -E "^(OK|MISS|NOTE|      install)" | grep -v "found$"
  [ "${PIPESTATUS[0]}" -ne 0 ] && BAD=1
  fi
fi

if [ "$LANE" != "quick" ]; then
  [ -f "$HOME_RK/.setup-complete-0.3.3" ] && ok "full setup" "successful setup recorded, current render still needs QA" || miss "full setup" "setup has not completed successfully for this release" "bash \"$STUDIO/bridge/install.sh\" run kit"
fi
# gates
echo "--- Gates"
EYEPY=""
[ -x "$PY" ] && "$PY" -c "import cv2, numpy" 2>/dev/null && EYEPY="$PY"
# Editing gates use the same private environment as the editing steps.
if [ -n "$EYEPY" ]; then ok "eyecheck" "OpenCV found, run eyecheck.py with: $EYEPY"; else miss "eyecheck" "no python here has OpenCV" "bash \"$STUDIO/bridge/install.sh\" run opencv (ask first)"; fi
if [ "$LANE" != "quick" ]; then
  if [ -x "$PY" ]; then
    "$PY" -c "import torch, transformers, numpy" 2>/dev/null && ok "wav2vec2 gates" "torch + transformers in the venv" || miss "wav2vec2 gates" "torch or transformers missing in the venv (joinaudit, fixjoins, align, capcheck)" "bash \"$STUDIO/bridge/install.sh\" run torch-gates (ask first)"
    ls ~/.cache/huggingface/hub 2>/dev/null | grep -q "wav2vec2-base-960h" && ok "wav2vec2 model" "cached" || note "wav2vec2 model" "not cached: the first join audit downloads about 360 MB, once. Ask first"
    "$PY" -c "import faster_whisper" 2>/dev/null && ok "faster-whisper" "in the venv" || miss "faster-whisper" "missing in the venv" "bash \"$STUDIO/bridge/install.sh\" run kit (ask first)"
  else
    note "word-level gates" "the kit's venv is not set up, so joinaudit, fixjoins, align and capcheck cannot run yet (kit lanes only)"
  fi
fi
for script in heavy.sh render_retry.sh autopilot_reel.sh; do
  bash -n "$STUDIO/engine/run/$script" 2>/dev/null && ok "run script" "$script parses" || miss "run script" "$script has a syntax error" "reinstall the skill"
done

# the Quick lane file is built from the style pack: is it stale?
DS="$HOME_RK/style/design-system.json"; SJ="$HOME_RK/style/style.json"; OV="$HOME_RK/style/quick-overrides.json"
if [ -f "$DS" ] && [ -f "$SJ" ]; then
  if [ "$SJ" -nt "$DS" ] || { [ -f "$OV" ] && [ "$OV" -nt "$DS" ]; }; then
    note "design-system" "style.json or quick-overrides.json changed since design-system.json was built. Rebuild: python3 \"$STUDIO/bridge/pack_to_design_system.py\" \"$HOME_RK/style\""
  else
    ok "design-system" "up to date with the style pack"
  fi
elif [ -f "$SJ" ] && [ ! -f "$DS" ]; then
  note "design-system" "no design-system.json yet: the Quick lane needs one. Build it: python3 \"$STUDIO/bridge/pack_to_design_system.py\" \"$HOME_RK/style\""
fi

if [ "$BAD" -eq 0 ]; then echo "HEALTHY for lane: $LANE"; else echo "NOT READY for lane: $LANE (see MISS above)"; echo "To fix it in order: bash \"$STUDIO/bridge/install.sh\" plan $LANE"; fi
exit $BAD
