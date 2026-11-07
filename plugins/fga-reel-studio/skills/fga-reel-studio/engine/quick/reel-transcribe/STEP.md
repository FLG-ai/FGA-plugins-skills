# Reel transcribe

> Quick lane step file of fga-reel-studio. Turns a raw talking-to-camera video into a word-by-word transcript with exact timings, on the person's own Mac, as the first editing step of the reel chain (after the design system). Makes an upright 1080x1920 working copy, transcribes it, fixes words the model clipped by checking the real sound, and corrects spellings of names. Use on: transcribe my reel, get the words from this video, start editing this raw video, word timings for this clip.

Turn one raw video into a work folder whose `words.json` the rest of the reel chain reads.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-transcribe/` inside fga-reel-studio).

## Steps

1. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. If it says the speech model will download, tell them it is about 480 MB, once, and ask before the first run. Never install or download without a yes.
2. **Get the video.** Ask for the raw video file (drag it in or give the path). One video per run.
3. **Make the working copy.** Run `"$PY" "<step>/scripts/prepare.py" "<video>"`. It makes `<video name> - reel work` next to the video. Grab one frame from `proxy.mp4` and look at it: it must be upright and show the person. If they filmed landscape, tell them it was centre-cropped to vertical.
4. **Transcribe.** Run `"$PY" "<step>/scripts/transcribe.py" "<work folder>"` (add `--lang <code>` if they speak a language other than English). Warnings about matmul or divide by zero are harmless.
5. **Fix clipped words.** Run `"$PY" "<step>/scripts/fix_timing.py" "<work folder>"`. It moves the start and end of words at every pause, where cuts happen, to where the sound really starts and stops.
6. **Check spellings.** Show them `sentences.txt` and list every name, brand or number you are unsure of. Read `references/output-format.md`. Wait for their fixes, then run `"$PY" "<step>/scripts/spelling.py" "<work folder>" "wrong=right" ...` for each misheard word. If they name something they only said in general terms ("my community" is called The Studio), don't change the words: save it in `corrections.json` under `"_names"` for the text pops to use.
7. **Hand over.** Tell them the word count, how many timings were fixed, and where the work folder is. The next step in the chain is reel-tighten, which reads this folder.

## Stop and ask
- Before installing anything or the first model download: wait for a yes.
- At step 6: wait for their spelling fixes, or a "looks right".

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
