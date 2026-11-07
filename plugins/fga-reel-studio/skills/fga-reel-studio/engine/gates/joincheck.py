#!/usr/bin/env python3
"""Join check: no look-downs, no glances at a script, no half words, no dead pauses.
For every picture piece of a reel-kit project: frames at its first frame, +0.15 s, and its last 0.4 / 0.25 / 0.12 /
0.03 s, tiled one row per piece (labelled), plus every pause over 0.35 s inside the kept voice.
Run: python3 joincheck.py <project>  -> <project>/work/joincheck.jpg and a pause list
"""
import json
import os
import subprocess
import sys

import numpy as np

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
TL = json.load(open(os.path.join(P, "timeline.json")))
clean = os.path.join(P, "public", "clean.mp4")
out = os.path.join(P, "work", "joincheck")
os.makedirs(out, exist_ok=True)
rows = []
pieces = TL["pieces"]
LAST = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", clean], capture_output=True, text=True).stdout.strip()) / 30 - 0.04
for k, pc in enumerate(pieces):
    a, b = pc["out_start"], pc["out_end"]
    ts = [a + 0.02, a + 0.15, b - 0.40, b - 0.25, b - 0.12, b - 0.03]
    imgs = []
    for j, t in enumerate(ts):
        f = os.path.join(out, f"p{k:02d}_{j}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(LAST, max(0, t)):.3f}", "-i", clean, "-frames:v", "1",
                        "-vf", f"crop=iw:ih*0.42:0:ih*0.22,scale=200:-2,drawtext=text='{k} {t:.2f}':x=4:y=4:fontsize=16:fontcolor=yellow:box=1:boxcolor=black@0.6",
                        f], check=True)
        imgs.append(f)
    row = os.path.join(out, f"row{k:02d}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *sum((["-i", i] for i in imgs), []), "-filter_complex",
                    f"hstack={len(imgs)}", row], check=True)
    rows.append(row)
half = (len(rows) + 1) // 2
for n, chunk in enumerate([rows[:half], rows[half:]]):
    if chunk:
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum((["-i", r] for r in chunk), []), "-filter_complex",
                        f"vstack={len(chunk)}", os.path.join(P, "work", f"joincheck_{n}.jpg")], check=True)
# pauses inside the voice
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(P, "assets", "voice.wav"), "-ac", "1", "-ar", "16000",
                      "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
n = len(x) // 160
db = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-6)
thr = np.percentile(db, 90) - 30
quiet = db < thr
words = json.load(open(os.path.join(P, "words.json")))
gaps, s = [], None
for i, qv in enumerate(quiet):
    if qv and s is None:
        s = i
    if not qv and s is not None:
        if (i - s) / 100 >= 0.35:
            gaps.append((s / 100, i / 100))
        s = None
print("pauses over 0.35 s in the voice (s):")
for g0, g1 in gaps:
    nxt = next((w["text"] for w in words if w["start"] >= g0 - 0.05), "")
    prv = [w["text"] for w in words if w["end"] <= g1 + 0.05][-1:]
    print(f"  {g0:6.2f}-{g1:6.2f} ({g1 - g0:.2f}s)  after {prv} before {nxt}")
print("sheets:", os.path.join(P, "work", "joincheck_0.jpg"), os.path.join(P, "work", "joincheck_1.jpg"))
