#!/usr/bin/env python3
"""Re-time captions on the cut voice. words.json keeps the checked text, only the times move.
faster-whisper small.en word timestamps on <project>/assets/voice.wav (no prompt, so nothing is invented), matched to
words.json word by word (difflib on normalised text). A matched word takes the heard start and end when they are
within 0.6 s of the old ones, and unmatched words keep their times. With --write: words.json is saved (the old one goes
to work/words.pre_retime.json) and every absolute time keyed to the old words moves with them through a
piecewise-linear warp (SOUND sfx times and CAMERA punch/zooms in edit.py). FX windows stay: they hang off picture cuts.
Run: "$PY" retime.py <project> [--write]   (prints the shifts)
"""
import difflib
import json
import os
import re
import shutil
import sys

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
WRITE = "--write" in sys.argv
W = json.load(open(os.path.join(P, "words.json")))


def norm(t):
    return re.sub(r"[^a-z0-9']", "", t.lower().replace(",", ""))


from faster_whisper import WhisperModel  # noqa: E402

model = WhisperModel("small.en", device="cpu", compute_type="int8")
import subprocess  # noqa: E402
import numpy as np  # noqa: E402
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(P, "assets", "voice.wav"), "-ac", "1", "-ar", "16000",
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout   # the venv's PyAV is too new for faster-whisper
segs, _ = model.transcribe(np.frombuffer(pcm, np.float32), language="en", word_timestamps=True,
                           beam_size=5, vad_filter=False, condition_on_previous_text=False)
H = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])]
a = [norm(w["text"]) for w in W]
b = [norm(h[0]) for h in H]
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
new = [dict(w) for w in W]
moved = []
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        i, j = blk.a + k, blk.b + k
        s, e = H[j][1], H[j][2]
        if abs(s - W[i]["start"]) < 0.6 and e > s:
            new[i]["start"], new[i]["end"] = round(s, 3), round(e, 3)
            moved.append((W[i]["text"], W[i]["start"], round(s - W[i]["start"], 3)))
for i in range(1, len(new)):                   # keep starts in order
    if new[i]["start"] < new[i - 1]["start"]:
        new[i]["start"] = new[i - 1]["start"]
sh = [m[2] for m in moved]
print(f"{len(moved)}/{len(W)} words matched; mean shift {sum(sh) / max(1, len(sh)):+.3f} s, "
      f"mean |shift| {sum(abs(x) for x in sh) / max(1, len(sh)):.3f} s, max |shift| {max([abs(x) for x in sh] or [0]):.3f} s")
for t, s0, d in moved:
    if abs(d) >= 0.08:
        print(f"  {t:<14} {s0:7.2f}  {d:+.2f}")
if not WRITE:
    sys.exit(0)
pts = sorted({(w["start"], n["start"]) for w, n in zip(W, new)})


def warp(t):
    """old timeline -> heard timeline, piecewise linear between word starts, flat beyond the ends"""
    if not pts or t <= pts[0][0]:
        return t + (pts[0][1] - pts[0][0] if pts else 0)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= t <= x1:
            return y0 + (t - x0) * (y1 - y0) / (x1 - x0) if x1 > x0 else y0
    return t + (pts[-1][1] - pts[-1][0])


os.makedirs(os.path.join(P, "work"), exist_ok=True)
shutil.copy(os.path.join(P, "words.json"), os.path.join(P, "work", "words.pre_retime.json"))
json.dump(new, open(os.path.join(P, "words.json"), "w"), indent=1)
E = os.path.join(P, "edit.py")
src = open(E).read()
m = re.search(r"^SOUND = dict\(music=None, sfx=\[\n(.*?)^\]\)\n", src, flags=re.S | re.M)
if m:
    body = m.group(1)
    body = re.sub(r"^(    \()([0-9.]+)", lambda x: f"{x.group(1)}{warp(float(x.group(2))):.3f}", body, flags=re.M)
    body = re.sub(r"(dict\(at=)([0-9.]+)", lambda x: f"{x.group(1)}{warp(float(x.group(2))):.3f}", body)
    src = src[:m.start(1)] + body + src[m.end(1):]
cm = re.search(r"^CAMERA = dict\(.*$", src, flags=re.M)
if cm:
    line = cm.group(0)
    line = re.sub(r"punch=\[(.*?)\]", lambda x: "punch=[" + re.sub(r"\(([0-9.]+),", lambda y: f"({warp(float(y.group(1))):.3f},", x.group(1)) + "]", line)
    line = re.sub(r"zooms=\[(.*?)\]\)", lambda x: "zooms=[" + re.sub(r"\(([0-9.]+), ([0-9.]+),", lambda y: f"({warp(float(y.group(1))):.3f}, {warp(float(y.group(2))):.3f},", x.group(1)) + "])", line)
    src = src[:cm.start()] + line + src[cm.end():]
open(E, "w").write(src)
print("words.json, SOUND and CAMERA moved to the heard times")
