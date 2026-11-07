---
name: reel-text-pops
description: "Adds the big text moments to a captioned reel, each popping in on the word that triggers it, in the person's design system look, as the fifth editing step of the reel chain: the hook header from the first frame, the giant number, numbered list cards, scattered word pops, the series title and the comment call to action. Use on: add the hook, make the number pop, add list cards, add text to my reel, add the comment keyword."
disable-model-invocation: true
---

# Reel text pops

Turn `captioned.mp4` from reel-captions into `popped.mp4`, with the big text moments placed from the transcript.

`<skill>` below means this skill's folder, shown as its base directory when it loads.

## Steps

1. **Check the tools.** Run `bash "<skill>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the files.** The work folder must hold `captioned.mp4`, `words_tight.json` and `sentences_tight.txt` (sentences with word indexes on the tight video; `sentences.txt` is from before the cuts, so don't use its numbers), and you need their `design-system.json`. If `captioned.mp4` is missing, run reel-captions first.
3. **Find the moments.** Read `references/moments.md`. Read `sentences_tight.txt` and offer the moments as a short list (type, words, trigger word). Ask: "Change, add or drop any?" Wait for an answer, including the comment keyword if they want one.
4. **Write the plan** `<work folder>/pops_plan.json` as `{"elements": [ ... ]}`, one object per agreed moment with its `type` and fields from `references/moments.md`. Word indexes are the `i` values in `words_tight.json`.
5. **Render.** Tell them it takes about a minute, then run `python3 "<skill>/scripts/render_pops.py" "<work folder>" "<design-system.json>"`.
6. **Check.** Read `pops_report.txt`: every moment inside the safe zone. Pull one frame from the middle of each moment with `ffmpeg -ss <time> -i popped.mp4 -frames:v 1 <name>.jpg` and look: nothing over the face, nothing cut off. Fix the way `references/moments.md` says and render again.
7. **Show the preview.** Send `popped_preview.mp4` with the list from `pops_report.txt` in plain words. Apply tweaks until they say yes. The next step in the chain is reel-sound, which reads `popped.mp4` and `pops_plan.json`.

## Stop and ask
- At step 3: wait for the moments to be agreed.
- At step 7: wait for a yes or tweaks.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to save that into the skill?" On a yes, write the correction into the reference file that step names, or into this file if it is a rule for every run.
- If the user says an output is good, ask: "Save this as an example?" On a yes, add it to `references/examples/`, creating the folder if it isn't there.
- After any change, reread the file and cut whatever no longer changes what you do.
