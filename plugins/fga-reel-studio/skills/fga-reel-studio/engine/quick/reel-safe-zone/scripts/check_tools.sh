#!/bin/bash
# Reel Safe Zone: checks the three things the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-10s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-10s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
{ command -v python3 >/dev/null && { [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; } && ok python3 "runs the check" || miss python3 "runs the check" "xcode-select --install"
{ command -v swiftc >/dev/null && { [ "$(command -v swiftc)" != /usr/bin/swiftc ] || xcode-select -p >/dev/null 2>&1; }; } && ok swiftc "reads the text with the Mac's built-in text recognition" || miss swiftc "reads the text with the Mac's built-in text recognition" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "pulls frames out of the video" || miss ffmpeg "pulls frames out of the video" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
[ "$(uname)" = "Darwin" ] || { echo "MISS  macOS      this skill uses Apple's text recognition, so it needs a Mac"; M=1; }
exit $M
