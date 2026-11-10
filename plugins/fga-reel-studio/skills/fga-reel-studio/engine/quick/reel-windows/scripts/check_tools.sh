#!/bin/bash
# Reel windows: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-8s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-8s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
{ command -v python3 >/dev/null && { [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; } && ok python3 "plans and renders the windows" || miss python3 "plans and renders the windows" "xcode-select --install"
python3 -c "import PIL" 2>/dev/null && ok pillow "draws the rounded corners and the shadow" || miss pillow "draws the rounded corners and the shadow" "ask Claude to run bridge/install.sh plan quick, then install the missing items after approval"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "puts the windows on the video" || miss ffmpeg "puts the windows on the video" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
exit $M
