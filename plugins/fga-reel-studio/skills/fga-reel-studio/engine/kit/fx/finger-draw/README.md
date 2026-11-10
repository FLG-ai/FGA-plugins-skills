# finger-draw (cam)
A dry grease-pencil line in the creator's accent follows the speaker's real fingertip, so they draw in the air. Two
shapes (MODE). `path`: whatever the finger draws between pen down and pen up, in real time, the live end on the
fingertip, drying up at the end of the window. `numeral`: the finger goes up on "one", the line rises with it, melts
behind the raised finger while it's held (the finger is the 1), and the whip away leaves a hand-drawn 1 hanging exactly
where it stood, its flag drawn by the real whip. Optional mono label lines land on their words beside the top of the
drawing. The fingertip is read off the speaker's own skin per frame (the track's landmark lags up to 70px on fast
frames). The line's sound, a china marker on glass driven by how fast the ink really moves, is synthesized by gen.py.

**It needs a take filmed for it.** A finger in an ordinary talking take rarely draws anything readable: it moves along
its own length and hides its own trail. Film the line on purpose (below). OVERRIDE is the per-take fix for the frames
where the tracker puts the tip on the wrong finger.

**Needs:** a camera that doesn't move (tripod, or a phone propped still) with the drawing hand in frame the whole time.
`public/subject.webm` (only skin on the speaker counts as the fingertip), `work/tracks/track.json`
(`PY KIT/pipeline/track.py <project>`, for the hands and face). Depth only in numeral mode (the kit's depth.py; the model
downloads on first use; about a second a frame, cached in `work/<id>/`). No plate.

**Reuse:** the table at the top of `gen.py`: MODE, PEN_DOWN and PEN_UP (cue words, with fallbacks in seconds), SIDE
(`auto` takes the hand that moves most), LABEL (text, cue word), NUMERAL (the foot, top and whip frames, when the reading
misses them), WIPE, OVERRIDE and SKIP. In numeral mode PEN_DOWN is the word the finger is up on ("one"): the rise is
its lowest point just before that word, the top the first frame it holds still (read off the skin), the whip the first
big move after (read off the landmark, which rides through a fast move), and rise frames the blur threw off the line
are left out. Read off the footage: the line's width, the fingertip search and the hand matte's
box from the face size and the hand's path, the skin colour from the speaker's own face, the label's place beside the top
of the drawing (LABEL_POS overrides) and light or ink against what's behind it. `gen.py --tips` prints the fingertip on
every frame, to fill OVERRIDE (in numeral mode also the path the beats are read from). A window with no tracked hand,
or one that loses it for most of the line, stops with a message instead of drawing. Then `PY fx/<id>/gen.py <project>` (`--stills T` first) and paste the SOUND lines it
prints: `<id>-marker` from the window's start, a tick per label line.

**Phone take:** the same code, if the phone stays still and the hand stays in frame. A handheld shake moves the line off
the room: it sits on the picture.

**Frame:** 9:16 as built; 1:1 and 16:9 work as they are (everything scales by the face).

## Film this for an air-drawn line (about 5 seconds)
- Camera locked off, the same framing as the rest of the take. Draw with the hand on the side the line goes up, so the
  forearm trails behind the line and never covers it.
- Index finger straight up, the other fingers curled tight, the back of the hand to the lens. Tilt the finger a little
  toward the lens: it keeps the tip clear of the knuckle for the tracker.
- Start low on the other side, across the chest. Hold still for half a second: pen down.
- Draw a hockey stick, not a diagonal, so the hand never crosses the face: flat across the chest, then bend up past the
  shoulder to eye level. Hold still for half a second: pen up.
- Slow: about 2 seconds for the whole line, never more than about a finger's width a frame. Slow enough to feel silly.
  Keep the finger the same shape the whole way.
- Say the line so the bend lands on the word that matters, and look at the camera, not the finger.
- Shutter 1/120 or faster and a true 30 fps file: a fast fingertip blurs away, and the repeated frames of a 24p source
  make the line stutter.

Then put PEN_DOWN and PEN_UP on the two holds and run gen.py. For axes, film them as a second pass with the same rules and
run it as a second window. For the numeral: raise one finger on the word ("one", "first"), hold it still for about half a
second, then flick it away to the side.
