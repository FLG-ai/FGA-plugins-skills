#!/bin/bash
# Reel tighten: checks what the skill needs. Prints OK or MISS with the install line.
ok(){ printf "OK    %-8s %s\n" "$1" "$2"; }; miss(){ printf "MISS  %-8s %s\n      install: %s\n" "$1" "$2" "$3"; M=1; }
M=0
{ command -v python3 >/dev/null && { [ "$(command -v python3)" != /usr/bin/python3 ] || xcode-select -p >/dev/null 2>&1; }; } && ok python3 "plans and renders the cuts" || miss python3 "plans and renders the cuts" "xcode-select --install"
{ command -v swiftc >/dev/null && { [ "$(command -v swiftc)" != /usr/bin/swiftc ] || xcode-select -p >/dev/null 2>&1; }; } && ok swiftc "spots looking down with the Mac's face detection" || miss swiftc "spots looking down with the Mac's face detection" "xcode-select --install"
F=$(command -v ffmpeg || ls /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg ~/.local/bin/ffmpeg 2>/dev/null | head -1)
[ -n "$F" ] && ok ffmpeg "cuts and joins the video" || miss ffmpeg "cuts and joins the video" "brew install ffmpeg   (no Homebrew? see https://brew.sh)"
exit $M
