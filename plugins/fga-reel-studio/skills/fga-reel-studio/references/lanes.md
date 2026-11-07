# Choosing a lane, and who does what in each

Both lanes read the same style folder, follow the same cut protocol and run the same checks. The difference is how the picture, type and sound get built.

## Which lane
| | Quick | Lo-fi | Hi-fi | Showcase |
|---|---|---|---|---|
| Best for | A simple text overlay: one raw take, captioned, with the big text moments, sound effects and, if they have them, their images in windows | The phone selfie look with more finish: storyboard first, text behind the head, images behind or on top | A sit-down, produced video with data | A show-off edit where each beat gets its own motion graphic |
| Install | Light: ffmpeg, Chrome, python, a speech model | The kit: Node, a render browser, a bigger speech model | The kit | The kit |
| Time | About 30 minutes | Longer | Longer | Longest |
| Review before render | A preview after every step | A storyboard with notes | A storyboard with notes | A storyboard with notes |
| Their screens and clips | Optional floating windows, a small square or a full-bleed cutaway | Land on top of them or behind the head | Full-screen cards | Inside effects |
| Text behind the head | No | Yes | Yes | Yes |
| Output | `final.mp4`, `COVER.jpg`, `captions.srt` | Video and a phone copy | Same | Same |

Show the plain-words menu from SKILL.md step 2 and suggest one. Never decide a kit mode from the footage alone.

## Who does what
| Stage | Quick lane | Kit lanes | Shared |
|---|---|---|---|
| Their examples and style | | | `references/style-first.md` builds one style folder both read |
| Transcript | `reel-transcribe` (small speech model, spelling fixes) | `pipeline/words.py` (medium model, `PROMPT` for names, `FIXES` for mishearings) | |
| Cut | `reel-tighten` | `pipeline/cut.py` with `KEEP` ranges, J-cuts, frame-exact encode | The cut protocol in `references/cut-craft.md` |
| Framing and grade | `reel-framing` | `FRAMES`, `SHOTS`, `CAMERA` in `edit.py` | Grade from the style pack |
| Captions | `reel-captions` | `CAPS` (hi-fi) or automatic karaoke (lo-fi) | Every spoken word captioned |
| Type moments | `reel-text-pops` | Cards, `OVERLAYS`, `BOXES`, or effects from `KIT/fx/LIBRARY.md` | |
| Sound | `reel-sound` | `SOUND` and `pipeline/mix.py` | About -14 LUFS, peaks under -1 dBFS |
| Review | Preview after each step | `pipeline/storyboard.py`, then "go" | |
| Safe zone | `reel-safe-zone` | `reel-safe-zone` on the final render | Same limits for both |
| Look-downs, joins, caption timing | `eyecheck.py` on `tight.mp4` | `eyecheck.py`, `joinaudit.py`, `fixjoins.py`, `capcheck.py`, `align.py` | `references/gates.md` |
| Cover | `reel-cover` | `reel-cover` on the final render (see below) | |
| Render | ffmpeg inside each step | `RUN/render_retry.sh` through `RUN/heavy.sh` | One heavy job at a time |

## A cover for a kit-lane video
`reel-cover` works from a folder with `proxy.mp4`. For a kit-lane video, make a small folder, put the final render in it as `proxy.mp4`, and pass the hook words with `--lines` (there is no `pops_plan.json`). Then follow `QUICK/reel-cover/STEP.md` from step 3.
