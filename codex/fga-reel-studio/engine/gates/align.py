#!/usr/bin/env python3
"""Forced alignment of captions to the cut voice. words.json keeps the checked text, only the times move.
wav2vec2 (facebook/wav2vec2-base-960h, CTC, 20 ms frames) hears assets/voice.wav, and a Viterbi pass pins the known
words onto it in order, so every caption starts on the frame the word starts. Numbers are spoken out for the aligner
only ("30" -> THIRTY). With --write: words.json is saved (the old one goes to work/words.pre_align.json) and the
absolute times keyed to the old words move with them through a piecewise-linear warp (SOUND sfx and CAMERA
punch/zooms in edit.py). FX windows stay: they hang off picture cuts.
work/pins.json ([{"text", "next", "src_start", "src_end"}], source seconds heard with look.py) pins words the aligner
gets wrong before anything moves.
Run: "$PY" align.py <project> [--write]
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
WRITE = "--write" in sys.argv
LEAD = 0.04                      # captions land this much before the aligned onset (CTC fires a little late)
KEEP = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--keep=")]   # sfx files already at heard times
W = json.load(open(os.path.join(P, "words.json")))
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def say(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + say(n % 100))
    return say(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + say(n % 1000))


def spoken(t):
    t = t.lower().replace("’", "'")
    t = re.sub(r"(\d+):(\d\d)", lambda m: say(int(m.group(1))) + " " + say(int(m.group(2))), t)
    t = re.sub(r"\d[\d,]*", lambda m: say(int(m.group(0).replace(",", ""))), t)
    t = re.sub(r"[^a-z' ]", " ", t)
    return " ".join(t.split()).upper()


pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(P, "assets", "voice.wav"), "-ac", "1", "-ar", "16000",
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.float32).copy()

import torch  # noqa: E402
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor  # noqa: E402

name = "facebook/wav2vec2-base-960h"
proc, model = Wav2Vec2Processor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval()
with torch.inference_mode():
    chunks, hop = [], 16000 * 20                     # 20 s pieces keep memory small on the 8 GB laptop
    for a in range(0, len(audio), hop):
        x = proc(audio[a:a + hop], sampling_rate=16000, return_tensors="pt").input_values
        chunks.append(torch.log_softmax(model(x).logits[0], dim=-1).numpy())
    em = np.concatenate(chunks)                       # (frames, vocab), 20 ms per frame
FR = len(audio) / 16000 / len(em)
vocab = proc.tokenizer.get_vocab()
blank = vocab["<pad>"]
toks, owner = [], []                                  # tokens and the words.json index each belongs to
for i, w in enumerate(W):
    s = spoken(w["text"])
    for ch in s.replace(" ", "|"):
        if ch in vocab:
            toks.append(vocab[ch]); owner.append(i)
    toks.append(vocab["|"]); owner.append(-1)
toks, owner = toks[:-1], owner[:-1]
T, N = len(em), len(toks)
# Viterbi trellis (CTC without repeats of blanks between tokens: stay on a token, or move on through optional blank)
NEG = -1e9
tr = np.full((T + 1, N + 1), NEG); tr[0, 0] = 0
for t in range(T):
    stay = tr[t, 1:] + em[t, blank]
    move = tr[t, :-1] + em[t, toks]
    tr[t + 1, 1:] = np.maximum(stay, move)
    tr[t + 1, 0] = tr[t, 0] + em[t, blank]
# backtrack
j, path = N, []
for t in range(T, 0, -1):
    if j == 0:
        break
    stay = tr[t - 1, j] + em[t - 1, blank]
    move = tr[t - 1, j - 1] + em[t - 1, toks[j - 1]]
    if move >= stay:
        path.append((j - 1, t - 1)); j -= 1
    else:
        pass
first, last = {}, {}
for k, t in path:
    i = owner[k]
    if i < 0:
        continue
    first[i] = min(first.get(i, t), t); last[i] = max(last.get(i, t), t)
new = [dict(w) for w in W]
moved = []
for i, w in enumerate(W):
    if i in first:
        s, e = round(max(0.0, first[i] * FR - LEAD), 3), round((last[i] + 1) * FR, 3)
        if abs(s - w["start"]) < 0.6:
            new[i]["start"], new[i]["end"] = s, max(e, s + 0.04)
            moved.append((w["text"], w["start"], round(s - w["start"], 3)))
pp = os.path.join(P, "work", "pins.json")
if os.path.exists(pp):          # words the aligner gets wrong (a short "I" can snap onto the tail of the word before),
    KP = json.load(open(os.path.join(P, "timeline.json")))["keep"]      # pinned where the speaker says them, before sounds move
    def o(s):
        for g in KP:
            if g["src_in"] - 1e-6 <= s <= g["src_out"] + 1e-6:
                return g["out"] + (s - g["src_in"]) / g.get("speed", 1.0)
    for p in json.load(open(pp)):
        a, b = o(p["src_start"]), o(p["src_end"])
        c = [i for i in range(len(new) - 1) if new[i]["text"] == p["text"] and new[i + 1]["text"] == p["next"]]
        if a is None or b is None or not c:
            print("pin skipped:", p)
            continue
        i = min(c, key=lambda i: abs(W[i]["start"] - a))
        if abs(W[i]["start"] - a) > 1.0:
            print("pin too far from its word:", p)
            continue
        new[i]["start"], new[i]["end"] = round(a, 3), round(max(b, a + 0.06), 3)
        print(f"pinned {p['text']} ({p['next']}) at {a:.2f}")
for i in range(1, len(new)):
    if new[i]["start"] < new[i - 1]["start"]:
        new[i]["start"] = new[i - 1]["start"]
sh = [m[2] for m in moved]
print(f"{len(moved)}/{len(W)} words aligned; mean shift {np.mean(sh):+.3f} s, mean |shift| {np.mean(np.abs(sh)):.3f} s, "
      f"max |shift| {np.max(np.abs(sh)):.3f} s")
for t, s0, d in moved:
    if abs(d) >= 0.08 or "--all" in sys.argv:
        print(f"  {t:<14} {s0:7.2f}  {d:+.2f}")
if not WRITE:
    sys.exit(0)
pts = sorted({(w["start"], n["start"]) for w, n in zip(W, new)})


def warp(t):
    if t <= pts[0][0]:
        return t + pts[0][1] - pts[0][0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= t <= x1:
            return y0 + (t - x0) * (y1 - y0) / (x1 - x0) if x1 > x0 else y0
    return t + pts[-1][1] - pts[-1][0]


shutil.copy(os.path.join(P, "words.json"), os.path.join(P, "work", "words.pre_align.json"))
json.dump(new, open(os.path.join(P, "words.json"), "w"), indent=1)
D = os.path.join(P, "work", "sfx")
for f in sorted(os.listdir(D)) if os.path.isdir(D) else []:
    if not f.endswith(".txt") or f[:-4] in KEEP:
        continue
    txt = open(os.path.join(D, f)).read()
    txt = re.sub(r"^\(\s*([0-9.]+)", lambda x: f"({warp(float(x.group(1))):.3f}", txt, flags=re.M)
    txt = re.sub(r"(dict\(at=)([0-9.]+)", lambda x: f"{x.group(1)}{warp(float(x.group(2))):.3f}", txt)
    open(os.path.join(D, f), "w").write(txt)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "merge_sound.py"), P], check=True)
E = os.path.join(P, "edit.py")
src = open(E).read()
cm = re.search(r"^CAMERA = dict\(.*$", src, flags=re.M)
if cm:
    line = re.sub(r"punch=\[(.*?)\]", lambda x: "punch=[" + re.sub(r"\(([0-9.]+),", lambda y: f"({warp(float(y.group(1))):.3f},", x.group(1)) + "]", cm.group(0))
    line = re.sub(r"zooms=\[(.*?)\]", lambda x: "zooms=[" + re.sub(r"\(([0-9.]+), ([0-9.]+),", lambda y: f"({warp(float(y.group(1))):.3f}, {warp(float(y.group(2))):.3f},", x.group(1)) + "]", line)
    src = src[:cm.start()] + line + src[cm.end():]
open(E, "w").write(src)
print("words.json, the sfx files (but", KEEP, ") and CAMERA moved to the aligned times")
