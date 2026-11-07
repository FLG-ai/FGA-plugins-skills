#!/usr/bin/env python3
"""Put a reel-kit project on fixed joins and move everything that hangs off the old cut.

Step 1 (--keep): write work/keep_fixed.json (from fixjoins.py) into edit.py KEEP, with each join's picture lead set
so the outgoing picture still ends where it did (a look-down comes right after the last word), between -0.35 and
-0.04 s, and never so long that the incoming picture shows the speaker talking before its own voice starts. The old
edit.py, words.json, timeline.json, work/sfx and work/edit_*.json are copied to work/pre_recut/ first.
Then run cut.py (through heavy.sh).
Step 2 (--remap): every absolute output time moves with the voice or the cut it belongs to. An old output time sits
in an old piece, so it has a source second, and the same piece in the new cut puts that second at a new output time
(clamped into the piece if the cut trimmed it). A time within 2 frames of an old picture cut keeps its offset from
that join's new picture cut. Moved: words.json, edit.py (FX at/end, KARAOKE, CUT_WINDOWS, CAMERA, BEHIND, BW, CARDS,
BOXES, OVERLAYS, GRADES), work/sfx/*.txt (then merge_sound.py), work/edit_*.json, camera-transitions SKIP, and
{{SYNC-x}} in each effect's html (its media start stays put when the effect moves).
Words in work/add_words.json ([{"text", "src"}], source seconds) are inserted (connectors the old transcript missed).
--remap can run again after a hand tweak to KEEP and a new cut.py (it starts from the old times each time).
After --remap: align.py --write, rerun every fx/*/gen.py, matte_windows.py, build, joincheck.py.
Run: "$PY" recut.py <project> --keep | --remap
"""
import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.abspath(os.path.expanduser(sys.argv[1]))
W = os.path.join(P, "work")
PRE = os.path.join(W, "pre_recut")
FPS = 30


def q(t):
    return round(t * FPS) / FPS


def load_keep(src):
    m = re.search(r"^KEEP = (\[.*?\])\s*$", src, flags=re.M)
    return [tuple(x) for x in ast.literal_eval(m.group(1))]


