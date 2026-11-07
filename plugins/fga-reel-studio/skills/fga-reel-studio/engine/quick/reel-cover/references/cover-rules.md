# Cover rules

## Picking the frame
- `find_frames.py` ranks frames by face quality (sharp, eyes open, facing the camera) and spreads the six picks across the reel. Point out which ones are smiling.
- A still from their camera roll is fine, even one the reel doesn't use. Add it with `--image <path>` and it joins the candidates.
- Skip frames mid-blink, mid-word with the mouth wide open, or with a hand over the face.

## The text
- The hook from `pops_plan.json`, in the design system's hook style. Version A has every line, version B drops the last line (cleaner).
- The text shrinks to stay above the hair and inside the side margins. If `text_scale` comes back under 0.7, the text has to be tiny to fit: use fewer lines, or pick a frame where the face sits lower.
- It starts 280 px from the top, so it sits inside the profile grid's 3:4 crop (240 to 1680 px).

## Checking
- Look at each `cover_<version>.jpg` and its `_grid.jpg`. Text must not touch the head and must read at grid size.
- Text behind the head only works when the head sits high in the frame. This skill doesn't do it. Mention it as a manual option only if they ask.

## Where it goes
Copy the chosen version to `<work folder>/COVER.jpg`. On Instagram, they choose it when posting (Edit cover, then Add from camera roll), or later from the reel's ⋯ menu, Edit, Edit cover.
