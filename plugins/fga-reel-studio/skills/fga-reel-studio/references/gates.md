# The gates: checks to run before sending anything

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

Say which gates you ran and what each found. A video is not ready to send until every gate that applies has passed.

**Which lane runs what.** Both lanes: safe zone, every word captioned, loudness. Quick lane: the step reports, `eyecheck.py` on `tight.mp4`, and the bare cut listened to (`tight_preview.mp4`). Kit lanes (Lo-fi, Hi-fi, Showcase): everything in the table, because the word-level tools read a kit project's `timeline.json`, `edit.py` and `assets/voice.wav`, which the Quick lane does not make. Tools live in `GATES` (`STUDIO/engine/gates/`) unless noted. `PROJECT` is a kit project folder (`RK_HOME/projects/<slug>/`). Run the word-level tools with `"$PY"`, because they need the kit venv.

| Gate | Catches | Command | Passes when |
|---|---|---|---|
| Windows | A window on the face, a private name or message readable, a window past y 1360 | `windows_report.txt` from `reel-windows`, plus a frame from the middle of each window | Nothing private readable, face clear, bottom edge at or above y 1360 |
| Safe zone | Text hidden by Instagram's header, caption, buttons, or cut off at the sides | `"$PY" "$QUICK/reel-safe-zone/scripts/safe_zone.py" <final video>` (needs the Swift compiler, builds its text reader on first run) | "All clear". Text that is part of their footage (screen recordings, signs) is a false alarm, say so out loud |
| Look-downs | Eyes dropping to a script or phone, eyes shut | `<python with OpenCV> "$GATES/eyecheck.py" <video> --min=4 [--cuts=PROJECT/timeline.json] [--sheet=<out.jpg>]`. Use the kit's `$PY` if it has OpenCV, else `python3` (`health.sh` says which). Run it on `tight.mp4` (Quick) or `PROJECT/public/clean.mp4` (kit lanes) | Every flagged run is a blink, a glance that nobody would notice, or already covered by a graphic. Look at the sheet, then at the render |
| Eye sheet | Look-downs and lean-outs at every picture cut | `python3 "$GATES/eyesheet.py" PROJECT <out.jpg>` | Nothing at a cut shows eyes down or a lean out |
| Join audit | A cut inside a word, half words, repeats | `"$PY" "$GATES/joinaudit.py" PROJECT` | Every join's energy is in the quiet and the read at each join shows whole words |
| Fix joins | Moves cuts into the quiet beside their words | `"$PY" "$GATES/fixjoins.py" PROJECT` then `"$PY" "$GATES/recut.py" PROJECT --keep`, run the kit's `cut.py`, then `recut.py PROJECT --remap` | The table shows no cut inside speech. Override by hand with `work/keep_manual.json` |
| Join sheet | Look-downs, pauses over 0.35 s, half words at each piece | `"$PY" "$GATES/joincheck.py" PROJECT` | The sheet and pause list are clean |
| Caption timing | A caption that lands before or after its word | `"$PY" "$GATES/capcheck.py" PROJECT [--tol=0.15] [--fix]` | No caption is off by more than the tolerance |
| Align captions | Whole-take drift between words.json and the cut voice | `"$PY" "$GATES/align.py" PROJECT --write`, then `pinwords.py` if `work/pins.json` exists | Captions start on the frame the word starts |
| Lip sync, loudness, cuts | Mouth out of time, flashes at a cut, wrong level | `"$PY" "$KIT/pipeline/qa.py" PROJECT renders/<file>.mp4 --phone` (the render script runs it) | Lip sync within 2 frames, no flash or doubled head at any cut, about -14 LUFS, peaks under -1 dBFS |
| Quick lane sound | Level | `sound_report.txt` from `reel-sound` | Within 1 of -14 LUFS, peak under -1 dBFS |
| Every word on screen | A spoken word with no caption and no effect or title showing it, text clipped by its cell | The captions step's report, plus a frame from the longest word, a key word, a plain word and one from the last 10 seconds | Every spoken word is on screen |
| Style contrast | Colors that read badly together | `"$PY" "$KIT/pipeline/style.py" RK_HOME/style/style.json` prints warnings | No warning. Fix by using the lighter or darker shade of the same hue only where it fails |
| Health | Missing tools, a job already running | `bash "$BRIDGE/health.sh" all` | HEALTHY, and nothing BUSY |

## Small helpers
- `"$PY" "$GATES/env.py" <clip> <from-to>`: 5 ms energy in dB, to see whether a point sits in room tone or in a word.
- `"$PY" "$GATES/look.py" <clip> <from-to>`: the words wav2vec2 hears with times, and an energy strip, to find where a word really starts.
- `"$PY" "$GATES/fw.py" <clip> <from-to>`: a second transcript with confidence per word.
- `"$PY" "$GATES/retime.py" PROJECT [--write]`: re-times captions from a second speech model. Use `align.py` first, this is the fallback.

## Always look as well as measure
The tools find candidates. Open the sheet or the render frames and judge. Always send the person the video itself to review, never only stills.
