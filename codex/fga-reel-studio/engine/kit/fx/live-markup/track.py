#!/usr/bin/env python3
"""live-markup: track the speaker's head over this effect's window, so the grease pencil marks follow it.

Finds the head on the window's first frame (the top of the cutout in public/subject.webm: the rows down to where it
narrows into the neck), or takes it from --head, then template-matches that patch on every frame of the window in
public/clean.mp4 (half resolution, a search round the last position, refined to 1 px) and smooths the path over 5
frames. Writes track.json and the HEAD / TRACK lines of <project>/fx/<id>/fx.js (fx.js is the only script the build
reads), between the "track" markers.

Run: PY fx/<id>/track.py <project> [<id>] [--head X,Y[,RX,RY]]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/public/clean.mp4, <project>/public/subject.webm
  writes  <project>/fx/<id>/track.json and the track block of <project>/fx/<id>/fx.js
  --head  the head's centre (and half width / half height) on the window's first frame, in 1080x1920 px, when
          there is no subject.webm or it finds the wrong thing
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the footage changes.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np

W, H, FPS = 1080, 1920, 30
R = 36                      # search radius per frame (half-res px)
BEGIN = "// ---- track: track.py rewrites the lines between these two markers ----"
END = "// ---- end of track ----"


def window(project, fid):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    for F in getattr(E, "FX", []):
        if F["id"] == fid:
            end = F["end"]
            if end == "end":
                end = json.load(open(os.path.join(project, "timeline.json")))["total"]
            return float(F["at"]), float(end)
    sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")


def grab(src, f0, n, fmt, w, h, alpha=False):
    args = ["ffmpeg", "-v", "error"] + (["-c:v", "libvpx-vp9"] if alpha else []) + ["-i", src,
            "-vf", f"select=between(n\\,{f0}\\,{f0 + n - 1}),scale={w}:{h}", "-fps_mode", "passthrough",
            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", fmt, "-"]
    raw = subprocess.run(args, capture_output=True, check=True).stdout
    c = {"gray": 1, "rgba": 4}[fmt]
    got = np.frombuffer(raw, np.uint8).reshape(-1, h, w, c)
    if len(got) == 0:
        sys.exit(f"{src}: no frames at {f0}..{f0 + n - 1}")
    if len(got) < n:
        got = np.concatenate([got, np.repeat(got[-1:], n - len(got), axis=0)])
    return got


def find_head(alpha):
    """centre and half size of the head: from the top of the cutout down to where it narrows into the neck"""
    m = alpha >= 128
    rows = np.nonzero(m.any(axis=1))[0]
    if not len(rows):
        sys.exit("subject.webm is empty on the first frame: pass --head X,Y")
    top = rows[0]
    widths, spans = [], []
    for y in range(top, min(H, top + 900)):
        xs = np.nonzero(m[y])[0]
        widths.append(xs.max() - xs.min() if len(xs) else 0)
        spans.append((xs.min(), xs.max()) if len(xs) else (0, 0))
    bottom, most = 300, 0                       # walk down: the neck is the first row well under the widest so far
    for k, w in enumerate(widths):
        most = max(most, w)
        if k > 40 and w < 0.7 * most:
            bottom = k
            break
    x0 = min(s[0] for s in spans[:bottom]); x1 = max(s[1] for s in spans[:bottom])
    return (x0 + x1) / 2, top + bottom / 2, (x1 - x0) / 2, bottom / 2


def ncc(win, tpl):
    win = win - win.mean()
    return float((win * tpl).sum() / (np.sqrt((win * win).sum() * (tpl * tpl).sum()) + 1e-6))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--head", default=None, help="X,Y[,RX,RY] on the window's first frame (1080x1920 px)")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    at, end = window(project, fid)
    f0 = round(at * FPS)
    n = max(1, round(end * FPS) - f0)
    pub = os.path.join(project, "public")
    if args.head:
        v = [float(x) for x in args.head.split(",")]
        hx, hy, rx, ry = (v + [130, 165])[:4] if len(v) == 2 else v[:4]
    else:
        a = grab(os.path.join(pub, "subject.webm"), f0, 1, "rgba", W, H, alpha=True)[0, ..., 3]
        hx, hy, rx, ry = find_head(a)
    fr = grab(os.path.join(pub, "clean.mp4"), f0, n, "gray", W // 2, H // 2)[..., 0].astype(np.float32)
    cx, cy = int(round(hx / 2)), int(round(hy / 2))
    tw, th = max(20, int(rx / 2 * 0.9)), max(24, int(ry / 2 * 0.9))
    tpl = fr[0, cy - th:cy + th, cx - tw:cx + tw]
    tpl = tpl - tpl.mean()
    hh, ww = fr.shape[1:]
    pts, x, y = [], cx, cy
    for k in range(n):
        best = (-2, x, y)
        for step, rad, ox, oy in ((2, R, x, y), (1, 1, None, None)):
            ox, oy = (best[1], best[2]) if ox is None else (ox, oy)
            for dy in range(-rad, rad + 1, step):
                for dx in range(-rad, rad + 1, step):
                    px, py = ox + dx, oy + dy
                    if px - tw < 0 or py - th < 0 or px + tw > ww or py + th > hh:
                        continue
                    s = ncc(fr[k, py - th:py + th, px - tw:px + tw], tpl)
                    if s > best[0]:
                        best = (s, px, py)
        _, x, y = best
        pts.append((x, y, best[0]))
    a = np.array([p[:2] for p in pts], np.float32)
    sm = a.copy()                                        # centred 5-frame moving average (edges held)
    for i in range(len(a)):
        sm[i] = a[max(0, i - 2):min(len(a), i + 3)].mean(axis=0)
    track = [[i, round(float(sm[i][0] - sm[0][0]) * 2, 1), round(float(sm[i][1] - sm[0][1]) * 2, 1)] for i in range(n)]
    head = dict(x=round(float(sm[0][0]) * 2, 1), y=round(float(sm[0][1]) * 2, 1), rx=round(float(rx), 1), ry=round(float(ry), 1))
    d = os.path.join(project, "fx", fid)
    json.dump(dict(fps=FPS, frame0=f0, head=head, track=track), open(os.path.join(d, "track.json"), "w"))
    js_path = os.path.join(d, "fx.js")
    js = open(js_path, encoding="utf-8").read()
    i, j = js.index(BEGIN), js.index(END)
    block = "\n".join([BEGIN,
                       f"var HEAD = {json.dumps(head)};   // the head on the window's first frame: centre, half size (px)",
                       f"var TRACK = {json.dumps(track)};   // per frame of the window: [frame, dx, dy] from HEAD",
                       ""])
    open(js_path, "w", encoding="utf-8").write(js[:i] + block + js[j:])
    low = [p for p in pts if p[2] < 0.6]
    print(f"head at ({head['x']}, {head['y']}), half size {head['rx']} x {head['ry']}; {n} frames from {f0}; "
          f"moved {np.ptp(a[:, 0]) * 2:.0f} x {np.ptp(a[:, 1]) * 2:.0f} px")
    if low:
        print(f"WARNING {len(low)} frames matched below 0.6: check the snapshots, or pass --head")
    print(f"wrote {os.path.join(d, 'track.json')} and the track block of {js_path}")


if __name__ == "__main__":
    main()
