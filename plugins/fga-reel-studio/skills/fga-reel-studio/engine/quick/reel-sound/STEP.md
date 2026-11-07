# Reel sound

> Quick lane step file of fga-reel-studio. Adds sound effects to a reel's text moments and mixes them under the voice, as the sixth editing step of the reel chain: a pop on list cards, numbers and the call to action, a sparkle on the series title, soft clicks on word pops, then evens out the loudness for Instagram. Use on: add sound effects, add pops to my reel, mix the sound, make it sound finished.

Turn `popped.mp4` from reel-text-pops into `final.mp4`, with sound effects on the text moments and the loudness set for Instagram.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-sound/` inside fga-reel-studio).

## Steps

1. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the files.** The work folder must hold `popped.mp4`, `pops_plan.json` and `words_tight.json`, and you need their `design-system.json`. If `popped.mp4` is missing, run reel-text-pops first.
3. **Ask about music.** "Will you add a song in the Instagram app?" If yes, use only pop, sparkle and swish (no chime or ding). If no, any of their kept sounds work.
4. **Plan.** Run `"$PY" "<step>/scripts/plan_sound.py" "<work folder>" "<design-system.json>"`. Read `references/sound-rules.md` and adjust `sound_plan.json` to it and to their answer at step 3.
5. **Mix.** Run `"$PY" "<step>/scripts/render_sound.py" "<work folder>" "<design-system.json>"`. Read `sound_report.txt`: loudness within 1 of -14 LUFS and peak under -1 dBFS.
6. **Show the preview.** Send `final_preview.mp4` with the cue list from `sound_report.txt` in plain words. Ask: "Any sound to change, move or drop?" Apply tweaks and mix again until they say yes. The next step in the chain is reel-safe-zone (a last check of `final.mp4`), then reel-cover.

## Stop and ask
- At step 3: wait for their answer.
- At step 6: wait for a yes or tweaks.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
