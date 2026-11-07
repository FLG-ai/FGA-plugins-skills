#!/usr/bin/env python3
"""Apply the builders' edit_<sandbox>.json files to edit.py (and camera-transitions SKIP). Idempotent.
Keys: fx {id: {at, end}}, karaoke_hide_add [[a, b]], camera_punch_add [[t, s]], camera_zooms_add [[a, b, s]],
skip_cuts [t], needs [[id, text]]. Run: python3 apply_changes.py <project>"""
import ast, glob, json, os, re, sys
P = os.path.abspath(os.path.expanduser(sys.argv[1]))
E = os.path.join(P, "edit.py")
src = open(E).read()
ch = {"fx": {}, "karaoke_hide_add": [], "camera_punch_add": [], "camera_zooms_add": [], "skip_cuts": [], "needs": []}
for f in sorted(glob.glob(os.path.join(P, "work", "edit_*.json"))):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("skip", f, e); continue
    for k in ch:
        if k == "fx":
            ch["fx"].update(d.get("fx", {}))
        else:
            ch[k] += d.get(k, [])
for fid, w in ch["fx"].items():
    for key in ("at", "end"):
        if key in w:
            val = w[key] if w[key] == "end" else float(w[key])
            pat = re.compile(r"(\{'id': '%s', 'layer': '[a-z]+', 'at': )([0-9.]+)(, 'end': )('end'|[0-9.]+)" % re.escape(fid))
            m = pat.search(src)
            if not m:
                print("fx not found", fid); continue
            at, end = m.group(2), m.group(4)
            if key == "at": at = f"{val}"
            else: end = repr(val) if val == "end" else f"{val}"
            src = src[:m.start()] + m.group(1) + at + m.group(3) + end + src[m.end():]
class _M:                                          # a match-like span for the balanced dict(...) after NAME =
    def __init__(self, a, b, text):
        self.a, self.b, self.text = a, b, text
    def start(self, g=0): return self.a
    def end(self, g=0): return self.b
    def group(self, g=0): return self.text


def lit(name):
    """NAME = dict(...) up to its own closing bracket (tuples inside and a comment after it are fine)"""
    m = re.search(r"^%s = dict\(" % name, src, flags=re.M)
    if not m:
        return None
    i, depth = m.end() - 1, 0
    for j in range(i, len(src)):
        depth += {"(": 1, ")": -1}.get(src[j], 0)
        if depth == 0:
            return _M(i - 4, j + 1, src[i - 4:j + 1])
    return None
m = lit("KARAOKE")
if m and ch["karaoke_hide_add"]:
    d = eval(m.group(1), {"dict": dict})
    hide = [tuple(x) for x in d.get("hide", [])]
    for a, b in ch["karaoke_hide_add"]:
        if (round(a, 4), round(b, 4)) not in [(round(x, 4), round(y, 4)) for x, y in hide]:
            hide.append((round(a, 4), round(b, 4)))
    d["hide"] = sorted(hide)
    src = src[:m.start(1)] + "dict(" + ", ".join(f"{k}={v!r}" for k, v in d.items()) + ")" + src[m.end(1):]
m = lit("CAMERA")
if m and (ch["camera_punch_add"] or ch["camera_zooms_add"]):
    d = eval(m.group(1), {"dict": dict})
    for key, add in (("punch", ch["camera_punch_add"]), ("zooms", ch["camera_zooms_add"])):
        cur = [tuple(x) for x in d.get(key, [])]
        for x in add:
            if tuple(x) not in cur: cur.append(tuple(x))
        d[key] = sorted(cur)
    src = src[:m.start(1)] + "dict(" + ", ".join(f"{k}={v!r}" for k, v in d.items()) + ")" + src[m.end(1):]
if ch["needs"]:
    m = re.search(r"^NEEDS = (\[.*?\])", src, flags=re.M | re.S)
    if m:
        cur = ast.literal_eval(m.group(1))
        for n in ch["needs"]:
            if tuple(n) not in [tuple(x) for x in cur]: cur.append(tuple(n))
        src = src[:m.start(1)] + repr(cur) + src[m.end(1):]
ast.parse(src)
open(E, "w").write(src)
CT = os.path.join(P, "fx", "camera-transitions", "fx.js")
if ch["skip_cuts"] and os.path.exists(CT):
    js = open(CT).read()
    m = re.search(r"^var SKIP = \[(.*?)\];", js, flags=re.M)
    cur = [float(x) for x in re.findall(r"[0-9.]+", m.group(1))] if m else []
    for t in ch["skip_cuts"]:
        if all(abs(t - c) > 0.05 for c in cur): cur.append(round(float(t), 3))
    js = js[:m.start()] + "var SKIP = [" + ", ".join(f"{c}" for c in sorted(cur)) + "];" + js[m.end():]
    open(CT, "w").write(js)
print("applied:", {k: (len(v) if not isinstance(v, dict) else len(v)) for k, v in ch.items()})
