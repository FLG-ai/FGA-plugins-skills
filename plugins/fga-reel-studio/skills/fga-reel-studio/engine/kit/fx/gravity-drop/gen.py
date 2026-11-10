#!/usr/bin/env python3
"""gravity-drop: the per-frame light/dark masks for the word that drops in behind the speaker.

For every output frame of this effect's window: where the picture under the word's band (y 0 to BAND) is light, an
alpha mask. The ink copy of the word shows through it and the light copy everywhere else, so the letters split
light/dark against the footage's own brightness, falling ones included, instead of wearing an outline. The speaker
is left out with the cutout (as word-stamp's mkmask.py does): where they cover the room, the room's median over the
window stands in, so a moving head never bleeds into the split (the word sits behind them there anyway).

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/public/clean.mp4, <project>/public/subject.webm
  writes  <project>/fx/<id>/masks.png: one band per frame, half resolution, COLS bands a row (fx.js reads it so)
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the footage changes.
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

BAND = 700                  # the band from the top of the frame: matches fx.js BAND (the word lands inside it)
COLS = 8                    # bands per row of masks.png: matches fx.js COLS
SCALE = 0.5                 # masks at half resolution (fx.js scales them back up)
LO, HI = 140, 170           # luma ramp (0-255): below LO the word stays light, above HI it turns ink
BLUR = 0.8                  # soften the split a hair (px, at mask resolution)
W, H, FPS = 1080, 1920, 30


def frames(src, f0, n, alpha=False):
    """output frames f0 .. f0+n-1 (rgba when alpha: VP9 with an alpha channel); past the end the last one holds"""
    args = ["ffmpeg", "-v", "error"] + (["-c:v", "libvpx-vp9"] if alpha else []) + ["-i", src,
            "-vf", f"select=between(n\\,{f0}\\,{f0 + n - 1})", "-fps_mode", "passthrough",
            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgba" if alpha else "rgb24", "-"]
    raw = subprocess.run(args, capture_output=True, check=True).stdout
    got = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 4 if alpha else 3)
    if len(got) == 0:
        sys.exit(f"{src}: no frames at {f0}..{f0 + n - 1}")
    if len(got) < n:
        got = np.concatenate([got, np.repeat(got[-1:], n - len(got), axis=0)])
    return got


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    at, end = window(project, fid)
    f0 = round(at * FPS)
    n = max(1, round(end * FPS) - f0)
    pub = os.path.join(project, "public")
    rgb = frames(os.path.join(pub, "clean.mp4"), f0, n)[:, :BAND].astype(np.float32)
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    sub = os.path.join(pub, "subject.webm")
    if os.path.exists(sub):                       # leave the speaker out: the room's median where they cover it
        cover = frames(sub, f0, n, alpha=True)[:, :BAND, :, 3] >= 128
        room = np.where(cover, np.nan, luma)
        seen = ~np.all(cover, axis=0)
        med = np.where(seen, np.nanmedian(np.where(seen, room, 0), axis=0), np.median(luma, axis=0))
        luma = np.where(cover, med[None], luma)
    else:
        print(f"no {sub}: the speaker counts in the split")
    bw, bh = round(W * SCALE), round(BAND * SCALE)
    rows = (n + COLS - 1) // COLS
    sheet = np.zeros((rows * bh, COLS * bw, 4), np.uint8)
    for k in range(n):
        m = np.clip((luma[k] - LO) / (HI - LO), 0, 1)
        im = Image.fromarray((m * 255).astype(np.uint8)).resize((bw, bh), Image.BILINEAR)
        a = np.asarray(im.filter(ImageFilter.GaussianBlur(BLUR)))
        r, c = divmod(k, COLS)
        sheet[r * bh:(r + 1) * bh, c * bw:(c + 1) * bw, 3] = a
    out = os.path.join(project, "fx", fid, "masks.png")
    Image.fromarray(sheet, "RGBA").save(out, optimize=True)
    print(f"{out}: {n} bands of {W}x{BAND} at {SCALE}x, {COLS} a row (frames {f0}-{f0 + n - 1})")


if __name__ == "__main__":
    main()
