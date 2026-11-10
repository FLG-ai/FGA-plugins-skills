# code-body

The speaker turns into their own source code. A hairline scans top to bottom on a word: above it every cell of a
monospaced grid is a character of the real text that edited this video, in reading order (`edit.py`, every effect's
generator and `fx.js`, the kit's pipeline), so a paused frame reads as code. Each cell's colour and glyph weight come
from the live frame under it: skin and face in the pack's light colour, highlights in its accent, the clothes in their
own colour family, the room as sparse dim type on the pack's dark ground. The text climbs a row every few frames while
the face stays put. The cells step down on the words until the face resolves, then the line runs back up and the
speaker is live again. Every frame is built from the same frame of the video, so the lips stay in sync.

**Needs:** any footage. The matte (`public/subject.webm`), `work/tracks/track.json` (the face, the hands, the head
top), the mic layer (`public/plates/mic_<FRAME>.webm`) when the shot has one. No plate. The type is the pack's mono
face (its weights, thinned below the lightest for the hairlines).

**Run:** `PY fx/<id>/gen.py <project> [<id>]` (layer `cam`), about 40 seconds, writes `code.mp4`, `fx.html` and
`fx.js`. Run it last, after every other effect exists, so the code on screen is the final code. `--still n,n` writes
frames as stills to `work/<id>/` without the clip.

**Reuse:** the table at the top of `gen.py`.
- The line runs down on the window's first word (`SCAN_ON`); the coarsest cells hold a beat, then they step down on
  the words nearest 39 to 65 percent of the way to the line going back up (`STEPS_ON`, `STEP_FROM`, `STEP_TO`,
  `CELLS`), so the face holds resolved before it goes live; the line runs back up `UP_BEFORE` seconds before the
  window ends (`UP_ON`).
- Read off the footage: the clothes are the matte under the chin minus the face, the hands and anything coloured like
  the speaker's own skin (sampled from their face), so any top works, any colour; their colour family and tone range
  are measured on the take (`CLOTHES` sets a pack role instead, `"accent"` or `"s2"`). The speaker's own tonal range
  is measured too, so a brightly lit face keeps its features. The room's level is measured so a dark or a bright room
  stays sparse (`ROOM_Y`). Light cells only flip to dark type on a light hat or light hair, never on skin. The accent
  only lands on small highlights (eyes, lips, a buckle), never as a rim round the speaker.
- `LOOK` tunes the tone per cell size; `HEAD` is how much of each generator comes first on screen.

The text is the creator's own project files and the kit's code; a quoted path shows only its file name and the home
folder shows as `~`, so nobody's folders or user name end up on screen.

**Captions:** keep them on: their box reads over the code.

**Sound:** `whoosh-soft` as the line scans down, a `click` on each step, `impact-low` and `ding` as the face resolves,
`typing` under the hold, `whoosh-soft` as the line runs back; gen.py prints the times.

**Phone take:** nothing depends on a tripod. A face that fills the frame reads at bigger cells.

**Canvas:** built for 1080x1920 (`W`, `H` at the top of gen.py); the grid fills whatever they are set to.
