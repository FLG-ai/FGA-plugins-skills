#!/bin/bash
# Reel design system: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-8s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-8s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
command -v python3 >/dev/null && ok python3 "builds the page and the settings file" || miss python3 "builds the page and the settings file" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "crops and shrinks frames" || miss ffmpeg "crops and shrinks frames" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] && ok Chrome "draws the style previews" || miss Chrome "draws the style previews" "download from https://www.google.com/chrome/"
exit $M
