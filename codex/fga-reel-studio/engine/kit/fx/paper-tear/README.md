# paper-tear (over)

A full-frame page rips in two on a picture cut: a seeded multi-octave torn edge, a band of raw white fibre on both
torn edges, stray fibres, the sheet bending up off the page with real shading, a soft contact shadow on what is
underneath, and the two halves pulling apart, turning and leaving off the sides with the next shot live underneath. By
default the page is the shot itself, so the picture rips open onto the next shot. It can also tear a press-front page
(`PAGE` = that entry's id, the pair that opens a video with a front page) or any full-frame clip or still on screen
before the cut (a card, a cover image). It is real paper, not the look: the fibre is paper white and the shadow black
in every pack.

**Needs:** any footage. A picture cut or reframe inside the window (on a J-cut the next shot's pre-roll keeps the lips
in sync under the page), and optionally `work/tracks/track.json` (the tear runs through the face). No matte, no plate.
It renders in about a minute.

**Reuse:** copy the folder to `<project>/fx/<id>/`, add `dict(id="<id>", layer="over", at=<cut - 0.133>,
end=<at + 0.367>)` to edit.FX (on frames: multiples of 1/30 s), set the table at the top of `gen.py` and run
`PY fx/<id>/gen.py <project>` (`--check` prints the plan, writes nothing). It writes `tear-a.mp4` (H.264: the page
tearing open with the next shot composited into the gap, up to the cut), `tear-b.webm` (VP9 with alpha: just the
halves and their shadow from the cut on, so the live picture and the captions show through the gap), fx.html, fx.js,
`audio/paper-rip.wav`, and the pre-roll and proof stills in `work/<id>/`.
- `PAGE`: `''` for the shot itself (it plays in the live grade); a press-front entry's id (its clip while it lasts,
  then the clip's own last frame, so the hand-over doesn't move a level; its `last.png` only when the clip is gone);
  or a clip or still in the project. `PAGE_AT`: when a clip's first frame is on screen, read from edit.FX for an
  effect and from edit.CARDS for a card. The page stays alive up to the cut, then the sheet holds its last frame.
- Read off the project: the cut (the picture cut or reframe inside the window, best 4 frames in), the pre-roll (cut
  from `edit.SRC` like cut.py; on a source that isn't 30 fps it tries a few sub-frame starts and keeps the one that
  matches clean.mp4 on the cut), the tear line (through the face under the page, leaning `TILT` px; `LINE` overrides).
- The tear is the cut's transition: camera-transitions and shape-transitions leave the cut alone; keep `CAMERA`
  settles off it.
- `SEED` gives another rip. `PULL` is the animation, one row per frame. With no cut in the window it tears a `PAGE`
  over the live shot (the shot itself can't tear open onto itself). Rerun it whenever the page, the window or the cut
  moves.

**Sound:** `mk_rip.py` synthesizes `audio/paper-rip.wav` from scratch (fracture clicks, fibre noise, the flap as the
halves let go), gen.py runs it. Place it by its start, with a `whoosh` as the halves pull away; gen.py prints both.

**Phone take:** nothing changes, it never touches the shot. Keep the page opaque.

**Other frames:** it sizes itself from `CANVAS`; the `PULL` rows run in 1920-tall px, so on a 16:9 cut the rip
crosses the shorter frame sooner.
