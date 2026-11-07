#!/usr/bin/env python3
"""Look-down finder. Scans every frame of a video (or a range): OpenCV's frontal-face detector finds the face,
the open-eye detector looks in the top half of it. A run of frames with the face found and no open eye is a blink
(a few frames) or a look-down / eyes shut (longer). Prints every run of MIN frames or more, with the picture cut it
touches. Runs on the system python3 (needs cv2), no extra models.
Run: python3 eyecheck.py <video> [--from=s] [--to=s] [--min=4] [--cuts=<timeline.json>] [--sheet=<out.jpg>] [--frames]
"""
import json
import subprocess
import sys

import cv2
import numpy as np

V = sys.argv[1]
arg = {a.split("=", 1)[0][2:]: a.split("=", 1)[1] for a in sys.argv[2:] if a.startswith("--") and "=" in a}
A, B, MIN = float(arg.get("from", 0)), float(arg.get("to", 1e9)), int(arg.get("min", 5))
CUTS = json.load(open(arg["cuts"]))["picture_cuts"] if "cuts" in arg else []
W = 540
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", V],
                           capture_output=True, text=True).stdout.strip() or 0)
B = min(B, dur)
H = int(round(W * 16 / 9))
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{A:.3f}", "-t", f"{B - A:.3f}", "-i", V, "-vf",
                      f"fps=30,scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
F = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
ec = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
rows = []
for i, g in enumerate(F):
    t = A + i / 30
    g2 = cv2.equalizeHist(g)
    faces = fc.detectMultiScale(g2, 1.1, 5, minSize=(110, 110))
    if len(faces) == 0:
        rows.append((t, 0, 0, None)); continue
    up = [f for f in faces if f[1] + f[3] / 2 < 0.55 * H]     # the face sits in the top half (a print on a shirt
    if not up:                                                 # lower down can fool the detector)
        rows.append((t, 0, 0, None)); continue
    x, y, w, h = max(up, key=lambda f: f[2] * f[3])
    band = g2[y + int(0.18 * h):y + int(0.58 * h), x:x + w]
    eyes = ec.detectMultiScale(band, 1.05, 6, minSize=(int(w * 0.12), int(w * 0.12)), maxSize=(int(w * 0.38), int(w * 0.38)))
    rows.append((t, 1, len(eyes), (x, y, w, h)))
# a frame is "down" when the face is found and fewer than two open eyes are: shut lids, lowered eyes. Runs bridge
# single stray frames (the eye detector sometimes finds lashes on a lowered lid).
down = [bool(f) and e < 2 for t, f, e, _ in rows]
runs, i = [], 0
while i < len(rows):
    if not down[i]:
        i += 1; continue
    j = i
    while j + 1 < len(rows) and (down[j + 1] or (j + 2 < len(rows) and down[j + 2])):
        j += 1
    while j > i and not down[j]:
        j -= 1
    runs.append([rows[i][0], rows[j][0]])
    i = j + 1
nf = sum(1 for r in rows if r[1]); ne = sum(1 for r in rows if r[1] and r[2])
print(f"{V.split('/')[-1]} {A:.2f}-{B:.2f}: {len(rows)} frames, face in {nf}, open eye in {ne}")
for a, b in runs:
    n = int(round((b - a) * 30)) + 1
    if n < MIN:
        continue
    near = [c for c in CUTS if a - 0.6 <= c <= b + 0.6]
    print(f"  eyes shut/down {a:7.3f}-{b:7.3f}  ({n} frames){'  near cut ' + ', '.join(f'{c:.3f}' for c in near) if near else ''}")
if "--frames" in sys.argv:
    print(" ".join(f"{t:.2f}:{'-' if not f else e}" for t, f, e, _ in rows))

if "sheet" in arg:                               # one row per flagged run: the eyes from just before to just after it
    tiles = []
    box0 = next((r[3] for r in rows if r[3] is not None), (0, 0, W, W))
    for a, b in runs:
        if int(round((b - a) * 30)) + 1 < MIN:
            continue
        ts = np.linspace(a - 0.13, b + 0.13, 8)
        row = []
        for t in ts:
            k = min(max(int(round((t - A) * 30)), 0), len(rows) - 1)
            bx = rows[k][3] or next((rows[j][3] for j in range(k, -1, -1) if rows[j][3] is not None), box0)
            x, y, w, h = bx
            crop = F[k][max(0, y + int(0.15 * h)):y + int(0.62 * h), max(0, x):x + w]
            crop = cv2.resize(crop, (200, max(1, int(200 * crop.shape[0] / max(1, crop.shape[1])))))
            crop = cv2.resize(crop, (200, 94))
            c = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
            col = (0, 0, 255) if down[k] else (0, 200, 0)
            cv2.rectangle(c, (0, 0), (199, 93), col, 2)
            cv2.putText(c, f"{rows[k][0]:.2f}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
            row.append(c)
        lab = np.zeros((94, 120, 3), np.uint8)
        cv2.putText(lab, f"{a:.2f}", (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cv2.putText(lab, f"-{b:.2f}", (4, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        tiles.append(np.hstack([lab] + row))
    if tiles:
        cv2.imwrite(arg["sheet"], np.vstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 82])
        print("sheet", arg["sheet"], len(tiles), "rows")
