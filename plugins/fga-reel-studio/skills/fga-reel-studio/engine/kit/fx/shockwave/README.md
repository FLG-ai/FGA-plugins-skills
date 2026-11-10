# shockwave

The room takes a hit on one word. A single refractive ring is born inside the speaker's head and radiates out across
the frame in 13 frames: pure displacement of the real picture (a derivative-of-gaussian radial push, so the band acts
like a lens), its strength falling as it travels, plus a 2-frame shove on the hit. No colour, no flash, nothing added,
so it has no look of its own and takes nothing from the style pack. The head does not move at all; the room takes all
of it and the speaker's body about half. Straight edges in the room (a picture frame, a shelf, a door) are what sell it.

**Needs**
- Footage: any. Best on a tripod with the room plate; a phone take works too (below).
- The matte (`public/subject.webm`) and the face track (`work/tracks/track.json` from `pipeline/track.py`).
- The room behind the speaker's soft edge, for the matte equation (the speaker with their share of the field, plus the
  room's own change behind their alpha): the filmed empty room's (`work/c/room_<FRAME>.npy` when
  `work/plate/plate.json` says `"empty"`), else read off each live frame just outside the edge. A fallback plate is not
  used: its fill is cut out exactly where the speaker sat, so it tears along their outline. Either way zero
  displacement is the live frame bit for bit and there are no seams.
- Something straight in the room to bend. A plain empty wall carries nothing: pick another effect.

**Reuse**
- The FX entry (`layer="cam"`) is the window. Start it one frame before the word and give it at least 15 frames
  after the hit: the frames before the hit and after the ring are copied from the live picture untouched.
- Constants at the top of `gen.py`: `HIT_ON` (the word it lands on; empty = the first word in the window), `CENTER`
  (None = behind the head, or any impact point in px), `BODY` (0 room only, 1 the whole picture), `HEAD_STEADY`,
  `STRENGTH`, `WIDTH`, `RING_FRAMES`, `SHOVE`.
- Read off the footage: the impact point and where the ring is born (the face in the track, per frame for the head
  mask), how far it travels (to the farthest corner of the frame), the crop (timeline.json), the room.
- `PY fx/<id>/gen.py <project> --stills 1.20 1.27` writes stills to `work/<id>/` to check before the clip.
- Sound: `impact-low` on the hit; gen.py prints the line for `edit.SOUND["sfx"]`.
- Canvas: everything is measured on the frame, so 1:1 or 16:9 needs no change; the ring only has less or more frame
  to cross.

**Phone take**
Works as it is: the room behind the edge is read off each frame, so a handheld take needs no plate (tested on a selfie,
the ring bends the picture frames on her wall). Handheld movement hides a weak ring: raise `STRENGTH` about 1.5x, or
`--body 1` to ripple the whole picture.
