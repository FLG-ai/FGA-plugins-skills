# impact-frame

A hit on one word, full frame, on layer `over`. The real frames of the shot turn to pure ink: fine line work on the
head, a brushed contour round the silhouette, everything below the head simplified to solid black shapes. Two frames
negative, two positive, two negative, each with fresh hand-ruled focus lines bursting off the face (tapered strokes in
uneven bursts, flipping whatever they cross), then the positive holds with the word stamped flat out of the black.
Hard in on the word, hard out to live: 14 frames as shipped. Paper and ink are the pack's light and dark, the word is
the pack's display face. Every frame is the real frame of the video, so the mouth stays on the words.

**Needs:** any footage, tripod or phone. The matte (`public/subject.webm`), `work/tracks/track.json` (the face, from
`pipeline/track.py`), `words.json`. The mic layer (`public/plates/mic_<FRAME>.webm`) is used when the shot has one,
so the mic inks with the speaker; without it nothing changes. No plate, no depth, nothing to supply.

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes `ink.mp4`, `fx.html` and `fx.js` into `fx/<id>/` (about 10
seconds). `--sheet` writes every frame and a contact sheet to `work/<id>/` instead of the clip. The edit.FX entry:
`dict(id="impact-frame", layer="over", at=<the word's onset>, end=<at + 14 frames>)`. gen.py prints the voice onset
when the window starts off it (whisper is often a frame or two late), the SFX lines and the caption hide.

**Reuse:** the table at the top of `gen.py`. Read off the footage, each with a constant to override it:
- the push-in: the frame scales about the face until the face is `FACE_W` wide (never out, at most `PUNCH_MAX`), the
  chin moves to `CHIN_Y` as far as the frame allows (`PUNCH = 1` turns it off);
- `FG_BELOW`: the first row under the chin the speaker fills edge to edge; below it everything is solid black;
- `BODY_BLACK`: the level the clothes go solid below, measured so `BODY_SOLID` of them goes black whatever they
  wear (hands and a light collar stay as shapes);
- `WORD_Y`: the first place under the chin where the speaker covers the whole word, so it stamps out of solid black;
  above the head when there is no room.

The word is the spoken word the window starts on, in caps (`WORD` and `UPPER` to set it), fitted to `WORD_W` and never
above `WORD_SIZE`. Each letter is paper out of the black, or ink where it reaches the page past the speaker. The
sequence is `STAMP_AT` (the frame the word slams on), `STAMP_SCALE` and `NEG`; `SECOND_ON` gives a second spoken word
inside the window its own hit (a flip, fresh lines, a shove). Keep the window short: it is a hit, not a hold.

**Captions:** hide them (`KARAOKE["hide"]`) from the window's start to the next line's start, so that line starts
under the print and shows on the cut back.

**Sound:** the hit (`impact-low`), a `tick` on each flip, `stamp` when the word lands; gen.py prints the times.

**Phone take:** works as it is. A selfie's face is already big, so the push stays near 1; when the chin sits low the
word goes above the head.

**Canvas:** built for 1080x1920. On a 1:1 or 16:9 canvas the push and the word still read off the face, but `W`, `H`,
`WORD_W` and `CHIN_Y` assume 9:16: set them for the canvas.
