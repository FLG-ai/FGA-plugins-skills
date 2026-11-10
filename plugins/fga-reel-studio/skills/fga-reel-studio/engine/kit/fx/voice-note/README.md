# voice-note

The speaker's line becomes a voice message. A chat bubble with their headshot pops into the clear space above their head (or under the chin, over the chest, when the head fills the top of the frame); its waveform is the project's own voice over that exact line, filling behind a playhead in real time as they say it (each bar plucks as the playhead reaches it), with a running time and the transcript growing word by word in a pill under it. A soft tap on the send button sends it: the bubble lifts and flies off up-right, and a small Delivered label stays a moment. Two skins with the same geometry and motion: dark (the bubble on the pack's dark ground) and light (on its light ground). Generic chat UI, no app imitated; every colour and font comes from the pack (the playhead and send button are the accent).

Layer: `top`. Reach for it on "I had to share it", "I told them", "I sent it", any line about sending or saying something to someone.

## Needs
- Footage: any. No plate, no depth.
- `words.json` (the line and every word time), `assets/voice.wav` from cut.py (else `public/master.wav`; with neither, a stand-in waveform from the word timing, and gen.py says so).
- The matte (`public/subject.webm`, the top of the head) and `work/tracks/track.json` (the chin), to keep the bubble off the face. Without them it sits at full size under the top safe line.
- The creator's headshot (`fxlib.headshot`: `assets/headshot.jpg` in the project, else the style pack's `headshot.jpg`). Without one a neutral person glyph stands in, marked as a placeholder in fx.html, and gen.py says so.
- Captions: the transcript carries the words, so hide the captions over the line (gen.py prints the `KARAOKE["hide"]` entry).

## Reuse
Copy the folder to `<project>/fx/<id>/`, add the FX entry (`layer="top"`, the window around the line), then `PY fx/<id>/gen.py <project> [<id>] [--theme light]`. It writes fx.html and fx.js and prints the hide window, the sounds and good frames. Rerun it whenever the window, the cut or the mix changes.

Read off the project: the line and its word times (words in the window), the waveform (the voice), where the bubble sits (under the top safe line when the head leaves room; under the chin when the head fills the top and the chest has room above the captions band; else the larger of the two, shrunk down to 0.62, and gen.py says the face gets covered for the beat), the headshot, the colours and fonts. gen.py also says when the bubble sits on picture its own skin won't stand out on (a dark skin on a black shirt): run the other skin there. Constants at the top of gen.py: `THEME`, `LINE` (a cleaner transcript than the transcription, same word count), `SEND_ON` (the spoken word the tap lands on; default as the playhead reaches the end), `POP`, the flight timing, `LABEL`, `HEADSHOT`, and the layout (`ROW_X`/`ROW_W` for the chat column, `TOP`/`SCALE` to override what the footage says). The bars fill the column's width, so a narrower column just has fewer bars. Keep lines short: the pill doesn't wrap, it shrinks its type to the bubble's width.

Both skins in one video: two FX entries and two runs (`... <project> vnote-dark` and `... <project> vnote-light --theme light`).

Sound (gen.py prints them with times): `pop` as the bubble pops, `click` on the send, `whoosh-soft` as it flies, `ding` on Delivered.

## Phone take
Nothing changes: a selfie with the head high gets the bubble under the chin, or a smaller one (gen.py says which). Built for the 1080x1920 canvas: a 1:1 cut taken from the middle of the 9:16 loses the top 420 px, where the bubble sits, so set `TOP` to about 440 for a square version.
