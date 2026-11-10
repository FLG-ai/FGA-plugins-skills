# double-exposure (cam)
A film's title sequence. A hard cut to a flat field in the creator's dark ground, the speaker's live silhouette on it in
high-contrast mono, and real footage screened into them per pixel: strongest in the chest and shoulders, nothing across
the face, so the eyes and mouth stay clear and in sync. The mono is a colour filter picked for what the speaker wears,
so their top goes dark and works as the window without blowing out the face. On a near-black ground the speaker's
blacks print a step lighter than the field, so dark clothes still read as a figure. The figure fades off into the field at the chest, and a mic and boom in
front of them are painted out with cloth cloned along the clothes' own repeat. The inner footage hard-cuts on the
words, and the line itself runs as title credits: a small role line over a spaced-caps name in the display face. The
picture is pre-rendered (`exposure.mp4`); the credits are live type in fx.js.

**Needs:** any footage with the speaker's head and shoulders in frame, tripod or phone. `public/subject.webm` (the
cutout), `work/tracks/track.json` (`PY KIT/pipeline/track.py <project>`, for the face). The creator's own clips to play
inside them: a few seconds each, with visible motion and a wide frame (a talking head at full size fights the real
face). Put them in `<project>/fx/<id>/inner/` (they fill the slots in name order) or list them in INNER; until then each
slot shows a labelled PLACEHOLDER page. Optional: `public/plates/mic_<FRAME>.webm` from the plate tools; with it the
mic and boom are painted out of the figure, without it they stay. No plate otherwise. A KARAOKE hide over the credits.

**Reuse:** the table at the top of `gen.py`. LOOK (`dark`, or `light`: the paper version on the pack's light ground,
more photographic, far louder in a dark video, and any dark fringe in the matte shows). INNER, one slot per cut: the
word it cuts in on, the clip and its start second, scale, dx, dy and gamma (`None` exposes each clip so its mids land
where the others' do: a bright clip darkens, a dark one lifts), or `kind="type"` for a page typed live in the pack's
text face, sized to fit between the shoulders and the fade (the creator's real words only). `PY fx/<id>/gen.py --survey a.mp4 b.mp4` ranks each clip's
windows by motion; `t0=None` picks the busiest by itself. The credits are fx.js constants: CREDITS (role, its word,
NAME, its word) and OFF_ON. Everything else is read off the footage: the face (track), the shoulders (the matte), the
fade rows (face heights below the chin), the colour filter (the clothes against the face), the clothes' repeat
(measured round the mic). Each has an override for a take the reading gets wrong: FADE, HAND_FADE, MONO_MIX,
KNIT_REPEAT, FRAME. Then `PY fx/<id>/gen.py <project>` (`--stills T` first to check a frame) and paste the SOUND lines
it prints: whoosh-deep on the cut to the field, clicks-run under the first clip (projector chatter), typing under a
typed page, shutter on the last slot.

**Framing:** a medium shot gives the footage the most room. On a tight close-up the chest is a short strip between the
chin and the credits: the footage fades out toward the frame's sides (SIDE_FADE) so it still sits in the body, and the
fade compresses so the figure is gone just under the credits (gen.py warns if the chin itself sits below them). Start
the window on a picture cut when there is one: the hard cut to the field hides it.

**Phone take:** works as is, no tripod or plate. A light or busy top: the filter picks the darkest mix it can; if the
chest still reads bright, lower KNIT.

**Frame:** built for 9:16. On 1:1 or 16:9 it runs on the frame as it is: rows are read off the face, the credits sit at
CREDIT_Y of the frame's height, and the field fills the sides of a wide frame, which reads as a title card.
