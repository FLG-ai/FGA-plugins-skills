#!/bin/bash
# fga-reel-studio guided setup, for a computer that has nothing yet.
#
#   install.sh plan [quick|full|all]    Lists what is missing, in the order to install it, how big it is and who runs it.
#                                       Changes nothing. Default lane: all.
#   install.sh run <item> [--dry-run]   Runs ONE item. Call it only after the person said yes to that item.
#                                       --dry-run prints the command and does nothing.
#   install.sh items                    Lists the item names.
#
# Items that need a password or a click in a window (Apple's command line tools, Homebrew) are never run for the person:
# `run` prints exactly what they should do themselves and stops. Everything else is a single known command.
# Nothing here installs without being asked, and nothing is installed outside these items.
# Written for macOS. On Linux, python3 "$KIT/setup/setup.py" prints the right fix for each missing piece.

STUDIO="$(cd "$(dirname "$0")/.." && pwd)"
KIT="$STUDIO/engine/kit"
HOME_RK="${REEL_KIT_HOME:-$HOME/reel-kit}"
# Homebrew installs to /opt/homebrew on Apple Silicon, which a fresh session does not have on its PATH yet
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"
# On a Mac without Apple's command line tools, python3 and swiftc are stubs that pop up an install window: never run them then
realpy() { [ "$(command -v python3)" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; }
VENV_PY="$HOME_RK/.venv/bin/python"
BREW="$(command -v brew || ls /opt/homebrew/bin/brew /usr/local/bin/brew 2>/dev/null | head -1)"
BR="${BREW:-brew}"   # the name to print in commands before Homebrew exists

ALL_QUICK="xcode-clt homebrew ffmpeg chrome python312 venv whisper-system opencv"
ALL_FULL="xcode-clt homebrew ffmpeg python312 venv node kit opencv torch-gates"
ALL_GATES=""

# ---- per item: what it is, size, who runs it, how to tell it is there, the command ----
desc()  { case "$1" in
  xcode-clt)      echo "Apple's command line tools (python3 and the Swift compiler)";;
  homebrew)       echo "Homebrew, the installer the next items use";;
  ffmpeg)         echo "ffmpeg, which does every cut, zoom, mix and frame grab";;
  chrome)         echo "Google Chrome, which draws captions and previews in your fonts";;
  whisper-system) echo "faster-whisper, Pillow, NumPy, SciPy and yt-dlp, speech to timed words and the window drawing (the speech model, about 480 MB, downloads on the first transcription)";;
  venv)           echo "a private Python environment for Reel Studio";;
  python312)      echo "Python 3.12 or newer, for the kit's own environment";;
  node)           echo "Node, the render engine";;
  kit)            echo "the full editing environment, render tools and speech model";;
  opencv)         echo "OpenCV, for the look-down check";;
  torch-gates)    echo "PyTorch and transformers for word-level checks";;
  matte)          echo "optional smoother cutouts, including PyTorch and the RVM model";;
  *) return 1;; esac; }
size()  { case "$1" in
  xcode-clt) echo "1 to 2 GB";; homebrew) echo "small";; ffmpeg) echo "about 100 MB";; chrome) echo "about 200 MB";;
  whisper-system) echo "about 50 MB";; python312) echo "about 100 MB";; node) echo "about 100 MB";;
  venv) echo "about 30 MB";;
  kit) echo "about 2 GB (1.5 GB is the speech model)";; opencv) echo "about 60 MB";; torch-gates) echo "about 1 GB";; matte) echo "about 1.1 GB";; esac; }
who()   { case "$1" in
  xcode-clt) echo "YOU: it opens an Apple window, click Install";;
  homebrew)  echo "YOU: it asks for your Mac password, so run it yourself in Terminal";;
  *) echo "agent, after your yes";; esac; }

pyok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; }   # the kit needs 3.12+
bestpy() { for p in python3.13 python3.12 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  P="$(command -v "$p" 2>/dev/null || ([ -x "$p" ] && echo "$p"))"; [ -n "$P" ] && pyok "$P" && { echo "$P"; return; }; done; }
QPY() { [ -x "$VENV_PY" ] && echo "$VENV_PY" || echo python3; }

have() { case " $INSTALL_SIM_MISSING " in *" $1 "*) return 1;; esac   # test hook: INSTALL_SIM_MISSING="ffmpeg chrome" pretends those are missing
  case "$1" in
  xcode-clt)      xcode-select -p >/dev/null 2>&1;;
  homebrew)       [ -n "$BREW" ];;
  ffmpeg)         command -v ffmpeg >/dev/null;;
  chrome)         [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ];;
  whisper-system) have venv && "$VENV_PY" -c "import faster_whisper, PIL, numpy, scipy, yt_dlp" 2>/dev/null;;
  python312)      [ -n "$(bestpy)" ];;
  venv)           [ -x "$VENV_PY" ] && pyok "$VENV_PY";;
  node)           N=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1); [ -n "$N" ] && [ "$N" -ge 22 ];;
  kit)            have venv && [ -f "$HOME_RK/.setup-complete-0.4.0" ] && "$VENV_PY" "$KIT/setup/setup.py" --check >/dev/null 2>&1;;
  opencv)         have venv && "$VENV_PY" -c "import cv2, numpy" 2>/dev/null;;
  torch-gates)    [ -x "$VENV_PY" ] && "$VENV_PY" -c "import torch, transformers" 2>/dev/null;;
  matte)          [ -x "$VENV_PY" ] && "$VENV_PY" -c "import torch" 2>/dev/null;;
  *) return 1;; esac; }

