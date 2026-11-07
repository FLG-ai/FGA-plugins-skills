#!/usr/bin/env python3
"""Precise joins. A cut that lands inside a word leaves half words, doubled syllables and clipped endings (word
times from a transcript can run 0.4 s off). For every kept piece this finds where its first and last captioned words
really start and end in the source (a greedy wav2vec2 read for the word, 5 ms energy for the edge) and moves each cut
into the quiet beside them: LEAD before the first word, TAIL after the last, never into the neighbouring speech. A cut
that already sits in the quiet next to its word stays where it is.
work/keep_manual.json ({"<piece index>": [in, out]}, source seconds) overrides pieces by hand (repeats inside a
piece, takes stitched mid-phrase). Prints a table and writes work/keep_fixed.json (KEEP as a list of [in, out]).
Run: "$PY" fixjoins.py <project>
"""
import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
LEAD, TAIL = 0.10, 0.10
QUIET = -36.0                  # dB re loud speech (99th percentile of 5 ms frames): below this is the room
TL = json.load(open(os.path.join(P, "timeline.json")))
W = json.load(open(os.path.join(P, "words.json")))
SRC = re.search(r'^SRC = ["\'](.+?)["\']', open(os.path.join(P, "edit.py")).read(), flags=re.M).group(1)
K = TL["keep"]
MAN = {}
mp = os.path.join(P, "work", "keep_manual.json")
if os.path.exists(mp):
    MAN = {int(k): v for k, v in json.load(open(mp)).items()}

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
    return re.sub(r"[^a-z]", "", t).upper()


pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", SRC, "-ac", "1", "-ar", "16000", "-af", "highpass=f=80",
                      "-f", "f32le", "-"], capture_output=True, check=True).stdout
X = np.frombuffer(pcm, np.float32).copy()
HOP = 80
n = len(X) // HOP
e = np.sqrt(np.mean(X[:n * HOP].reshape(n, HOP) ** 2, axis=1)) + 1e-9
DB = 20 * np.log10(e / np.percentile(e, 99))
DUR = len(X) / 16000


def db(t):
    return DB[min(max(int(round(t * 200)), 0), len(DB) - 1)]


def peak(a, b):
    i, j = int(a * 200), max(int(a * 200) + 1, int(b * 200))
    return float(DB[max(i, 0):min(j, len(DB))].max())


import torch  # noqa: E402
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor  # noqa: E402

name = "facebook/wav2vec2-base-960h"
proc, model = Wav2Vec2Processor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval()
INV = {v: k for k, v in proc.tokenizer.get_vocab().items()}


def read(a, b):
    """greedy CTC words in [a, b]: [(TEXT, start, end)] in source seconds"""
    a, b = max(0.0, a), min(DUR, b)
    seg = X[int(a * 16000):int(b * 16000)]
    if len(seg) < 3200:
        return []
    with torch.inference_mode():
        ids = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values).logits[0].argmax(-1).numpy()
    fr = len(seg) / 16000 / len(ids)
    words, cur, t0, last, prev = [], "", 0, 0, None
    for t, i in enumerate(ids):
        ch = INV[int(i)]
        if i != prev and ch != "<pad>":
            if ch == "|":
                if cur:
                    words.append((cur, a + t0 * fr, a + (last + 1) * fr))
                cur = ""
            else:
                if not cur:
                    t0 = t
                cur += ch
        if ch not in ("<pad>", "|"):
            last = t
        prev = i
    if cur:
        words.append((cur, a + t0 * fr, a + (last + 1) * fr))
    return words


def match(word, t, cands, key):
    """the read word that is this caption word: best letters, near its mapped time"""
    best, bs = None, -9
    target = spoken(word)
    for c in cands:
        r = difflib.SequenceMatcher(a=target, b=c[0].replace("'", "")).ratio()
        d = abs((c[1] if key == "start" else c[2]) - t)
        if d > 0.5 or r < 0.4:
            continue
        s = r - 0.8 * d
        if s > bs:
            best, bs = c, s
    return best


