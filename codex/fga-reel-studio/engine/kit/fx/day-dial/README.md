# day-dial

The frame becomes a clock face with the speaker's head as its hub. On the first word an hour hand (a hairline in the
accent) comes out from behind the head and ticks clockwise, one hour per spoken word, so the clock runs on the voice.
Everything it has passed turns into a flat printed sheet between the speaker and the wall: rings, minute ticks,
numerals and one word in every swept hour. The speaker's live shadow falls on the sheet, its leading edge throws a thin
contact shadow on the real room, a thin minute hand whirls under it with exact motion blur, and the real room still
showing gets darker as the day runs out. The last wedge of real room carries the label and closes on its word with a
small shove. Hold on the full dial, then the hand spins back and unwinds to the live room. The speaker is the live
frame the whole time, so the lips stay in sync.

**Needs**
- Footage: a tripod or a phone on a stand (the sheet is printed in the frame, so a handheld room swims under it). The
  more room above the shoulders, the more dial shows.
- The matte (`public/subject.webm`) and the track (`work/tracks/track.json`: the face places and sizes the dial and
  says where the sheet stops).
- No room plate: the speaker's soft edge comes off the live room just outside it. When the plate tools wrote
  `public/plates/desk_<FRAME>.webm` or `mic_<FRAME>.webm`, the desk and the mic stay in front of the sheet.
- A line about a day or time being eaten, about 13 words from the hand word on (one hour per word). A shorter line
  runs the eleven hours on a clock instead (`SWEEP`), then the last wedge holds its label for a beat and closes.

**Reuse**
- The FX entry (`layer="cam"`) is the window: from just before the hand word to the end of the unwind (the line plus
  about half a second). Captions stay on: the dial's type is texture, the sentence lives in the captions.
- Constants at the top of `gen.py`: `WORD` (set in every swept hour: what the time went to), `LABEL` (the last wedge:
  what got none), `HAND_ON` and `CLOSE_ON` (the cue words; empty = the first word in the window and the hand's 13th
  word), `MIN_WORDS` and `SWEEP`, `UNWIND`, `NIGHT`, `SHADOW`, `HUB` and `DIAL_SCALE` (None = read off the face),
  `LOWER` (the sheet stops this many face heights below the chin, 1.5: the lap, the chair and the desk stay live,
  which is where a matte is weakest; None runs it to the bottom), `NECK` (off; closes the notch between jaw and
  shoulders for a matte that reads a shadowed neck as room).
- Read off the footage: the hub (the middle of the head over the window), the dial's size (the face height, kept
  inside the frame's sides), where the label starts (the top of the head in the matte) and how long it can run (the
  wall left before the frame edge), the neck, the crop. The hours come from words.json.
- Look, from the style pack: the sheet is `light`, the print and the minute hand on it `ink`, the fine hour rules
  `muted_light`, the hour hand `accent`; numerals and the label in the display face, the hour words in the text face,
  sized to fit their hour. Paint on the real room (the label, the minute hand's blur) is `light` on a dark wall and
  `ink` on a bright one, per pixel, so it reads on any room and as night falls on it. The room's light, its night and
  the shadows stay real.
- `PY fx/<id>/gen.py <project> --stills 13.2 15.6` writes stills to `work/<id>/` first. A full run is about half a
  second a frame.
- Sound: gen.py prints the lines: a `tick` per hour, `click` as the movement engages, `clicks-run` under the whirl,
  `tick` and `impact-low` (cut to 0.9 s) on the close, `whoosh-soft` as the hand comes out, and
  `audio/<id>-unwind.wav`, an accelerating ratchet synthesized by gen.py, placed by its start.
- Canvas: the dial sizes itself to the frame's sides, so a 1:1 or 16:9 frame takes a bigger dial if the face allows
  it, and the sheet covers the extra room beside the speaker too.

**Phone take**
A selfie fills the frame with the face, so most of the dial hides behind the head (gen.py warns when the hour words
would sit behind it): hold the phone further back or pick another effect. Handheld works but reads as a graphic
pasted on; a stand is better.
