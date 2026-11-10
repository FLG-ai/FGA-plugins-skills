# search-suggest

A search box types the question as the speaker says it, and the dropdown answers with what people really search. A generic search pill (a thin magnifier, no search engine's logo or colours: the pack's light ground and text face) drops in above the head on the first word. The query types in bursts on the speaker's words, a letter a frame with the caret leading, and the suggestion rows under it swap live per prefix with the part the user hasn't typed in bold, as real search UI does. The rows float in the room behind the speaker: the head cuts through the panel and throws a soft shadow on it (which also keeps a light cap or hair apart from a light panel). On the last word the top row highlights, a soft tap presses it, and it all lifts away.

Layer: `behind`, with CUT_WINDOWS over the window (gen.py prints them). A picture cut inside the window is fine: the cutout windows split around it, skipping the cut frame, and the rows sit that one frame out (on the cut frame the footage can still show the shot before, and a cutout on it doubles the head). Reach for it on "I needed to...", "how do I...", anything people actually search.

## Needs
- Footage: any. The speaker's matte (`public/subject.webm`) for the cutout, the shadow and to measure the head.
- `words.json` (every burst of letters lands on a spoken word).
- The network the first time: gen.py fetches public autocomplete for every prefix of the query and saves it with the date in `suggest.json` next to fx.html. The wording is never edited and the order is as returned; reruns keep that snapshot, `--refresh` fetches again (autocomplete moves with the date and the place).

## Reuse
Copy the folder to `<project>/fx/<id>/`, set the table at the top of gen.py, then `PY fx/<id>/gen.py <project> [<id>] [--refresh]`. It writes fx.html and fx.js, prints every row it will show with its time, the sounds (a tick per letter, a softer click on each space) and good frames.

- `QUERY`: `[(query word, the spoken word it types on)]`, for a query that isn't word for word what is said (`[("how", "needed"), ("to", "to"), ...]`). Empty: the words that start inside the window, each typing on itself.
- Read every printed row before you render: real autocomplete can surface names, brands or worse. Put a prefix in `SKIP` to hold the previous rows instead, or pick another query. `OPEN_AFTER` (the dropdown opens once that many words are typed), `SWAP` (frames between swaps), `N_ROWS`, `TAP` / `LIFT` (frames after the last letter).
- Read off the project: the pill sits under the top safe line and the whole box scales down (to 0.72) until the pill and the top row clear the top of the head over the window; the rest of the rows pass behind the head on purpose. `SCALE` overrides it. `SHADOW` (dx, dy, blur, opacity) is the head's shadow on the panel.

Sound (gen.py prints them with times): `whoosh-soft` as the pill lands, `tick` per letter and `click` per space, `click` on the tap, `whoosh-soft` as it lifts.

## Phone take
No CUTS trouble: the matte is all it needs. Handheld, set `SHADOW` dx, dy near 0. If the head sits so high the top row can't clear it even scaled (gen.py says so), use layer `top` with `N_ROWS = 2` so the panel stops above the head. Built for the 1080x1920 canvas: a 1:1 cut from the middle of the 9:16 loses the top 420 px, where the pill sits, so set `PILL_Y` to about 440 for a square version.
