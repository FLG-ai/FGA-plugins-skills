# Showcase: the edit that shows off

The third mode, next to hi-fi and lo-fi. Works on any footage, a 4K sit-down or a phone selfie: the footage only
decides FRAMES and the cutout. Set `STYLE = "showcase"`. The build uses the lo-fi type system (word-by-word captions,
text boxes, overlays, backdrops) plus `FX`: one hand-built motion graphic per beat, from `fx/LIBRARY.md` or new.
Reference: `examples/showcase/edit.py`.

The look is the creator's: `<project>/style/STYLE.md` (its Showcase section) and `modes.showcase` in `style.json`
decide how an emphatic word lands (stamp, slam or scale), which transitions the edit may use, how dense it gets and
what the motif could be (`kit/STYLE_PACK.md`). The lo-fi caption settings (`modes.lofi`) carry over, since showcase
uses the lo-fi type system. Where the pack and this file disagree, the creator's pack wins.

## The rule
Every beat shows off a different editing technique, and every technique is motivated by the words on it. The edit
does what the speaker says, on the word: "warms up" warms the picture, "magazine cover" puts them on a cover,
"tighter cut" cuts tighter, "huge" goes huge. A viewer should feel the range (kinetic type, masks, wipes, recursion,
grids, UI builds, camera moves) without it ever feeling random. Busy is the brief; slop is not. Showing off means
craft, not presets.

Still true: no gradients, glows, neon, glassmorphism, light leaks, lens flares, bokeh, emoji confetti, stock HUD.
Real artifacts over invented ones (the creator's files, screenshots, clips, headshot, the real storyboard, the
real raw take). Text on screen is their words or plain true labels. No imitation of a real brand's UI.

## Beat map (write it before any agent starts)
Read the transcript and give EVERY line a technique, no two adjacent beats the same kind. The menu is the library
(`fx/LIBRARY.md`, plus the creator's own `HOME/fx/LIBRARY.md`); a new technique is welcome when a line asks for one. Effects the creator named
(SKILL.md "Effects by name") go on their lines first; fill the rest around them. Then:
- **One motif** that recurs 3 or 4 times so the video feels designed, not assembled (a prompt bar that types each
  instruction, a sticker that tallies a count, a recurring frame). Same component, same position, same in and out
  move every time.
- **The hook** is the strongest beat: big type readable on frame 0 (it is the thumbnail), building on the words.
- **The payoff lines** get the literal treatment (the script says "bigger captions": the captions get giant).
- **A different transition on every picture cut** (`camera-transitions`: whip, zoom-through, spin, push, drop,
  reveal), camera moves only, 4 to 8 frames a side, never on a cut a graphic already covers. The creator's
  Showcase section can narrow the set.
- **Grades the script asks for** (`GRADES` + `grade-slider` / `mood-curtain` reveals), held until the next one.
- **Sound for every visual event**: each agent reports its SFX.

## Craft rules that came out of building it
- An emphatic single word (never, huge, always, zero) gets the creator's emphatic treatment, by default
  `word-stamp`: the display face, huge, stamped letter by letter behind the head so the head breaks it.
- Type over moving footage splits light/dark against the picture's own brightness (`kinetic-hook` builds the
  masks); never an outline.
- On a beat about the edit itself ("tighter cut"), go full frame and zoom; don't frame the picture in bars.
- Every video-in-video shows visible movement (the speaker AND the screen): pick moments by motion
  (`video-card/energy.py`), never a near-still. Speed-ups of 1.5-2.5x are fine to make movement read.
- "Lots of people are doing this" fills the grid with real screenshots of others doing it (the creator supplies
  them) and keeps the speaker live in the centre tile.
- Type is flat, never tilted, and type standing alone (hook lines, a script page, a card) is centred; two stacked
  lines in the same face match widths.
- A look (film, black and white, a grade) starts on its word and ends with its line. It never freezes the frame:
  the picture keeps playing under it.
