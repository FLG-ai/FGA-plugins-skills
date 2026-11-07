---
name: fga-reel-studio
description: Turns a raw talking-to-camera video into a finished vertical reel (Instagram Reels, TikTok, YouTube Shorts) in the person's own style, and starts by asking for 2 or 3 reels they love so the style is theirs. Sets up a brand-new computer step by step, asking before every install. Two lanes share one style folder, one cut protocol and one set of checks. Quick is a chain of small steps (transcribe, tighten, frame, caption, text moments, sound, safe-zone check, cover). Showcase, Hi-fi and Lo-fi build a storyboard first, then hand-built motion graphics, sound design and QA, on Justyn Berk's reel-kit. Runs on the person's own computer. Use on - edit my reel, make a reel from this video, cut my talking-head video, set up my reel style, set me up from scratch, here are reels I love, caption my reel, storyboard my video, showcase edit, check my safe zone, make my reel cover, fix the cuts in my edit. Not for writing the script or caption, or for deciding what to post.
---

# FGA Reel Studio

For local Claude Code sessions, including the Code tab in Claude Desktop. Quick mode needs macOS.

Raw take in, finished reel out, in the person's own style. Each step shows a preview and waits for a yes. A person who has never used a terminal can start from nothing: `START-HERE.md` is written for them.

## Names used below
These are names, not shell variables, and shell state does not carry from one command to the next. Write the full path in every command.
- `STUDIO` = the folder holding this file. `KIT` = `STUDIO/engine/kit`. `QUICK` = `STUDIO/engine/quick`. `GATES` = `STUDIO/engine/gates`. `RUN` = `STUDIO/engine/run`. `BRIDGE` = `STUDIO/bridge`.
- `RK_HOME` = `$REEL_KIT_HOME`, default `~/reel-kit`. It holds the venv, downloaded tools, models, projects, and the person's **style folder `RK_HOME/style/`**. (`KIT/KIT.md` calls this folder `HOME`.) Nothing they make is ever written into the skill folder.
- `PY` = `RK_HOME/.venv/bin/python`. Both lanes use the Python 3.12+ environment at this path. If it is missing, finish step 3 before running editing scripts. Every `"$PY"` in a Quick step file means this.
- `<step>` in a Quick step file is its own folder, `QUICK/<name>/`.

## The first message
Your first message does two things, then waits. It never asks for anything else first.
1. The reminder, in plain words:
> Use the most capable model available in your Claude Code session. Higher effort can help with complex edits and uses more of your plan.
Do not require a particular model version, claim a measured quality advantage, or guess the current model or effort setting. Continue to the examples ask.
2. The examples ask (step 1 below).

## Step 1. Their examples come first
"To build your reel look, paste links to 2 or 3 reels whose style you love. Add anything else you have: a brand guide or website, a screenshot of yourself from a video, and your raw video."
- A style folder already exists (`RK_HOME/style/style.json` or `design-system.json`): "I found your style, <name>. Use it, or add new examples?" On "use it", go to step 2.
- They have no examples and no brand file: ask the four feel questions in `KIT/onboarding/ONBOARDING.md` section 3, in one message.
- Take the style, never the identity: no logos, handles, names or signature graphics from the creators they point to.

## Step 2. Show the options and let them pick
Never assume they know the words lo-fi, hi-fi or showcase. Show this menu in plain words (a short list, not a wall of text), say which one you suggest and why, and ask them to choose one. Say that **Quick is the best first video**, and that they can try a bigger one later with the same style.

> Here are the four kinds of edit. Which one do you want?
> 1. **Quick: simple text overlay** (about 30 minutes, lightest setup). One take of you talking. It cuts the dead air and stumbles, adds word-by-word captions, a hook, text cards on screen, sound effects and a cover. If you have screenshots, screen recordings or clips, it can also show them in floating windows while you talk. You don't need anything but the video.
> 2. **Lo-fi** (a few hours). The phone selfie look with more finish: a storyboard you comment on first, native-style text boxes, your images on top of you or swapped in behind your head, and type behind your head.
> 3. **Hi-fi** (a few hours). A produced, sit-down look. Full-screen charts and number cards, and words behind your head. It needs a good camera setup and numbers to show.
> 4. **Showcase: the most graphics** (the longest, half a day the first time). A different hand-built motion graphic on every line, such as kinetic type, a word stamped behind your head, a typing prompt bar, an editing timeline, or a grid of you. A new transition on every cut and dense sound. The show-off edit.
> Lo-fi, hi-fi and showcase show you a storyboard to comment on before anything renders. Quick shows a preview after every step.

**Always make a recommendation**, in one or two sentences, and give the reason from their own material. Look at the example reels they pasted and at what they have, then use this:
- Their examples are mostly a person talking with captions and text on screen, or they only have a talking video, or they are unsure: **Quick**. If it is their first video, Quick too, whatever their examples look like, because it is the fastest way to see their style working.
- Their examples show screenshots, screen recordings or photos in windows over the speaker: **Quick**, with the windows step. If they also want a storyboard first, type behind their head or images swapped in behind it: **lo-fi**.
- Their examples show full-screen charts, numbers or a polished studio look, and they have the numbers: **hi-fi**.
- Their examples are packed with moving graphics and sound effects and they want that: **showcase**, and say it takes much longer.
Say it like this: "From your examples I'd start with Quick, because they are mostly you talking with captions and text. Want that, or one of the others?" Then let them overrule you. Never choose a kit mode from the footage alone. The comparison table and the step map: `references/lanes.md`.

