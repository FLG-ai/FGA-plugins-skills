# The Quick lane

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

A chain of small steps. One work folder per video (made by `reel-transcribe`). Each step shows a preview and waits for a yes. Every `"$PY"` is the kit venv python (it has the speech library). `<step>` is `QUICK/<name>/`.

## Before step 1
- `RK_HOME/style/design-system.json` exists and is fresh: `bash "$BRIDGE/health.sh" quick`. If not: `python3 "$BRIDGE/pack_to_design_system.py" "RK_HOME/style" [--look NAME]`.
- Pick the caption look for this video. If the style has named looks, ask which one, or show a picker.
- Read `RK_HOME/style/RULES.md` and `references/cut-craft.md`.
- Tell them the chain is 8 steps (9 with the optional windows step) and you will say which one you are on ("Step 3 of 8: framing").

## The chain
| # | Step file | Makes | Notes from this skill |
|---|---|---|---|
| 1 | `reel-transcribe/STEP.md` | `<video> - reel work/` with `words.json` | Put names and brands in the spelling check. Show `sentences.txt` and wait for fixes |
| 2 | `reel-tighten/STEP.md` | `tight.mp4`, `words_tight.json` | Apply `references/cut-craft.md`: compare every take, cut look-downs, keep tails short, never shave words. `tight_preview.mp4` is already a bare cut, so ask them to listen to the joins. Then run `python3 "$GATES/eyecheck.py" tight.mp4 --min=4` and look at every flagged run |
| 3 | `reel-framing/STEP.md` | `framed.mp4` | Pass `--ds design-system.json` so the grade follows the style (`cool`, `calm_reds` or `none`). Say which grade ran |
| 3b | `reel-windows/STEP.md` | `windowed.mp4` | Optional. Only if they have images or clips: floating windows, a small square, or a full-bleed cutaway. Blur other people's names, faces and messages. Captions then drop to a small caption under each window |
| 4 | `reel-captions/STEP.md` | `captioned.mp4` | Every spoken word, in the look chosen for this video |
| 5 | `reel-text-pops/STEP.md` | `popped.mp4` | The hook, list cards, series title and call to action. Giant number pops and scattered word pops are optional extras: only if `extras` lists them or the person asks |
| 6 | `reel-sound/STEP.md` | `final.mp4` | Ask about music first. Click sounds go only where text really types on, not on every word pop |
| 7 | `reel-safe-zone/STEP.md` | A report and a contact sheet | Run on `final.mp4`. Fix in the step that placed the text, then check again |
| 8 | `reel-cover/STEP.md` | `COVER.jpg` | Frame pick, then A or B |
Then `QUICK/reel-studio/references/handover.md`: a `Ready to post` folder with the final video, the cover and `captions.srt`.

## Python note
The step files say `"$PY" "<step>/scripts/..."`. With no kit venv, use `python3`, and `faster-whisper` must be installed for it (`references/setup.md`).

## Names that changed inside this skill
Any step text that says the "Reel Design System folder" means `RK_HOME/style/`. Any step text that offers to save a correction "into the skill" means: add a dated line to `RK_HOME/style/RULES.md` instead.

## First-use downloads
The first transcription downloads the speech model (about 480 MB). The style previews and captions load their fonts from Google Fonts, so the first run needs internet. Ask before each, once.

## When something is off
- A step flags a "big move" or a piece that ends while sound is still going: follow that step's own text, the framing step hides it with a zoom step.
- Captions or text outside the safe zone: change `captions.y` or the case in the settings, never the safe-zone numbers.
- A look they like that the Quick lane cannot draw (its caption styles are `italic_punch`, `serif_mix`, `yellow_key`, `small_top`): say so, show the nearest, and offer the Showcase or Lo-fi lane for the exact one.
- Each step has a "Keep improving" section. When they correct something, offer to remember it, and put the rule in `RK_HOME/style/RULES.md` (step 9 of SKILL.md), not into the skill folder.
