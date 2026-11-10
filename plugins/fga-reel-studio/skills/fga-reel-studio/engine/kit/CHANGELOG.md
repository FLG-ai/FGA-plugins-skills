# Changelog

Every release says what's new and what updating means for videos you've already made. Your style pack, your
projects and your finished videos live in `~/reel-kit/` (or the folder you gave Cowork or ChatGPT), outside the
skill, so an update never touches them. How to update: README, "Update".

## 1.2.0
- **27 new effects built from the footage itself.** They pre-render clips from your take (your cutout, face and
  hand tracking, depth and the room behind you), so the graphics sit in your room, in front of you and behind you,
  and stay in sync with your voice. All of them in your style. Among them: a broadsheet front page with you live in
  the photo (`press-front`), the picture ripping like paper (`paper-tear`), a blade slicing the frame
  (`blade-slice`), a clock face eating your day (`day-dial`), the Vertigo shot (`dolly-zoom`), you blowing away as
  sand (`blow-away`), a cursor that drags you across your own room (`live-cursor`) and an exploded view of the
  edit's layers (`layer-explode`). Every one, with what it needs, is in `fx/LIBRARY.md` ("Added in 1.2.0") and on
  your effects page.
- **Film the empty room for the big ones.** Five of them (`dolly-zoom`, `blow-away`, `live-cursor`, `layer-explode`,
  `room-doors`) want a locked-off camera and five seconds of the empty room at the end of the take: walk out of frame
  and let it record, without touching the camera. When one of them is picked and the take doesn't have it, the
  storyboard asks for a shot of your background (5 seconds of the empty room, or a photo from the same spot), or, if
  you'd rather, makes your background for you with Higgsfield (or another image generator you've connected). Without
  either they use a guessed room, which shows when you move.
- Tracking and depth install the first time an effect needs them (about 400 MB and 100 MB), so setup stays quick.
- Your style pack can hold a headshot (`headshot.jpg`): effects that show your face in a chip or a bubble use it.
- Cutouts land at the footage's own levels, so the edge where you meet the room no longer darkens.
- Camera transitions leave alone any cut an effect already handles.

Updating: setup runs once after the update and adds the new Python packages. Your style, effects library, projects
and videos stay as they are.

## 1.1.0
- **Make your own effects**: `/reel-kit:effect <link or file> 17-19`. Send any video and when the effect plays (or
  describe the moment). Claude rebuilds it in your style, tests it on your own footage, and sends one page with the
  original and yours side by side: Keep, Fix or Drop. A keep lands in your effects library, ready to use by name.
- **Your effects page**: `/reel-kit:effect-list` opens every effect you can use, yours first, each with a
  playing preview, in your own fonts and colours. Tap a name to copy it into a request or a storyboard note.
- **Trials**: `/reel-kit:trials` opens an app that posts two or more versions of a reel as Instagram Trial Reels
  (seen by non-followers only), spaced a few minutes apart, then shows which one wins on views, watch time, shares
  and saves. It flags versions Instagram is holding back as duplicates. Needs a Zernio account: paste its key into
  the Trials page once. Your key and your test history live in `~/reel-kit/trials/`, and an update never changes a file
  you've changed in the app. On a Mac you choose: Trials for Mac (its own window and Dock
  icon, opens from Spotlight, turns itself on) or your browser.
- Every kit effect now has a short preview video next to its still.
- Setup repairs a kit whose Python went missing (after a Homebrew or Python upgrade) instead of stopping.
- The skill zip (ChatGPT, claude.ai) fits skill uploads (200 files at most): setup downloads the kit's effects on
  first run (about 25 MB). The Claude plugin still carries them.

Updating: nothing to do. Your style, effects library, projects and videos stay as they are.

## 1.0.0
The first full release: three modes, 40 effects, your own style and your own effects library, one-step setup with
nothing to install by hand.
- An effect can't take an id the video page already uses (like `hook`): the build names the clash and the fix,
  instead of the effect quietly picking up the page's own styling.
- Something behind you from the very first frame no longer fails the render check.
- The storyboard reads every way of writing a sound effect, including the typing sounds in the showcase example.
- The lip-sync check samples frames where nothing on top can cover your face, and says "check by eye" instead of
  failing when it has no clear frame.

Updating: nothing to do. Your style, effects library, projects and videos stay as they are.

## 0.4.6
- **Your own effects library**: `~/reel-kit/fx/` and `~/reel-kit/cards/`. Effects and cards you make or change are
  saved there ("save this effect"), and updates never touch them. When a release brings a new version of an effect
  you changed, yours is the one your videos use.
- Installed the old Reel Kit by hand (a clone or the zip in `~/.claude/skills/reel-kit`)? The plugin's setup copies
  every effect and card you made or changed into your library, then moves the old kit into `~/reel-kit/old-skill/`,
  so it stops taking over `/reel-kit`. Nothing is deleted.