## Step 3. Check the computer for that lane (works from a brand-new Mac)
0. First, `bash "BRIDGE/unpack.sh"`. This checks the bundled library files and changes nothing. All effects, cards and sounds are already included as ordinary files. If it says MISS, ask the person to download and install the complete package again.
1. `bash "BRIDGE/health.sh" quick` (or `full`). It only reads. If it shows BUSY, another heavy job is running, so do not start a second one.
2. If anything is missing: `bash "BRIDGE/install.sh" plan <lane>`. It lists each missing item in install order with its size, the exact command and who runs it. Show it in plain words.
3. **Never install or download anything without a yes.** Ask item by item: what it is, where it comes from, how big, that it happens once. After a yes run exactly that item: `bash "BRIDGE/install.sh" run <item>`. Then run `plan` again.
4. Two items are the person's own to do, because they need a click or their Mac password: Apple's command line tools and Homebrew. `install.sh run` prints what to do. Wait for them to say it finished. Never type a password for them.
5. When `plan` says "Nothing to install" and `health.sh` says HEALTHY, go on. Full list with sizes: `references/setup.md`.
Some downloads happen on first use, such as the speech model. Say so and ask before the step that triggers them (`references/setup.md`, "First use").

## Step 4. Build their style (once, then reuse)
The full flow is `references/style-first.md`. In short:
1. Study the examples and write a style card per reel naming the techniques worth borrowing.
2. Let them pick caption, title, number and word-pop styles, colors, fonts and sounds. That makes `RK_HOME/style/design-system.json` and a visual page.
3. Both lanes: `python3 "BRIDGE/design_system_to_pack.py" "RK_HOME/style/design-system.json" --out "RK_HOME/style"`, so the pack exists whichever lane they use. Kit lanes then fill the mode sections of `STYLE.md` from what the references do, ask before `"$PY" "KIT/pipeline/style.py" "RK_HOME/style/style.json"` (it downloads their fonts from Google Fonts, a few MB), and run `"$PY" "KIT/onboarding/board.py" --clip <one of their videos>`.
4. Ask "Does this look like you?" until they say yes. Serve the board on their own computer. Publishing it anywhere uploads frames of their footage, so only after a yes that says so.
5. Giant number pops and scattered word pops are optional extras. Mention they exist, never include them unless the person wants them (`extras` in `design-system.json`).
6. From here on the pack leads. Edit `style.json`, `STYLE.md` or `quick-overrides.json`, then `python3 "BRIDGE/pack_to_design_system.py" "RK_HOME/style" [--look NAME]`. Never edit `design-system.json` or `brand.css` by hand, and never run `design_system_to_pack.py --force` on a filled pack.

## Step 5. Cut protocol (both lanes)
Read `RK_HOME/style/RULES.md` if it exists, then `references/rules-and-precedence.md`, then `references/cut-craft.md`. The short version:
1. Transcribe the whole take and read it.
2. Compare every take of every line, openers first: pace, eyes on the lens, energy, expression. Look at a frame of each candidate. Tell them which take each line came from.
3. Cut dead air, repeats, false starts, fillers, obvious look-downs at a script or phone, and leans or reaches. Keep real smiles, laughs and reactions.
4. Every cut lands in the quiet between words, never inside one. Connectors said at the start of a line stay whole.
5. A drawn-out word is sped up about 1.3x, not chopped.
6. Send a bare cut (no effects, small file) first so they can hear the joins. Build effects only after their yes.

## Step 6. Run the lane
- **Quick**: `references/quick-lane.md`. Order: transcribe, tighten, framing, captions, text-pops, sound, safe-zone, cover. A preview and a yes after each. Hand over with `QUICK/reel-studio/references/handover.md`.
- **Lo-fi, Hi-fi, Showcase**: read `KIT/KIT.md` in full, then `references/full-lane.md`, which lists where this skill overrides it. Storyboard first, then STOP until they say go.

## Step 7. Checks before sending anything
`references/gates.md` lists the gates per lane. Say which you ran and what each found. Not ready until all pass.
- **Both lanes**: safe zone on the final video, every spoken word on screen as text, loudness near -14 LUFS with peaks under -1 dBFS.
- **Quick**: the captions report, `eyecheck.py` on `tight.mp4`, the sound report, and the bare cut listened to.
- **Kit lanes**: `fixjoins`, `joinaudit`, `eyecheck`, `capcheck`, `align`, and the render's QA (lip sync within 2 frames, no flash at a cut).

## Step 8. Deliver
- Send the video itself, never only stills, plus a phone-size copy.
- Say exactly what you still need from them (screen recordings, screenshots, a photo), each tied to its moment, or "nothing needed".
- Name the files and where they are. Remind them to add music in their posting app if they want it, and how to set the cover.
- Never post, send or publish anything for them.

## Step 9. Remember what they correct
After a correction, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (start it from `BRIDGE/templates/RULES.template.md`). When they say a look is right, save it as a named look in `RK_HOME/style/quick-overrides.json` and describe it in `STYLE.md`. Newest dated rule wins. Never write to the skill folder.

## Stop points
- The first message: wait for their examples.
- Step 2: wait for the lane. Step 3: wait for a yes on every install or download.
- Step 4: wait for every pick and for "yes, that looks like me".
- Every Quick step: wait for a yes on the preview.
- Kit lanes: STOP after the storyboard until they say go.
- Anything that uploads their footage, spends money on a generator, or starts a heavy render: wait for a yes that says what it does.

## Always true
Their footage never leaves their computer without a yes that names what leaves. Nothing is overwritten. One heavy job at a time on a laptop. If a rule of theirs would break a hard limit (for example text under Instagram's buttons), say so and fix it. The full list is `references/rules-and-precedence.md`.
