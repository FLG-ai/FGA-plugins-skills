# Reel safe zone

> Quick lane step file of fga-reel-studio. Checks a finished Instagram Reel (or TikTok or Short) for on-screen text that the app will cover or cut off - under the Reels header, behind the username, caption and music line, under the like, comment and share buttons, or off the sides - and returns a short report plus a contact sheet with the red zone drawn on and every problem boxed. Use on "check my reel", "will my text get cut off", "safe zone check", "is anything hidden by the buttons", or a video file someone wants to post. Not for editing the reel itself.

One job: before a reel goes up, find any on-screen text Instagram will hide. It runs on the person's own Mac. Nothing is uploaded anywhere.

## Step 0: check the tools

`<step>` is the folder this STEP.md sits in (shown as the skill's base directory when it loads). Run this first, unless reel-studio already ran its own check:

```bash
bash "<step>/scripts/check_tools.sh"
```

If anything shows MISS, show the person the list it prints and ask them to run those lines in Terminal, or offer to run them yourself once they say yes. Never install without a yes. Re-run the check after they install. The first real run takes a few extra seconds while it builds its small text reader.

## Step 1: get the video

Ask for the finished video file (drag it into the chat or give the path). It should be the version they will post, with all text burned in. Text they plan to add later in the Instagram app can't be checked.

## Step 2: run the check

```bash
"$PY" "<step>/scripts/safe_zone.py" "<path to video>"
```

Options: `--fps 4` is the default (four frames a second, enough to catch text that flashes up). Use `--fps 8` for very fast cuts. `--out <folder>` changes where the results go. By default they go in a new folder next to the video called `<video name> - safe zone check`.

It writes three files:
- `report.md`: the verdict and a table of problems, grouped by which part of the screen covers them, with the times and the text it read.
- `flagged.jpg`: one frame for each problem, with the red zone shaded, problem text boxed in red and safe text boxed in green.
- `overview.jpg`: the whole reel at a glance with the red zone drawn on.

## Step 3: tell them what to fix

Open `flagged.jpg` and look at it before you reply. Then give a short, plain answer:

1. **The verdict first.** "All clear" or "3 things will get covered".
2. **Each problem in one line:** when, what text, what covers it, and the fix. For example: "0:25, 'awkward' runs off the right edge. Make it smaller or move it in."
3. **Skip false alarms out loud.** The check reads every bit of text in the frame, including text inside screenshots, signs, clothes and timestamps in screen recordings. If a hit is clearly part of the footage and not their own caption or title, say so and leave it out of the fix list. Example: "The times on the voice notes at 0:03 are part of your screen recording, so ignore those."
4. Send them `flagged.jpg` and say where the folder is.

## The zone it uses

For a 1080x1920 vertical video (other sizes are scaled to match):

| Area | What covers it |
|---|---|
| Top 250 px | Reels header and camera icon |
| Below 1480 px | Username, caption, music line |
| 60 px at each side | Edge of the screen on some phones and in the grid crop |
| Right of 940 px, from 1050 to 1480 px | Like, comment, share and more buttons |

Safe area in plain words: keep text between 250 px and 1480 px from the top, at least 60 px in from each side, and left of the buttons in the lower third.

## Limits to mention if they matter

- It checks text, so a logo or emoji sticker with no letters isn't checked. Mention `overview.jpg` for those.
- Built for a Mac (it uses Apple's text recognition).
- Very stylised or tiny text can be missed. If something looked borderline to them, check that moment by eye in `overview.jpg`.
- Instagram moves its buttons now and then. If they ever look off, check a real reel on your phone and tell the skill the new numbers.
