---
name: reel-captions
description: "Captions every spoken word of a framed reel, one word at a time with a small pop, in the caption style from the person's reel design system, as the fourth editing step of the reel chain. Picks out key words, shrinks long words to fit, keeps every caption inside Instagram's safe zone, and never skips a word. Use on: caption my reel, add subtitles, add captions in my style, words on screen."
disable-model-invocation: true
---

# Reel captions

Turn `framed.mp4` from reel-framing into `captioned.mp4`, with every spoken word on screen.

`<skill>` below means this skill's folder, shown as its base directory when it loads.

## Steps

1. **Check the tools.** Run `bash "<skill>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the files.** The work folder from reel-framing must hold `framed.mp4` and `words_tight.json`. Find their `design-system.json` from reel-design-system (ask where their `Reel Design System` folder is if it isn't next to the work folder). No design system yet: offer to run reel-design-system first, or use the italic punch style with yellow key words if they want to go ahead.
3. **Pick key words.** Run `python3 "<skill>/scripts/plan_captions.py" "<work folder>"`. Read `references/key-words.md`, edit `key` in `captions_plan.json`, then show them the key words in order: "These will stand out: … Add or drop any?" Wait for an answer.
4. **Render.** Tell them it takes a minute or two, then run `python3 "<skill>/scripts/render_captions.py" "<work folder>" "<design-system.json>"`.
5. **Check.** Read `captions_report.txt`. Every caption must be inside the safe zone. If any aren't, move `captions.y` in their design system up or down (small captions sit at 1400 or higher on screen), or shorten the case (lowercase is narrower than caps), and render again. Pull four frames with `ffmpeg -ss <word start + 0.1> -i captioned.mp4 -frames:v 1 <name>.jpg`: the word with the most letters, a key word, a plain word, and one from the last 10 seconds. Look at them: readable, nothing cut off, nothing over the face.
6. **Show the preview.** Send `captioned_preview.mp4`. Ask: "Any caption to fix?" Apply tweaks (key words, spelling in `words_tight.json`) and render again until they say yes. The next step in the chain is reel-text-pops, which reads `captioned.mp4`.

## Stop and ask
- At step 3: wait for the key word list to be agreed.
- At step 6: wait for a yes or tweaks.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to save that into the skill?" On a yes, write the correction into the reference file that step names, or into this file if it is a rule for every run.
- If the user says an output is good, ask: "Save this as an example?" On a yes, add it to `references/examples/`, creating the folder if it isn't there.
- After any change, reread the file and cut whatever no longer changes what you do.
