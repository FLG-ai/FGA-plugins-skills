# Sharing this skill with other people

This folder is already free of personal files: no style pack, no footage, no handles, no personal paths. Before sharing it, run this checklist.

## Licences
- `engine/kit/` is reel-kit by Justyn Berk, MIT. **The copyright line and the MIT text must travel with it**: `LICENSE-reel-kit.txt` at the top of this folder and `engine/kit/LICENSE`. Keep `CREDITS.md`.
- Its sound effects are CC0, free to use anywhere.
- Not bundled, and never to be bundled: GSAP (downloaded by setup under GreenSock's own licence), HyperFrames (fetched by `npx`, Apache-2.0), the RVM matte model (GPL-3.0, an optional download for personal use), and any model weights. Fonts come from Google Fonts under their open licences.
- The Quick lane's starter sounds in `engine/quick/reel-design-system/assets/sounds/` were made for it. Do not add sounds from Pixabay or any other third party into the package. Point people to them instead.

## Checklist
1. `grep -rniE "<your name>|<your handle>|<your site>|/Users/" "$STUDIO" --exclude-dir=kit` finds nothing you did not mean to leave. The kit folder carries its author's name by design.
2. No images of people in the package. Search for image files and look at each: `find "$STUDIO" -iname "*.jpg" -o -iname "*.png" -o -iname "*.mp4" -o -iname "*.mov" | grep -v "engine/kit"`.
3. No style pack, `RULES.md`, `quick-overrides.json` or `design-system.json` from a real person inside `STUDIO`. The examples in `BRIDGE/templates/` are neutral.
4. `bash "$BRIDGE/health.sh" all` runs without errors on a clean machine, and `python3 -m py_compile` passes on every script.
5. Test the first run as a stranger would: no style folder, paste two reel links, get to a finished video.
6. Package the folder as one zip with `SKILL.md` at the top of a single folder named after the skill.

## Keeping up with the kit
`engine/kit/patches/upstream-commit.txt` is the upstream commit this snapshot started from. `engine/kit/patches/local-patches.diff` is every local change to it. To update: fetch the new upstream, copy it over `engine/kit/` (keeping `KIT.md`, which is the upstream `SKILL.md` renamed so this folder has only one skill file), then reapply the patch and check each hunk.

## Keeping up with the Quick lane
`engine/quick/` is a copy of the standalone plugin with two edits: each `SKILL.md` is a `STEP.md`, and `reel-framing` gained a `--grade` option with a `grade` key in the settings file. If the standalone plugin is also published, copy those changes back into it before it is next released.