def step_keep():
    if os.path.exists(PRE):
        sys.exit(f"{PRE} exists: a recut is already in progress (move it away to start again)")
    os.makedirs(os.path.join(PRE, "sfx"))
    for f in ("edit.py", "words.json", "timeline.json"):
        shutil.copy(os.path.join(P, f), PRE)
    for f in glob.glob(os.path.join(W, "sfx", "*.txt")):
        shutil.copy(f, os.path.join(PRE, "sfx"))
    for f in glob.glob(os.path.join(W, "edit_*.json")):
        shutil.copy(f, PRE)
    for f in glob.glob(os.path.join(P, "fx", "*", "fx.html")) + [os.path.join(P, "fx", "camera-transitions", "fx.js")]:
        if os.path.exists(f):
            d = os.path.join(PRE, "fx", os.path.basename(os.path.dirname(f)))
            os.makedirs(d, exist_ok=True)
            shutil.copy(f, d)
    E = os.path.join(P, "edit.py")
    src = open(E).read()
    old = load_keep(src)
    spec = json.load(open(os.path.join(W, "keep_fixed.json")))
    if isinstance(spec, list):
        spec = dict(keep=spec)
    new = [tuple(x[:2]) for x in spec["keep"]]
    frm = [x[2] if len(x) > 2 else i for i, x in enumerate(spec["keep"])]
    if len(new) != len(old) and not all(len(x) > 2 for x in spec["keep"]):
        sys.exit("pieces were added or removed: give every piece its old index, [in, out, from]")
    json.dump(dict(frm=frm), open(os.path.join(PRE, "from.json"), "w"))
    lm = re.search(r"^J_LEADS = (\[.*?\])", src, flags=re.M)
    leads = ast.literal_eval(lm.group(1)) if lm else [0.0] * (len(old) - 1)
    import numpy as np
    S = re.search(r'^SRC = ["\'](.+?)["\']', src, flags=re.M).group(1)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", S, "-ac", "1", "-ar", "16000", "-af", "highpass=f=80",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.float32)
    n = len(x) // 80
    e = np.sqrt(np.mean(x[:n * 80].reshape(n, 80) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(e / np.percentile(e, 99))
    nl = []
    for j in range(len(new) - 1):
        a1, b1 = new[j]
        c1 = new[j + 1][0]
        if frm[j + 1] == frm[j] + 1:                       # an old join: keep its outgoing picture end
            k = frm[j]
            L, b0 = leads[k], old[k][1]
            lead = min(max(b0 + L - b1, -0.35), -0.04) if abs(b1 - b0) > 1e-3 else L
        else:                                              # a new join inside an old piece
            lead = -0.04
        while lead < -0.04 and db[int((c1 + lead) * 200):int(c1 * 200)].max() > -30:   # the speaker talks in the pre-roll
            lead = round(lead + 0.01, 3)
        nl.append(round(lead, 3))
    print("J_LEADS", nl)
    src = re.sub(r"^KEEP = \[.*?\]\s*$", "KEEP = [" + ", ".join(f"({a}, {b})" for a, b in new) + "]", src, flags=re.M)
    lm = re.search(r"^J_LEADS = (\[.*?\])", src, flags=re.M)
    if lm:
        src = src[:lm.start(1)] + "[" + ", ".join(str(v) for v in nl) + "]" + src[lm.end(1):]
    tm = re.search(r"^TAKES = (\[.*?\])", src, flags=re.M)
    if tm:
        takes = spec.get("takes") or [ast.literal_eval(tm.group(1))[k] for k in frm]
        src = src[:tm.start(1)] + repr(list(takes)) + src[tm.end(1):]
    if spec.get("add_frames"):
        fm = re.search(r"^FRAMES = (\{.*?\})", src, flags=re.M)
        fr = ast.literal_eval(fm.group(1))
        fr.update({k: tuple(v) for k, v in spec["add_frames"].items()})
        src = src[:fm.start(1)] + "{" + ", ".join(f'"{k}": {tuple(v)}' for k, v in fr.items()) + "}" + src[fm.end(1):]
    if spec.get("speed") is not None:                 # {new piece index: factor}
        line = "SPEED = " + repr({int(k): float(v) for k, v in spec["speed"].items()}) + "   # recut.py: drawn-out words played faster (speed up, don't chop)"
        if re.search(r"^SPEED = ", src, flags=re.M):
            src = re.sub(r"^SPEED = .*$", line, src, flags=re.M)
        else:
            src = re.sub(r"^(TAKES = .*)$", lambda m: m.group(1) + "\n" + line, src, count=1, flags=re.M)
        src = re.sub(r"^(        t \+= )b - a$", lambda m: m.group(1) + "(b - a) / (globals().get('SPEED') or {}).get(i, 1.0)", src, count=1, flags=re.M)
    if spec.get("frames"):
        assert len(spec["frames"]) == len(new), "one frame per piece"
        line = "FRAMESEQ = " + repr(spec["frames"]) + "   # per piece (recut.py): the old piece's frame, a TIGHT punch-in where one was split"
        if re.search(r"^FRAMESEQ = ", src, flags=re.M):
            src = re.sub(r"^FRAMESEQ = .*$", line, src, flags=re.M)
        else:
            src = re.sub(r"^(TAKES = .*)$", lambda m: m.group(1) + "\n" + line, src, count=1, flags=re.M)
        src = re.sub(r"^(        fr = )(?!FRAMESEQ)(.*)$", lambda m: f"{m.group(1)}FRAMESEQ[i] if globals().get('FRAMESEQ') else ({m.group(2)})", src, count=1, flags=re.M)
    open(E, "w").write(src)
    print("KEEP, J_LEADS, TAKES (and FRAMESEQ) written; old files in", PRE)
    print("next: run/heavy.sh \"$PY\" \"$KIT/pipeline/cut.py\"", P, "  (PY and KIT as set in SKILL.md)")


def step_remap():
    TO = json.load(open(os.path.join(PRE, "timeline.json")))
    TN = json.load(open(os.path.join(P, "timeline.json")))
    ko, kn = TO["keep"], TN["keep"]
    frm = json.load(open(os.path.join(PRE, "from.json")))["frm"]
    assert len(frm) == len(kn), "from.json does not match the new cut"
    pco, pcn = TO["picture_cuts"], TN["picture_cuts"]
    jmap = {}                                          # old join -> new join (a removed run of pieces folds its
    for j in range(len(kn) - 1):                       # joins into the one new join that replaces them)
        for k in range(frm[j], frm[j + 1]):
            jmap[k] = j
    kept = set(frm)

    def gone(t):
        """an old output second inside a piece the new cut dropped (that line was removed)"""
        if t >= end_o or t < 0:
            return False
        k = max(i for i in range(len(ko)) if ko[i]["out"] <= t + 1e-6)
        return k not in kept
    sp = lambda g: g.get("speed", 1.0)                 # noqa: E731  (a sped piece: output = source / speed)
    end_o = ko[-1]["out"] + (ko[-1]["src_out"] - ko[-1]["src_in"]) / sp(ko[-1])
    end_n = kn[-1]["out"] + (kn[-1]["src_out"] - kn[-1]["src_in"]) / sp(kn[-1])

    def M(t):
        """old output second -> new, through the source (pieces matched by from.json)"""
        if t >= end_o:
            return t + (end_n - end_o)
        k = max(i for i in range(len(ko)) if ko[i]["out"] <= t + 1e-6)
        s = ko[k]["src_in"] + (t - ko[k]["out"]) * sp(ko[k])
        js = [j for j in range(len(kn)) if frm[j] == k]
        if not js:                                         # the old piece is gone: its place in the new cut
            prev = [j for j in range(len(kn)) if frm[j] < k]
            j = prev[-1] if prev else 0
            return kn[j]["out"] + (kn[j]["src_out"] - kn[j]["src_in"]) / sp(kn[j])
        for j in js:
            if kn[j]["src_in"] - 1e-6 <= s <= kn[j]["src_out"] + 1e-6:
                return kn[j]["out"] + (s - kn[j]["src_in"]) / sp(kn[j])
        best = min(js, key=lambda j: min(abs(s - kn[j]["src_in"]), abs(s - kn[j]["src_out"])))   # trimmed: clamp
        g = kn[best]
        return g["out"] + (0.0 if abs(s - g["src_in"]) <= abs(s - g["src_out"]) else (g["src_out"] - g["src_in"]) / sp(g))

    def T(t):
        """M, but a time near an old picture cut keeps its offset from that cut"""
        if t <= 0:
            return t
        c = min(range(len(pco)), key=lambda i: abs(pco[i] - t)) if pco else None
        if c is not None and abs(pco[c] - t) <= 2.0 / FPS + 1e-3 and c in jmap:
            return pcn[jmap[c]] + (t - pco[c])
        return M(t)

    def f3(v):
        return f"{v:.4f}".rstrip("0").rstrip(".") if "." in f"{v:.4f}" else f"{v}"

    # ---- words: through the source, then the added connectors
    words = json.load(open(os.path.join(PRE, "words.json")))
    def trimmed(w):
        """the word's middle sits in source the new cut leaves out (a trimmed false start, a cut "so")"""
        t = (w["start"] + w["end"]) / 2
        if t >= end_o:
            return False
        k = max(i for i in range(len(ko)) if ko[i]["out"] <= t + 1e-6)
        s = ko[k]["src_in"] + (t - ko[k]["out"]) * sp(ko[k])
        js = [j for j in range(len(kn)) if frm[j] == k]
        return bool(js) and not any(kn[j]["src_in"] - 0.02 <= s <= kn[j]["src_out"] + 0.02 for j in js)
    dropped = [w["text"] for w in words if gone(w["start"]) or trimmed(w)]
    words = [w for w in words if not (gone(w["start"]) or trimmed(w))]
    if dropped:
        print("words cut with their line:", " ".join(dropped))
    for w in words:
        w["start"], w["end"] = round(M(w["start"]), 3), round(M(w["end"]), 3)
        if w["end"] <= w["start"]:
            w["end"] = round(w["start"] + 0.08, 3)
    addp = os.path.join(W, "add_words.json")
    for a in json.load(open(addp)) if os.path.exists(addp) else []:
        k = next(i for i, g in enumerate(kn) if g["src_in"] - 1e-6 <= a["src"] <= g["src_out"] + 1e-6)
        t = round(kn[k]["out"] + a["src"] - kn[k]["src_in"], 3)
        words.append(dict(text=a["text"], start=t, end=round(t + a.get("dur", 0.2), 3)))
        print("added word", a["text"], "at", t)
    words.sort(key=lambda w: w["start"])
    json.dump(words, open(os.path.join(P, "words.json"), "w"), indent=1)

    # ---- edit.py
    E = os.path.join(P, "edit.py")
    src = open(E).read()
    base = os.path.join(PRE, "edit_keep.py")          # edit.py as --keep left it (old effect times, new KEEP)
    if os.path.exists(base):                           # a second --remap (KEEP tweaked by hand since): start again
        b = open(base).read()                          # from the old times, with today's cut lines
        for key in ("KEEP", "J_LEADS", "TAKES", "FRAMESEQ", "FRAMES", "SPEED"):
            cur = re.search(rf"^{key} = .*$", src, flags=re.M)
            old_l = re.search(rf"^{key} = .*$", b, flags=re.M)
            if cur and old_l:
                b = b[:old_l.start()] + cur.group(0) + b[old_l.end():]
        src = b
    else:
        open(base, "w").write(src)

    def nums_in(text, fn, pat=r"(?<![\w.])(-?\d+\.\d+|\d+)(?![\w.])"):
        return re.sub(pat, lambda m: f3(fn(float(m.group(1)))), text)

    out = []
    fx_moves = {}
    removed_fx = []
    for line in src.split("\n"):
        m = re.match(r"(\s*\{'id': '([^']+)', 'layer': '[^']+', 'at': )([0-9.]+)(, 'end': )([0-9.]+|'end')(.*)$", line)
        if m:
            a0 = float(m.group(3))
            a1 = T(a0)
            e1 = m.group(5) if m.group(5) == "'end'" else f3(T(float(m.group(5))))
            fx_moves[m.group(2)] = (a0, a1)
            line = f"{m.group(1)}{f3(a1)}{m.group(4)}{e1}{m.group(6)}"
            if e1 != "'end'" and float(e1) - a1 < 0.1:   # its whole beat was cut
                removed_fx.append((m.group(2), a0, float(m.group(5))))
                line = "    # CUT with its line (recut.py): " + line.strip()
        out.append(line)
    src = "\n".join(out)
    if removed_fx:
        print("effects cut with their line:", [r[0] for r in removed_fx])

    def pairs(body):                                   # (a, b) windows: move both ends, drop the ones that collapsed
        def one(x):
            a, b = T(float(x.group(1))), T(float(x.group(2)))
            return f"({f3(a)}, {f3(b)})" if b - a >= 0.05 else ""
        body = re.sub(r"\(([0-9.]+), ([0-9.]+)\)", one, body)
        return re.sub(r"\[\s*,\s*", "[", re.sub(r",\s*(,|\])", r"\1", body))
    for name in ("KARAOKE", "CUT_WINDOWS"):
        m = re.search(rf"^{name} = (.*?)(\s*#.*)?$", src, flags=re.M)
        if m and re.search(r"\d", m.group(1)):
            src = src[:m.start(1)] + pairs(m.group(1)) + src[m.end(1):]
    for name in ("BEHIND", "BW", "CARDS", "BOXES", "OVERLAYS", "GRADES"):
        m = re.search(rf"^{name} = (.*?)(\s*#.*)?$", src, flags=re.M)
        if m and re.search(r"\d", m.group(1)):
            body = m.group(1)
            if name in ("CARDS", "BOXES", "OVERLAYS"):
                print(f"CHECK by hand: {name} = {body[:120]}")
                continue
            src = src[:m.start(1)] + nums_in(body, T) + src[m.end(1):]
    m = re.search(r"^CAMERA = dict\((.*?)\)(\s*#.*)?$", src, flags=re.M)
    if m:
        body = m.group(1)
        body = re.sub(r"open=\(([0-9.]+), ([0-9.]+)\)", lambda x: f"open=({f3(T(float(x.group(1))))}, {f3(T(float(x.group(2))))})", body)
        body = re.sub(r"zooms=\[(.*?)\]", lambda x: "zooms=[" + re.sub(r"\(([0-9.]+), ([0-9.]+), ", lambda y: f"({f3(T(float(y.group(1))))}, {f3(T(float(y.group(2))))}, ", x.group(1)) + "]", body)
        body = re.sub(r"punch=\[(.*?)\]", lambda x: "punch=[" + re.sub(r"\(([0-9.]+), ", lambda y: f"({f3(T(float(y.group(1))))}, ", x.group(1)) + "]", body)
        body = re.sub(r"settles=\[(.*?)\]", lambda x: "settles=[" + nums_in(x.group(1), T) + "]", body)
        src = src[:m.start(1)] + body + src[m.end(1):]
    open(E, "w").write(src)

    # ---- sounds (then merged), builders' edit requests
    for f in glob.glob(os.path.join(PRE, "sfx", "*.txt")):
        txt = open(f).read()

        def cut_sound(t):
            return gone(t) or any(a - 0.05 <= t <= b for _, a, b in removed_fx)
        lines = []
        for ln in txt.split("\n"):
            mm = re.match(r"^\(\s*([0-9.]+)", ln) or re.search(r"dict\(at=([0-9.]+)", ln)
            lines.append("# cut with its line: " + ln if mm and not ln.startswith("#") and cut_sound(float(mm.group(1))) else ln)
        txt = "\n".join(lines)
        txt = re.sub(r"^\(\s*([0-9.]+)", lambda x: f"({T(float(x.group(1))):.3f}", txt, flags=re.M)
        txt = re.sub(r"(dict\(at=)([0-9.]+)", lambda x: f"{x.group(1)}{T(float(x.group(2))):.3f}", txt)
        open(os.path.join(W, "sfx", os.path.basename(f)), "w").write(txt)
    subprocess.run([sys.executable, os.path.join(HERE, "merge_sound.py"), P], check=True)
    TIMEKEYS = {"at", "end", "t", "start"}

    def walk(o, key=None):
        if isinstance(o, dict):
            return {k: walk(v, k) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, key) for v in o]
        if isinstance(o, (int, float)) and not isinstance(o, bool) and key in TIMEKEYS | {"karaoke_hide_add", "skip_cuts", "camera_punch_add", "zooms_add"}:
            return round(T(o), 4)
        return o
    for f in glob.glob(os.path.join(PRE, "edit_*.json")):
        d = json.load(open(f))
        if d:
            print("CHECK edit request", os.path.basename(f), "(remapped at/end/start/t, hide, skip, punch and zoom times)")
        json.dump(walk(d), open(os.path.join(W, os.path.basename(f)), "w"), indent=1)

    # ---- effects: camera-transitions SKIP, SYNC offsets
    ct = os.path.join(P, "fx", "camera-transitions", "fx.js")
    if os.path.exists(ct):
        js = open(ct).read()
        pre_ct = os.path.join(PRE, "fx", "camera-transitions", "fx.js")   # a second --remap starts from the old SKIP too
        m0 = re.search(r"var SKIP = \[([^\]]*)\]", open(pre_ct).read()) if os.path.exists(pre_ct) else None
        if m0:
            js = re.sub(r"(var SKIP = \[)([^\]]*)(\])", lambda x: x.group(1) + m0.group(1) + x.group(3), js, count=1)
        js = re.sub(r"(var SKIP = \[)([^\]]*)(\])", lambda x: x.group(1) + nums_in(x.group(2), T) + x.group(3), js)
        open(ct, "w").write(js)
    for f in glob.glob(os.path.join(P, "fx", "*", "fx.html")):
        fid = os.path.basename(os.path.dirname(f))
        if fid not in fx_moves:
            continue
        a0, a1 = fx_moves[fid]
        html = open(f).read()
        new = re.sub(r"\{\{SYNC-([0-9.]+)\}\}", lambda x: "{{SYNC-" + f3(float(x.group(1)) + (a1 - a0)) + "}}", html)
        if new != html:
            open(f, "w").write(new)
            print("SYNC kept for", fid)
    shutil.copy(os.path.join(P, "assets", "aroll.mp4"), os.path.join(P, "public", "clean.mp4"))   # render.py plays clean.mp4
    print("public/clean.mp4 = the new assets/aroll.mp4")
    print("moves:", {k: (round(a, 3), round(b, 3)) for k, (a, b) in fx_moves.items() if abs(a - b) > 1e-3})
    print("old end", round(end_o, 3), "new end", round(end_n, 3))


if "--keep" in sys.argv:
    step_keep()
elif "--remap" in sys.argv:
    step_remap()
else:
    sys.exit(__doc__)
