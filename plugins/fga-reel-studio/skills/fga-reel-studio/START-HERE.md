# FGA Reel Studio for Claude Code

Version 0.4.0. The ZIP includes the skill, editing scripts and effects library. This guide is for local sessions on a Mac.

## Install with a message

**Do not use an Upload skill button or a normal web chat for this.** They cannot take this ZIP, because it holds more files than that screen allows. Use the local Claude Code session described below.

Some browsers, Safari especially, unzip the download for you and delete the ZIP. That is fine: the message below covers both.

1. Download `fga-reel-studio-claude-code.zip` to your Downloads folder. Keep the ZIP together. You do not need to open Terminal.
2. In Claude Desktop, open the Code tab and start a local session. Give the session access to your Downloads folder if it asks.
3. Copy and send this message:

> Install FGA Reel Studio for Claude Code from fga-reel-studio-claude-code.zip (or the fga-reel-studio folder, if my browser already unzipped it) in my Downloads folder. Inspect the package, extract it and run its installer. Back up any existing copy. Ask me before installing extra tools or downloading models. Tell me when it's ready.

If your browser renamed the download, tell Claude Code the exact filename. If it cannot see Downloads, select that folder for the local session or provide the downloaded file's full path. Keep any folder it extracts together.

Use the local Code tab or local Codex task for installation. The Customize > Skills upload screen and a standard web chat use a different installation route.

## Start your first reel

Once installation finishes, start a new local session in Claude Code, choose your video folder and send:

> Use the fga-reel-studio skill to help me make my first reel.

You can also invoke `/fga-reel-studio` where slash or skill commands are supported. Have your raw video and two or three example reels ready. Start with Quick. The skill asks you to approve your style and previews, and asks before installing extra tools or downloading models. Initial setup may need several gigabytes and takes longer on a new Mac.

On a new Mac, two setup steps need you: Apple's command line tools (a click) and Homebrew (your Mac password). The skill tells you exactly what to press, and never asks for your password in chat.

Choose the most capable model available in your app. Higher effort uses more of your plan. Quick mode uses Apple tools and requires macOS. Linux and Windows have not been tested for this release.

## What gets installed

The installer copies the skill to `~/.claude/skills/fga-reel-studio/` (the hidden `.claude` folder inside your home folder, where Claude Code looks for skills). Earlier copies are backed up in the adjacent `skill-backups` folder. There is no second ZIP to install. Your style, video projects and Python environment normally live in `~/reel-kit/`.

## If something fails

Copy the exact error into the same local session and ask Claude Code to run the Reel Studio health check. If it cannot find the skill, ask it to confirm `~/.claude/skills/fga-reel-studio/SKILL.md` exists, then start a new local session.

The skill asks before sending footage elsewhere and does not post your reel. Review the exported video and audio before using it.
