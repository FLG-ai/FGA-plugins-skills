# banknote (over)
A money line, full frame. The speaker becomes the engraved portrait on a generic note, live and lip-synced: a true line
engraving of every frame (parallel lines whose width follows the tone, lozenges in the lights, two cross-hatch families
in the deep shadows, the lines bent round the head by an ellipsoid plus the depth map and riding with the head as it
moves), inside an oval with a turned lattice behind them. The note is pure math: guilloche border, rope, scallop,
rosette, lathe-work tint, microtext of the speaker's own words, a serial in a second ink. The number prints glyph by
glyph in the big plate and all four corners, each glyph on its spoken word, and goes wet once more on the last word.
Printed on it: THIS NOTE IS NOT MONEY. THE NUMBER IS REAL. The paper and inks are a real note's (intaglio green, a
serial red, off-white paper); the type is the creator's (the pack's display face for the number, the title and the
signer, text for the microtext and small print, mono for the serial).

**Needs:** any footage: no tripod and no plate, a phone selfie works. `public/subject.webm`,
`work/tracks/track.json` (`PY KIT/pipeline/track.py <project>`, for the face), depth (the kit's depth.py; the model
downloads on first use). The creator's real number and what it is (NUMBER, TITLE): the note says the number is real, so
never a made-up one. A KARAOKE hide over the window.

**Reuse:** the table at the top of `gen.py`: NUMBER, TITLE, LANDS_ON (one spoken word per glyph, commas and the point
included; empty is a quick run from PRINT_AT, one glyph every PRINT_STEP, for a number that isn't said out loud),
PUNCH_ON, SPOKEN (the microtext; default the words spoken in the window), SERIAL (default the title's initials round
the number's digits), SIGNER (default the pack's creator name, else their handle, else nothing: the kit's placeholder name "reel-kit" never
prints), SIGNER_ROLE, DISCLAIMER, FLIP. Read
off the footage: where the face sits in the oval and how big (FACE_SIZE, FACE_Y; FACE_CX, SRC_CY and SCALE override it,
measured on a still). Every size on the note fits the pack's faces to their plate, so a long number or a wide display
face still fits. `PY fx/<id>/gen.py <project>` (`--stills T` first) writes note.mp4 and fx.html; paste the SOUND lines
it prints: impact-low on the slam, a tick per glyph, shutter when the whole note hits. Delete `work/<id>/` after a
recut (it holds the depth cache).

**Phone take:** works as is. A mirrored front-camera take (text on their clothes reads backwards): FLIP = True. Plain
tops engrave best; a busy pattern below the chin is calmed, but still shows.

**Frame:** the note is a 9:16 object. On 1:1 or 16:9 it is fitted to the frame's height and centred on the pack's dark
ground: a smaller note in the middle of the frame.
