---
name: reel-framing
description: "Gives a tightened talking-to-camera reel its movement, as the third editing step of the reel chain: frames the face for vertical with headroom for text, starts the opener wider with a light lift, adds a slow drift to every shot, a zoom step on jumpy cuts, one or two snap zooms on key lines, and a light cool grade. Use on: frame my reel, add zooms, make my talking head less flat, punch in on this line, fix the jump cuts."
disable-model-invocation: true
---

# Reel framing

Turn `tight.mp4` from reel-tighten into `framed.mp4`, with the sound and word timings unchanged.

`<skill>` below means this skill's folder, shown as its base directory when it loads.

## Steps

1. **Check the tools.** Run `bash "<skill>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the work folder** from reel-tighten. It must hold `tight.mp4`, `segments.json` and `words_tight.json`. If not, run reel-tighten first.
3. **Plan.** Run `python3 "<skill>/scripts/plan_framing.py" "<work folder>"`.
4. **Choose the snap zooms.** Read `references/moves.md`. Read `words_tight.json`, pick one or two key phrases, and offer them: "I'd punch in on '<phrase>' and '<phrase>'. Swap either?" Wait for an answer, then add them to `snaps` in `framing.json`.
5. **Render.** Tell them it takes about a minute, then run `python3 "<skill>/scripts/render_framing.py" "<work folder>"`. Grab four frames from `framed.mp4` (start, a zoom step, a snap, the end) and look at them: the whole head must be in frame with room above it. If not, fix it the way `references/moves.md` says and render again.
6. **Show the preview.** Send `framed_preview.mp4` with the list from `framing_report.txt` in plain words. Ask: "Any zoom to change?" Apply tweaks and render again until they say yes. The next step in the chain is reel-captions, which reads `framed.mp4` and `words_tight.json`.

## Stop and ask
- At step 4: offer the snap zoom phrases and wait.
- At step 6: wait for a yes or tweaks.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to save that into the skill?" On a yes, write the correction into the reference file that step names, or into this file if it is a rule for every run.
- If the user says an output is good, ask: "Save this as an example?" On a yes, add it to `references/examples/`, creating the folder if it isn't there.
- After any change, reread the file and cut whatever no longer changes what you do.
