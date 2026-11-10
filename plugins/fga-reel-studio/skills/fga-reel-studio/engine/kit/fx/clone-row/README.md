# clone-row

Six more of the speaker, all talking, slide out from behind them in pairs on three words and snap back into them on a
fourth. Each row is the cutout scaled about the head (the vanishing point), a touch darker and softer with distance,
one frame later in media time per generation so they are not robotically identical, each falling off into the dark
from the collar down so its own mic, desk and hands never show. Horizontal motion blur on the slides through one SVG
filter per row. Layer `cam`: the clones furthest first, then the speaker's cutout on top, over the live footage. No
plate: the room stays the real pixels, so it can start and end anywhere without a seam.

**Needs:** any footage, tripod or handheld. The matte (`public/subject.webm`) and `work/tracks/track.json`. Seven
video tracks (`{{T0}}`..`{{T6}}`).

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes `fx.html` and `fx.js` (a few seconds). The edit.FX entry:
`dict(id="clone-row", layer="cam", at=..., end=...)`, the window running a little past the snap back.

**Reuse:** the table at the top of `gen.py`.
- The rows come out on the window's first three words (`OUT_ON` names them) and snap back on the next word
  (`BACK_ON`).
- `ROWS`: scale, distance out, height, brightness and softness per row. Distances are in head half-widths, measured
  on the matte at the eye line, so the clones line up beside any head on any framing. The vanishing point is the head
  at the eye line (track.json).
- The fall-off runs from just under the chin to about a face height below it (`FADE_FACE`), read off the track; set
  `FADE` in px to place it by hand, above the clones' own hands and mic.

**Sound:** a `whoosh-soft` per pair, `whoosh-deep` into the snap back, `pop` and `impact-low` as they land in the
speaker; gen.py prints the times.

**Phone take:** works as it is. A selfie fills the frame, so the outer rows run off the edges (the line carries on out
of shot); fewer rows or smaller distances keep them in.

**Canvas:** built for 1080x1920 (the wrappers are 1080x1920 boxes). On another canvas set `W`, `H` and the box size
in gen.py; the spacing still comes from the head.
