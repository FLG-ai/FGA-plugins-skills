#!/usr/bin/env python3
"""receipt-printer: write every appearance of the motif from one table.

The receipt printer is a motif: the same component comes back 3 or 4 times in a video, each time the speaker says
what they told the AI to do. This writes <project>/fx/<id>/fx.html + fx.js for every row of BEATS from the library
template next to this file: fx.html is copied as it is and fx.js gets the row's constants, so every appearance has
the same design, size, position (centred on x 540) and move. It checks each cue word against <project>/words.json,
prints when each beat lands, and prints the edit.FX entries to paste.

Run: PY gen.py <project>            fill in BEATS first; run it again whenever the cut or the template changes
     PY gen.py <project> --check    only check the cue words and print the times, write nothing
A row whose folder is this library folder itself (the effects lab) only gets its constants rewritten in place.
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# One row per appearance, keyed by its FX id. Times are on the output timeline.
#   at, end   the FX window (the printer drops in at `at` and is gone at `end`); an FX entry with this id already in
#             <project>/edit.py wins
#   lines     [(text, the spoken word it prints on)], 1 to 3 lines of at most 16 characters, in caps
#   head      the spoken word the header feeds out on
#   total     the spoken word the TOTAL line feeds out on ('' = it comes out with the last line, for a tight window)
#   tear      the spoken word the receipt tears off on
BEATS = {
    "receipt-printer": dict(at=4.50, end=6.40, lines=[("CUT THE PAUSES,", "typed"), ("ADD CAPTIONS.", "one")],
                            head="I", total="sentence", tear="done"),
}
FALLBACK = dict(head=0.06, lines=[0.30, 0.55, 0.80], total=1.00, tear=0.50, out=0.20)   # keep in step with fx.js T
STEP = 0.034
LINE0, LH, JAG = 88, 48, 10

BEGIN = "// ---- constants: gen.py rewrites the lines between these two markers ----"
END = "// ---- end of constants ----"


def js(v):
    return json.dumps(v, ensure_ascii=False)


def block(n, b):
    return "\n".join([
        BEGIN,
        f"var NUM = {n};   // the receipt's number in the header (01, 02, ...)",
        f"var LINES = {js([list(x) for x in b['lines']])};   // [text, the spoken word it prints on]; 1 to 3 lines",
        f"var HEAD_ON = {js(b.get('head', ''))};   // the header feeds out on this word",
        f"var TOTAL_ON = {js(b.get('total', ''))};   // the TOTAL line feeds out on this word; '' = with the last line",
        f"var TEAR_ON = {js(b.get('tear', ''))};   // the receipt tears off on this word",
        END,
    ])


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def find(words, w, after, before, fallback):
    """start of the first spoken word w at or after `after` and before `before` (as wordAt in fx.js), else fallback"""
    if w:
        for s, e, text in words:
            if s >= after - 0.001 and norm(text) == norm(w):
                return (s, True) if s < before else (fallback, False)
    return fallback, not w


def check(fid, b, words):
    a, z, notes = b["at"], b["end"], []
    out = z - FALLBACK["out"]
    head, ok = find(words, b.get("head"), a, z, a + FALLBACK["head"])
    head = max(a + 0.04, head)
    if not ok:
        notes.append(f"header word {b.get('head')!r} not spoken in {a}-{z}: fallback {head:.2f}")
    t, prev, times = None, head + 0.01, []
    for i, (text, w) in enumerate(b["lines"]):
        fb = a + FALLBACK["lines"][min(i, len(FALLBACK["lines"]) - 1)]
        t, ok = find(words, w, prev, z, fb)
        if not ok:
            notes.append(f"line {i + 1} word {w!r} not spoken after the previous beat: fallback {t:.2f}")
        if len(text) > 16:
            notes.append(f"line {i + 1} {text!r} is {len(text)} characters: 16 fit the paper")
        times.append(t)
        prev = t + 0.01
    if not 1 <= len(b["lines"]) <= 3:
        notes.append("1 to 3 lines fit above the head")
    total = None
    if b.get("total"):
        total, ok = find(words, b["total"], prev, z, a + FALLBACK["total"])
        if not ok:
            notes.append(f"TOTAL word {b['total']!r} not spoken after the lines: fallback {total:.2f}")
    tear, ok = find(words, b.get("tear"), prev, z, z - FALLBACK["tear"])
    tear = min(tear, z - 0.30)
    if not ok:
        notes.append(f"tear word {b.get('tear')!r} not spoken: tears at {tear:.2f}")
    # the feeds take time: a beat never starts before the previous feed has finished
    n = len(b["lines"])
    h = LINE0 + LH * n + 6 + 10 + 36 + 10 + JAG
    stops = [head] + times + ([total] if total is not None else [])
    fed = [84] + [LINE0 + LH * (i + 1) + 2 for i in range(n)] + ([h - JAG - 2] if total is not None else [])
    if total is None:
        fed[-1] = h - JAG - 2
    cur, tcur, land = 0, 0, []
    for s, f in zip(stops, fed):
        k = max(2, min(4, round((f - cur) / 24)))
        s = max(s, tcur + 0.02)
        land.append(s)
        tcur, cur = s + k * STEP, f
    tear = max(tear, tcur)
    if tear > z - 0.29:
        notes.append("the tear has no room before the printer leaves: move `end` later")
    print(f"{fid:<16} in {a:.2f}  feeds " + " ".join(f"{x:.2f}" for x in land) + f"  tear {tear:.2f}  out {out:.2f}  gone {z:.2f}")
    for m in notes:
        print(f"{'':<16} WARNING {m}")


def windows(project):
    """the FX windows already in <project>/edit.py, by id (they win over a row's at / end)"""
    path = os.path.join(project, "edit.py")
    if not os.path.exists(path):
        return {}
    spec = importlib.util.spec_from_file_location("edit", path)
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    out = {}
    for F in getattr(E, "FX", []):
        end = F["end"]
        if end == "end":
            end = json.load(open(os.path.join(project, "timeline.json")))["total"]
        out[F["id"]] = (float(F["at"]), float(end))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    project = os.path.abspath(os.path.expanduser(args[0]))
    html = open(os.path.join(HERE, "fx.html"), encoding="utf-8").read()
    tpl = open(os.path.join(HERE, "fx.js"), encoding="utf-8").read()
    i, j = tpl.index(BEGIN), tpl.index(END) + len(END)
    wpath = os.path.join(project, "words.json")
    words = [(w["start"], w["end"], w["text"]) for w in json.load(open(wpath))] if os.path.exists(wpath) else []
    if not words:
        print(f"no {wpath}: cue words are not checked")
    have = windows(project)
    for n, (fid, b) in enumerate(BEATS.items(), 1):
        if fid in have and have[fid] != (b["at"], b["end"]):
            print(f"{fid}: window {have[fid][0]:.2f}-{have[fid][1]:.2f} from edit.py (BEATS says {b['at']:.2f}-{b['end']:.2f})")
            b = dict(b, at=have[fid][0], end=have[fid][1])
        if words:
            check(fid, b, words)
        if "--check" in args:
            continue
        d = os.path.join(project, "fx", fid)
        os.makedirs(d, exist_ok=True)
        if os.path.realpath(d) != os.path.realpath(HERE):          # the library folder keeps its own fx.html
            with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as f:
                f.write(html)
        with open(os.path.join(d, "fx.js"), "w", encoding="utf-8") as f:
            f.write(tpl[:i] + block(n, b) + tpl[j:])
    if "--check" not in args:
        print("\nwrote " + ", ".join(f"fx/{fid}/" for fid in BEATS) + f" in {project}\nedit.FX entries:")
        for fid, b in BEATS.items():
            print(f'    dict(id="{fid}", layer="top", at={b["at"]:.2f}, end={b["end"]:.2f}, '
                  f'note="receipt: {" ".join(x[0] for x in b["lines"]).lower()}"),')


if __name__ == "__main__":
    main()