cmd() { case "$1" in
  xcode-clt)      echo "xcode-select --install";;
  homebrew)       echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"';;
  ffmpeg)         printf '%q install ffmpeg\n' "$BR";;
  chrome)         printf '%q install --cask google-chrome\n' "$BR";;
  whisper-system) printf '%q -m pip install faster-whisper pillow numpy scipy yt-dlp\n' "$VENV_PY";;
  venv)           printf 'bash %q\n' "$STUDIO/bridge/create-venv.sh";;
  python312)      printf '%q install python@3.12\n' "$BR";;
  node)           printf '%q install node\n' "$BR";;
  kit)            printf '%q %q\n' "$VENV_PY" "$KIT/setup/setup.py";;
  opencv)         printf '%q -m pip install opencv-python-headless numpy\n' "$VENV_PY";;
  torch-gates)    printf '%q -m pip install torch transformers\n' "$VENV_PY";;
  matte)          printf '%q %q --matte\n' "$VENV_PY" "$KIT/setup/setup.py";;
esac; }

# items that must exist first
needs() { case "$1" in
  ffmpeg|chrome|python312|node) echo homebrew;;
  homebrew) echo xcode-clt;;
  venv) echo python312;;
  kit) echo "venv node ffmpeg";;
  torch-gates|matte) echo kit;;
  opencv) echo venv;;
  whisper-system) echo venv;;
esac; }

lane_items() { case "${1:-all}" in
  quick) echo "$ALL_QUICK";; full) echo "$ALL_FULL";;
  all) echo "xcode-clt homebrew ffmpeg chrome python312 venv node kit whisper-system opencv torch-gates";;
  *) echo "usage: install.sh plan [quick|full|all]" >&2; return 1;; esac; }

plan() {
  [ "$(uname)" = "Darwin" ] || { echo "This guided setup is written for macOS. On Linux, run: python3 \"$KIT/setup/setup.py\" --check and pass on the fixes it prints."; return 0; }
  ITEMS="$(lane_items "$1")" || return 1
  echo "Setup plan for lane: ${1:-all}   (home folder for everything the kit installs: $HOME_RK)"
  n=0; todo=0
  for it in $ITEMS; do
    # a Quick-only machine without the kit's environment needs faster-whisper itself, the kit installs it otherwise
    if [ "$it" = "whisper-system" ] && have kit; then continue; fi
    if [ "$it" = "homebrew" ] && ! have homebrew; then
      need_brew=0; for d in ffmpeg chrome python312 node; do case " $ITEMS " in *" $d "*) have "$d" || need_brew=1;; esac; done
      [ "$need_brew" -eq 0 ] && { printf "  [-] %-15s not installed, and nothing in this plan needs it\n" "$it"; continue; }
    fi
    if have "$it"; then printf "  [x] %-15s already there\n" "$it"; continue; fi
    todo=$((todo+1)); printf "  [ ] %-15s %s\n" "$it" "$(desc "$it")"
    printf "      size: %s    who: %s\n      command: %s\n" "$(size "$it")" "$(who "$it")" "$(cmd "$it")"
    nd="$(needs "$it")"; [ -n "$nd" ] && printf "      needs first: %s\n" "$nd"
  done
  [ "$todo" -eq 0 ] && echo "Nothing to install for this lane." || echo "$todo item(s) to go. Say yes to each one, then: install.sh run <item>"
  echo "Optional: matte ($(size matte)): $(desc matte)"
}

run() {
  it="$1"; shift
  desc "$it" >/dev/null || { echo "unknown item '$it'. See: install.sh items" >&2; exit 2; }
  [ "$(uname)" = "Darwin" ] || { echo "macOS only. See references/setup.md" >&2; exit 2; }
  if have "$it"; then echo "$it is already installed."; exit 0; fi
  for nd in $(needs "$it"); do have "$nd" || { echo "Not yet: $it needs $nd first. Run: install.sh run $nd" >&2; exit 4; }; done
  if [ "$(who "$it" | cut -c1-3)" = "YOU" ]; then
    echo "This one is yours to do, because it needs a click or your password."
    echo "  What: $(desc "$it")"; echo "  Do:   $(cmd "$it")"
    [ "$it" = "homebrew" ] && echo "  Open Terminal, paste that line, press Return, type your Mac password when it asks. When it finishes it prints two or three lines under 'Next steps' that start with echo or eval: paste those too and press Return. Then tell me it is done."
    [ "$it" = "xcode-clt" ] && echo "  An Apple window opens. Click Install, accept, wait. Then tell me when it finishes."
    exit 3
  fi
  C="$(cmd "$it")"; echo "Running: $C"
  [ "$1" = "--dry-run" ] && { echo "(dry run, nothing done)"; exit 0; }
  bash -c "$C"; rc=$?
  if [ "$rc" -eq 0 ] && have "$it"; then
    echo "OK: $it is installed."
  else
    echo "Setup for $it did not pass its checks (command exit $rc). Show the output above."
    [ "$rc" -ne 0 ] || rc=1
  fi
  exit "$rc"
}

case "$1" in
  plan) plan "$2";;
  run) shift; [ -n "$1" ] || { echo "usage: install.sh run <item> [--dry-run]" >&2; exit 2; }; run "$@";;
  items) echo "$ALL_QUICK $ALL_FULL $ALL_GATES matte" | tr ' ' '\n' | awk '!s[$0]++' | tr '\n' ' '; echo;;
  *) sed -n 2,17p "$0" | sed 's/^# \{0,1\}//'; exit 2;;
esac
