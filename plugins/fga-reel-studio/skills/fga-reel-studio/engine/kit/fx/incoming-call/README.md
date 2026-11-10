# incoming-call

The speaker's phone rings mid-sentence and they hang up on it. A call banner drops in on a word and buzzes in two-burst pairs like a phone on a desk (a tiny sideways jitter, the answer handset rocking), and sits there being ignored while the speaker keeps talking. On the word a soft tap lands on decline, the banner squashes under the finger and flies off up, and a small "Call declined" pill lives for about half a second. Played deadpan: the comedy is the speaker not reacting at all. The banner is a phone's own call screen, so it keeps a phone's colours (a dark banner, red decline, green accept, a grey contact glyph) whatever the pack; the type is the pack's text face. Generic, no phone's UI copied: the handset and person glyphs are drawn by gen.py.

Layer: `top`. Reach for it on a line that dismisses someone or something: "that isn't for you", "I stopped answering", "who needs an editor". Captions stay on.

## Needs
- Footage: any. No plate, matte or depth.
- `words.json` for the cue words.
- `work/tracks/track.json` (or the matte) to keep the banner above the eyes; without either it sits at full size under the top safe line.
- The buzz: `audio/phone-buzz.wav`, synthesized from scratch by `mk_buzz.py` (5 frames on, 2 off, 5 on, matching the jitter). gen.py writes it into the project when it's missing; `PY fx/<id>/mk_buzz.py <project>` rewrites it.

## Reuse
Copy the folder to `<project>/fx/<id>/`, set the table at the top of gen.py, then `PY fx/<id>/gen.py <project> [<id>]`. It writes fx.html and fx.js and prints the sounds and good frames.

- `CALLER` (a role, never a real person's name or number; "Your Video Editor" by default), `LABEL`, `PILL`.
- Words: `LAND_ON` (the banner lands and the first buzz starts), `TAP_ON` (decline), `GONE_ON` (the pill is gone by it). `RING_EVERY` keeps the buzz pairs evenly spaced, as a real motor does, as many as fit before the tap: they just happen to hit words. Pick a line the speaker keeps going through; it plays best where the music drops out.
- Read off the project: the banner sits under the top safe line when it clears the brow (the eyes on track.json; it may cover hair or a cap crown), else under the chin over the chest when the face fills the top of the frame, else the larger space shrunk to 0.7 (gen.py says which). The pill sits just under where the banner was (`PILL_TOP`). `CY`, `SCALE` override.
- The colours under "the phone's own colours" are a phone's, not the creator's look; leave them unless the video is about a particular phone.

Sound (gen.py prints them with times): `phone-buzz` (the project's own synthesized file) on each pair, `click` on the decline, `whoosh-soft` as the banner flies, a quiet `pop` on the pill.

## Phone take
Nothing changes. Without a cap the banner still stops above the brow; with the face filling the top of the frame it lands under the chin. Built for the 1080x1920 canvas: a 1:1 cut from the middle of the 9:16 loses the top 420 px, where the banner sits, so set `CY` to about 440 for a square version.
