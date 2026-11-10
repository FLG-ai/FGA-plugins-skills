# follow-chip

The sign-off. A profile chip rises over the top edge of the captions band just before the speaker says "make sure to follow": their headshot, their handle and a Follow button. On "follow" the button presses, the Follow label slides out and Following slides in with a check drawing itself; on "daily" a short line slides in under the handle. It holds to the last frame. Generic profile UI in the creator's text-box colours (the same chip comment-cta carries), the type is the pack's text face, the corners follow the pack's radius.

Layer: `top`, window from the line to `"end"`. Reach for it on "follow me", "make sure to follow", the sign-off of any video. Captions stay on.

## Needs
- Footage: any. No matte, tracks, depth or plate.
- `words.json` (fx.js finds the cue words itself with `wordAt`).
- The creator's handle in their style pack (`creator.handle`, else `site`, else `name`) and their headshot (`fxlib.headshot`: `assets/headshot.jpg` in the project, else the style pack's `headshot.jpg`). `gen.py` puts both on the chip. Without a headshot a neutral person glyph stands in, marked as a placeholder; without a handle the chip says `@yourhandle`.

## Reuse
Copy the folder to `<project>/fx/<id>/`, add `dict(id=..., layer="top", at=<just before "make">, end="end")`, then `PY fx/<id>/gen.py <project> [<id>]`. It writes the HANDLE and HEADSHOT block at the top of fx.js (and copies the photo in), prints when each beat lands on this video's words, the sounds, and warns if the chin comes down behind the chip or the press lands as the chip arrives ("Follow me...": put the chip on "Follow" and the press on "me"). Rerun it when the creator changes their handle or photo.

The rest are constants at the top of fx.js: `SUB` (the line under the handle; it only comes in when `SUB_ON` is spoken, so the chip never claims a line the speaker didn't say), `LABELS`, the cue words `CHIP_ON` / `PRESS_ON` / `SUB_ON` and their fallbacks in `T`. A long handle shrinks to fit once the pack's fonts load.

Sound (gen.py prints them with times): `pop` as the chip arrives, `click` on the press, a softer `pop` as it turns to Following, `tick` on the line under the handle.

If the speaker looks down to stop the recording at the end, end the video before it (or hold a good frame under the chip with a camera effect); the chip itself doesn't hide it.

## Phone take
Nothing changes. On a low framing where the chin reaches y 1150, gen.py says so: end the window earlier or move `.fc-chip` up in fx.html. Built for the 1080x1920 canvas; a 1:1 cut from the middle of the 9:16 keeps the chip (it sits at y 1150 to 1270).
