#!/usr/bin/env python3
"""grease-pencil-sheet: pull the contact sheet's frames from the real raw take, and mark the ones the edit cut.

The sheet shows 12 frames of the SOURCE take (edit.SRC, the raw file before the cut), in time order. A frame whose
time falls inside a range the cut removed (between edit.KEEP ranges, or before the first / after the last) is junk:
the grease pencil circles or X's it. Leave TIMES empty and the times are picked for you: one frame in the middle of
each of the longest removed ranges (up to JUNK of them), the rest spread evenly over what the edit kept. Or list your
own TIMES (seconds in the source); junk is still worked out from KEEP. The footer gets the file's real name, length
and size (ffprobe).

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (SRC, KEEP, and the FX entry <id> must exist)
  writes  <project>/fx/<id>/frames.jpg (the frames side by side) and the frames block of <project>/fx/<id>/fx.js
<id> defaults to this script's folder name. Rerun it whenever KEEP, the times or the source change.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

TIMES = []                  # source times (s) to show, in order; [] = picked from KEEP (see above)
COUNT = 12                  # frames on the sheet (two strips of six)
JUNK = 4                    # when picking: how many frames come from removed ranges (the marks)
CELL = (256, 456)           # one frame in frames.jpg (2x its 128x228 cell on the sheet, 9:16)
BEGIN = "// ---- frames: gen.py rewrites the lines between these two markers ----"
END = "// ---- end of frames ----"


def load_edit(project, fid):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    if not any(F["id"] == fid for F in getattr(E, "FX", [])):
        sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")
    return E


def probe(src):
    out = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", src],
                                    capture_output=True, check=True).stdout)["format"]
    return float(out["duration"]), int(out["size"])


def removed(keep, dur):
    """the source ranges the edit cut, longest first"""
    keep = sorted(keep)
    gaps, t = [], 0.0
    for a, b in keep:
        if a - t > 1 / 30:
            gaps.append((t, a))
        t = max(t, b)
    if dur - t > 1 / 30:
        gaps.append((t, dur))
    return sorted(gaps, key=lambda g: g[0] - g[1])


def pick(keep, dur):
    gaps = removed(keep, dur)[:JUNK]
    junk = [round((a + b) / 2, 3) for a, b in gaps]
    kept = [(a, min(b, dur)) for a, b in sorted(keep) if min(b, dur) > a]
    total = sum(b - a for a, b in kept)
    good = []
    for i in range(COUNT - len(junk)):              # evenly over the kept time, half a step in from each end
        x = (i + 0.5) / (COUNT - len(junk)) * total
        for a, b in kept:
            if x <= b - a:
                good.append(round(a + x, 3))
                break
            x -= b - a
    return sorted(junk + good)


def frame(src, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
                          "-vf", f"scale={CELL[0]}:{CELL[1]}:force_original_aspect_ratio=increase,crop={CELL[0]}:{CELL[1]}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    if len(raw) < CELL[0] * CELL[1] * 3:
        sys.exit(f"{src}: no frame at {t}s")
    return np.frombuffer(raw[:CELL[0] * CELL[1] * 3], np.uint8).reshape(CELL[1], CELL[0], 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project, fid)
    src = os.path.expanduser(E.SRC)
    dur, size = probe(src)
    keep = [tuple(k[:2]) for k in E.KEEP]
    times = sorted(TIMES) if TIMES else pick(keep, dur)
    times = times[:COUNT]
    gaps = removed(keep, dur)
    rows = [[t, int(any(a <= t < b for a, b in gaps))] for t in times]
    sheet = np.concatenate([frame(src, t) for t in times], axis=1)
    d = os.path.join(project, "fx", fid)
    Image.fromarray(sheet).save(os.path.join(d, "frames.jpg"), quality=86)
    m, s = divmod(int(round(dur)), 60)
    foot = [os.path.basename(src).upper(), f"RAW TAKE · {m}:{s:02d} · {size / 1e6:.1f} MB"]
    js_path = os.path.join(d, "fx.js")
    js = open(js_path, encoding="utf-8").read()
    i, j = js.index(BEGIN), js.index(END)
    block = "\n".join([BEGIN,
                       f"var FRAMES = {json.dumps(rows)};   // [source time (s), 1 = the edit cut it] per frame, in order",
                       f"var FOOT = {json.dumps(foot, ensure_ascii=False)};   // the footer: the raw file's name, length, size",
                       ""])
    open(js_path, "w", encoding="utf-8").write(js[:i] + block + js[j:])
    for t, j_ in rows:
        print(f"{t:8.3f}s  {'CUT  (marked)' if j_ else 'kept'}")
    if not any(j_ for _, j_ in rows):
        print("WARNING no frame falls in a removed range: nothing gets marked (list TIMES inside the cut ranges)")
    print(f"wrote {os.path.join(d, 'frames.jpg')} and the frames block of {js_path}")


if __name__ == "__main__":
    main()
