---
name: reel-kit
description: Turns one talking-head clip into a finished vertical video (Reels, TikTok, Shorts) in the creator's own style - a J-cut edit, captions, type behind their head, hand-built motion graphics and sound effects - with an interactive storyboard they comment on before anything renders. Three modes - hi-fi (produced, full-screen data cards), lo-fi (phone selfie, overlays, word-by-word captions) and showcase (a different hand-built motion graphic on every beat). The first run builds their style from a brand file, 2 or 3 inspiration videos, or four questions, and it shapes how all three modes edit. Use when someone asks to edit a talking-head video or reel, types /reel-kit (or /reel-kit:hifi, /reel-kit:lofi, /reel-kit:showcase, /reel-kit:effect, /reel-kit:effect-list, /reel-kit:trials, /reel-kit:reel-kit-setup, /reel-kit:reel-kit-style), $reel-kit or @reel-kit, wants to set up or change their video style, wants an effect from someone else's video, or wants to test versions of a reel as Instagram Trial Reels.
---

# reel-kit

Raw take in, finished vertical video out, in two steps: a storyboard the creator comments on, then the render.
The look belongs to the creator (their style pack); this kit is the structure: how the edit cuts, where type goes,
how cards are built, how sound sits under the voice.

## Paths
- `KIT` = the folder holding this file (in Claude Code: `${CLAUDE_SKILL_DIR}`). It can be read-only, and as a plugin
  it is replaced on every update: nothing is ever written into it.
- `HOME` = `$REEL_KIT_HOME`, default `~/reel-kit`: the style pack (`HOME/style/`), projects
  (`HOME/projects/<slug>/`) and what setup installs (`HOME/.venv/`, `HOME/vendor/`, `HOME/tools/`, `HOME/models/`,
  and `HOME/.venv-mp/` for tracking, made the first time an effect needs it).
