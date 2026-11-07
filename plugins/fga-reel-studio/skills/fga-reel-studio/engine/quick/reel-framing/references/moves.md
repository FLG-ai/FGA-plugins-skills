# The framing moves

`framing.json` has one entry per shot (a piece from tighten) plus `snaps`. All zooms are relative to the full frame (1.0 = no zoom).

| Move | What it does | Default |
|---|---|---|
| Base framing | Face about 18% of the frame height, eyes about a third down, centered left to right | from face detection per shot |
| Opener | First shot starts a little wider and pulls in slowly, picture lifts from slightly dark over 0.25 s | `push` 1.12x to 1.0x of a wider base, `opener_lift` 0.10 |
| Drift | Every talking shot slowly pulls out, so nothing sits dead still | 1.08x to 1.0x of base, linear |
| Zoom step | On a cut tighten marked as a big move, the next shot steps in closer so the jump reads as an edit | 1.16x to 1.10x of base, eases out |
| Snap zoom | A quick punch-in held on a key phrase | 1.18x of base, held for the phrase |
| Grade | `cool` (default): light and slightly cool, no skin smoothing: contrast 1.04, saturation 0.94, gamma 1.03. `calm_reds`: reds and magentas down 16% saturation plus a very light bilateral smooth, nothing lightened (the one to use when the person said a lighter cool grade washes them out). `none`: straight | `--grade`, or the `grade` key in design-system.json |

## Choosing snap zooms
- One or two per reel. Pick the phrase that carries the point: the big number, the result, the punchline.
- Add each as `{"from": first word index, "to": last word index}` using indexes from `words_tight.json`.
- Not on a phrase where the hands are moving fast or the person is mid-gesture. The punch-in exaggerates the movement.

## Fixing the framing
- Head cut off or too tight: rerun `plan_framing.py` with `--face 0.16`. Too loose: `--face 0.20`.
- One shot framed wrong (the face detector picked something else): edit that shot's `fx` (0 = left, 1 = right) and `fy` (0 = top, 1 = bottom) and `base_zoom`, and scale its `push` values to match.
- Hook text planned over the opener: keep the opener's zoom at or below 1.2 so there is room above the head.
- An action flagged by tighten (in `plan.json` `flag_actions`) during a shot: a zoom step or a tighter `base_zoom` on that shot can crop it out of frame.
