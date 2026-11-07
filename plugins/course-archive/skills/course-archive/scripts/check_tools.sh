#!/bin/bash
# Checks every tool course-archive uses. Prints what is missing and the
# command to install it. Installs nothing. Exit 1 if a core tool is missing.

core_missing=0
missing=()

have() { command -v "$1" >/dev/null 2>&1; }
pymod() { python3 -c "import $1" >/dev/null 2>&1; }

row() { # status, name, used for
  printf '  %-4s %-16s %s\n' "$1" "$2" "$3"
}

echo "course-archive tool check"
echo

if have python3; then row "ok" "python3" "runs every script"
else row "MISS" "python3" "runs every script"; core_missing=1
  missing+=("python3|xcode-select --install   (or: brew install python)"); fi

if have brew; then row "ok" "brew" "installs the rest"
else row "--" "brew" "installs the rest (optional, makes the others easy)"
  missing+=("brew|/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""); fi

if have python3 && pymod yt_dlp; then row "ok" "yt-dlp" "reads browser cookies, downloads videos"
else row "MISS" "yt-dlp" "reads browser cookies, downloads videos"; core_missing=1
  missing+=("yt-dlp|python3 -m pip install --user -U yt-dlp"); fi

if have ffmpeg && have ffprobe; then row "ok" "ffmpeg" "checks videos, feeds audio to transcription"
else row "MISS" "ffmpeg" "checks videos, feeds audio to transcription"
  missing+=("ffmpeg|brew install ffmpeg"); fi

if have python3 && pymod faster_whisper; then row "ok" "faster-whisper" "transcribes videos with no captions"
else row "MISS" "faster-whisper" "transcribes videos with no captions"
  missing+=("faster-whisper|python3 -m pip install --user -U faster-whisper"); fi

if have python3 && pymod fitz; then row "ok" "pymupdf" "reuses images from an older PDF"
else row "MISS" "pymupdf" "reuses images from an older PDF (--images-from only)"
  missing+=("pymupdf|python3 -m pip install --user -U pymupdf"); fi

if have python3 && pymod docx; then row "ok" "python-docx" "writes the Word index and Word recaps"
else row "MISS" "python-docx" "writes the Word index and Word recaps"
  missing+=("python-docx|python3 -m pip install --user -U python-docx"); fi

if have uvx || have uv; then row "ok" "uv" "runs a current yt-dlp for YouTube replays"
else row "--" "uv" "runs a current yt-dlp for YouTube replays (only if a course hosts replays on YouTube)"
  missing+=("uv|brew install uv"); fi

if ls -d "$HOME/Library/CloudStorage/GoogleDrive-"* >/dev/null 2>&1; then row "ok" "Google Drive" "index and recap links open your Drive copies"
else row "--" "Google Drive" "optional: without Drive for Desktop, links open the files in the course folder instead"; fi

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ -x "$CHROME" ] || have google-chrome || have chromium; then row "ok" "Chrome" "your login session, and prints notes PDFs"
elif have python3 && pymod weasyprint; then row "ok" "weasyprint" "prints notes PDFs (no Chrome found)"
else row "MISS" "Chrome" "your login session, and prints notes PDFs"; core_missing=1
  missing+=("Chrome|download from https://www.google.com/chrome and sign in to the course there"); fi

echo
if [ ${#missing[@]} -eq 0 ]; then
  echo "All set."
  exit 0
fi

echo "To install what is missing, run these in Terminal:"
for m in "${missing[@]}"; do
  echo "  ${m%%|*}:  ${m#*|}"
done
[ $core_missing -eq 1 ] && echo && echo "Core tools are missing, so the pull cannot start until they are installed."
exit $core_missing
