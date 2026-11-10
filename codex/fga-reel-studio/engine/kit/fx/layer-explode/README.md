# layer-explode (cam)

The live frame swings round in 3D (a real motion-control move: spring-driven pan, tilt and dolly, the camera banks
into the turn), the sheets slide apart on the words and the shot holds as a true exploded view of THIS edit: ROOM,
TYPE (the cue words in the display face, rising through masks on their words), ME (the speaker, live, lips in sync),
CAPTIONS (the real caption box, word by word) and SOUND (the video's real waveform, playhead running). It folds back
flat on the frame, so the seam is invisible. The rig is filmed through the real renderer with a 180 degree shutter
(real motion blur), then plays as one clip. Hairlines, tabs, type and the played bars are the pack's light colour, the
bars its accent, the void behind the sheets its dark ground, the tabs its mono face.

**Needs:** a locked-off shot, `public/subject.webm`, `words.json`, `assets/voice.wav`, and the plate tools' room
(`work/c/room_<FRAME>.npy`, built from the empty-room stretch the creator films): when ME leaves the ROOM sheet, the
empty room is what shows behind them. On a fallback plate (no empty room filmed) layers.py warns: the ROOM sheet shows
the plate's guess where the speaker sat for as long as ME is lifted off it. Without plates `layers.py` builds the room
from the window's own frames, with the same guess behind the speaker. Film the empty room. `work/tracks/track.json`
(optional) puts the TYPE block on the side away from the face. No assets from the creator.

**Run, in order:** `layers.py` (the room clips), `gen.py` (the rig; prints the SOUND lines), `calib.py` once per
video (three short renders, then the LUT that cancels the few levels the filmed path shifts), `prerender.py --passes 24`
(about 3 minutes; `--passes 8` to review). All take `<project> [<id>]`; work goes to `work/fx/<id>/`, the clip and its
`fx.html` / `fx.js` to `fx/<id>/`. Edit.py: `dict(id="layer-explode", layer="cam", at=..., end=...)` and a KARAOKE hide
over the same window (the CAPTIONS sheet carries the words, a line still on screen at the window's start included;
gen.py warns when the hide is missing). No camera zoom, push or settle inside the window (the clip already holds the
move), and no picture cut inside it. Rerun gen.py and prerender.py whenever the window or the cut moves.

**Reuse:** the tables at the top of `gen.py` and `rig_js.py`. `WORDS` is the TYPE sheet as `(text, cue word)` pairs
(default: the first three words spoken in the window): the swing starts on the first, the back sheets (ROOM, TYPE)
leave on the second, the front ones (CAPTIONS, SOUND) on the third. It folds back over the last 29% of the window (at
most 0.82 s) and lands flat one frame before the end; a window shorter than 2.8 s runs the springs faster. `POSE` (the
exploded camera), `Z` (plane depths), `LABELS` and `TABS` (the tabs on the sheets) are the look. What reads off the
footage: the room, the caption lines exactly as the build groups them (`build.karaoke_lines`), the waveform, which
side the TYPE block goes (`TYPE_BOX` pins it). On a close shot, where the head would hide more than 30% of the TYPE
block, gen.py warns: the words read as fragments behind the head, so use a wider window, fewer or shorter `WORDS`, or
`TYPE_BOX`. `ROOM_LIFT` in `layers.py` nudges the room sheet's levels if it sits off the live room. A mic in the
speaker's matte stays on the ME sheet: there is no separate MIC sheet, so the stack never shows two.

**Phone take:** a phone that doesn't move works like a tripod. Handheld is out (the room sheet has to hold still);
if the shot moves, keep only ME, CAPTIONS and SOUND over a ground instead of the room. Built for 1080x1920: on another
canvas gen.py stops.
