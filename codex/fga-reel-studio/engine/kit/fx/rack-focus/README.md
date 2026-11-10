# rack-focus (cam)

Nothing is added. On the cue word the room falls out of focus and dims behind the speaker, as if a lens racked to
their eyes and someone brought the lights down, while they stay razor sharp. The blur is a real lens disc in linear
light, sized per pixel from depth (the far wall most, a chair right behind them less, a desk in front some), the room
grows 1.5% as it racks (focus breathing), and a desk in front of them goes soft over them. One clip of the live shot,
so the lips are the footage. It hard-cuts out at the end of the window: end it on a picture cut or the end of the line.

**Needs:** a locked-off shot (tripod, or a phone that doesn't move), `public/subject.webm` (cutout.py or matte.py),
`words.json`. Best with the plate tools' room (`room_<FRAME>.npy`, built from the empty-room stretch the creator
films); without it the room is taken from the window's own frames, which holds on a locked-off shot. The desk layer
(`public/plates/desk_<FRAME>.webm`) when there is one, `work/tracks/track.json` when there is one (it keeps the focus
on the face). The depth model, which `pipeline/depth.py` downloads on first use. No assets from the creator.

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes `<id>.mp4`, `fx.html` and `fx.js` in the project's copy
(`--stills 18.3 19.0` writes stills to `work/fx/<id>/` and nothing else). Rerun it whenever the window or the cut
moves. Edit.py: `dict(id="rack-focus", layer="cam", at=..., end=...)`. No sound on purpose: a viewer shouldn't know
why it suddenly felt expensive.

**Reuse:** the table at the top of `gen.py`. `RACK_ON` is the two cue words (it starts on the first, lands on the
second); without them it starts on the first word in the window and lands on the word nearest 62% in. `DIM`,
`BREATH`, `DESK_R` are the look. What reads off the footage: the speaker's depth (the median depth of their face on a
live frame, the room's depth mapped onto it), how far the wall is, the patch they always cover (refilled from what is
around it, so the blur can't drag a hidden chair out round their outline), the desk, and `R_FAR` (30 px for a camera
on a tripod, 18 px for a phone take). Set `FOCUS_DEPTH` or `R_FAR` to override. What the window's own frames show of
the room wins over the plate, so a stale plate or a fallback plate's inpainted patch never shows. `KEEP_NEAR`: what
the matte missed at the speaker's distance (a book in their hands, the chair they sit in) is found on each frame's
depth and stays sharp. The first frame is the live picture itself (it lands within the footage's own noise at the
cut-in), so it can start anywhere; on a fallback plate (no empty room filmed) it holds as well, because the speaker
stays put.

**Phone take:** works the same if the phone is locked off; it picks the smaller blur on its own, because a selfie
lens is shallow already. Handheld is out: the room has to hold still. On a 1:1 or 16:9 canvas it needs no changes
(it reads the frame size from clean.mp4); the kit renders 9:16 today.
