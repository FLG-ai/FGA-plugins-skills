# Reel cover

> Quick lane step file of fga-reel-studio. Makes a reel's cover as the last step of the reel chain: finds the frames where the person looks best (sharp, eyes open, facing the camera), lets them pick one or add a still from their camera roll, then puts the hook on it in their design system's hook style, above their head and inside the profile grid crop, in two versions. Use on: make my cover, reel cover, thumbnail for my reel, cover image.

Make `COVER.jpg` for the reel in the work folder.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-cover/` inside fga-reel-studio).

## Steps

1. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
2. **Find the files.** The work folder must hold `proxy.mp4` and ideally `pops_plan.json` (for the hook), and you need their `design-system.json`. Ask: "Want to use a frame from the video, or do you have a better photo for the cover?" Note any photo path.
3. **Find frames.** Run `"$PY" "<step>/scripts/find_frames.py" "<work folder>"` (add `--image <path>` for each photo they gave). Read `references/cover-rules.md`. Send `cover/candidates.jpg` and ask which number. Wait.
4. **Make the cover.** Run `"$PY" "<step>/scripts/make_cover.py" "<work folder>" "<design-system.json>" --pick <n>` (add `--lines '<json>'` if there is no hook in `pops_plan.json` or they want different words).
5. **Check.** Look at each `cover/cover_<version>.jpg` and `_grid.jpg`. Text must clear the head and read at grid size. Fix the way `references/cover-rules.md` says and run step 4 again.
6. **Let them choose.** Send `cover/versions.jpg`. Ask "A or B?" Wait, then copy their choice to `<work folder>/COVER.jpg` and tell them how to set it in Instagram, from `references/cover-rules.md`.

## Stop and ask
- At step 3: wait for their frame pick.
- At step 6: wait for A or B.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
