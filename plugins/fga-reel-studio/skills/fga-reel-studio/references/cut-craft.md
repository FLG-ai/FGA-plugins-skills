# The cut protocol (both lanes)

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

The rules are the same in both lanes. The tools that check them differ: the word-level tools (`joinaudit`, `fixjoins`, `capcheck`, `align`) need a kit project, so in the Quick lane the checks are the step reports, `eyecheck.py` on `tight.mp4`, and listening to the bare cut. See `references/gates.md` for which gate runs where.

A talking-head video lives or dies on the cut. These rules come from hours of reviewing edits with sound on. The numbers are defaults: the person's `RULES.md` can change any of them, and their newest dated rule wins.

## 1. Know the whole take first
Transcribe the full take and read it end to end before deciding anything. Note every line said more than once.

## 2. Compare every take of every line
People repeat a line until it lands, and the best one is often not the last. Line up every take of each line, openers first. Compare pace (words per second, gaps), eyes on the lens, energy and expression. Pull a frame from each candidate and look at it. Takes can be mixed freely. Tell the person which take each line came from.
Keep their personality. Real smiles, laughs and reactions to camera stay. Only dead air, look-downs, stumbles and repeats go.

## 3. What gets cut
- Dead air at the start and between lines.
- Repeats, false starts, hesitations ("the... the safe zones"), fillers and stutters.
- Obvious look-downs: the eyes drop to a script or phone, or they move to look at it. Tiny or natural side glances stay in, and so do blinks.
- Leans, reaches and shuffles before a line.
- Default timing: a gap of 0.45 s or more is a cut. Keep about 0.12 s before the first word and about 0.15 s after the last. Look-downs usually come right after a line ends, so tails stay short.
- Never shave a word's start or end to the voice envelope, and never clamp a drawn-out word.

## 4. Every join lands in the quiet
A cut inside a word leaves half words, doubled syllables and clipped endings that people hear as a skip. Word times from a transcript can be 0.4 s off, so do not trust them for cut points.
- At each join the 5 ms energy should sit below about -30 dB relative to loud speech.
- Read the last 0.8 s of the outgoing piece and the first 0.8 s of the incoming piece (a greedy wav2vec2 read). No fragments.
- Also read the 0.4 s tail of every outgoing piece and the first 0.2 s of every incoming one. Breaths and the end of a drawn-out "s" sit at -25 to -35 dB and slip past a check that only looks at the cut itself.
- Where two words run together with no gap ("So now"), cut at the start of the next consonant.
- A connector said at the start of a line ("So", "And", "Now", "I mean") stays whole and gets captioned. Never half-cut one.
- Two pieces that touch in the source join with no fade, so a reframe inside a phrase is silent.
Tools: `GATES/joinaudit.py`, `GATES/fixjoins.py`, `GATES/look.py`, `GATES/env.py`. See `references/gates.md`.

## 5. Drawn-out words
When they stretch a word on purpose ("the second iiis"), speed that piece up about 1.3x. Do not chop it.

## 6. Frame-exact
Every cut lands on a frame and picture and sound stay in step. Lip sync stays within 2 frames before and after the render. Rounding drift across many cuts is the usual cause of a mouth out of time near the end.

## 7. Bare cut first
After a recut, send a bare cut (no effects, small file) so they can hear the joins before the full render. People review with sound on, and any skip makes an edit feel machine-made.

## 8. Captions follow the voice
Word times from a first transcript can lead the voice by up to 0.26 s. Before the final version, re-align caption times to the cut voice (`GATES/align.py`, then `GATES/capcheck.py`). Pin a word the aligner gets wrong with `work/pins.json` and `GATES/pinwords.py`. Every spoken word is captioned.

## Grade
Choose one and apply it to the footage before the edit rather than as a late filter:
| Grade | What it does | ffmpeg filter |
|---|---|---|
| `cool` | Light and slightly cool, no smoothing | `eq=contrast=1.04:saturation=0.94:gamma=1.03,colorbalance=bm=0.02:rm=-0.01` |
| `calm_reds` | Reds and magentas down 16% saturation plus a very light smooth. Nothing lightened. Use when a lighter cool grade washes the person out | `huesaturation=saturation=-0.16:colors=r+m:strength=6,bilateral=sigmaS=4:sigmaR=0.035` |
| `none` | Straight | |
The Quick lane applies it in `reel-framing` (`--grade`, or the `grade` key in `design-system.json`). In the kit lanes, run the filter on the source when you make the working clip.

## Look-down review, every time
A frame at each cut's end is not enough. Pre-roll or tail that an L-cut lead pulled in, at the start of the next line, hides most of them. Run `eyecheck.py` over the whole cut, look at every flagged run on the sheet, then at the render frames for the real ones (an effect may already cover the face). Fix with the join's picture lead first. Where the eyes are down on both sides of a join, cover it with a beat's own graphic.
