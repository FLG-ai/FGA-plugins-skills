# room-doors (cam)

"The doors open", literally. On the cue word the wall behind the speaker cracks open from behind their head and two
heavy panels roll apart on inertia with a soft stop. Behind them is a real page, lit like a thing in the room: light
falls in as the gap widens, each panel throws a soft shadow on it, a lintel shadow up top, the speaker's own shadow,
lens blur, a slow scroll, much less parallax than the panels. The speaker, the desk, the mic and the furniture stay
exactly where they are. The panels are the shot's own wall with real inner faces drawn in perspective toward the lens
centre, the lamp's side lit and the far side dark, with true motion blur (10 samples through a half-frame shutter).
Everything in front is the live frame, so lips and edges are the footage. One clip, plus the panels' own rumble.

**Needs:** a locked-off shot (a tripod, or a phone that doesn't move), `public/subject.webm`, `words.json`, and what
is behind the doors: a capture of a real page (`--capture` with `PAGE_URL` set, a phone-sized headless browser), or
any tall image dropped into the project's copy of this folder as `page.png` (a screenshot, a sales page, a poster).
Without one it shows a placeholder page in the creator's type and colours, labelled PLACEHOLDER. Best with the plate
tools' room (`room_<FRAME>.npy`) and the desk and mic layers (`public/plates/desk_<FRAME>.webm`, `mic_<FRAME>.webm`);
without a room it builds the wall from the frames on that framing. `work/tracks/track.json` puts the seam on the head
(without it the matte does). The depth model (`pipeline/depth.py` downloads it on first use) finds what stands in
front of the wall.

**Run:** `PY fx/<id>/gen.py <project> [<id>] [--capture [URL]]` writes `<id>.mp4`, `fx.html`, `fx.js` and
`audio/<id>-rumble.wav` (synthesized from the panels' speed curve, CC0), and prints the SOUND lines: the rumble placed
by its start 0.04 s before the crack, `click` on the latch, `impact-low` on the stop. `--stills 26.3 26.9` writes PNGs
to `work/fx/<id>/` and nothing else; `--fresh` forgets the cached room measurements. Start the window one frame before
the cue word and end it on the picture cut. A window that can't end on a cut gets the panels rolling shut over its
last `CLOSE_S` (0.45 s, `CLOSE_AT_END`) with the same rumble and a bump on the close; as they meet, the seam and the
cut-out edges heal into the live frame (`HEAL_GAP`), so the live shot takes over with no snap. Give that about 1.3 s
from the cue word: in less, gen.py warns and closes faster. Edit.py: `dict(id="room-doors", layer="cam", at=...,
end=...)`.

**Reuse:** the table at the top of `gen.py`. `SEAM_ON` is the cue word, `OPEN_S` how long the panels roll,
`LEFT_STOP` / `RIGHT_STOP` where they stop (leave some door in frame: it sells them as objects), `PAGE_*` what is
behind them (`PAGE_CUT` blanks everything below a line of the image, a price or a footer). What reads off the
footage: the seam (the centre of the head on the cue word, `SEAM_X`), where the crack starts (just inside the top of
the head, `SEAM_FROM_Y`), the lens centre (`OPTICAL`, the centre of the source mapped into the crop), which side the
lamp is on and how high (shadows, the lit inner face, the fall-off across the page all follow it), the colour of the
light and how bright a lit page reads in this room, and what stands in front of the wall (anything clearly nearer than
it on the room's depth: a chair, a shelf, the floor). `work/fx/<id>/standing_<FRAME>.jpg` shows what stays in front;
raise `FURNITURE_DEPTH` if part of the wall stays put, lower it if a chair slides away with a panel. Depth, light and
the panels read the room as the take shows it (the plate only behind the speaker). `KEEP_NEAR`: what the matte missed
at the speaker's distance (a book in their hands) is found on each frame's depth and stays in front.

**Fallback plate** (no empty room filmed, `work/plate/plate.json` says `fallback`): gen.py warns. The patch where the
speaker always sat is the plate's guess, so it is not taken as furniture and is bridged over from the wall either side
of it; the panels carry that bridged patch as they roll (soft streaks of the wall's colours beside the speaker, clean
at a glance, wrong under a pause). Film 5 s of the empty room for a true wall.

**Phone take:** only on a phone that doesn't move; handheld is out. Keep the seam behind the head and over something
lit if you can: on a dark wall a crack only reads where it crosses a picture or a lit edge. Built for 1080x1920:
on another canvas gen.py stops.
