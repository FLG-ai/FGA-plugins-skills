# FX brief: hand-built motion graphics inside a video (showcase mode)

You build one or more motion-graphic beats (`edit.FX`) for a talking-head video. Start from the closest effect in
`KIT/fx/LIBRARY.md` or the creator's own library (`HOME/fx/LIBRARY.md`; on the same name theirs wins, and your
prompt gives the folder): copy its folder to `<project>/fx/<id>/` (no renaming needed: `{{ID}}` becomes your id) and
change the words, the beat times and the assets. Each effect lives in its own folder and is composited into the
video's single HyperFrames/GSAP timeline by `pipeline/build.py`. You never touch the footage timing, the cut or
another agent's folder.

Tools: when your prompt gives a `PATH=` prefix (the kit's own ffmpeg and Node), start every shell command with it.

Read first: `<project>/style/STYLE.md` (the creator's style, including its Showcase section) and `KIT/kit/TOKENS.md`.

## The contract
Folder: `<project>/fx/<id>/`
- `fx.html`: markup plus one `<style>` block. Scope every selector under `#{{ID}}` or prefix ids and classes with
  `{{ID}}-`. The build wraps it in `<div id="<id>" class="layer fx">` (1080x1920, absolute, top-left 0,0) and shows
  that wrapper from A to B. Don't use `class="layer"` / `full` inside unless you mean full-frame.
- `fx.js`: plain JS appended inside the video's timeline code, wrapped as `(function (A, B) { ... })(start, end)`.
  In scope: `tl` (the paused master timeline), `gsap`, `q(t)` (snaps a time onto its frame: ALWAYS position tweens
  with `q(...)`), `on(sel, t)`, `off(sel, t)`, `A`, `B` (start and end in seconds on the output timeline), `CUTS`
  (the picture cuts), `WORDS` (`[start, end, text]` per word), `wordAt(text, after)` (the start of the first word
  matching `text` at or after `after`, or null), `wordSpan(text, after)` (its `[start, end]`, or null), `FXS` (every
  effect's `{id, layer, at, end}`) and `LOOKS` (the named grades: name -> CSS filter).
- Key beats to words where you can (`var tSend = wordAt('sentence', A)`), with a relative fallback, and keep every
  other beat time relative to `A` as a named constant at the top of fx.js (`var T = { type: 0.40, send: 1.10 }`,
  used as `q(A + T.send)`). Put every word or label in a constant at the top too. Copying the effect to a new video
  should mean changing those constants, nothing else.
- `{{ID}}` in fx.html and fx.js becomes the entry's id. `{{T0}}`..`{{T9}}` in fx.html become unique
  `data-track-index` values: use them for every `<video>`.
- Assets (png/jpg/svg/mp4/webm) go in the same folder and are published at `fx/<id>/<file>`: reference them as
  `fx/{{ID}}/<file>`.
- Layers (edit.FX `layer`): `behind` = under the speaker's cutout, inside the camera (type behind the head; needs a
  CUT_WINDOWS entry over its window, which never crosses a picture cut and starts a frame after one: on the cut
  frame itself the cutout still holds the shot before, a doubled head for one frame); `cam` = on the camera above the cutout
  (extra copies of the footage, wipes, grids); `top` = above the speaker, under the captions; `over` = above
  everything (full-frame transitions, effects that carry the words).

## Look: the creator's, through tokens
- Every colour and font is a token (`var(--c-accent)`, `var(--font-display)`; in JS
  `getComputedStyle(document.documentElement).getPropertyValue('--c-accent')`). No hex, rgb or font names in an effect.
  The same meanings as everywhere: accent = emphasis, negative = losses or "no", positive = gains or "yes".
- The creator's STYLE.md Showcase section sets the treatment for an emphatic word, the transition set, the motif and
  how dense the edit gets. Follow it over anything in the library.
- Never: gradients, glows, neon, glassmorphism, orbs, lens flares, light leaks, bokeh, drop-shadow halos, emoji
  confetti, stock "tech HUD". Shadows only soft and functional (a card lifting off the footage). No outline on type
  over footage: split it light/dark against the picture instead (see `kinetic-hook`).
- Real artifacts over invented ones: the creator's own files, screenshots, clips, headshot. Text on screen is their
  words or plain true labels. No made-up stats, no imitation of a real brand's UI: build generic, well-made
  components. Library placeholders are labelled as placeholders.
- Motion: purposeful and fast. power3 / expo / back(1.4-1.8) eases, 0.15-0.45s moves, staggered reveals, masks
  (clip-path / overflow hidden) for type, overshoot sparingly. Every move lands ON its word (words.json times).
- Safe zones on 1080x1920: top 220, sides 35, nothing below y 1470, keep x < 980 from y 1155 down. The caption band
  (y 1300-1470) belongs to the captions: keep `top` and `behind` graphics out of it unless the effect carries the
  words (then the edit hides the captions there with `KARAOKE["hide"]`).
- One idea per beat, legible in 1-2 seconds. Covering the face for a beat is fine when the graphic is the point.

## Determinism (it renders frame by frame by seeking)
- Everything is a tween or set on `tl` at an absolute time `q(t)`. No CSS animations or transitions, no timers, no
  `Math.random()` (seed your own: `function rnd(i){ var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }`).
- Hide what starts later with `gsap.set(sel, {opacity: 0})` at build time, then `tl.set` / `fromTo` it in.
- `fromTo` after time 0 always carries `immediateRender: false`.
- Tween `clip-path` with `fromTo` only: a `.to` reads the current value back from the browser, which reports a full
  inset in short form, and the tween jumps.
- Typewriters: `tl.set` the text (or a width / clip) per character at `q(t0 + i * dt)`; never `onUpdate` slicing.
- Counters: `tl.set` per frame, or tween an object and render through a per-frame `tl.set` loop.
- `hyperframes check` gates the render. Every `<video>` needs its own `id` (without one it renders frozen); never
  tween layout props (left, top, letterSpacing): use x / y / scale; never give an element a CSS `transform` that
  GSAP also tweens (set it with `gsap.set`); mark intentional overlaps with `data-layout-allow-overlap` (and
  `data-layout-allow-occlusion`) on the text elements themselves: the layout audit doesn't read them off the
  build's wrapper div.

## Media timing (clips, footage copies)
The renderer reads media timing from the static HTML, so write it with template variables relative to where the
effect sits (the build fills them in; never hard-code absolute times):
- `{{START}}`, `{{START+0.77}}`: `data-start` for a clip that starts at A (or 0.77 s after A), frame-snapped.
- `{{SYNC}}`, `{{SYNC+0.77}}`: `data-media-start` for a copy of `clean.mp4` starting there, so it shows the same
  frame as the main picture (lips in sync).
- Hide a footage copy with opacity 0 or `display:none`, never `visibility:hidden`: the renderer still draws a video
  under a hidden ancestor.
- `{{DUR}}`, `{{DUR-0.133}}`: the effect's length (frames / 30), or less, for a clip that starts late and should
  end with the effect. A clip with its own length gives its own `data-duration`.

A second copy of the video's own footage: `<video id="{{ID}}-v0" class="{{ID}}-x g" src="clean.mp4" muted playsinline
data-start="{{START}}" data-media-start="{{SYNC}}" data-duration="{{DUR}}" data-track-index="{{T0}}">` shows the same
frame as the main picture. `class="g"` inherits the live grade. Two copies with identical start and
duration trip a duplicate-media lint: stagger one by a frame. Scale or translate the copy or its wrapper with GSAP;
never re-time it. Prove sync on a snapshot (no ghosting where it overlaps the main picture).

## Layered effects (pre-rendered on the real footage)
Some effects can't be drawn in the browser: the speaker turns to sand, the room splits behind them, type circles
behind the head. These pre-render a clip with numpy in the effect's own `gen.py` and play it as a `<video>` in the
timeline. Run it with PY: `PY <project>/fx/<id>/gen.py <project> [<id>]` (`<id>` defaults to the folder name).
`import fxlib` works from any folder with PY (setup puts the kit's pipeline on its path), and so do `import depth`
and the rest of `KIT/pipeline`.
- **Frame n is video frame n.** `for n, rgb in fxlib.frames(P, a, b)` reads clean.mp4 at true levels (uint8 HxWx3,
  n = round(t * 30)); `fxlib.alpha(P, a, b)` / `fxlib.rgba(P, a, b)` read the matte. Write with `fxlib.Writer(path)`:
  all-intra H.264, every frame a keyframe, so the renderer's seeks land exactly and the lips stay in sync;
  `fxlib.Writer(path, alpha=True)` writes VP9 with alpha (.webm). The H.264 path lands on the live picture's exact
  levels; the browser decodes VP9 with alpha on another path that lands about half a level to a level off (more in
  saturated colour). So a clip that takes over the whole frame from the live picture is H.264 (opaque, no alpha);
  keep alpha for layers that only cover part of it. Clips the effect plays go in `<project>/fx/<id>/` (published
  as `fx/<id>/<file>`); caches and intermediates go in `<project>/work/<id>/`, because everything in `fx/<id>/` but
  .py, .md, fx.html, fx.js and the library's preview.mp4 / preview.jpg is published.
- **The tag.** `fxlib.tag(id, "fx/<id>/<file>", a, b, "g", "{{T0}}", style)` writes the `<video>` for a clip made for
  window a..b; gen.py writes it into fx.html. `class="g"` on every clip that holds the live picture: it takes the live
  grade (the pack's grade, GRADES, black and white); without it a full-frame clip lands about 7 levels off the
  footage. `{{T0}}`..`{{T9}}` give each video its own track.
- **The window and the words.** `F = fxlib.entry(P, id)` is the effect's edit.FX entry ("end" resolved to seconds);
  `fxlib.word_at(P, "word", after)` is a word's start (like `wordAt`), `fxlib.words(P)` all of them. Key every beat to
  a word with a relative fallback, as in fx.js.
- **Where the speaker is**: `fxlib.tracks(P)["frames"][n]` from `track.py` (`work/tracks/track.json`, canvas px, per
  video frame): `face` {cx, cy, w, h, top, chin, mouth, open, eyes, forehead, nose, roll, yaw, pitch} or null, `hands`
  [{side, wrist, palm, thumb, index, middle, pinky, pinch, span}], `pose` {ls, rs, le, re, lw, rw} or null. Read every
  position from here or the matte, never from numbers measured on another take.
- **Depth**: `import depth; depth.infer(rgb[, side])` -> float32 HxW 0..1, near = 1, normalised per image (`side`:
  the longer side the model sees, 518 by default). It flickers: smooth over frames. The model (99 MB) downloads the
  first time. On a Mac it runs on the neural engine, where several depth jobs at once queue for minutes: when other
  agents may run depth at the same time, run your gen.py with `REEL_KIT_DEPTH_CPU=1` (CPU only).
- **The room** (a locked-off shot, after `plate.py` and `plate_finish.py`; `work/plate/plate.json` says `"mode":
  "empty"` when it came from a real empty room, `"filled"` when a photo or a generated background filled the patch the
  take never saw (treat it as the room), `"fallback"` when the patch the speaker always covered is filled and
  WILL show if they move: then don't move them off their spot, and say so in your report). `frame =
  fxlib.crop_at(P, a)` is the FRAMES crop at the window's start. Every file is per crop and colour matched to
  clean.mp4:
  - `fxlib.scene(prefix, a, b, frame)`: four `<video>` tags for a `cam` effect, in stack order: the room
    (`plates/plate_<FRAME>.mp4`), the desk (`plates/desk_<FRAME>.webm`), the speaker (`subject.webm`), the mic
    (`plates/mic_<FRAME>.webm`). On its own the stack looks exactly like the live shot; move any of them with GSAP.
    A shoot with nothing in front of the speaker has transparent desk and mic layers.
  - `fxlib.room(P, frame)`: the room as the take saw it (`work/c/room_<FRAME>.npy`, float32 HxWx3 RGB at live levels):
    use it while the speaker is in place, it can't pop against the live shot. `fxlib.room(P, frame, empty=True)`
    (`work/c/room_empty_<FRAME>.npy`): the empty room alone, for when they've left or moved (things they moved, like a
    chair, can sit differently: cut to it on a big move).
  - Every file, by folder. `public/plates/`: `plate_<FRAME>.mp4` (+ `.jpg`), `desk_<FRAME>.webm`, `mic_<FRAME>.webm`.
    `work/c/`: `room_<FRAME>.npy`, `room_empty_<FRAME>.npy`, `lut_<FRAME>.npy` (256x3, plate value -> live level),
    `mic_<FRAME>.npy` (HxWx5: the foreground's live colour, its alpha, solid alpha), `plate_clean.png` and
    `plate_pure.png` (the room and the empty room at the source's size, BGR). `work/plate/`: `plate_src.png` (the
    room, source size), `room_pure.png` (the empty room, source size), `hole.png` (what the take never saw, 255),
    `plate.json` (mode, empty-room source, level match), `near.png` (depth's nearest), `fg.png` (desk green, mic
    blue), `check.jpg` (per crop: live, room, empty room, layers).
- **The look is the pack's.** `S = fxlib.pack(P)`: `S["colors"][role]` is (r, g, b, a) 0-255 for every colour role
  in style.json (`series` is a list), `S["creator"]` is {name, handle, site} (empty strings when unset),
  `S["fonts"][role]` is the pack's font entry plus `path`, its TTF in `<project>/style/fonts/`;
  `fxlib.font(P, role, size)` is a PIL font for display | text | mono | caption at the pack's weight;
  `fxlib.headshot(P)` is the creator's photo (`<project>/assets/headshot.*`, else the pack's `headshot.jpg`), or
  None: then draw a labelled placeholder. Colour that
  belongs to a real object stays real (newsprint, banknote ink, paper, a wooden desk, a phone's call screen, the
  room's own light); the creator's look (type, labels, grounds, accents, UI chrome) comes from the pack. Never bake in
  a creator's name, numbers, titles or links: identity from the pack, content in constants at the top of gen.py.
- **See it move.** `PY KIT/pipeline/fxclip.py <project> <name> --only <ids> --from S --to E [--fresh]` renders just
  that slice through the real renderer with sound, in under a minute: `<project>/work/sandbox/<name>/clips/S-E.mp4`
  and a contact sheet `.jpg`. Colour in these clips is final colour; snapshots show live footage about 8 levels dark,
  so judge seams and colour in clips. Check the first and last frame of the window for pops.
- One big layered trick per video, not all of them.

## Your loop (phase 1: stills, no render)
1. Read `<project>/edit.py` (FX entries, times), `<project>/words.json` (word times on the output timeline), and
   look at the footage under your window: `ffmpeg -ss <t> -i <project>/public/clean.mp4 -frames:v 1 -vf scale=540:-1 x.jpg`.
2. Build `fx/<id>/fx.html` + `fx.js` (+ assets).
3. Preview in your own sandbox: `PY KIT/pipeline/fxsandbox.py <project> <your-name> --only <ids> --at t1 t2 ...`
   (edit `work/sandbox/<your-name>/edit.py` to try GRADES / CUT_WINDOWS / CAMERA changes there). Read every
   snapshot at full size: key frames AND the in and out frames (no pop, no flash, nothing clipped, no ghosting).
   Run `npx -y hyperframes@0.8.139 check` in `<sandbox>/public` before you report.
4. Report back (short): per id, what it does beat by beat; 2-3 absolute times that sell it (`frames=[...]`); SFX
   as `(time, name, dB, what)` with the time of the visual event (mix.py lines up each sound's loudest moment);
   any edit.py change it needs (CUT_WINDOWS, GRADES, CAMERA, KARAOKE hide, FX at / end); the paths of your best stills.

SFX names (`KIT/audio/SFX.md` has what each sounds like and a starting level): whoosh, whoosh-soft, whoosh-deep,
whoosh-long, pop, click, tick, clicks-run, typing, key, ding, shutter, stamp, impact-low, boom-low, riser,
riser-long, drum-hit, scratch, switch-off.
