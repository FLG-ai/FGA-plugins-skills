# Reel design system

> Quick lane step file of fga-reel-studio. Builds a person's own reel design system from 2 or 3 Instagram reels they love plus a starter set of free fonts and sounds. Pulls frames from each reel, writes a style card naming the techniques, lets them pick caption, title, number and word-pop styles, then makes a visual design system page and a settings file the reel editor skills read. Use on: build my reel design system, make my reel style guide, set up my reel look, here are reels I love, what fonts and sounds should my reels use.

Turn 2 or 3 reels someone loves into their own reel look: a visual page plus `design-system.json`, which every reel editor skill in this plugin reads.

`<step>` below means the folder holding this STEP.md (`engine/quick/reel-design-system/` inside fga-reel-studio).

## Steps

> Inside fga-reel-studio: steps 1 and 2 already happened (the examples were asked first and the tools were checked), and the folder in step 3 is `RK_HOME/style/` (default `~/reel-kit/style/`) instead of a new `Reel Design System` folder. Use the links they already gave and start at step 4.

1. **Ask for the reels first.** Open with one message, before anything else: "To build your reel look, paste links to 2 or 3 Instagram reels whose style you love. If you have a screenshot of yourself from a video you've filmed, add that too, and I'll show every style on you." Wait for the links. Fewer than 2, ask for one more. More than 3, ask which 3 matter most.
2. **Check the tools.** Run `bash "<step>/scripts/check_tools.sh"`. If anything shows MISS, show the list and ask them to run the install lines, or offer to run them once they say yes. Never install without a yes.
3. **Set up the folder.** Ask what to call their look, then make a folder named `Reel Design System` in the current folder (or where they say) with `refs/`, `stills/` and `sounds/` inside.
4. **Pull each reel in.** Grab an overview sheet, a detail sheet and three single frames per reel into `refs/`. Read `references/pull-reels.md`.
5. **Write a style card per reel**, naming the techniques worth borrowing. Show the cards in one short message. Read `references/style-card.md` and the technique names in `references/starter-set.md`.
6. **Show the starter options.** Run `"$PY" "<step>/scripts/render_styles.py" options "<folder>/stills/options" --bg <their frame>`, send them `options.jpg`, and list the options with the closest match to their inspo marked, using the fonts and sounds in `references/starter-set.md`.
7. **Let them pick.** They choose one caption style, one title style and their colors. Mention once that two optional extras exist, a giant number pop and scattered word pops, say in a line what each does, and add the one they want to `extras` and let them pick its style. If they do not want them, leave `extras` empty and do not include them in the plan. Their colors (start from the colors in their inspo). Then play the sounds: copy `<step>/assets/sounds/` into `<folder>/sounds/`, send the files they ask to hear, and let them keep three to six. Wait for every pick.
8. **Write the settings file** `<folder>/design-system.json` from their picks and the style cards. Read `references/settings-file.md`.
9. **Render their look.** Run `"$PY" "<step>/scripts/render_styles.py" system "<folder>/design-system.json" "<folder>/stills" --bg <their frame>`. Look at `system.jpg`. Every element must sit inside the safe zone and read clearly over their frame. Fix and re-render anything that doesn't, using `captions.y`, `word_pops.spots` or the colors in the settings file. If something still can't be fixed, tell them what and why.
10. **Build the page.** Run `"$PY" "<step>/scripts/make_page.py" "<folder>"`, run `open "<folder>/Reel Design System.html"` so it opens in their browser, and send it. Tell them the reel editor skills read `design-system.json` from this folder, so keep the two together.

## Stop and ask
- At step 7: offer the real options and wait for each pick. Never pick for them.
- Before changing a rule in the settings file: show the change and wait for a yes.

## Keep improving

After each run:
- If the user corrected a step, ask: "Want me to remember that?" On a yes, add a dated line to `RK_HOME/style/RULES.md` (SKILL.md step 9). Never write into the skill folder.
- If the user says an output is good, ask: "Save this as an example?" On a yes, keep it in `RK_HOME/style/examples/`, creating the folder if it isn't there.
