# sketch-words

The words get drawn while the speaker stays live and untouched. Each row in `WORDS` is laid down by a pencil on the
word it is spoken on. A `comp` row is a designer's pencil comp in the pack's display face: two ruled guidelines
overshoot across the frame, the letterforms are drawn stroke by stroke from the font's real outlines (corners split
into hand movements, stems before bowls, three light passes with overshooting corners), quick hatching in the accent
fills them past their edges, one underline last. A `hand` row is plain handwriting from a single-stroke alphabet,
joined where a pen would not lift. Every drawing holds three frames with its own boil, hatch seeds and paper offset;
the tip moves on ones. Two grounds ship: `paper` (a sheet in the pack's light colour behind the speaker, graphite and
accent pencil, the speaker moved down the sheet so the word has headroom) and `footage` (light pencil straight on the
live shot, across the chest, the mic in front).

**Needs**
- Footage: any. Handheld is fine: the paper hides the room, and the footage ground draws on whatever is there.
- The matte (`public/subject.webm`), and the track (`work/tracks/track.json`) for the layout when there is one (the
  matte alone gives a rougher one).
- Optional: the filmed empty room (`work/c/room_<FRAME>.npy` when `work/plate/plate.json` says `"empty"`), so on paper
  the speaker's soft edge comes off the room in closed form. Without it the room near the speaker is estimated from
  the frame itself, and that holds up (a fallback plate is skipped: its fill is least right exactly at the speaker's
  edge). The desk and mic layers when the plate tools found them: they stay in front of the sheet, and the frame
  below the desk's top edge stays live.
- One word worth drawing: "for me, that's X", anything about an idea, a draft or writing. One word, not a list.

**Reuse**
- The FX entry (`layer="cam"`) is the window: from just before the first row to a beat after the comp word, about
  1.5 s. Hard cut in, hard cut out. Hide the captions over it (`KARAOKE["hide"]`): the drawing carries the words.
  gen.py prints that line and the sound.
- Constants at the top of `gen.py`: `WORDS` (rows in spoken order: `text`, `kind`; optional `say` when the spoken
  words differ, and `x`, `base`, `xh` to place a row by hand), `GROUND`, `SHIFT`, `GUIDES`, `HATCH`, `UNDER` (timing
  around the comp word), `SOLID_BELOW`, `UNDER_ROOM`, `BOIL`.
- Read off the footage: when each word is spoken (words.json: a hand row of several words writes each one on its own
  spoken word), the top of the head (the matte) the display word sits on, how far the speaker moves down the sheet
  (just enough for the words to clear the top safe line, at most `SHIFT_MAX` of the height), and on the footage
  ground the face and shoulders: the comp across the chest with its tallest letter under the chin, the handwriting
  either side of the neck word by word (under the comp when the face leaves no room), the desk line.
- Look, from the style pack: the comp in the display face (any glyph), the handwriting's missing letters from the text
  face, the paper `light`, hatching and underline `accent_on_light` on paper; light pencil `light` and the underline
  `accent` on footage. Graphite stays graphite: it is the pencil.
- `--stills 34.4 34.8` renders single frames (about a second each), `--specimen` draws the pack's type alone on paper
  (is it drawn, or is it a font?), `--ground footage` switches the ground without editing the file. Copy the folder
  twice for both grounds in one video.
- Sound: gen.py writes `audio/<id>-pencil.wav` from the drawn motion (rules swipe, letters scratch, hatching chatters,
  the underline swishes; synthesized here) and prints it, placed by its start on the window's first frame.
- Canvas: every position is computed from the frame size, so 1:1 and 16:9 lay out on their own; the paper ground's
  shift is capped at about a fifth of the height.

**Phone take**
Works as it is: the matte and the words are all it needs, and the paper ground hides the room. A selfie's head sits
near the top, so the speaker moves further down the sheet (or the word gets smaller); the footage ground needs the
chest in frame. Hand letters the alphabet doesn't have (capitals, digits) fall back to the text face's medial line,
rougher: write them in lowercase, or set the word as a comp.
