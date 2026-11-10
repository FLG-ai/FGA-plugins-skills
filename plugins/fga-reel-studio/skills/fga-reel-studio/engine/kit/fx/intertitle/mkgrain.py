#!/usr/bin/env python3
"""intertitle: the four film-grain frames the title card cycles through (g0..g3.png).

Seeded, so the same project always gets the same files: sparse light and dark grain, a few dust specks and hairs, a
faint vertical scratch on one frame. The specks take the project's pack colours (style/style.json: colors.light and
colors.dark) so the grain sits in the creator's palette; without a pack they are near white and near black. Frames
are 540x960 with alpha, shown at 2x over the card; fx.js swaps them every two frames.

Run: PY fx/<id>/mkgrain.py <project> [<id>]
  reads   <project>/edit.py (checks the FX entry <id> exists), <project>/style/style.json (optional)
  writes  <project>/fx/<id>/g0.png .. g3.png
<id> defaults to this script's folder name.
"""
import argparse
import importlib.util
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

W, H = 540, 960
GRAIN = 0.035          # share of pixels that carry a light grain, and the same for dark
ALPHA = (18, 58)       # grain alpha range (0-255)


def rgb(c, fallback):
    c = str(c or "").strip()
    if c.startswith("#") and len(c) in (4, 7):
        c = c[1:] if len(c) == 7 else "".join(ch * 2 for ch in c[1:])
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    if c.startswith("rgb"):
        return tuple(int(float(v)) for v in c[c.index("(") + 1:c.index(")")].split(",")[:3])
    return fallback


def check(project, fid):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    if not any(F["id"] == fid for F in getattr(E, "FX", [])):
        sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    check(project, fid)
    light, dark = (240, 240, 236), (8, 8, 8)
    sp = os.path.join(project, "style", "style.json")
    if os.path.exists(sp):
        C = json.load(open(sp)).get("colors", {})
        light, dark = rgb(C.get("light"), light), rgb(C.get("dark"), dark)
    dark = tuple(int(v * 0.4) for v in dark)          # the dark grain sits under the card's own ground
    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)
    for k in range(4):
        r = np.random.default_rng(100 + k)
        a = np.zeros((H, W, 4), np.uint8)
        n = r.random((H, W))
        lt, dk = n > 1 - GRAIN, n < GRAIN
        a[lt, :3] = light
        a[dk, :3] = dark
        a[..., 3] = np.where(lt | dk, (r.random((H, W)) * (ALPHA[1] - ALPHA[0]) + ALPHA[0]).astype(np.uint8), 0)
        im = Image.fromarray(a, "RGBA")
        d = ImageDraw.Draw(im)
        for _ in range(5):                                 # dust specks
            x, y, s = r.random() * W, r.random() * H, 0.6 + r.random() * 1.6
            d.ellipse([x - s, y - s, x + s, y + s], fill=light + (120,) if r.random() > 0.5 else dark + (140,))
        for _ in range(2):                                 # hairs
            x, y = r.random() * W, r.random() * H
            pts = [(x + 6 * np.sin(i * 0.7 + k), y + i * 2.2) for i in range(int(6 + r.random() * 10))]
            d.line(pts, fill=light + (55,), width=1)
        if k == 2:                                         # a faint scratch
            x = int(W * 0.68)
            d.line([(x, 0), (x + 3, H)], fill=light + (55,), width=1)
        im.save(os.path.join(out, f"g{k}.png"), optimize=True)
    print(f"{out}: g0..g3.png ({W}x{H}), light {light}, dark {dark}")


if __name__ == "__main__":
    main()
