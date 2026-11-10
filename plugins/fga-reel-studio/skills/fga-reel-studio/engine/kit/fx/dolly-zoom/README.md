# dolly-zoom

The Vertigo shot on a locked-off talking head. The speaker holds their size and place, lips in sync, while the room
behind them rushes forward. It is the real camera move computed from the room's depth: the camera pulls back while the
lens zooms in, so everything at the speaker's distance stays put and the further back something is, the more it grows.
The wall is fitted as a plane (a true homography, so a picture frame stays straight as it grows), furniture in front of
it moves by its own distance (barely, near the speaker, which is what keeps them in the room instead of pasted on it)
and the desk falls back a touch. Motion blur on the room only. It lands on the word, holds, and goes home before the
window ends.

**Needs**
- Footage: a tripod, the camera untouched, and a room with depth: something between the speaker and the far wall (a
  chair, a shelf, a lamp) and a wall with an edge on it. A plain backdrop reads as a zoom on a background card.
- A clean room, because the move reveals what was behind the speaker. Film the empty room at the end (walk out for 5
  seconds, `EMPTY` in edit.py) and run the kit's plate tools: they write `work/c/room_<FRAME>.npy` (the room as the
  take saw it) and `work/c/room_empty_<FRAME>.npy` (the empty room alone). The wall hands over to the empty room in
  the first part of the move, so there is no seam where a fill meets the real room. Without the empty stretch the
  patch the speaker always covered is wall the take never saw: gen.py treats it as wall and fills it smoothly from the
  wall around it, so a soft plain area grows into view behind the head. On a plain wall it passes; on a busy one
  (shelves, art, a window behind the speaker) it reads as a smear, and gen.py says how much of the crop it is. Without
  any room file gen.py stops and says what to film.
- The matte (`public/subject.webm`), the track (`work/tracks/track.json`: the face for the point the room rushes out of
  and for the depth calibration, the shoulders for where the matte is held solid), the depth model (pipeline/depth.py,
  downloaded on first use), and the desk and mic layers when the plate tools found them: the mic never moves, the desk
  is the foreground.
- A line where the speaker holds roughly still: fast hands in front of the room are the matte's weak spot.
- Nothing from the style pack: everything on screen is the speaker's own room.

**Reuse**
- The FX entry (`layer="cam"`) is the window: the move starts at its start (from nothing, nobody sees it begin),
  lands on `MOVE_ON`, holds, and goes home in the last `RETURN` seconds. About 1.2 to 1.5 s in all.
- Constants at the top of `gen.py`: `MOVE_ON` (empty = the last word before 70% of the window), `SCALE` (how much the
  far wall grows), `CENTER` (None = behind the head), `WALL_DIST` (the wall's distance in speaker distances; it sets
  how much the furniture moves), `NEAR`, `MID_GAP`, `DESK_SCALE`, `PURE_AT`.
- Read off the footage: the depth of the room and of a live frame, calibrated so the speaker is at distance 1 and the
  wall at `WALL_DIST`; the wall's plane; what counts as furniture and foreground (by depth, edges from the picture);
  the point behind the head; the crop. The depth is cached in `work/<id>/` until the room or the landing frame changes.
- `PY fx/<id>/gen.py <project> --stills 7.5 7.7` writes stills to `work/<id>/`, plus `layers.jpg` (the wall, the
  furniture, the foreground) to check what moves.
- Sound: gen.py prints `riser` under the move peaking on the landing (for a move shorter than the riser it writes
  `audio/<id>-riser.wav`, the riser's last part, placed by its start), `impact-low` on the landing, `whoosh-soft` as
  the room goes home.
- Canvas: the geometry is all measured on the frame, so 1:1 and 16:9 work as they are; a wide frame shows more wall to
  grow.

**Phone take**
It needs a locked phone and the empty room filmed the same way. Handheld, the room is never the same twice, so there is
no plate to move: pick another effect.