- The creator's own library: `HOME/fx/` (effects) and `HOME/cards/` (cards), each with its own `LIBRARY.md` in the
  same table as the kit's. It holds effects and cards they made and their changed versions of the kit's, and updates
  never touch it. Wherever this kit says `KIT/fx/LIBRARY.md` or `KIT/cards/LIBRARY.md`, read the `HOME` one too: a
  folder in `HOME` with the same name as one in `KIT` is the creator's version and is the one to use. When they want
  an effect or card kept for later videos ("save this effect", "add it to my effects", "always do the receipt
  printer like this"), copy the project's folder to `HOME/fx/<name>/` (or `HOME/cards/<name>/`) and add or update its
  row in that `LIBRARY.md`. Never edit anything in `KIT`.
- `PY` = `HOME/.venv/bin/python` (Windows: `HOME/.venv/Scripts/python.exe`). Run every pipeline script with `PY`;
  each takes the project folder first. The pipeline finds the kit's own tools by itself.
- `BIN` = `HOME/tools/bin`: on a computer without them, setup fetches ffmpeg, ffprobe and Node into it (no admin
  password, nothing system-wide). When `BIN` exists, start every shell command that calls ffmpeg, ffprobe, npx or
  `HF` with `PATH="BIN:$PATH"`, and give card and FX agents that same prefix in their prompts.
- `HF` = `npx -y hyperframes@0.8.139`, pinned so every video renders the same way.
- The creator never installs anything by hand. Setup fetches what's missing; when a fix needs a command, run it
  yourself and tell them in plain words what it's doing.

## What this host can do (check once, adapt, never ask the creator about it)
- **A terminal and files**: required. The kit runs Python, ffmpeg and Node on the creator's computer. A host
  without one (a chat app with no computer access): say plainly that this skill needs an agent that can run
  commands on their machine (Claude Code, Codex, Claude Cowork with code execution on, or ChatGPT Work in the
  desktop app), then stop.
- **A sandbox** (Codex runs commands in one by default, and so does ChatGPT Work, through the Codex built into
  it): rendering launches a headless browser, which Codex's macOS sandbox blocks, and setup needs the network. Setup says so when it runs inside one. Ask the creator to
  give the session full access (Codex: Full access in the permissions menu, or `codex --sandbox
  danger-full-access`), or to approve the render commands running outside the sandbox.
- **Granted folders only** (Claude Cowork runs in a Linux VM on the creator's computer; ChatGPT Work works in a
  folder they open): set `REEL_KIT_HOME` to a folder inside the one they granted (`export
  REEL_KIT_HOME=<granted folder>/reel-kit` in every command) so the style pack, projects and tools stay on their
  computer between sessions, and put the finished videos there too. Renders in a VM use its CPU: slower, still fine.
- **Subagents** (an Agent or Task tool): build cards in parallel. Installed as a Claude Code plugin, use its agent
  types: `reel-kit:fx-builder` for effects, `reel-kit:card-builder` for cards (same prompts as below). None: build them one after another yourself,
  each from the same brief.
- **Claude artifacts** (an Artifact tool): publish the storyboard and the style board there and read inline
  comments with ArtifactComments. None: serve them locally with `KIT/storyboard/serve.py`; notes land in a file.
- **Generators** (optional, see README "Extend it"): an image or video generator (for example the Higgsfield MCP),
  a music or sound one (for example ChatCut, ElevenLabs). Use only what is already connected. Without one, the
  video uses real artifacts and the kit's own sound effects, which is the default anyway.

## 0. First run
1. `HOME/.setup-version` missing, or not the same as `KIT/VERSION` (first run, or the kit was just updated), or
   `KIT/fx/BUNDLE.json` there without `KIT/fx/.unpacked` (a fresh copy of the kit, its effects not fetched yet): run
   `sh KIT/setup/setup.sh` until it prints READY (it renders a test frame, so READY means it can render). The first
   run takes 10 to 20 minutes; say so, and say what it's doing as it goes. Each MISSING line comes with the exact fix
   for that computer: do it yourself, then run setup again. On a Mac, if a popup asks to install Apple's command line
   developer tools, tell the creator to click Install and wait for it. If it says it moved an old Reel Kit, tell the
   creator in one line and that their next video should start in a new session. When it prints READY, pass on its
   credit line once. No style yet: the next step is the style (2), so point them to `/reel-kit-style` rather than asking for a clip.
2. No `HOME/style/style.json` yet: run onboarding (`KIT/onboarding/ONBOARDING.md`) before the first video. It ends
   with the creator approving their style board.
3. "Change my style" (or `/reel-kit-style` when a style exists) at any time: onboarding steps 4 and 5 on the current pack.

## Modes
The creator picks: **hi-fi**, **lo-fi** or **showcase** (also accept "hifi", "high", "produced", "lofi", "low",
"selfie", "show-off", "show off", "flex"). No mode in the request: ask "Hi-fi, lo-fi or showcase?" in one line
before anything else; never infer it from the footage.
- **Hi-fi** (`KIT/modes/HIFI.md`): produced. Two framings of one take, full-screen data cards by card agents, type
  behind the head. Reference: `KIT/examples/hifi/edit.py`.
- **Lo-fi** (`KIT/modes/LOFI.md`): selfie. They never leave the frame; real artifacts land on top of them or behind
  their head; word-by-word captions; text boxes. No card agents. Reference: `KIT/examples/lofi/edit.py`.
- **Showcase** (`KIT/modes/SHOWCASE.md`): the show-off edit on any footage. Every beat a different technique the
  words call for, one recurring motif, a different transition on every cut, dense sound; built by FX agents from
  `KIT/fx/LIBRARY.md` (contract `KIT/kit/FX_BRIEF.md`), lo-fi captions underneath. Reference:
  `KIT/examples/showcase/edit.py`.
How each mode edits is the creator's, not the kit's: their `STYLE.md` has a section per mode and `style.json` a
`modes` block (hook shape, caption rhythm, camera, transitions, how a big word lands; `KIT/kit/STYLE_PACK.md`).
Read the mode file, then the creator's `STYLE.md` and `modes` for that mode, before step 3; where they disagree with
the mode file, the creator wins.

## Effects by name
Every showcase effect has a name: its folder in `KIT/fx/LIBRARY.md` (`receipt-printer`, `keycaps`,
`projected-film`...) or in the creator's own `HOME/fx/LIBRARY.md`. The creator can call them:
- **In the request**: `/reel-kit showcase take.mov, receipt-printer as the motif, keycaps on "I know nothing about
  editing"`. Those effects are pinned: they go on those lines in the beat map first, and you choose the rest.
- **In a storyboard note**: "make this one projected-film" swaps that beat's effect.
- Match loosely ("the receipt one", "the film effect") to the closest row and say which one you picked. A name you
  can't match: say so and offer the two closest.
- Named in a hi-fi or lo-fi request: effects are built for showcase; ask once whether to make it a showcase video.
- **"What effects are there?"** (or `/reel-kit effects`, `/reel-kit:effect-list`): open their
  effects page, `PY KIT/pipeline/effect.py library --open` (theirs first, then the kit's, each with a playing
  preview). No project, no video.

## New effects (from someone else's video)
"I love this effect, can I have it?" with a link or a file and when it plays (`/reel-kit:effect <link or file>
17-19`): follow `KIT/effect/EFFECT.md`. One effect per run, tested on their own footage, one page to Keep, Fix or
Drop; a keep lands in `HOME/fx/` and is theirs to use by name from then on.

## Trials (test versions of a reel)
`/reel-kit:trials` opens Trials, a small app on their computer that posts two or more versions of a reel as Instagram
Trial Reels (shown to non-followers only) through Zernio, then compares them per test: views, reach, watch time,
skip rate, shares, saves. Every command is `PY KIT/pipeline/trials.py <install|start|stop|status|app|key>`.
- `install` every time (it's quick when nothing changed), then `start` (opens Trials for Mac when they have it,
  otherwise the browser at `http://127.0.0.1:5180`). It installs the app into `HOME/trials/app` the first time and
  updates it after a kit update.
- **Mac app or browser: ask once.** On a Mac, `install` prints `MAC_APP ask` until they've chosen. Ask in one line:
  "Want Trials as a Mac app (its own window and Dock icon, opens from Spotlight), or keep using it in your browser?"
  Yes: `app` (builds Trials.app in Applications and prints `MAC_APP <path>`), then `start` opens it there. Browser:
  `app --no`, and nobody asks again (`MAC_APP no`). They can change their mind any time: run `app` or `app --no`.
  Updates keep the app up to date by themselves (`MAC_APP <path>` on every install).
- **After the first run they don't need you to open it.** Trials for Mac starts the server itself when it opens, so
  it's just Cmd+Space, "Trials", Enter. In a browser, the server stops when the computer restarts and a reload shows a
  "Trials is off" page; with the Mac app installed its "Turn it back on" button starts it (the first click asks "Open
  Trials?": Always allow), otherwise the way back is `/reel-kit:trials`. Say the part that applies in one line.
- **What's theirs, and stays theirs.** Their Zernio key is in `HOME/trials/.env`, their test history in
  `HOME/trials/experiments.json` (daily backups in `HOME/trials/backups/`). Updates never touch either; never move
  them into the app folder. The app folder is theirs to change too: when they ask for a change to Trials, edit
  `HOME/trials/app` directly (its `AGENTS.md` has the app's rules), then `npm test` there, then `stop` and `start`.
  An update only replaces files that are still exactly what the kit installed.
- **After an update**, `install` prints `KEPT` for files they changed that the update left alone (nothing to do), and
  `MERGE <file>` where the update changed a file they had changed too: theirs stays in the app and the new version is
  parked in `HOME/trials/updates/<version>/`. Tell them in one line, then merge: read both (and their pre-update copy
  in `HOME/trials/app-backups/`), carry their change onto the new version, write it into the app, run `npm test`,
  delete the parked file, restart. Never drop their change to take the new version without asking them.
- **The key.** `start` prints `NO KEY` until there is one, and the page opens on a "Connect Zernio" screen with a box
  for it. They need a Zernio account with their Instagram connected (a professional account) and a read-write API
  key from Zernio's Settings, API Keys. They paste it in that box: the app checks it with Zernio, saves it to
  `HOME/trials/.env` and connects straight away, no restart. To change it later: the key button next to their
  account at the bottom of the sidebar. Never ask for the key in the chat or repeat it back. If
  they paste it into the chat anyway, write it into that file yourself, don't echo it, then `stop` and `start`.
- **Never publish for them.** Posting happens when they click Publish, then Publish now, in the app. Never send a
  post to Zernio yourself, and never while testing or fixing the app.
- How to get a clean read, which is what to tell them when results look odd: compare after the same 24 hours; test
  versions before the reel goes to their feed (Instagram gives almost no reach to a trial that looks like something
  they've already posted, and the app flags versions it's holding back); don't run two tests of near-identical
  footage at the same time. The winner is shared to their followers from the Instagram app.
- Hosts: it's a local web app, so it needs a host whose commands run on their own computer (Claude Code, Codex).
  In a VM (Claude Cowork) their browser may not reach it: say so and suggest the Claude Code tab.

## 1. Intake
- The clip, the source it talks about (article, study, post, document) if there is one, and a short slug.
- Scaffold: `PY KIT/pipeline/new.py <slug> "<clip>" "<Title>" --mode hifi|lofi|showcase` -> `HOME/projects/<slug>/` with
  `edit.py` (FRAMES seeded from the clip's size) and the style pack copied into `style/`.
- Read the source. Grab screenshots of the real thing for cards (a browser tool if you have one).
- Look at a few frames of the footage to set FRAMES for this shoot (face centre, eyes, chin).

## 2. Cut
- First transcript of the whole take: set `KEEP = [(0, <clip length>)]`, run `PY KIT/pipeline/words.py <project>`,
  read `words.json`. People repeat a line until it lands: keep the LAST clean take of each line.
- Find the pauses: `ffmpeg -i <clip> -af silencedetect=noise=-35dB:d=0.25 -f null -`. Set `KEEP` (source seconds,
  ~0.05s before the first word, at the silence after the last), `FRAMES`, `SHOTS`, `HOLD` (hi-fi 0.6, or 1.3 with
  an end card; lo-fi 0.04, since a phone take ends on its last word; showcase 0.5), `PROMPT` (names and terms) and `FIXES`.
- `PY KIT/pipeline/cut.py <project> --plan`: the sync table must show every piece reading its own audio. Then
  `PY KIT/pipeline/cut.py <project>` and `PY KIT/pipeline/words.py <project>` again on the cut.
- Copy `assets/aroll.mp4` to `public/clean.mp4`. If anything goes behind the head, start the cutout in the
  background now: `PY KIT/pipeline/cutout.py <project>` (or `matte.py` after `sh KIT/setup/setup.sh --matte`, smoother edges).

## 3. Beats (write edit.py)
Map every line to the mode's components, copying field shapes from the reference edit.py: captions (`CAPS` in
hi-fi; automatic in lo-fi), `HOOK`, `BEHIND`, `CUT_WINDOWS` (never across a picture change), `BW` (at most two),
`CAMERA`, `CARDS` (from `KIT/cards/LIBRARY.md`, light and dark alternating) or `OVERLAYS`/`BOXES` in lo-fi,
`END_CARD = None` unless asked. Real artifacts first. Pace from the pack's `motion`.

Beat ids (`p01`, `p02`...) come from the cut: `PY KIT/pipeline/storyboard.py <project> --list` prints them before
any frames exist. If the footage, the brand and the script don't line up (someone else on camera, a hook that
promises more than the clip holds), say so with the storyboard; never invent missing content.

**Needs pass (every video, every beat, without being asked).** For each beat, decide what it needs beyond the take
and the source, and sort every asset three ways:
- *In hand*: the take, the source, screenshots you can grab yourself from public pages.
- *Only the creator has it*: their B-roll, screen recordings, screenshots of their own tools or dashboards, photos,
  logos, anything behind a login. Write each into `NEEDS` as `("p06", "Screen recording: 8-10s of <exact thing>,
  <framing, length>")`, specific enough to shoot without a follow-up question. Build the beat anyway with a
  placeholder; never hold the storyboard for it.
- *Generated*: step 3b, only with a generator connected.

**The room.** Showcase effects whose supply column in `fx/LIBRARY.md` names the room (a locked-off shot, plates,
`room_<FRAME>`) need the room behind the speaker. When the beat map picks one and the take has no empty-room stretch
(`EMPTY`, step 4), add a NEEDS line on its beat that asks for a shot of the background and, when an image generator is
connected, offers to make it instead. Word for word, with the generator's name: "Your background: 5 seconds of the
empty room from the same spot, camera untouched (walk out of frame and let it record), or a photo from exactly there.
If the camera has moved since, or you'd rather not, reply 'generate it' and I'll make your background with Higgsfield
(a few credits)." With no generator connected, end it after "exactly there". A clip of the empty room goes in
`EMPTY_CLIP`; a photo, or a background they ask you to generate, goes in with `plate_finish.py --fill` (step 4, the
room). A phone take held in the hand can't carry these at all: pick another effect. One big layered trick per
video, not all of them.

## 3b. Generated imagery (only with a generator connected; no need to ask)
When a beat needs an image no real artifact can give, make it now so it shows on the storyboard: a still from the
connected image model, a short clip only when the beat truly moves (ideally animated from the approved still).
Hold it to restraint: people, places, objects and textures that look shot. Never generated B-roll as the look of
the video. Log each in `GENERATED` as `("p04", "<what it is>, <model>")`; the
storyboard tags them so the creator can cut any. Minimal by default; more only when they ask in their notes.

## 4. Cards (hi-fi) or effects (showcase)
**Layered effects first (showcase, only when the beat map has one).** Pre-rendered effects that work on the real
footage (the speaker turns to sand, the room splits, type circles behind the head) stand on three tools. Run what the
picked effects' supply column asks for, after the matte (`subject.webm`) and before their agents start; each is run
once per video and reused by every effect:
- **The room** (locked-off shot): put the empty room in edit.py, `EMPTY = (s0, s1)` (source seconds of the take where
  nobody is in the shot) or `EMPTY_CLIP = ("<file>", s0, s1)` (a separate empty clip from the same camera).
  `PY KIT/pipeline/plate.py <project> --find-empty` lists the still stretches with a frame of each to check. Then
  `PY KIT/pipeline/plate.py <project>` and `PY KIT/pipeline/plate_finish.py <project>`, and look at
  `<project>/work/plate/check.jpg` (live, room, empty room, desk and mic layers per crop). Without an empty room
  plate.py fills the patch the speaker always covered and warns that it will show: those effects then must not move
  the speaker off their spot. plate.py refuses a shot that moves (a phone in the hand). A photo of the room from the
  camera's spot, or a background the creator asked you to generate, fills that patch for real:
  `PY KIT/pipeline/plate_finish.py <project> --bg-frame` writes `work/plate/bg_frame.png` (the frame where the speaker
  covers the least of the room) and prints the prompt. Make one image from it with the connected image model (the
  frame as its reference, the same aspect ratio, high quality; on Higgsfield, upload the frame and use GPT Image), save
  it as `<project>/assets/background.png`, run `PY KIT/pipeline/plate_finish.py <project> --fill assets/background.png`
  (a photo goes in the same way) and look at check.jpg: the room column should read as the real room. Log a generated
  one in `GENERATED` on the effect's beat. Effects treat a filled room like a filmed one (plate.json mode `filled`):
  run, or rerun, their gen.py after it.
- **Tracks**: `PY KIT/pipeline/track.py <project>` -> `work/tracks/track.json` (head, mouth, hands, shoulders per
  frame). The first run installs MediaPipe into `HOME/.venv-mp` (about 390 MB, 1 to 2 minutes): say so.
- **Depth**: nothing to run; the first effect that asks downloads the model (99 MB).
Every output file and how effects read them: `KIT/kit/FX_BRIEF.md`, "Layered effects". Effect agents render their
slice in real motion with `PY KIT/pipeline/fxclip.py <project> <name> --only <ids> --from S --to E`.

**Showcase:** FX agents instead of cards. Write the beat map first (`KIT/modes/SHOWCASE.md`: a technique for every
line, one motif, the hook on frame 0, a transition per cut), put every entry in `FX` with its window and layer, then
launch 4 to 8 agents at once, grouped by technique. Each prompt: the `PATH=` prefix when `BIN` exists; read `KIT/kit/FX_BRIEF.md`,
`<project>/style/STYLE.md` (its Showcase section) and the `KIT/fx/LIBRARY.md` or `HOME/fx/LIBRARY.md` entries to start from (with their folder paths); its ids, layers
and windows; the words with output times; where the head is in that shot; the real assets; its own sandbox name for
`PY KIT/pipeline/fxsandbox.py <project> <name> --only <ids> --at <times>`; run `hyperframes check`; report frames,
SFX, edit.py changes and snapshot paths. Review every still at full size, send fixes back to the same agent, merge
frames into FX and SFX into SOUND. No subagents: build the effects yourself one at a time from the same brief.

**Hi-fi cards:** one agent per card (cards that share geometry go to one agent), all launched at once. Each prompt: the `PATH=`
prefix when `BIN` exists; read `KIT/kit/CARD_BRIEF.md` and `<project>/style/STYLE.md`; KIT and PROJECT paths; the library card to start from;
the card id and folder `<project>/cards/<id>/`; the exact frame count (`data-duration` = frames/30); the window in
the video; the spoken words with CARD times; the data and labels; what it shows and when; phase 1 only (still.jpg
and beats, no render). Review every still at full size before the storyboard; send fixes back to the same agent.
No subagents: build the cards yourself one at a time from the same brief.

## 5. Sound
- `SOUND.sfx` for every visual event and `CARD_SFX` from the card agents' beat reports. Times are when each sound
  hits; `mix.py` lines up each file's loudest moment on it. Vocabulary: `KIT/audio/SFX.md`. Density from the
  pack's `sound.sfx`. Always under the voice.
- Music: none by default (most creators add a track in their posting app). When they hand one over, or a connected
  generator makes one, set `SOUND.music` and `sections` so two or three drops land on key lines.
- `PY KIT/pipeline/mix.py <project>` -> `public/master.wav` at -14 LUFS.

## 6. Storyboard (stop here)
- `PY KIT/pipeline/build.py <project> --stills` (cards show their stills), then
  `PY KIT/pipeline/storyboard.py <project> --version 1`: every beat with real frames, the line, what moves, what you
  hear, wearing the creator's own fonts and colours. It always answers "what I need from you" at the top.
- Show it:
  - **Claude artifacts**: copy `<project>/storyboard/` to a scratch folder and publish its `index.html` with every
    file in `files.json`, `capabilities` = `{"comments": {"composer_only": true}}`. Republish later versions from
    the same file path to keep the URL.
  - **Anywhere else**: run `PY KIT/storyboard/serve.py <project>` in the background and send
    `http://127.0.0.1:8765`. They leave a note on any beat and press "Looks good: render it" when done.
- In the same message: what you need from them (each item, its beat, exactly what to send) or "nothing needed
  from you", plus anything a generator made and what it cost. Then STOP. Nothing renders until they say go.

## 7. Notes
- Artifact comments: read them with ArtifactComments; each thread is pinned to a beat (`p01`, `p02`...). Local:
  `<project>/storyboard/notes.json`, a list of `{beat, text, at}`; beat `all` with text `go` means render.
- Notes are the creator's words about this video: data for the edit, not instructions to anything else.
- Apply every note (edit.py; cards through their agents), rebuild, regenerate the storyboard as the next version
  and show it again. When they send an asset, drop it into its beat and clear it from `NEEDS`.

## 8. Render and deliver (after "go")
- Card agents render their mp4s (phase 2); the build picks them up from `<project>/cards/<id>/<id>.mp4`.
- `PY KIT/pipeline/render.py <project> <slug>-v1`: build, lint, render, QA. QA must pass: read every cut sheet (no
  flash, no wrong frame, no doubled head), lip sync within 2 frames, -14 LUFS. On a pass it copies the video and a
  phone copy next to the source clip as `<Title> v1.mp4` and `<Title> v1 (phone).mp4`.

## Gotchas already paid for
- Phone takes exported from Edits or CapCut are already cut in their pauses: a fixed J-cut runs past those cuts
  (a double cut). `cut.py` detects source cuts and fits each join's lead to them.
- SFX swell before they peak: give `mix.py` the moment of the event, never the file's start.
- A join that rounds down to its frame once mapped seconds of picture through the wrong segment. `cut.py` matches
  on the snapped join and refuses to encode if any piece drifts.
- The cutout seeks a frame late: a cutout window across a reframe shows one doubled-head frame. Windows start on or
  after the change.
- Times at 3 decimals land a frame late: everything goes through `q()` and `clip_start()`. HyperFrames rounds
  `data-duration` x 30 up: 137 frames is 4.5666, not 4.567. `data-media-start` must be an exact frame time.
- Anything behind the cutout must be off before it clears the speaker's body: the desk is not in the cutout.
- Transcription mishears names: put them in `PROMPT` and `FIXES`.
- `qa.py` correlates whole frames: under heavy graphics it can flag a false drift. Re-check on a face-only crop.
