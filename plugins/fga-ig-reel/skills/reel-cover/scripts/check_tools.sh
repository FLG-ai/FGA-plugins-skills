#!/bin/bash
# Reel cover: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-8s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-8s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
command -v python3 >/dev/null && ok python3 "finds the frames and lays out the cover" || miss python3 "finds the frames and lays out the cover" "xcode-select --install"
command -v swiftc >/dev/null && ok swiftc "scores faces with the Mac's face detection" || miss swiftc "scores faces with the Mac's face detection" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "pulls the stills" || miss ffmpeg "pulls the stills" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && ok Chrome "draws the hook in your fonts" || miss Chrome "draws the hook in your fonts" "download from https://www.google.com/chrome/"
exit $M
