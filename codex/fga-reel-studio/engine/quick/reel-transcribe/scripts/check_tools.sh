#!/bin/bash
# Reel transcribe: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-15s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-15s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
{ command -v python3 >/dev/null && { [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; } && ok python3 "runs the scripts" || miss python3 "runs the scripts" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "makes the working copy and the audio" || miss ffmpeg "makes the working copy and the audio" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
"${REEL_PY:-python3}" -c "import faster_whisper" 2>/dev/null && ok faster-whisper "turns speech into timed words, on this Mac" || miss faster-whisper "turns speech into timed words, on this Mac" "ask Claude to run bridge/install.sh plan quick, then install the missing items after approval"
ls ~/.cache/huggingface/hub 2>/dev/null | grep -q faster-whisper-small && ok "speech model" "downloaded" || echo "NOTE  speech model    downloads once on the first run (about 480 MB), then works offline"
exit $M