def onset(t):
    """walk back from t (inside or at the start of the word) to where the voice begins"""
    u = t
    while u > t - 0.15 and db(u - 0.005) > QUIET:
        u -= 0.005
    return u


def offset(t):
    """walk forward from t to where the voice ends (short dips inside a word are bridged)"""
    u = t
    while u < t + 0.30:
        if db(u) > QUIET:
            u += 0.005
            continue
        if peak(u, u + 0.03) > QUIET:              # a dip under 30 ms: still the word (a stop, a fricative)
            u += 0.005
            continue
        break
    return u


def quiet_before(t):
    """start of the quiet run that ends at t"""
    u = t
    while u > t - 1.5 and db(u - 0.005) <= QUIET + 2:
        u -= 0.005
    return u


def quiet_after(t):
    """end of the quiet run that starts at t"""
    u = t
    while u < t + 1.5 and db(u) <= QUIET + 2:
        u += 0.005
    return u


# caption words -> pieces (by midpoint) and source seconds
outs = [g["out"] for g in K] + [1e9]
piece_words = {k: [] for k in range(len(K))}
for w in W:
    m = (w["start"] + w["end"]) / 2
    k = max(i for i in range(len(K)) if outs[i] <= m + 1e-6)
    g = K[k]
    piece_words[k].append(dict(text=w["text"], s=g["src_in"] + (w["start"] - g["out"]), e=g["src_in"] + (w["end"] - g["out"])))

rows, new = [], []
for k, g in enumerate(K):
    a0, b0 = g["src_in"], g["src_out"]
    ws = piece_words[k]
    if k in MAN:
        a1, b1 = MAN[k]
        flag = "MANUAL"
    elif not ws:
        a1, b1, flag = a0, b0, "NO WORDS"
    else:
        cands = read(a0 - 0.9, b0 + 0.9)
        F, L = ws[0], ws[-1]
        cf, cl = match(F["text"], F["s"], cands, "start"), match(L["text"], L["e"], cands, "end")
        on = onset(cf[1] + 0.02 if cf else F["s"] + 0.04)
        off = offset(cl[2] - 0.02 if cl else L["e"])
        flag = ("" if cf else "first?") + ("" if cl else " last?")
        q0 = quiet_before(on)                      # the quiet before the first word
        q1 = quiet_after(off)                      # the quiet after the last word
        a1 = a0 if (q0 <= a0 <= on - 0.03 and peak(a0, a0 + 0.025) <= QUIET) else max(on - LEAD, q0 + 0.02)
        b1 = b0 if (off + 0.03 <= b0 <= q1 and peak(b0 - 0.035, b0) <= QUIET) else min(off + TAIL, q1 - 0.02)
        if on - q0 < 0.05:
            flag += " TIGHT-IN"
        if q1 - off < 0.05:
            flag += " TIGHT-OUT"
    a1, b1 = round(a1, 3), round(b1, 3)
    new.append([a1, b1])
    text = " ".join(w["text"] for w in ws)
    heard = " ".join(c[0].lower() for c in read(a1, b1))
    ch = "" if (abs(a1 - a0) < 1e-3 and abs(b1 - b0) < 1e-3) else "CHANGED"
    rows.append(f"p{k:02d} {a0:7.3f}-{b0:7.3f} -> {a1:7.3f}-{b1:7.3f}  in {peak(a1, a1 + 0.025):4.0f} out {peak(b1 - 0.035, b1):4.0f} dB"
                f"  d{(b1 - a1) - (b0 - a0):+.3f} {ch} {flag}\n     says: {text}\n     hear: {heard}")
print("\n".join(rows))
for k in range(len(new) - 1):
    if new[k][1] > new[k + 1][0] + 1e-6 and not (k in MAN or k + 1 in MAN):
        print(f"OVERLAP p{k:02d}/p{k + 1:02d}: {new[k][1]} > {new[k + 1][0]}")
json.dump(new, open(os.path.join(P, "work", "keep_fixed.json"), "w"))
print("total", round(sum(b - a for a, b in new), 3), "was", round(sum(g["src_out"] - g["src_in"] for g in K), 3))
