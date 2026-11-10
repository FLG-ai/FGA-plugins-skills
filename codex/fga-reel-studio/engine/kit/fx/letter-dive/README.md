# letter-dive (over)

Saul Bass. A flat plate in the pack's light (or dark) ground slams over the frame with one word cut out of it in the
pack's display face, the live shot playing through the letters. The word builds letter by letter, then the camera dives
into one letter's stroke (expo.in) until it swallows the frame. When a picture cut ends the window, the next shot is
already playing through the stroke from its pre-roll, so you land in it on the cut (a reframe works the same way);
without one it lands on the live shot, fully open on the last frame.

**Needs:** any footage. `words.json`, the pack's display font (`style/fonts/`), a picture cut or reframe at the end of
the window for the pre-roll (`h.mp4`, cut from `edit.SRC` the way cut.py cuts; on a source that isn't 30 fps it tries a
few sub-frame starts and keeps the one that matches clean.mp4 on the cut), and optionally `work/tracks/track.json`
(keeps the word near the chin). No matte, no plate.

**Reuse:** copy the folder to `<project>/fx/<id>/`, add `dict(id="<id>", layer="over", at=..., end=<the picture cut>)`
to edit.FX (start it a few frames before `SLAM_ON`, on a frame), set the table at the top of `gen.py` and run
`PY fx/<id>/gen.py <project>` (`--check` prints the plan, writes nothing).
- `WORD`: the word cut out, as it should read. `SLAM_ON`: the spoken word the plate lands on. `SAY`: the spoken word
  the letters build on, when it differs from WORD.
- Read off the project: the glyphs from the display face's real outlines (fontTools, cut through a mask, so the
  overlapping contours many variable fonts keep still cut clean); the stroke to dive into (the letter nearest the
  middle whose ink holds the biggest frame-shaped box; `STEM_LETTER` with `STEM` overrides); the zoom it needs
  (`SCALE`, `MARGIN` past the minimum); the baseline (the x-height band where the footage reads best against the
  plate, its middle between the chin and two x-heights under it; `BASELINE` overrides).
- Beats: the plate drops on the `DROP` frames and lands on `SLAM_ON`, the letters build until `BUILD` of the way
  through the spoken word, the dive takes the last `DIVE` s, the next shot shows through the letters from `SWITCH` s
  before the cut and leans in to `LAND`. Add the `CAMERA["punch"]` line gen.py prints so the lean carries through the cut.
- The dive is the cut's transition: camera-transitions and shape-transitions leave the cut alone.
- A synced copy of the shot plays through the letters, so captions never show inside them: no KARAOKE hide needed.

**Sound:** `impact-low` and `shutter` on the slam, a `tick` per letter, `whoosh-deep` on the landing. gen.py prints
the lines.

**Phone take:** nothing changes.

**Other frames:** it sizes itself from `CANVAS` (the dive box is the frame's shape), but the baseline search keeps to
the 9:16 safe zone (y 220 to 1470): on 1:1 or 16:9 set `BASELINE`.