Updating: start a new session after setup so only the plugin loads. Your style, projects and videos stay as they are.

## 0.4.5
- When there's no style yet, setup's status line now points to `/reel-kit-style` instead of saying the first video
  will start with it.

## 0.4.4
- New command: `/reel-kit-style` (`/reel-kit:reel-kit-style` in Claude Code). The first time it builds your style
  from your brand and the videos you like; after that it changes it.
- Setup now ends by pointing to `/reel-kit-style` when you don't have a style yet, instead of asking for a clip.

## 0.4.3
- Setup's last line is just the credit: Reel Kit is part of the AI Video Editing Masterclass.

## 0.4.2
- Setup's last line now names the AI Video Editing Masterclass and points to Lesson 2.5 when something's stuck,
  instead of the waitlist.

## 0.4.1
- The setup command is now `/reel-kit-setup` (`/reel-kit:reel-kit-setup` in Claude Code), so it can't be mistaken
  for another plugin's setup. Everything else is the same.
- Claude installs come from `reel-kit-plugin.zip`: upload it in Cowork (Customize > Plugins), or add the unzipped
  folder in Claude Code. Updating is the same steps with the new file. Your style, projects and videos stay.

## 0.4.0
- **Reel Kit is a Claude Code plugin.** Install it with one message (README, "Install"), and updates arrive on
  their own instead of through `git pull`. In Claude Cowork it installs from Customize > Plugins > Add marketplace.
- **Nothing to install by hand.** On a Mac or Linux without them, setup fetches its own Python, ffmpeg and Node into
  `~/reel-kit/tools/`: no Homebrew, no admin password, nothing changed on the rest of the computer. Setup starts with
  `sh setup/setup.sh` now.
- New commands in Claude Code: `/reel-kit:hifi`, `/reel-kit:lofi` and `/reel-kit:showcase` with your clip (the mode
  is in the command), and `/reel-kit:setup`. `/reel-kit` still works.
- After an update, the next video runs setup again by itself when the new release needs it.

Updating: if you installed by cloning into `~/.claude/skills/reel-kit`, delete that folder and install the plugin
(README, "Moving from the cloned skill"). Your style, projects and videos in `~/reel-kit/` stay as they are.

## 0.3.0
- **Twenty-three new showcase effects** (40 in all), each in your style through your pack's tokens:
  a receipt printer motif, a contact-sheet hook, iOS-style jiggle-delete, projected film, a film look, a 3D cascade
  of your videos, a grid of them playing, a silent-film title card, a screenplay page, keycaps that pile up, a
  grease-pencil contact sheet of your raw take, a documentary title card, a picture of the frame on the wall you
  dive into, an eyedropper grade, see-through giant captions, a feed of other creators, live black and white with
  a grease pencil that follows you, a storyboard deck (deal, flip, note), a word that drops in behind you, a lens
  ring, your walkthrough playing behind you, a comment keyword that drops into a comment box, and shape transitions.
  `fx/LIBRARY.md` has every one.
- **Call effects by name**: put them in your request (`/reel-kit showcase take.mov, receipt-printer as the motif`)
  or in a storyboard note ("make this one projected-film"). Ask "what effects are there?" for the list.
- New showcase craft rules: flat, centred type; looks that start and end with their line and never freeze the
  frame; a motif that sits in the same place every time; labels that never overlap.
- `VERSION` file; setup prints the version, and new projects record the release they were started on
  (`KIT_VERSION` in edit.py).

Updating: safe for existing videos. Projects keep their own copies of the effects and the style they were made
with. The new effects show up in your next showcase video.

## 0.2.1
- Install guides for Claude Cowork and ChatGPT Work, and a recommended model (Claude Opus 5.5 on max effort).
- Setup requires Node 22+ and, on Linux (including Cowork's sandbox), installs a render browser that works there.
  The skill keeps its home in the folder you give Cowork or ChatGPT.

Updating: run setup again after you update (it checks Node and the render browser).

## 0.2.0
- Showcase mode: a different hand-built motion graphic on every line, a recurring motif and a different transition
  on every cut. 17 effects in `fx/`, all in your style.
- Your style decides how each mode edits (hook shape, caption rhythm, camera, transitions, how a big word lands),
  read from your brand file or inspiration videos. The style board shows all three modes on your own footage.
- Typing and key sounds, a colour check for emphasis words in the caption box, QA that skips lip-sync samples under
  effects that repaint the background.

Updating: pull (or upload the new zip), then run setup again.

## 0.1.0
- First release: hi-fi and lo-fi modes, style onboarding (a brand file, inspiration videos or four questions), nine
  motion-graphic cards, 18 CC0 sound effects, storyboard review in Claude or locally.
