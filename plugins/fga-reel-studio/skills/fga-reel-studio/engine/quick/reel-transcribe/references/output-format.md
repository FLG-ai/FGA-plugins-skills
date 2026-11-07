# What the work folder holds

The next skills in the chain (tighten, captions, text pops, cover) read these files by name, so keep the names and formats.

| File | What it is |
|---|---|
| `proxy.mp4` | Working copy: upright, 1080x1920, 30 fps. All editing happens on this, never on the original. |
| `audio.wav` | 16 kHz mono audio, for transcribing and the timing check |
| `words.json` | Every spoken word in order: `{"t": "word", "s": start seconds, "e": end seconds, "i": index}`. Times are on `proxy.mp4`. |
| `sentences.txt` | One line per sentence with its word numbers and times, for reading. Rewritten whenever words.json changes. |
| `lines.txt` | The words split at every pause over 0.9 s, each as `word[index@start]`, for finding cut points |
| `timing-report.txt` | Every start or end the timing check moved |
| `corrections.json` | Spelling fixes, reused if the person re-runs this video |
| `source.json` | Path of the original video and its length |

## Words the model often mishears
Check these on every run: "AI" written as "Al", brand and app names, pet and people's names, numbers written as words or the other way round, and words cut at a hyphen.
