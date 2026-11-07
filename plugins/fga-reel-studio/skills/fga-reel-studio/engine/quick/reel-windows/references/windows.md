# Windows: modes and the plan file

## Modes
| Mode | What it looks like | Default size and place | Use for |
|---|---|---|---|
| `window` | A screenshot or screen recording in a rounded window over the shot, the room visible around it. Soft shadow, no border. Fades in with a small rise (silent) | 620 to 984 px wide (default 900), top at y 640, centered. The bottom edge stays at or above y 1360 so the small captions fit under it | Apps, profiles, messages, any screen |
| `square` | Real-life footage or a photo as a small rounded square instead of full screen | 560 px square at x 260, y 785, cropped to fill | A walk, the car, a pet, a place |
| `fullbleed` | The picture takes the whole screen while their voice keeps going | 1080 x 1920, cropped to fill, a quick fade | A real-life moment, a close-up |

Windows are silent by default. A sound on a window is added only if the person asks.

## windows_plan.json
```json
{"windows": [
  {"mode": "window", "src": "/path/to/screenshot.png", "at_word": 12, "until_word": 20, "w": 900, "blur": [[0.05, 0.10, 0.40, 0.08]]},
  {"mode": "square", "src": "/path/to/clip.mov", "at_word": 31, "until_word": 38},
  {"mode": "fullbleed", "src": "/path/to/photo.jpg", "at_word": 44, "until_word": 49}
]}
```
- `src`: an image or a video. A clip plays from its start and holds its last frame.
- `at_word` and `until_word`: word indexes in `words_tight.json`. The window appears as the first word starts and clears a quarter second after the last one ends (`tail` changes that).
- `w`, `x`, `y`: optional. Leave them out for the defaults.
- `blur`: optional boxes `[x, y, w, h]` as fractions (0 to 1) of the picture, for names, faces, messages and logos that are not theirs.
- Optional `windows` key in `design-system.json` changes the defaults: `radius`, `w`, `y`, `bottom`, `rise`, `square`, `square_x`, `square_y`.

## Rules
- Two windows never overlap in time.
- The window does not sit on the face for long. If it does, move `y` lower or use `square`.
- Every spoken word stays on screen: the captions step shows the words under a window as small captions, below it.
- Never put another person's name, face or message on screen unblurred.
- The safe-zone check reads text inside screenshots and may flag it. That is part of their screen, not their caption, so say so and leave it.
