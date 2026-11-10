# predict-keys (top)

A phone keyboard rises from the bottom and types the speaker's line as they say it: keycaps with no tray, a preview
balloon on every press, the text field growing a line when the sentence wraps, the predictive bar updating on every
keystroke. Then the bar offers three words, the caret waits, a soft tap lands on the word the speaker says, it jumps
into the sentence in the accent colour, send presses, the whole thing drops. The keyboard is a generic one (no real
phone's copied); its look is the creator's: light keycaps, dark field and function keys, the pack's text face, the
accent on the picked word, the caret and send.

**Needs:** any footage. `words.json` and `work/tracks/track.json` for the chin (`PY KIT/pipeline/track.py <project>`,
or set `CHIN`). No matte, no plate. Hide the captions over the window (`KARAOKE["hide"]`): the keyboard carries the
line.

**Reuse:** copy the folder to `<project>/fx/<id>/`, add `dict(id="<id>", layer="top", at=..., end=...)` to edit.FX
(start a beat into the line: words said before it are already in the field when it rises; end it about 0.6 s after
the picked word starts; both on frames), set the table at the top of `gen.py` and run `PY fx/<id>/gen.py <project>`
(`--check` prints the plan and the bar's words, writes nothing).
- `LINE`: the words typed, as said, ending right before the pick. `PICK`: the word the tap picks. `SUGGEST`: the bar's
  three words for the payoff, PICK among them.
- Read off the project: every word's onset (words.json); the chin across the window (when it is low, the whole
  keyboard scales down about its bottom centre so the field stays `CHIN_GAP` under it, never below `MIN_FIT`); the
  pack's text face (the line wraps from its real metrics and the size steps down until it fits two rows).
- The bar: while a word types it shows the letters so far, the word, an alternative; after it, three guesses for the
  next word with the real one first. Both come from the video's own transcript (real words only); `GUESS` overrides
  any word. After the pick it shows a comma, the next word said and a full stop (`AFTER` overrides).
- Timing: `RISE`, `SEND_AFTER`, `DROP_AFTER`. Layout: `KX`, `KW`, `KEY_H`, `BOTTOM` keep it inside Instagram's UI
  (bottom 1468, x 100 to 980).

**Sound:** a `tick` per letter and a `key` per space at the real, uneven thumb times, `whoosh-soft` as it rises,
`click` on the tap and on send, `pop` as the word lands, `whoosh` as it drops. gen.py prints every line with a level.

**Phone take:** nothing changes. A close selfie with a low chin shrinks the keyboard, and gen.py warns when even
`MIN_FIT` covers the mouth (use the line on a wider shot). Hands near the keyboard read as typing: check where they are.

**Other frames:** 9:16 only. The layout sits on the 1920 frame above Instagram's UI; on 1:1 or 16:9 it needs its own
layout numbers.
