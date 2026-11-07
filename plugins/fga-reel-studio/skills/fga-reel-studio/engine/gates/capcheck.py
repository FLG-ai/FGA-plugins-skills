#!/usr/bin/env python3
"""Caption timing check. A greedy wav2vec2 read of the cut voice (assets/voice.wav) is matched word for word to
words.json (difflib on the spelled-out letters). Every caption that starts more than TOL before or after its heard word
is listed with the heard time. Captions land LEAD (0.04 s) before the heard onset, as align.py does. --fix moves each
flagged caption to the heard time (between its neighbours; words.json is copied to work/words.pre_capfix.json first).
Run: "$PY" capcheck.py <project> [--tol=0.15] [--fix]
"""
import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
TOL = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--tol=")), 0.15))
LEAD = 0.04
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
    return re.sub(r"[^a-z' ]", " ", t).upper().split()


pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(P, "assets", "voice.wav"), "-ac", "1", "-ar", "16000",
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.float32).copy()
import torch  # noqa: E402
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor  # noqa: E402

name = "facebook/wav2vec2-base-960h"
proc, model = Wav2Vec2Processor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval()
inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
heard = []
hop = 16000 * 20
with torch.inference_mode():
    for a in range(0, len(audio), hop):
        seg = audio[a:a + hop]
        ids = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values).logits[0].argmax(-1).numpy()
        fr = len(seg) / 16000 / len(ids)
        cur, t0, prev = "", 0, None
        for t, i in enumerate(ids):
            ch = inv[int(i)]
            if i != prev and ch != "<pad>":
                if ch == "|":
                    if cur:
                        heard.append((cur, a / 16000 + t0 * fr))
                    cur = ""
                else:
                    if not cur:
                        t0 = t
                    cur += ch
            prev = i
        if cur:
            heard.append((cur, a / 16000 + t0 * fr))
cap = []                                              # (caption index, spelled word) for every spoken token
for i, w in enumerate(W):
    for s in spoken(w["text"]):
        cap.append((i, s))
sm = difflib.SequenceMatcher(a=[c[1] for c in cap], b=[h[0] for h in heard], autojunk=False)
first = {}
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        ci = cap[blk.a + k][0]
        if ci not in first:
            first[ci] = heard[blk.b + k][1]
bad = 0
for i, w in enumerate(W):
    if i not in first:
        continue
    want = round(first[i] - LEAD, 3)
    d = w["start"] - want
    if abs(d) > TOL:
        bad += 1
        print(f"  {w['text']:<14} caption {w['start']:7.2f}  heard {first[i]:7.2f}  ({'early' if d < 0 else 'late'} {abs(d):.2f} s)")
print(f"{os.path.basename(P)}: {len(first)}/{len(W)} captions matched to the voice, {bad} off by more than {TOL} s")
if "--fix" in sys.argv and bad:
    import shutil
    shutil.copy(os.path.join(P, "words.json"), os.path.join(P, "work", "words.pre_capfix.json"))
    moved = 0
    for i, w in enumerate(W):
        if i not in first:
            continue
        want = round(first[i] - LEAD, 3)
        if abs(w["start"] - want) <= TOL:
            continue
        lo = W[i - 1]["start"] + 0.04 if i else 0.0
        hi = W[i + 1]["start"] - 0.04 if i + 1 < len(W) else want + 1
        if not (lo <= want <= hi):
            print(f"  not moved (neighbours): {w['text']} {w['start']:.2f} -> {want:.2f}")
            continue
        ln = max(0.06, w["end"] - w["start"])
        w["start"] = want
        w["end"] = round(min(want + ln, W[i + 1]["start"] if i + 1 < len(W) else want + ln), 3)
        if i and W[i - 1]["end"] > want:
            W[i - 1]["end"] = want
        moved += 1
    json.dump(W, open(os.path.join(P, "words.json"), "w"), indent=1)
    print(f"  fixed {moved} captions in words.json")
