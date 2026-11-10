#!/usr/bin/env python3
"""contact-sheet-hook: the 30 contact-sheet stills and the per-frame light/dark masks for the hook's type.

The idea: one real second is 30 frames. The live shot shrinks into cell 01 of a 6x5 contact sheet, and the sheet
exposes one cell per frame: the still in each cell is the frame of THIS video playing at that moment, so the sheet
fills in exactly one real second, the one right before the drop (the last cell exposes DIVE frames before it, then
the sheet dives into that cell and lands full frame on the drop word).

This reads fx.js's KEY / AT / CROP constants and the project's words.json to find the shrink and the drop, then:
  cells.jpg   the 30 frames of that second, cropped to the cell (3:4, CROP from the top and bottom of the frame),
              6 a row
  masks.png   for every frame the opener is on screen (A up to the shrink) and every frame the payoff is
              (the drop up to B): where the picture under the type band (y BAND_Y to BAND_Y + BAND_H) is light,
              half resolution, COLS bands a row. The ink copies of the type show through them, so the type splits
              light/dark against the footage instead of wearing an outline.
  fx.js       the GEN line (the frames the above were made for): fx.js times the sheet from it
and prints a warning when the sheet's second starts before the shrink has finished (move the drop later, or the
shrink earlier).

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/words.json, <project>/public/clean.mp4,
          <project>/fx/<id>/fx.js (KEY, AT, CROP)
  writes  <project>/fx/<id>/cells.jpg, masks.png and the GEN line of fx.js
<id> defaults to this script's folder name. Rerun it whenever the window, the cut, the cue words or the footage change.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

BAND_Y, BAND_H = 200, 560   # the type band on the frame: matches fx.html (#<id>-band)
COLS = 8                    # mask bands per row: matches fx.js
SCALE = 0.5                 # masks at half resolution
LO, HI = 140, 170           # luma ramp (0-255): below LO the type stays light, above HI it turns ink
BLUR = 0.8                  # soften the split a hair (px, at mask resolution)
CELL = (308, 410)           # one still in cells.jpg (2x the 154x205 cell)
DIVE = 3                    # frames from the last exposed cell to the drop (matches fx.js)
SHRINK = 0.30               # the shrink's length (s, matches fx.js T.shrink)
W, H, FPS = 1080, 1920, 30
GEN = re.compile(r"^var GEN = .*$", re.M)


def frames(src, f0, n):
    args = ["ffmpeg", "-v", "error", "-i", src, "-vf", f"select=between(n\\,{f0}\\,{f0 + n - 1})", "-fps_mode", "passthrough",
            "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    got = np.frombuffer(subprocess.run(args, capture_output=True, check=True).stdout, np.uint8).reshape(-1, H, W, 3)
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


def const(js, name):
    m = re.search(r"^var " + name + r" = (\{.*?\});", js, re.M)
    if not m:
        sys.exit(f"fx.js has no `var {name} = {{...}};` line")
    return json.loads(m.group(1))


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def word_at(words, w, after):
    for s, e, t in words:
        if s >= after - 0.001 and norm(t) == norm(w):
            return s
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    A, B = window(project, fid)
    d = os.path.join(project, "fx", fid)
    js_path = os.path.join(d, "fx.js")
    js = open(js_path, encoding="utf-8").read()
    KEY, AT, CROP = const(js, "KEY"), const(js, "AT"), const(js, "CROP")
    wpath = os.path.join(project, "words.json")
    words = [(w["start"], w["end"], w["text"]) for w in json.load(open(wpath))] if os.path.exists(wpath) else []

    def find(key, after, fallback):
        t = word_at(words, KEY.get(key, ""), after) if KEY.get(key) else None
        return A + fallback if t is None or t >= B else t
    t_shrink = find("shrink", A, AT["shrink"])
    t_drop = find("drop", t_shrink, AT["drop"])
    fa, fb = round(A * FPS), round(B * FPS)
    f_shrink, f_drop = round(t_shrink * FPS), round(t_drop * FPS)
    run = f_drop - DIVE - 29
    if run < round((t_shrink + SHRINK) * FPS):
        print(f"WARNING the sheet's second starts on frame {run}, before the shrink ends "
              f"({t_shrink + SHRINK:.2f}s): move the drop later or the shrink earlier")
    if run < fa:
        sys.exit("the drop is less than a second after A: there is no second to show")
    pub = os.path.join(project, "public", "clean.mp4")

    # the sheet: frames run .. run+29, cropped to the cell
    F = frames(pub, run, 30)
    top, bot = int(CROP["top"]), int(CROP["bottom"])
    sheet = Image.new("RGB", (CELL[0] * 6, CELL[1] * 5))
    for k in range(30):
        sheet.paste(Image.fromarray(F[k, top:H - bot]).resize(CELL, Image.LANCZOS), ((k % 6) * CELL[0], (k // 6) * CELL[1]))
    sheet.save(os.path.join(d, "cells.jpg"), quality=86)

    # the masks: opener frames A .. shrink-1, then payoff frames drop .. B-1
    spans = [(fa, max(1, f_shrink - fa)), (f_drop, max(1, fb - f_drop))]
    bands = []
    for f0, n in spans:
        rgb = frames(pub, f0, n)[:, BAND_Y:BAND_Y + BAND_H].astype(np.float32)
        bands.append(0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])
    luma = np.concatenate(bands)
    bw, bh = round(W * SCALE), round(BAND_H * SCALE)
    rows = (len(luma) + COLS - 1) // COLS
    out = np.zeros((rows * bh, COLS * bw, 4), np.uint8)
    for k, l in enumerate(luma):
        m = np.clip((l - LO) / (HI - LO), 0, 1)
        a = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((bw, bh), Image.BILINEAR).filter(ImageFilter.GaussianBlur(BLUR)))
        r, c = divmod(k, COLS)
        out[r * bh:(r + 1) * bh, c * bw:(c + 1) * bw, 3] = a
    Image.fromarray(out, "RGBA").save(os.path.join(d, "masks.png"), optimize=True)

    gen = dict(shrink=f_shrink, drop=f_drop, run=run, open=spans[0][1], pay=spans[1][1])
    line = f"var GEN = {json.dumps(gen)};   // written by gen.py: the frames cells.jpg and masks.png were made for"
    if not GEN.search(js):
        sys.exit("fx.js has no `var GEN = ...` line")
    open(js_path, "w", encoding="utf-8").write(GEN.sub(lambda m: line, js, count=1))
    print(f"shrink {t_shrink:.3f}s (frame {f_shrink}), the second on the sheet: frames {run}-{run + 29} "
          f"({run / FPS:.3f}-{(run + 29) / FPS:.3f}s), drop {t_drop:.3f}s (frame {f_drop})")
    print(f"masks: {spans[0][1]} opener + {spans[1][1]} payoff frames; wrote cells.jpg, masks.png and the GEN line in {d}")


if __name__ == "__main__":
    main()
