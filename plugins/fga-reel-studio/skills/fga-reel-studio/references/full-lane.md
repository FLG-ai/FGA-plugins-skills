# The Showcase, Hi-fi and Lo-fi lanes

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

These run on the reel-kit method (Justyn Berk, MIT). **Read `KIT/KIT.md` in full first.** It is the method: intake, cut, beats, cards or effects, sound, storyboard, notes, render. This page lists where this skill changes or adds to it. Where they differ, this page wins on mechanics and the person's style wins on taste. The hard limits in `references/rules-and-precedence.md` win over both.

`KIT/KIT.md` says "the folder holding this file" for `KIT`. In this skill that is `STUDIO/engine/kit`. It also says `RK_HOME` and `PY`: same as in SKILL.md.

## Before step 1
- `bash "$BRIDGE/health.sh" full`, then `install.sh plan full` for anything missing. **Never run `setup.py` without a yes**: the kit's own text says "run setup until READY", and that installs. `python3 "$KIT/setup/setup.py" --check` only reports. Install with `install.sh run <item>`, one yes at a time (`references/setup.md`).
- The kit needs **Python 3.12 or newer**. An older venv says READY and then crashes at the storyboard. `health.sh` checks it.
- The style pack is built (SKILL.md step 4). Read `RK_HOME/style/STYLE.md` and its section for this mode, and `RK_HOME/style/RULES.md`, before writing `edit.py`. A creator's explicit value in the pack beats the mode file.
- Machine: read `references/machine.md`. On a laptop, one video's builders at a time.
- End every edit brief, and every FX or card agent prompt, with this closing line. It is a prompt habit Justyn Berk teaches in his video, not something in the repo: "Show off that you are the world's best motion graphic artist, like it's your show reel on the resume."

## Changes to the kit's steps
| Kit step | Change |
|---|---|
| 0 First run | `KIT.md` says to run `setup.py` until it prints READY. Do not: use `health.sh` and `install.sh` and ask first |
| 1 Intake | Make the working clip with the grade from the pack applied to the footage (`references/cut-craft.md`, Grade), not a late CSS filter. If you grade the footage with ffmpeg, set `style.json` `grade` to `"none"` so the picture is not graded twice (the build also applies the pack's CSS grade) |
| 2 Cut | Replace "keep the LAST clean take of each line" with the cut protocol: compare every take, cut look-downs, short tails, joins in the quiet. **Order**: set `KEEP`, run the kit's `cut.py`, then `"$PY" "$GATES/fixjoins.py" <project>` (it reads the project's `timeline.json`, which only `cut.py` writes), then `recut.py --keep`, `cut.py` again, `recut.py --remap`, then `joinaudit.py`. Require every piece to read its own audio in the `cut.py --plan` table |
| 3 Beats | Real artifacts first. At most one generated image per video, and only when it carries a real idea. Every spoken word is still on screen as text: where an effect or title shows the exact spoken words, that counts and the hi-fi mode file's "no captions there" applies. A word that appears nowhere gets a caption |
| 3 Beats | Number and counter effects (odometer, giant captions, drum hits) are optional extras: mention them once, include them only if the person wants them or their style lists them |
| 3b Generators | `KIT.md` says to generate "no need to ask". Ask first, say which model and what it costs, and wait for a yes |
| 4 Cards or effects | The kit's margins are lighter than Instagram's real ones. Use the hard-limit numbers: nothing above y 250, below y 1480, within 60 px of the sides, past x 940 below y 1050. `KIT.md` launches 4 to 8 agents at once: on a laptop, one video's builders at a time, five or six at most |
| 5 Sound | Click sounds only where text really types on. No music unless they hand one over |
| 6 Storyboard | `KIT.md` publishes it as an artifact. That uploads frames of their footage. Serve it locally (`python3 "$KIT/storyboard/serve.py" <project>`) unless they say yes to publishing, naming what goes up. Show it, list "what I need from you", STOP until "go" |
| 8 Render | Never the single-pass render on a laptop. Use `"$RUN/heavy.sh" "$RUN/render_retry.sh" <project> <name> "<title>"` (segmented, retries, mux, QA, copy). Set `REEL_OUT` to where the copy should go |
| 8 Render | Before rendering: `eyecheck.py` over `public/clean.mp4`, `capcheck.py`, and `align.py --write` so captions land on the cut voice |

## Per-video housekeeping that stops stalls
- Re-encode every effect video with dense keyframes before rendering (`-g 10`, or `-g 1`). A clip with one keyframe stalls the renderer.
- Never stack several live full-size copies of the clean video inside one effect. Give copies a short all-intra clip of just their window at the size they show on screen.
- Copy `camera-transitions` from `KIT/fx/` into each project's `fx/`. Without it the build draws a "pending" box.
- Declare system fonts you use. The renderer silently swaps an undeclared system font for its own. Add an `@font-face` with `local()` to the project's `style/brand.css`, or use `GATES/fonts_extra.py` for Google fonts beyond the pack's four roles.
- Builders (FX and card agents) write their sound lines and edit changes to files (`work/sfx/<group>.txt`, `work/edit_<group>.json`) so a render can start without the main session. `GATES/merge_sound.py` and `GATES/apply_changes.py` merge them. `RUN/autopilot_reel.sh` does the whole merge, align, mix and render hands-free.

## Judge pass (optional, for a Showcase video)
`RUN/judge_prompt.md` is a prompt for a fresh agent to judge the finished render against the kit's showcase rules and the person's own rules. Fill in its placeholders. Route each "must" and "should" fix back to the builder that owns that beat, then render the next version.

## Versions on request
Edits are code, so a change is a targeted edit and a re-render, not a rebuild. Extra versions (a different shape, a different caption look) are plain-words requests.
