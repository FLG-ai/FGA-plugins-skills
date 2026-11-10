#!/usr/bin/env python3
"""comment-drop: the per-frame light/dark masks for the big falling letters.

For every output frame of this effect's window: where the picture in the letters' band (y 160-760) is light, an
alpha mask. The dark copy of the letters shows through it and the light copy everywhere else, so the letters split
light/dark against the footage's own brightness (dark over light areas, light over dark ones) instead of wearing an
outline. The masks are half resolution (the letters are huge, the split stays clean) and tiled COLS to a row in one
sheet; fx.js picks frame k's tile with mask-position.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/timeline.json (for end="end"),
          <project>/public/clean.mp4
  writes  <project>/fx/<id>/masks.png
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the footage changes.
"""
import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

Y0, H = 160, 600            # the letters' band on the 1080x1920 frame (fx.html .cd-band, fx.js BAND_Y)
COLS = 8                    # tiles per row of the sheet (fx.js COLS)
LO, HI = 140, 170           # luma ramp (0-255): below LO the letters stay light, above HI they turn dark
BLUR = 0.8                  # soften the split a hair (px, at half resolution)
W, FH, FPS = 1080, 1920, 30
TW, TH = W // 2, H // 2     # one tile


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


def frames(src, f0, n):
    """the band of output frames f0 .. f0+n-1 at half resolution, as luma"""
    args = ["ffmpeg", "-v", "error", "-i", src,
            "-vf", f"select=between(n\\,{f0}\\,{f0 + n - 1}),crop={W}:{H}:0:{Y0},scale={TW}:{TH}:flags=area",
            "-fps_mode", "passthrough", "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(args, capture_output=True, check=True).stdout
    got = np.frombuffer(raw, np.uint8).reshape(-1, TH, TW, 3)
    if len(got) == 0:
        sys.exit(f"{src}: no frames at {f0}..{f0 + n - 1}")
    if len(got) < n:                                   # past the end: hold the last frame
        got = np.concatenate([got, np.repeat(got[-1:], n - len(got), axis=0)])
    rgb = got.astype(np.float32)
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    at, end = window(project, fid)
    f0 = round(at * FPS)
    n = max(1, round(end * FPS) - f0)
    luma = frames(os.path.join(project, "public", "clean.mp4"), f0, n)
    rows = math.ceil(n / COLS)
    sheet = np.zeros((rows * TH, COLS * TW, 4), np.uint8)
    for k in range(n):
        m = np.clip((luma[k] - LO) / (HI - LO), 0, 1)
        a = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(BLUR)))
        r, c = divmod(k, COLS)
        sheet[r * TH:(r + 1) * TH, c * TW:(c + 1) * TW, 3] = a
    out = os.path.join(project, "fx", fid, "masks.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    Image.fromarray(sheet, "RGBA").save(out, optimize=True)
    print(f"{out}: {n} tiles of {TW}x{TH} ({COLS} a row), frames {f0}-{f0 + n - 1}, "
          f"dark {sheet[..., 3].mean() / 255:.3f} of the sheet")


if __name__ == "__main__":
    main()
