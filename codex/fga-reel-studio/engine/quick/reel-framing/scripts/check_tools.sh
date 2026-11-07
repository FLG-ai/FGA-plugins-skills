#!/bin/bash
# Reel framing: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-8s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-8s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
{ command -v python3 >/dev/null && { [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; } && ok python3 "plans the framing" || miss python3 "plans the framing" "xcode-select --install"
{ command -v swiftc >/dev/null && { [ "$(command -v swiftc)" != /usr/bin/swiftc ] || xcode-select -p >/dev/null 2>&1; }; } && ok swiftc "finds the face with the Mac's face detection" || miss swiftc "finds the face with the Mac's face detection" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "renders the zooms and grade" || miss ffmpeg "renders the zooms and grade" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
exit $M
