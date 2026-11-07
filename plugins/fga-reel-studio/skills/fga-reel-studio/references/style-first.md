# Steps 1 and 2 in detail: their examples, then their style

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

The look belongs to the person, so it starts with what they like. Everything after this reads the style folder this builds.

The style folder is `RK_HOME/style/` (default `~/reel-kit/style/`). It holds both forms of the style:
- `style.json`, `STYLE.md`, `brand.css`, `fonts/`: the style pack the kit lanes read.
- `design-system.json`, `sounds/`, `stills/`, `refs/`, `Reel Design System.html`: what the Quick lane reads, and the page the person approves.
- `quick-overrides.json`: the picks a pack cannot hold (hook style, list cards, series title, named caption looks).
- `RULES.md`: their own dated rules, added as they correct things.
- `measure/`: output of `refs.py` when you measure their examples (always pass this folder to `refs.py`, because its own default `refs/` is the Quick lane's picture folder).
- `examples/`: looks they said were right, saved by the Quick steps.

## 1. The ask
One message, then wait:
"To build your reel look, paste links to 2 or 3 reels whose style you love. Add anything else you have: a brand guide or website, a screenshot of yourself from a video (so I can show every option on you), and your raw video."
- Fewer than 2 reels and no brand file: ask for one more. More than 3: ask which 3 matter most.
- A style folder already exists: offer to reuse it or add examples.
- No examples and no brand file at all: use the four feel questions and the starting-point tables in `KIT/onboarding/ONBOARDING.md` section 3 and write `style.json` and `STYLE.md` from the table. Then build the Quick-lane file and page: `python3 "$BRIDGE/pack_to_design_system.py" "RK_HOME/style"`, copy `QUICK/reel-design-system/assets/sounds/` to `RK_HOME/style/sounds/`, and run `QUICK/reel-design-system/STEP.md` steps 9 and 10 (render their look, build the page) before "Approve it" below.

## 2. Study the examples
Pick the way that needs the least from them:
1. **A browser tool is available** (Claude in Chrome or Claude's built-in browser): pull frames from the page without downloading anything. `QUICK/reel-design-system/references/pull-reels.md` has the exact steps. Check the reel that opened is the one they linked.
2. **No browser tool, or a link fails**: ask them to save the reel or send a screen recording, or four to six screenshots per reel (first frame, caption style, each insert or title).
3. **To measure pace, caption position, loudness and palette**: run `"$PY" "$KIT/onboarding/refs.py" "RK_HOME/style/measure" <saved file> [<saved file> ...]`. It reads files. Downloading a link with yt-dlp needs a yes first, naming the link, the file and the size. Instagram usually wants a login, so ask for the saved file.
4. Read the summary it writes, then **look at every contact sheet**. Numbers say how fast. Pictures say how it looks.
5. A brand file or website sets colors and fonts. The examples decide pace, captions and motion.

Take the style, never the identity: no logos, handles, names or signature graphics from the creators they point to.

## 3. Read it off
- Mode: produced and sit-down (hi-fi) or phone selfie (lo-fi).
- Captions: box or plain, case, size, where they sit, the kind of letterform.
- Color: the palette and the one color that means "look here".
- Pace: cuts per minute. Under 15 is calm, 15 to 30 normal, over 30 punchy.
- Motion: still, slow pushes, or hard zooms.
- Sound: music under the voice or not, how many effects.
- Grade: straight, warm, cool, muted. If they want one that is not the default, see "Grade" in `references/cut-craft.md`.

## 4. Style cards, options and picks
Follow `QUICK/reel-design-system/STEP.md` from step 5, with two changes: the folder it asks for is `RK_HOME/style/` instead of a new `Reel Design System` folder, and the picks include the grade. Sequence: one style card per reel naming the techniques worth borrowing, the options sheet shown on their own frame, their picks (never pick for them), sounds they keep, the settings file, a render of their look checked against the safe zone, then the page.

## 5. Build the pack
1. `python3 "$BRIDGE/design_system_to_pack.py" "RK_HOME/style/design-system.json" --out "RK_HOME/style"` writes `style.json`, `STYLE.md` and `quick-overrides.json`. Use it once, for the first pack. It refuses to overwrite an existing pack, and you must never pass `--force` to a pack that has been filled in, because that wipes the mode sections of `STYLE.md` and the named looks.
2. Fill the three mode sections of `STYLE.md` (hi-fi, lo-fi, showcase) and the `modes` block of `style.json` from what the references do, using `KIT/kit/STYLE_PACK.md`. This is where the examples matter most: caption rhythm, camera language, transitions, how a big word lands.
3. Kit lanes only: `"$PY" "$KIT/pipeline/style.py" "RK_HOME/style/style.json"` fetches the fonts and writes `brand.css`. Fix every contrast warning it prints before the board.
4. Quick lane only: stop after step 1. The page from step 4 is the approval.

## 6. Approve it
- Quick: the `Reel Design System.html` page. "Does this look like you?"
- Kit lanes: `"$PY" "$KIT/onboarding/board.py" --clip <one of their videos>` then show `RK_HOME/style/board/index.html` (publish it as an artifact if the host has one, otherwise `python3 "$KIT/storyboard/serve.py" "RK_HOME/style/board"`). Apply what they say, rerun, show again.
Start the first video only after a yes.

## Reuse and change
- Next time they only need the raw video.
- "Update my style": change the pack, not the design system. Edit `style.json`, `STYLE.md` and `quick-overrides.json` for what they want different, rerun `style.py` (kit lanes), rebuild `design-system.json` with `pack_to_design_system.py`, and show the board or page again. Projects keep a copy of the pack they were made with, so old videos still render the same.
- After the pack exists it leads. Edit `style.json`, `STYLE.md` or `quick-overrides.json`, then `python3 "$BRIDGE/pack_to_design_system.py" "RK_HOME/style" [--look NAME]`. Never edit `design-system.json` or `brand.css` by hand.
- Different caption look per video: define named looks in `quick-overrides.json` (format: `BRIDGE/templates/quick-overrides.example.json`) and pass `--look`.
