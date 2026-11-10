# head-stack

Tiles fall from above the frame on the speaker's words and land on their real moving silhouette: rigid bodies in
pymunk at 240 Hz, the top edge of the matte rebuilt every step as a chain of segments moving at the speaker's actual
velocity. The pile rides the head, slips when they lean, a tile slides off the tower onto the pile below; on the
release word the side piles lose their floor and the tower topples off past the ear, gone by the end of the line.
Crisp tiles are page elements (one tl.set per frame); `shadow.webm` carries the soft contact shadow, which only falls
on the speaker, and true motion blur on the fast frames. The tiles are the pack's light ground with its dark edge,
hairline lip, ink and mono face; the corners follow the pack's radius.

**Needs:** any footage, a tripod helps but isn't needed (the collider follows the matte). The matte
(`public/subject.webm`), `work/tracks/track.json` (face and shoulders), `words.json`, and pymunk in the kit's Python
(setup installs it).

**Run:** `PY fx/<id>/gen.py <project> [<id>]` (layer `top`). The first run searches for a pile that holds on this take
(`search.py`, a few minutes on a laptop: the sim is chaotic, a millimetre at one drop changes the whole pile), writes the
winner into this folder's `sim.py` (`TARGETS`, `SEED`), simulates, and writes `shadow.webm`, `fx.html` and `fx.js`.
Later runs reuse the winner; `--search` looks again (`--n 200` for a wider look). It prints every real contact as an
SFX line.

**Reuse:** the table at the top of `sim.py`.
- `TILES`: the labels in landing order. The first word of a label is set big, the rest small ("9 AM", "10 AM").
- Each tile lands on a word of the window, spread evenly (`LANDS_ON` names them); the pile gives out on a word 0.5 to
  0.9 s before the window ends (`RELEASE_ON`), and the tower goes off the side with more room (`TOPPLE`).
- Read off the footage: the scale of everything (tile size, gravity, the collider) from the face width, so a close-up
  and a wide shot behave alike; where each tile is aimed, relative to the head and the shoulders; whether the shoulders
  can hold tiles at all; how many tiles fit on the head under the top of the frame (a head that sits high gets one
  tile and the rest go on the shoulders).

**Sound:** `tick` when a tile lands on the head or another tile, `pop` on the shoulders, softer ticks on the knocks,
`impact-low` and `whoosh-deep` on the release; gen.py prints them from the sim's real contacts.

**Phone take:** it holds handheld (the collider follows the matte). The shoulders are often out of shot, so every tile
goes on the head and the tower runs out of room fast: use fewer tiles, four on a selfie (gen.py warns when the tower
would leave the top of the frame). The speaker moves more, so a search may need `--n 200`.

**Canvas:** built for 1080x1920 (`W`, `H` in sim.py). On another canvas set them; the rest scales with the face.
