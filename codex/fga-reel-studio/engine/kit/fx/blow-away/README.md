# blow-away

The line says the speaker was blown away, so they are. A camera jolt on the word, dust strips off every windward edge,
then a front of wind crosses them from lower left to upper right and they come apart as hundreds of thousands of
grains in their real colours, each read from the live frame the moment it lets go. What the front has not reached IS
the live frame, lips in sync. The grains ride a seeded wind (drag, curl noise that grows with age, heavy grains fall,
most pass behind what is still attached) and shrink away, never fade. Then the empty room holds, a few specks drifting
in the settled air: whatever the speaker leaves behind (the empty chair) is simply there. Same run, same film: the
physics is seeded.

**Needs**
- Footage: a tripod, the camera untouched for the whole take, and the empty room filmed at the end: walk out of frame
  and let it record for 5 seconds (`EMPTY` in edit.py). The plate tools turn that stretch into
  `work/c/room_empty_<FRAME>.npy`, the room with nobody in it, which the room cuts to on the jolt. The hold then
  carries the empty stretch's own grain, so it is filmed, not frozen.
- Without an empty stretch it falls back to `work/c/room_<FRAME>.npy` (the room as the take saw it): what the speaker
  never touches stays live, and where they sat becomes a smooth guess filled in from the room around it. It shows as
  soon as they're gone (a soft blur in their shape). gen.py says so and prints the time to end the window by: a
  window that ends there cuts away mid-dissolve, the house's own advice without a plate. No room file at all: the
  same smooth guess from the frame itself.
- The matte (`public/subject.webm`), the track (`work/tracks/track.json`: the face width sets the dust, the shoulders
  where the body is solid; without it both are guessed), and the desk and mic layers when the plate tools found them
  (`public/plates/desk_<FRAME>.webm`, `mic_<FRAME>.webm`): the sand passes behind them and the mic sheds nothing.
- Nothing from the style pack: everything on screen is the speaker and their room.

**Reuse**
- The FX entry (`layer="cam"`) is the window: start it one frame before the hit word, run it through the hold. As the
  last beat of a video it can run to the end and loop on the empty room.
- Constants at the top of `gen.py`: `HIT_ON` (the word the wind hits on; empty = the first word in the window),
  `GONE_ON` (the word the last grain leaves on; empty = `GONE_AFTER` after the hit), `CLEAR_AFTER`, `SLANT`,
  `FRONT_EASE`, `WIND`, `SPECKS`, `GRAIN`.
- Read off the footage: the speaker's outline and colours (the matte and the live frames), the dust depth (the face
  width), where the matte is held solid (below the shoulders), the crop (timeline.json), the room, the desk and mic.
- `PY fx/<id>/gen.py <project> --stills 23.4 23.7` writes stills to `work/<id>/` (the sim still runs every frame, about
  30 to 60 s).
- Sound: gen.py writes `audio/<id>-sand.wav` from the simulation's own grain counts (hiss, grit and air that pan with
  the sand, synthesized here) and prints the lines: `impact-low` on the hit, the sand placed by its start,
  `whoosh-deep` in the gust, `whoosh-soft` as the last of them goes.
- Canvas: everything is measured on the frame; the jolt scales around the upper middle, so 1:1 and 16:9 work as they
  are.

**Phone take**
It needs a locked-off phone and the empty room filmed the same way; handheld breaks the hold on the empty room. With
no plate, keep the window short and cut away before the speaker is fully gone.
