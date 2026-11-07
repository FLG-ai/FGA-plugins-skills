# Finding the moments and writing pops_plan.json

Read `sentences_tight.txt` and `words_tight.json` (word indexes and times on the tight video). Offer the moments as a short list: type, the words, and the word that triggers each one.

## The moments
| Type | When to use it | Fields |
|---|---|---|
| `hook` | Always. The opening claim, on screen from the first frame, 2 to 4 short lines with one `big` line (usually the number) | `lines`: `[{"text", "size": "small" / "mid" / "big"}]`, `at`: 0, `until_word`: the word where the big number or main point is said |
| `number` | **Optional extra.** The key number when it's spoken. One or two per reel. Offer it only if `extras` in `design-system.json` lists `number_pop` or the person asks. Otherwise put a result like "saved 5 hours" in a `list` card | `text`, optional `sub` (a short word under it, like "DAYS IN A ROW"), `at_word`, `until_word` (about 2 s later) |
| `list` | When they list things done or steps, one card per real item. Never a card for a summary or result | `n` ("01"), `label` (3 or 4 words, starts with a verb), `at_word`, `until_word` (the next card's word) |
| `word` | **Optional extra.** Feeling words in a quick run ("weird, awkward, cringe"), scattered around the head. Offer it only if `extras` lists `word_pops` or the person asks | `text`, `at_word`, `until_word`, `x`, `y`, `rot` (-8 to 8). Keep x,y off the face |
| `series` | When they name a series ("part 1 of…") | `lines`, `at_word`, `until_word` |
| `cta` | The comment ask at the end | `small` ("comment"), `big` (the keyword in caps), `at_word`. Holds to the end |

`until_word` means the moment clears as that word starts. `at` (seconds) can replace `at_word`.

## Rules
- The hook clears when the big number lands, so one number is on screen at a time.
- List labels describe what was done ("booked my meetings"). A result line ("saved 5 hours") becomes a `number`, not a list card.
- The hook lines pop in 0.12 s apart, so frame 1 shows the first line and the full stack lands within half a second.
- During a `number` moment, add the spoken words it shows to `skip` in `captions_plan.json`. If the number would sit on the other captions, put those words in `small` instead (never skip a word that isn't on screen). Then re-render reel-captions.
- After rendering, look at a frame of each moment. If a `series` or `number` covers the face, set its `y` lower (for example 1080) or a `word`'s `x`,`y` further out, and render again. If the hook or the call to action touches the hair or covers the face, use fewer lines or smaller sizes (`mid` instead of `big`), or ask reel-framing for a wider opener (a lower opener zoom drops the face).
- If a moment shows the exact words being spoken at that moment (often the series title), add those word indexes to `skip` in `captions_plan.json` and re-render reel-captions, so the words don't appear twice.
