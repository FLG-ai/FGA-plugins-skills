# What to cut and what to keep

The draft plan already splits at every pause over 0.35 s and drops um, uh and erm. Read `lines.txt` (words split at pauses, as `word[index@start]`) next to `plan.json` and edit the `keep` list of `[first word, last word]` ranges.

## Cut
- **Dead air before the first word.** Talking starts within a beat of the first frame.
- **Long pauses mid-sentence.** Already split by the draft. Rerun `plan_cuts.py` with `--gap 0.5` if the result feels breathless, or `--gap 0.25` for a faster pace.
- **Stutters:** the same word twice by accident ("the the"). Keep the second.
- **False starts and restarts:** a phrase begun, dropped and said again. Keep the complete version.
- **A line said twice:** keep the take that is clearer and sounds more confident. If unsure, keep the later one, which is usually the better take, and say which you kept.
- **Looking down** (from `lookdown.json`): cut those words if the sentence still makes sense without them. Otherwise keep them and tell the person.
- **Actions the person names** (fixing hair, reaching off screen): add them to `flag_actions` as `{"start": s, "end": s, "what": "fixes hair"}` (seconds on the original), and cut the pause around them. If the action overlaps words that must stay (like the hook), keep the words, note it in `flag_actions` for the framing step, and tell the person.

## Keep
- **Repeats said for emphasis** ("never, ever"): keep up to two. Cut the third.
- **Looking to the side, laughing, a natural pause inside a list.** These are how people talk. Only looking down or away from the camera gets cut.
- **A long line that flows.** Don't split it just because it's long. A cut in the middle of a moving gesture makes the hands jump.

## Pacing
A tight talking reel loses about a fifth of the raw length. If more than a third is gone, check nothing meaningful was cut, and tell the person what took the time (usually double takes).
