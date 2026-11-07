#!/usr/bin/env python3
"""Merge the FX builders' sound reports into edit.py SOUND.sfx.

Each builder's SFX go in <project>/work/sfx/<group>.txt, one per line, exactly as reported:
  (12.34, "pop", -17)            a hit at 12.34 s
  (12.34, "typing", -15, 0.6)    a sound cut to 0.6 s
  dict(at=12.3, name="typing", db=-15, max_len=0.6, align="start")
Lines starting with # are notes. Sounds are capped so no two of the same name land within 30 ms.
Run: python3 merge_sound.py <project>
"""
import ast
import os
import re
import sys

P = os.path.abspath(os.path.expanduser(sys.argv[1]))
D = os.path.join(P, "work", "sfx")
items = []
for f in sorted(os.listdir(D)) if os.path.isdir(D) else []:
    for line in open(os.path.join(D, f)):
        line = line.strip().rstrip(",")
        if not line or line.startswith("#"):
            continue
        if line.startswith("dict("):
            items.append(line)
            continue
        try:
            t = ast.literal_eval(line)
        except Exception:
            print("skip", f, line)
            continue
        items.append(repr(tuple(t)))


def key(s):
    m = re.search(r"at=([0-9.]+)", s) if s.startswith("dict(") else re.match(r"\(([0-9.]+)", s)
    return float(m.group(1)) if m else 0.0


items.sort(key=key)
seen, out = {}, []
for s in items:
    name = re.search(r"name=\"([^\"]+)\"", s) if s.startswith("dict(") else re.search(r"'([^']+)'", s)
    n = name.group(1) if name else ""
    t = key(s)
    if n in seen and abs(seen[n] - t) < 0.03:
        continue
    seen[n] = t
    out.append(s)
body = "SOUND = dict(music=None, sfx=[\n" + "".join(f"    {s},\n" for s in out) + "])\n"
E = os.path.join(P, "edit.py")
src = open(E).read()
m = (re.search(r"^SOUND = dict\(music=None, sfx=\[\n.*?^\]\)\n", src, flags=re.S | re.M)   # one this script wrote
     or re.search(r"^SOUND = dict\([^\n]*\n", src, flags=re.M))                         # the kit's one-liner (+ comment)
if not m:
    sys.exit("SOUND block not found")
open(E, "w").write(src[:m.start()] + body + src[m.end():])
print(f"{len(out)} sounds merged into {E}")
