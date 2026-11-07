# Reel windows

> Quick lane step file of fga-reel-studio. Optional. Puts the person's own images and clips on the reel as floating windows, a small square, or a full-bleed cutaway, between framing and captions. Only used when they have images or clips to show. Use on: add my screenshots, put this on screen, show this clip while I talk, cutaway.

Turn `framed.mp4` from reel-framing into `windowed.mp4`, with the sound and word timings unchanged. The captions step picks `windowed.mp4` up by itself and drops to a smaller caption under each window.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-windows/` inside fga-reel-studio).

## Steps

1. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Ask what they have.** "Do you have screenshots, screen recordings, photos or clips to show while you talk?" None: skip this step, the chain goes straight to reel-captions. Read `references/windows.md`.
3. **Find the moments.** Read `sentences_tight.txt` and `words_tight.json`. Offer a short list: which image or clip, on which words, in which style (window, small square or full bleed). Ask what they still need to send, each tied to its moment. Wait for their answer.
4. **Check privacy.** Look at every image. Other people's names, faces, messages and logos get blurred (`blur` boxes) or cropped. Ask before using anything that shows someone else.
5. **Write the plan** `<work folder>/windows_plan.json` as described in `references/windows.md`. Word indexes are the `i` values in `words_tight.json`.
6. **Render.** Run `"$PY" "<step>/scripts/render_windows.py" "<work folder>" "<design-system.json>"`. Read `windows_report.txt`. Pull a frame from the middle of each window with `ffmpeg -ss <time> -i windowed.mp4 -frames:v 1 <name>.jpg` and look: nothing private readable, the window clear of the face, bottom edge at or above y 1360.
7. **Show the preview.** Send `windowed_preview.mp4` with the list from the report in plain words. Apply tweaks and render again until they say yes. The next step is reel-captions, which reads `windowed.mp4`.

## Stop and ask
- At step 3: wait for the moments and for anything they still have to send.
- At step 4: wait for a yes on anything that shows other people.
- At step 7: wait for a yes or tweaks.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
