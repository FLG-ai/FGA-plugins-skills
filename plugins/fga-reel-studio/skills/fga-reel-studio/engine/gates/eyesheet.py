#!/usr/bin/env python3
"""Eye sheet: for every picture cut of a reel-kit project, the face from public/clean.mp4 (the bare picture) at
-0.30, -0.15 and -0.03 s before the cut and +0.00, +0.10, +0.25 s after it, one row per cut, labelled with the cut
time. Look for eyes down, eyes closed, leaning out.
Run: python3 eyesheet.py <project> <out.jpg>
"""
import json, os, subprocess, sys, tempfile
P, OUT = os.path.expanduser(sys.argv[1]), sys.argv[2]
TL = json.load(open(os.path.join(P, "timeline.json")))
clip = os.path.join(P, "public", "clean.mp4")
OFF = [-0.30, -0.15, -0.034, 0.0, 0.10, 0.25]
tmp = tempfile.mkdtemp()
rows = []
for i, c in enumerate(TL["picture_cuts"]):
    tiles = []
    for j, o in enumerate(OFF):
        f = os.path.join(tmp, f"{i:02d}_{j}.jpg")
        txt = f"{c:.2f}" if j == 0 else ("|" if j == 3 else "")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, c + o + 0.001):.3f}", "-i", clip, "-frames:v", "1",
                        "-vf", "crop=600:450:240:560,scale=160:120", f], check=True)
        tiles.append(f)
    row = os.path.join(tmp, f"row{i:02d}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + sum([["-i", t] for t in tiles], []) +
                   ["-filter_complex", f"hstack={len(tiles)}", row], check=True)
    rows.append((c, row))
# two columns of rows, each row labelled by a thin bar image is overkill: print the cut list in order instead
half = (len(rows) + 1) // 2
cols = []
for part in (rows[:half], rows[half:]):
    if not part:
        continue
    col = os.path.join(tmp, f"col{len(cols)}.jpg")
    if len(part) < half:   # pad to the same height
        part = part + [part[-1]] * (half - len(part))
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + sum([["-i", r] for _, r in part], []) +
                   ["-filter_complex", f"vstack={len(part)}" if len(part) > 1 else "null", col], check=True)
    cols.append(col)
subprocess.run(["ffmpeg", "-v", "error", "-y"] + sum([["-i", c] for c in cols], []) +
               ["-filter_complex", f"hstack={len(cols)}" if len(cols) > 1 else "null", OUT], check=True)
print("rows (left column, then right):", [round(c, 2) for c, _ in rows])
