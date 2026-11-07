# Reel tighten

> Quick lane step file of fga-reel-studio. Cuts a transcribed talking-to-camera video down to a tight take, as the second editing step of the reel chain: dead air at the start, long pauses, filler sounds, stutters, false starts, the weaker take of a line said twice, and moments looking down. Renders a preview, then saves the tightened video and the word timings moved onto it. Use on: tighten my reel, cut the pauses, remove the ums, cut the dead air, keep my best take.

Turn the transcribe work folder into a tight take: `tight.mp4` plus `words_tight.json`, which the rest of the chain reads.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-tighten/` inside fga-reel-studio).

## Steps

1. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the work folder.** Use the `<video name> - reel work` folder from reel-transcribe. It must hold `proxy.mp4`, `audio.wav` and `words.json`. If it doesn't exist, run reel-transcribe first.
3. **Ask what else to cut.** "Anything you already know you want out, like a moment you fix your hair or a line you flubbed?" Note their answer.
4. **Draft the plan.** Run `"$PY" "<step>/scripts/plan_cuts.py" "<work folder>"`, then `"$PY" "<step>/scripts/lookdown.py" "<work folder>"`.
5. **Edit the plan.** Read `references/cut-rules.md`. Then read `lines.txt`, `plan.json` and `lookdown.json`, decide every repeat, false start, double take and look-down, add their step 3 requests, and save the `keep` list.
6. **Render.** Run `"$PY" "<step>/scripts/render_tight.py" "<work folder>"`.
7. **Show the preview.** Send `tight_preview.mp4` with a short list: the new length against the raw length, each thing cut and why, and any cut marked "big move" or any piece flagged as ending while sound is still going in `cut_report.txt` (if the next kept word starts more than 0.5 s later it's only a tail or a breath, so leave it. End the piece one word earlier only when it runs into the next spoken word) (the framing step hides those with a zoom step). Ask: "Anything to put back or take out?"
8. **Apply tweaks.** Change `keep` in `plan.json` (or rerun `plan_cuts.py` with a different `--gap` for an overall faster or slower pace) and run step 6 again until they say yes. The next step in the chain is reel-framing, which reads `tight.mp4` and `segments.json`.

## Stop and ask
- At step 7: wait for a yes or tweaks before moving on.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
