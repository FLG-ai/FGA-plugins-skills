#!/bin/bash
# Reel studio: checks everything the whole chain needs, once. Prints OK or MISS with the install line.
ok(){ printf "OK    %-15s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-15s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
[ "$(uname)" = "Darwin" ] && ok macOS "uses the Mac's face detection and text reading" || { echo "MISS  macOS           this plugin needs a Mac"; M=1; }
command -v python3 >/dev/null && ok python3 "runs every step" || miss python3 "runs every step" "xcode-select --install"
command -v swiftc >/dev/null && ok swiftc "face detection and text checks" || miss swiftc "face detection and text checks" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "cuts, zooms, overlays and mixes" || miss ffmpeg "cuts, zooms, overlays and mixes" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && ok Chrome "draws text in your fonts, and pulls frames from inspo reels" || miss Chrome "draws text in your fonts" "download from https://www.google.com/chrome/"
python3 -c "import faster_whisper" 2>/dev/null && ok faster-whisper "speech to timed words, on this Mac" || miss faster-whisper "speech to timed words, on this Mac" "python3 -m pip install --user faster-whisper"
ls ~/.cache/huggingface/hub 2>/dev/null | grep -q faster-whisper-small && ok "speech model" "downloaded" || echo "NOTE  speech model    downloads once on the first transcribe (about 480 MB), then works offline"
H="$(cd "$(dirname "$0")/../.." && pwd)"
for s in reel-design-system reel-transcribe reel-tighten reel-framing reel-captions reel-text-pops reel-sound reel-safe-zone reel-cover; do
  [ -f "$H/$s/SKILL.md" ] && ok "$s" "found" || miss "$s" "missing from the plugin" "reinstall the FGA IG Reel Designer + Editor plugin"
done
exit $M