- The motif sits in the same place every time (centred unless it is tracking something).
- Labels that follow each other (chapters, steps) never overlap: the old one leaves before the new one lands.
- A highlighter or karaoke mark only ever lands on spoken words, never on headings or stage directions.
- When a line has a physical-world version (a receipt, film running through a gate, a title card, keycaps, grease
  pencil on a contact sheet), reach for it before a generic app screen: it reads as crafted, not assembled.
- A shot that runs into the speaker leaning in to the phone or reaching for the record button ends on the word:
  shorten that one join's J-cut with `J_LEADS` instead of moving KEEP.

## Layers and contract
`kit/FX_BRIEF.md` is the contract every FX agent reads (fx.html + fx.js per `fx/<id>/`, layers behind / cam / top /
over, determinism, footage copies, the `hyperframes check` rules that gate the render). `KARAOKE = dict(huge=[...],
hide=[...])`: `hide` windows hand the words to an effect (`giant-captions`, `word-stamp`). Image floats
(screenshots) work in BEHIND `float` like videos.

## Layered effects (the room, tracks, depth)
The library's layered effects work on the real footage itself: the speaker turns to sand, the room splits behind
them, type circles behind the head, a pencil draws a word between their hands. They pre-render a clip in numpy that
plays frame for frame with the footage, so the lips stay in sync. What they need is in their supply column.
- **One big layered trick per video, not all of them.** They are the payoff beat, not the rhythm: one, maybe two in a
  minute, on the line that earns it, with the lighter library effects around them.
- **The room** (any effect that moves the speaker, reveals the wall or needs `room_<FRAME>`) needs a locked-off shot:
  a camera on a tripod that nobody touches. The default and the clean way is a real empty room: the creator walks out
  at the end and lets the camera record the empty room for 5 seconds (`EMPTY` in edit.py), or films it as a separate
  clip from the same spot (`EMPTY_CLIP`). When the beat map picks a room effect and there is no empty room, the
  storyboard's NEEDS asks for a shot of the background on that beat (5 seconds of the empty room, or a photo from the
  same spot) and, when an image generator is connected, offers to generate it instead (SKILL.md, the needs pass). A
  photo or a generated background goes in with `plate_finish.py --fill`, and the effects treat it like a filmed room.
  Without any of them, plate.py fills what the speaker always covered, and that patch shows the moment the speaker
  moves off their spot: keep those effects to ones where they stay put.
  A phone held in the hand gets no room effects at all.
- **The layered step**, after the matte and before the FX agents (SKILL.md step 4): `plate.py --find-empty` to find
  the empty stretch, `plate.py` and `plate_finish.py` for the room and its layers (plate, desk, the speaker, mic),
  `track.py` for head, hands and shoulders, depth on first use. Every output path is in `kit/FX_BRIEF.md`, "Layered
  effects". Look at `work/plate/check.jpg` before an agent builds on it.

## Workflow differences from hi-fi and lo-fi
- Step 4 is **FX agents** instead of card agents: group the beats into 4 to 8 agents by technique (kinetic type;
  the motif; UI graphics; covers and file drops; footage tricks; grades and transitions; the close), each with its
  own sandbox (`pipeline/fxsandbox.py`). Each brief: FX_BRIEF.md, the library entries to start from, ids, layers and
  windows, the words with output times, where the head is in that shot, the real assets, and "report frames, SFX,
  edit.py changes, snapshot paths". No subagents: build the beats one after another yourself, same brief.
- Review every still at full size before merging; send fixes back to the same agent. Merge each agent's `frames`
  into its FX entry and its SFX into `SOUND.sfx`.
- The storyboard counts each FX with a note as a beat; an FX without a note (transitions) stays out of the beat list.
- The cutout matters more here (things sit behind the head often): `pipeline/matte.py` after `sh setup/setup.sh --matte`
  gives smoother edges than `cutout.py`.

## Sound
Much denser than hi-fi: one sound per visual event (100+ in a minute is normal), each placed at the time of its
event (mix.py lines up the loudest moment), 5 to 14 dB under the voice. Ticks per stamped letter, typing under a
typewriter, clicks on sends, pops on tiles, low hits on stamps, whooshes on transitions. Music stays off unless the
creator hands over a track.
