# Sound rules

`plan_sound.py` drafts `sound_plan.json` from the text moments. Each cue is `{"t": seconds on the tight video, "sound": name, "gain": dB, "why": label}`. Edit it to add, move or drop cues.

## Where sounds go
| Moment | Sound |
|---|---|
| List card, giant number, call to action | `pop` (or the design system's `pop`) |
| Series title | the `reveal` sound (sparkle), starting a hair before the title lands |
| Word pops | a soft click on each |
| Hook header | none (it's there from the first frame) |
| Captions | none. A sound on every word is too busy |

Two of the same sound within half a second become one.

## Levels
- Effects sit about 14 dB under the voice (`volume_db` in the design system). Raise one by 2 to 3 dB at most if it gets lost.
- The finished reel is evened out to about -14 LUFS with peaks under -1 dB, which suits Instagram.

## Music
- Talking reels get no music in the edit. If the person wants music, they add it in the Instagram app, at about 10 to 15%.
- If they will add music, prefer pop, sparkle and swish. A chime or ding has a clear note and can clash with the song.

## Their own sounds
Sounds they download (for example from pixabay.com) go in their `Reel Design System/sounds/` folder. Use them by file name without the extension.
