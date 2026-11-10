# press-front (over)

The speaker prints. A broadsheet front page fills the frame from the first frame (masthead, dateline, a full-measure
headline, body columns set from the video's real words, an index with real times, a pull quote they say), and the
speaker's live, lip-synced footage is the photo: a true one-ink 45 degree round-dot halftone, redone every frame on a
static screen, so only the dots over them breathe. The deck prints word by word as it is spoken (each word lands fat
and wet and draws in over three frames). A press slam on the first frames. Newsprint and ink stay the real object's
colours; every face on the page is the creator's (masthead, headlines and crossheads in the display face, body in the
text face, dateline, times and the ad's small print in mono).

**Needs:** any footage. `words.json`, `public/subject.webm`, and the style pack (fonts and creator fields). With
`work/tracks/track.json` the photo is cropped to head and shoulders and the picture desk opens the eyes and lifts the
mouth so they read through the dots (without it the crop comes from the matte and there is no retouch). With the
plate tools' room (`room_<FRAME>.npy`) the room behind them is screened once and holds dead still; without it the live
room is screened every frame and shimmers a little. Nothing from the creator but the ad, if they want one.

**Run:** `PY fx/<id>/gen.py <project> [<id>]` writes `fx/<id>/<id>.mp4` (the live page: its frame n is the frame at
the window's start + n), `fx.html`, `fx.js` and `work/fx/<id>/last.png` (the last frame as a still), and prints the
SOUND lines (the slam on `impact-low`, a `shutter` per deck print) and the KARAOKE hide (the page carries the words).
`--stills 0 1.4` writes PNGs to `work/fx/<id>/`. Edit.py: `dict(id="press-front", layer="over", at=0.0, end=...)`.
It is a hook: the first frame is complete and is the thumbnail. An effect that tears or turns the page after it
(`paper-tear`) reads those two files: the clip while the page is alive, the still after it.

**Reuse:** the table at the top of `gen.py`. Per video: `HEADLINE` (default: the first sentence spoken in the window,
or its first clause when it runs long), `DECK` as `(text, cue word)` pairs (default: the words after the headline, two
to a print; a window with nothing after the headline has no deck and the headline sits centred), `KICKER`, `PULL`
(default: a sentence from later in the video), `AD` (the creator's own offer: title, who it is by, the ask; it ships
as a labelled placeholder), `EARS`, `CORRECTION`, `INDEX` (default: sentence openings with their times), `HEADS` for
crossheads. Identity comes from the pack: the byline and caption use the creator's name (their handle when the pack
has no name; with neither, no byline and a caption without a name, never the kit's own name), the dateline their site
or handle, the follow strip their handle; set `BYLINE`, `CAPTION`, `FOLLOW` to override. `PAPER_NAME` defaults to The
Daily Reel. What reads off the footage: the crop (`CROP`, from the face's median box over the window), the eyes, mouth
and chin per frame for the retouch, the side the light comes from (the weather box). The tone curves (`TONE`,
`TONE_ROOM`), the screen (`CELL`, `SHARP`), `SLAM` and `SHUDDER` are the print. Headline, deck and masthead shrink to
fit the pack's face. The body copy flows from the left column into the right one and is set as large as the columns
allow (up to 24 px); what is left of a short video's columns fills with lines the speaker says, set as quotes. A
script that is one long list (no sentences of 4 to 14 words) leaves the columns part empty: give it HEADS or a few
true lines of its own. `inkscreen.py` here is the print shop (round dots, line screen, XDoG ink, paper, the headless
browser that sets the page); `impact-frame` and `banknote` carry their own copies of the parts they use.

**Phone take:** works as it is: the photo is the live shot, the crop follows the face. A bright room behind them
screens light; lower `TONE_ROOM` if it washes out. Built for 1080x1920: on another canvas gen.py stops.
