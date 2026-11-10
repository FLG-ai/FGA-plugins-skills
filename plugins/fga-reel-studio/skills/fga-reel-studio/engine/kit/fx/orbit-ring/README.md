# orbit-ring (+ `<id>-front`)

A Saturn ring of type round the speaker's head: a real perspective circle tilted 32 degrees, locked to the face track
(centre and roll). The far half sits behind the speaker (`<id>`, layer `behind`), the near half in front of them
(`<id>-front`, layer `top`); letters hand over at the two extremes, where nothing overlaps the head. The letters spiral
in, each word arrives at the front and lights in the accent as it is spoken, then the ring whips round and reels into
the back of the head like a tape measure, so nothing ever crosses the face (gen.py prints the closest a near letter
gets to the eyes and mouth). Every letter is rendered with true motion blur into two all-intra clips (a 72 degree
shutter at cruise, 180 on the spiral and the whip); the near clip also carries the letters' soft shadow, on the
speaker only. Type is the pack's display face in its light colour, the lit word in the accent.

**Needs:** any footage. The matte (`public/subject.webm`), `work/tracks/track.json`, `words.json`, a `CUT_WINDOWS`
entry over the window, and one continuous shot under it: no picture cut or reframe inside the window (gen.py refuses
one; start the window on the cut instead) and no camera zoom (the near half sits above the camera).

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes `fx/<id>/smear.webm` and `fx/<id>-front/smear.webm`, with their
`fx.html` and `fx.js` (about 20 seconds). Two edit.FX entries with the same window:
`dict(id="orbit-ring", layer="behind", at=..., end=...)` and `dict(id="orbit-ring-front", layer="top", at=..., end=...)`.
gen.py says when either entry or the CUT_WINDOWS entry is missing. `DOM = True` writes crisp letters and one tl.set
per letter per frame instead of the clips (no motion blur).

**Reuse:** the table at the top of `gen.py`.
- `TEXT`: the ring in caps, items split by ` · `, ending with one so it loops.
- Every word of TEXT lights on itself, spoken in the window; `LIGHT` pairs ring words with other spoken words. A word
  goes back to the light colour when the next item lights; the last item stays lit.
- Each item reaches the front `CENTRE_LAG` after its first word lights; that sets the spin, so keep the words' spacing
  and the speech in step. The ring reels in on the last lit word (`SHUT_ON` to choose another).
- Read off the footage: the radius (`R_FACE` face widths), the letter size (`FONT_FACE`), the ring's height (the near
  arc just under the chin, `CHIN_CLEAR`), the tilt (the far arc `FAR_AT` of the way down from the top of the head, read
  off the matte: 32 degrees on the shipped take, steeper on a close-up), the head's position and roll per frame. When
  the ring would leave the frame, radius and letters shrink together. A wide, heavy display face gets smaller letters
  rather than touching ones (`MIN_GAP` between neighbours on the near front). `R`, `FONT_NEAR`, `TILT`, `CY_OFF`
  override; `CX_OFF` slides it sideways to dodge something else on screen.

**Captions:** hide them over the window if they repeat the ring's words.

**Sound:** `whoosh-soft` as the letters spiral in, `whoosh-deep` as each item passes the front, a `tick` on every word
that lights, `whoosh` on the whip, `pop` as it snaps shut; gen.py prints the times.

**Phone take:** the head is bigger and closer, so the ring is held inside the frame and tilts more steeply to keep its
far arc at the top of the head; if gen.py warns that the far arc leaves the frame, set `TILT` lower.

**Canvas:** built for 1080x1920. On another canvas set `W` and `H` at the top of gen.py; the ring still centres on the
head and keeps `MARGIN` from the edges.
