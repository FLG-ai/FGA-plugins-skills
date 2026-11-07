# Choosing key words

Key words get the design system's key treatment (a color, or a serif swap). `plan_captions.py` guesses numbers, names and long words. Edit `key` in `captions_plan.json` by word index (from `words_tight.json`).

## Good key words
- Numbers and results: "30 days", "$5,000", "2 hours".
- Names: the product, app, place or person the reel is about.
- The one word in each sentence that carries the feeling or the point ("finally", "never", "free").
- About one word in five or six. Read just the key words in order: they should tell the story.

## Not key words
- "I", "I'm", "I'll", filler, and small words.
- The same word every time it repeats. Mark the first time it matters.

## small and skip
- `small`: word ranges shown in the smaller caption lower down, for when a window or big text sits where captions usually go. Never use it to hide words.
- `skip`: only words already on screen at that exact moment in a big text moment (for example the series title as it pops in). Every other spoken word gets a caption.
