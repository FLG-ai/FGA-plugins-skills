# blade-slice (cam)

The picture is cut with a katana on one violent word. One frame of hairline (the pack's light colour) crosses the whole
frame on the word, then two synced copies of the live shot, one each side of a straight cut through the speaker's
mouth, slide apart along it over a gap in the pack's dark ground while the speaker keeps talking in both halves. Just
after the voice stops they slam home with a back ease and a punch, clean before the window ends.

**Needs:** any footage, tripod or handheld. `public/clean.mp4`, `words.json`, `work/tracks/track.json`
(`PY KIT/pipeline/track.py <project>`), and `assets/voice.wav` from cut.py (optional: it finds where the voice really
stops). No matte, no plate, no depth.

**Reuse:** copy the folder to `<project>/fx/<id>/`, add `dict(id="<id>", layer="cam", at=..., end=...)` to edit.FX
(start a beat before the word, end about 0.35 s after it, both on frames), set `WORD` at the top of `gen.py` and run
`PY fx/<id>/gen.py <project>` (`--check` prints the plan and writes nothing). It reads off the project:
- the hairline: the first frame of `WORD` inside the window (words.json)
- the cut: through the mouth on that frame (the track), so the upper lip lands in one half and the lower lip in the
  other. `THROUGH = "eyes"` runs it along the eye line (cleaner, less violent); `PASS = (x, y)` overrides both
- the slam: where the voice stops after the word (voice.wav, else words.json), the impact `AFTER` s later and always
  before the next word; the halves start home one frame before it

The look is in the constants: `ANGLE`, `SLIDE`, `GAP`, `HAIR_W`, `MIN_SLIDE` and the `HOME` / `PUNCH` curves (a
shorter set is used when the window ends early; gen.py says when). The slam punches without shaking, as it shipped;
`SHAKE = True` adds a 7 px jolt on the punch (`JOLT`), the harder version. Rerun it whenever the window, the cut or the
word moves.

**Sound:** `whoosh-soft` and `tick` on the hairline, `impact-low` and `tick` on the impact. gen.py prints the lines.

**Phone take:** nothing changes. The track finds the mouth on any framing; on handheld the slide hides the shake.

**Other frames:** built for 1080x1920. It sizes itself from `CANVAS` (the cut runs past every edge), so a 1:1 or 16:9
cut still slices through the mouth; `SLIDE` and `GAP` are px, so they read smaller on a wider frame.
