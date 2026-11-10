# live-cursor (top, + `<id>-room` on cam)

A multiplayer cursor with a name flag walks into the shot and edits the video live while the speaker keeps talking:
it rubber-bands them, the box snaps to their real silhouette with a live pixel readout, it drags them across the room
(the room, the desk and a mic stay where they are; they come forward a touch while held and snap to a guide through
their face), fetches a 9:16 card of the creator's own clip from off frame and drops it in the gap, one last click,
then everything clears and they are back on the live pixels. Selection, handles and the pixel readout are the pack's
accent, the guides its third series colour, the cursor and flag its light and dark, the flag and labels its text and
mono faces.

**Needs:** `public/subject.webm`, `words.json`. For the drag: a locked-off shot and the plate tools' room
(`room_<FRAME>.npy`), plus the desk and mic layers when there are any (they go back in front of the speaker). Without a
room the drag is left out and the rest runs over the live picture. When the speaker touches the side of the frame
(shoulders, arms) a drag would show a straight cut down their side: if the source is wider than the crop (a 4K
landscape take cut to 9:16), gen.py re-cuts the speaker wider from it at exactly the crop's scale and keys it with
the kit's background remover; otherwise it feathers that edge and says so. `work/tracks/track.json` puts the guide on
their face line and the box's lower edge at their shoulders (without it the matte decides). For the card: the
creator's own clip as a project file (`src` in BEATS); without one, a labelled placeholder card.

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes the overlay in `fx/<id>/` (cursor, flag, marquee, box, guides,
cards, an outline video of the speaker's edge) and, with a drag, the room clip in `fx/<id>-room/`, then prints both
edit.FX entries and the SOUND lines (`click`, `tick`, `pop`, `whoosh-soft`, each on its frame). Edit.py:
`dict(id="live-cursor", layer="top", at=<the cursor enters>, end=<everyone home>)` plus the printed
`dict(id="live-cursor-room", layer="cam", ...)`. Rerun it whenever the window, the cut or BEATS change. Nothing may
zoom `#cam` during the window (the overlay tracks at scale 1). The live captions stay on; the box stops at y 1272.

**Reuse:** the table at the top of `gen.py`. `NAME` is the flag (default: the creator's first name from the pack, else
their handle, else no flag, never the kit's own name; set it to the AI they name when the line says the AI did it).
`BEATS` in order, each optional but `enter` and `exit`: `enter` (curved glide in, a correction, a hover), `select` (a
marquee; the box then tracks the matte every frame), `drag` (press, they follow, snap; `dx` in px or None for 21% of
the width away from the side they sit nearer; several drags add up), `drop` (fetch a card from the open side and drop
it in the gap; `src` the clip, `src_at` the second of it that lands on `src_on`, `label`), `click` (one last click
lets the selection go), `exit` (cursor and cards out, the speaker slides home on the last frame before the end). A
beat's `at` is a cue word or seconds after the start; the default rhythm fits 2.33 s and runs faster in a shorter
window. A window under 2 s (`SHORT_UNDER`) runs `SHORT_BEATS` instead: enter, select, drag, exit, with the selection
riding them home and letting go as they land. Every position reads off the speaker's box (give `to`, `frm`, `via` as
(x, y) to pin one); `CARD`, `CARD_MARGIN`, `FLOOR`, `HEIGHT`, `LIFT`, `SHUTTER` are the look. A mic in the matte is
painted out of the moving speaker (a soft patch; check their chest).

**Fallback plate** (no empty room filmed): gen.py warns and leaves the drag out (`DRAG_ON_FALLBACK` puts it back),
because the patch where the speaker sat is the plate's guess and shows the moment they move. With no drag there is no
gap, so the card lands beside the face on the side with more room, narrower if it must be, and is left out when
neither side has 220 px (a close shot).

**Phone take:** a phone that doesn't move can drag if there is a room plate built from an empty room; handheld, the
drag is left out and the cursor, selection and card run over the live picture, which still reads. Laid out for
1080x1920: on another canvas gen.py stops.
