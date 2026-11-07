---
name: reel-studio
description: "Runs the whole FGA IG Reel Designer + Editor chain, from a raw talking-to-camera video to a finished, captioned Instagram Reel and cover in the person's own look, with a preview after every step. Starts by asking for 2 or 3 reels they love to build their design system, or reuses a saved one. Use on: edit my reel, make a reel from this video, run the reel studio, turn this raw video into a reel."
disable-model-invocation: true
---

# Reel studio

Take one raw video to a finished reel and cover, running each skill in the chain in order. `<skill>` below means this skill's folder, shown as its base directory when it loads. `<plugin>` means the folder above it, which holds every other reel skill.

## Steps

1. **Ask for the reels first.** Open with one message: "To build your reel look, paste links to 2 or 3 Instagram reels whose style you love, and send me your raw video. If you've done this before, tell me where your Reel Design System folder is and I'll reuse your look." Wait for their answer.
2. **Check everything once.** Run `bash "<skill>/scripts/check_all.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes. In the steps below, skip each skill's own tools check.
3. **Design system.** If they gave reel links, follow `<plugin>/reel-design-system/SKILL.md` from its step 3 (it already has the links). If they have a saved design system, use its `design-system.json`.
4. **Run the chain.** For each skill below, read its `SKILL.md` in `<plugin>` and follow its steps, using one work folder for the video (made by reel-transcribe) and their `design-system.json`. Each skill stops at its preview: wait for their yes before moving on. Tell them which step they're on ("Step 3 of 8: framing").
   1. reel-transcribe. If tighten flags an action (like fixing hair) under the hook at the start, ask whether to start the reel a beat later instead.
   2. reel-tighten
   3. reel-framing
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
- If the user corrected a step, ask: "Want me to save that into the skill?" On a yes, write the correction into the reference file of the skill that step ran, or into this file if it is about how the chain runs.
- If the user says an output is good, ask: "Save this as an example?" On a yes, add it to `references/examples/`, creating the folder if it isn't there.
- After any change, reread the file and cut whatever no longer changes what you do.
