# Reel studio

> Quick lane step file of fga-reel-studio. Runs the whole FGA IG Reel Designer + Editor chain, from a raw talking-to-camera video to a finished, captioned Instagram Reel and cover in the person's own look, with a preview after every step. Starts by asking for 2 or 3 reels they love to build their design system, or reuses a saved one. Use on: edit my reel, make a reel from this video, run the reel studio, turn this raw video into a reel.

Take one raw video to a finished reel and cover, running each skill in the chain in order. `<step>` below means the folder holding this STEP.md (`engine/quick/reel-studio/` inside fga-reel-studio). `<quick>` means `engine/quick/`, the folder above it, which holds every other step.

## Steps

> Inside fga-reel-studio: steps 1 to 3 below are done by SKILL.md (examples first, the computer check, then the style folder `RK_HOME/style/`). Start at step 4 with the work folder, and read the design system from `RK_HOME/style/design-system.json`.

1. **Ask for the reels first.** Open with one message: "To build your reel look, paste links to 2 or 3 Instagram reels whose style you love, and send me your raw video. If you've done this before, tell me where your Reel Design System folder is and I'll reuse your look." Wait for their answer.
2. **Check everything once.** Run `bash "<step>/scripts/check_all.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes. In the steps below, skip each skill's own tools check.
3. **Design system.** If they gave reel links, follow `<quick>/reel-design-system/STEP.md` from its step 3 (it already has the links). If they have a saved design system, use its `design-system.json`.
4. **Run the chain.** For each skill below, read its `STEP.md` in `<quick>` and follow its steps, using one work folder for the video (made by reel-transcribe) and their `design-system.json`. Each skill stops at its preview: wait for their yes before moving on. Tell them which step they're on ("Step 3 of 8: framing").
   1. reel-transcribe. If tighten flags an action (like fixing hair) under the hook at the start, ask whether to start the reel a beat later instead.
   2. reel-tighten
   3. reel-framing
   3b. reel-windows, only if they have images or clips to show. Ask first, skip it if they have none
   4. reel-captions
   5. reel-text-pops
   6. reel-sound
   7. reel-safe-zone, run on `final.mp4`. Fix anything it finds in the skill that placed it, then check again.
   8. reel-cover
5. **Hand over.** Read `references/handover.md` and follow it.

## Stop and ask
- At step 1: wait for the reels and the video.
- Every skill's own stop points (picks and previews) still apply. Never skip a preview to go faster.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
