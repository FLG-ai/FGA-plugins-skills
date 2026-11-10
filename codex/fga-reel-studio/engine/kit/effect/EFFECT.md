# New effect: from someone else's video to the creator's library

The creator saw an effect they love in someone else's video. They give you the video (a link or a file) and when it
plays. You rebuild it as theirs: the same idea, their fonts and colours, tested on their own footage. They see the
two side by side on one page and pick Keep, Fix or Drop. A keep lands in their library (`HOME/fx/`), where showcase
can pick it and they can call it by name.

What they do: ask, review, use. Everything else in this file is yours to do quietly. Never show them frame sheets,
measurements, the testbed or the sandbox, and never ask them a question this file answers.

`EF` = `PY KIT/pipeline/effect.py` (with the `PATH=` prefix when `BIN` exists, like every command in SKILL.md).
One effect per run. A video with two effects in it is two runs: do the one they named first, offer the second after.

## 1. Take the request
- They need a video (link or file) and the moment: seconds (`17-19`, `0:17 to 0:19`, `at 17`) or words ("the text
  right after the hook", "the cutout bit"). Missing one: ask for it in one line, nothing else.
- Pick a short working name for the folder (`HOME/effects/<name>/`), like `ref-2610-text`. The library name comes
  later, once you know what the effect is.
- `EF fetch <name> <link or file>`. A link that won't download: say in one line that the site wouldn't hand it over,
  and ask for the file (any downloader for that site works). Don't retry other ways.
- Only words for the moment: look at the whole video at 2 fps (`EF look <name> 0 <length> --fps 2`), find it, and
  name the seconds you'll use in your next message, so they can correct you.
- Say how long this takes, once: "About 15 to 20 minutes, mostly the test render. I'll send one page to review."

## 2. Study it (before building anything)
- `EF look <name> <start> <end>` with half a second either side: every frame, labelled. Read every sheet at full size.
- `EF measure <name> <start> <end>` when type is involved: the text box per frame shows size and weight changes
  (a box that grows on one word is a size or weight step), the bands show hard cuts and layout switches.
- Write `HOME/effects/<name>/BREAKDOWN.md`: what happens frame by frame, the timings (cuts on words? holds?), the
  sizes as fractions of the frame, what's footage and what's graphics, and what makes it work (the one idea).
- **The honest verdict, before you build.** Can this kit build it on their footage? Graphics, type, cards, masks,
  copies of the footage, the cutout, grades and camera moves: yes. Things it can't do: 3D scenes, AI-generated or
  stock footage they'd have to supply, effects that need a second camera angle, tracking a moving object (not
  their head). If it can't, say so in one or two plain lines, offer the closest thing it can build, and wait for a
  yes before building. If it can, don't announce it; build.

## 3. Build it on their footage
- `EF testbed <name>`: their newest edited video, nothing on it, in their current style. No edited video yet
  (`NO_FOOTAGE`): ask for any short clip of them talking, run SKILL.md steps 1 and 2 on it (scaffold, cut, words,
  cutout), then `EF testbed <name> <that project>`.
- Pick a line from their `words.json` with the same shape as the reference's (a setup and a turn, a list, one big
  word) and about the same length. Their words, never invented ones.
- Build it exactly to `KIT/kit/FX_BRIEF.md`, starting from the closest library effect if one is close. Folder:
  `<testbed>/fx/<id>/` (a short id like `nx`). Set its entry at the end of `<testbed>/edit.py`:
  `FX = [dict(id="nx", layer=..., at=..., end=..., frames=[...])]`, plus `KARAOKE["hide"]` when it carries the
  words and `CUT_WINDOWS` when anything sits behind them.
- Copy the mechanism, not the surface. Keep from the reference: the structure, the timing logic, the proportions,
  what moves on which word. Make theirs: every colour and font is a token (their pack), their footage, their words.
  The kit's rules still hold (no gradients, glows or outlines on type; safe zones; real artifacts over invented).
- `EF try <name> <id> --at t1 t2 t3`: read every still at full size, including the first and last frame of the
  window. Fix until it holds up, then `EF compare <name> <ref start> <ref end> <test start> <test end>`
  (it renders the whole testbed once, a few minutes). Watch `HOME/effects/<name>/compare.mp4` frame by frame where
  it matters (`ffmpeg -ss <t> -i compare.mp4 -frames:v 1 x.jpg`): timing on the words, sizes, nothing popping.
  Something off: fix, `try`, `compare` again. They only see a version you'd keep.

## 4. Review (one page)
- Name it now: a plain two or three word name that says what it does (`sized-words`, `presenter-card`,
  `photo-card-words`), lowercase with dashes, and not already a folder in `KIT/fx/` or `HOME/fx/`.
- Write `HOME/effects/<name>/review.json`:
  `{"name": "Sized words", "folder": "sized-words", "layer": "top", "source": "<file name or link>",
  "window": "10 to 12s", "line": "<their line it plays on>", "does": "<one or two sentences>",
  "copied": ["<what came from the reference>", ...], "changed": ["<what was made theirs>", ...],
  "reach": "<the kind of line it's for>", "supply": "<what they hand over to use it, or Nothing>",
  "flag": "<a limit worth knowing, or empty>", "recommend": "Keep." }`
  Plain words throughout, written to them ("your footage", "your accent colour"), no jargon.
- `EF review <name>` -> `HOME/effects/<name>/review/`. Show it:
  - **Claude artifacts**: copy `review/` to a scratch folder and publish its `index.html` with every file in
    `files.json` and `capabilities` = `{"db": {}}`. A fix round republishes the same file path (same link).
    Verdicts land in the artifact's database: read `verdicts/<folder>` (`{verdict, note}`) and `review/state`
    (`{done}`) with the artifact data tool.
  - **Anywhere else**: run `PY KIT/storyboard/serve.py HOME/effects/<name>/review` in the background and send
    `http://127.0.0.1:8765`. Verdicts land in `review/notes.json` as `{beat: <folder>, text: "keep: <note>"}`.
- In the same message: one line on what it is, the link, "pick Keep, Fix or Drop, press Send, then tell me here".
  Then stop.

## 5. Their verdict
- **Keep**: `EF keep <name>`. It copies the effect to `HOME/fx/<folder>/` with its preview and breakdown, adds its
  row to `HOME/fx/LIBRARY.md`, logs it and rebuilds their effects page. Tell them in two lines: it's in, and how to
  use it (`/reel-kit:showcase take.mov, <folder> on "<a line>"`, or a storyboard note "make this one <folder>").
  Open the effects page (`EF library --open`).
- **Fix**: apply their note, `try`, `compare`, `review` again with the same review.json (update what changed),
  republish to the same link. Same page, new version.
- **Drop**: say it's dropped in one line. Add a row to `HOME/effects/LOG.md` with verdict `drop` and their note, so
  the same effect isn't offered again.

## Their effects page
`EF library --open` writes and opens `HOME/effects/index.html`: their own effects first, then the kit's 40, each with
its preview, its name (tap to copy) and when to reach for it, in their fonts and colours. `/reel-kit:effect-list`,
"show me my effects" or "what effects are there?" all open it. Rebuild it after anything changes
`HOME/fx/`.
