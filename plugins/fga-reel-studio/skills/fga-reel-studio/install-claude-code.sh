#!/bin/bash
# Copy this package into Claude Code's personal skills folder.
# No downloads, dependency installs or changes to Claude settings.
set -eu
SOURCE="$(cd "$(dirname "$0")" && pwd -P)"
SKILLS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
if [ "$#" -gt 0 ]; then
  [ "$#" -eq 2 ] && [ "$1" = "--skills-dir" ] || { echo "Usage: bash install-claude-code.sh [--skills-dir /absolute/path]"; exit 2; }
  SKILLS="$2"
fi
case "$SKILLS" in /*) ;; *) echo "Skills directory must be an absolute path."; exit 2;; esac
[ -f "$SOURCE/SKILL.md" ] || { echo "SKILL.md is missing. Download and unzip the complete package."; exit 1; }
bash "$SOURCE/bridge/unpack.sh"
mkdir -p "$SKILLS"
SKILLS="$(cd "$SKILLS" && pwd -P)"
DEST="$SKILLS/fga-reel-studio"
[ ! -L "$DEST" ] || { echo "The existing skill is a symbolic link. Leave it in place and ask Claude Code to review it before updating."; exit 1; }
if [ "$SOURCE" = "$DEST" ]; then
  echo "Reel Studio is already in Claude Code's skills folder."
  exit 0
fi
STAGE="$(mktemp -d "$SKILLS/.fga-reel-stage.XXXXXX")"
BACKUP=""
cleanup() {
  rc=$?
  if [ "$rc" -ne 0 ] && [ -n "$BACKUP" ] && [ ! -e "$DEST" ]; then
    mv "$BACKUP/fga-reel-studio" "$DEST" || true
  fi
  rm -rf "$STAGE"
}
trap cleanup EXIT
cp -R "$SOURCE" "$STAGE/fga-reel-studio"
bash "$STAGE/fga-reel-studio/bridge/unpack.sh"
if [ -e "$DEST" ]; then
  BACKUP_ROOT="$(dirname "$SKILLS")/skill-backups"
  mkdir -p "$BACKUP_ROOT"
  BACKUP="$(mktemp -d "$BACKUP_ROOT/reel-studio.XXXXXX")"
  mv "$DEST" "$BACKUP/fga-reel-studio"
fi
mv "$STAGE/fga-reel-studio" "$DEST"
printf '\nInstalled: %s\n' "$DEST"
[ -z "$BACKUP" ] || printf 'Previous copy: %s/fga-reel-studio\n' "$BACKUP"
printf '
Start a new local Claude Code session and send: Use the fga-reel-studio skill to help me make my first reel.
'
printf 'Video tools and models are set up separately, with your approval.\n'
