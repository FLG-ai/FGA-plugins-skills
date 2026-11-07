#!/usr/bin/env python3
"""Pin caption words the forced aligner gets wrong (for example a short word like "I" dropped onto the tail of the word
before it). work/pins.json: [{"text", "next", "src_start", "src_end"}], source seconds where the word is said (heard
with look.py). Each pin finds the caption word with that text followed by that next word, nearest to where the source
time lands in this cut, and sets its start and end. Run after align.py --write.
Run: "$PY" pinwords.py <project>
"""
import json
import os
import sys

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
pp = os.path.join(P, "work", "pins.json")
if not os.path.exists(pp):
    sys.exit(0)
K = json.load(open(os.path.join(P, "timeline.json")))["keep"]
W = json.load(open(os.path.join(P, "words.json")))


def out(s):
    for g in K:
        if g["src_in"] - 1e-6 <= s <= g["src_out"] + 1e-6:
            return g["out"] + (s - g["src_in"]) / g.get("speed", 1.0)
    return None


for p in json.load(open(pp)):
    a, b = out(p["src_start"]), out(p["src_end"])
    if a is None or b is None:
        print("pin not in the cut:", p)
        continue
    c = [i for i in range(len(W) - 1) if W[i]["text"] == p["text"] and W[i + 1]["text"] == p["next"]]
    if not c:
        print("pin word not found:", p)
        continue
    i = min(c, key=lambda i: abs(W[i]["start"] - a))
    if abs(W[i]["start"] - a) > 1.0:
        print("pin too far from its word:", p, W[i])
        continue
    print(f"pinned {p['text']} ({p['next']}): {W[i]['start']:.2f} -> {a:.2f}")
    W[i]["start"], W[i]["end"] = round(a, 3), round(max(b, a + 0.06), 3)
    if W[i]["end"] > W[i + 1]["start"]:
        W[i]["end"] = W[i + 1]["start"]
json.dump(W, open(os.path.join(P, "words.json"), "w"), indent=1)
