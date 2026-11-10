#!/usr/bin/env python3
"""letter-dive: a flat plate slams over the frame with one word cut out of it, the live shot playing through the
letters. The word builds letter by letter, then the camera dives into the stem of one letter (expo.in) and the stroke
swallows the frame. With a picture cut at the end of the window, the next shot is already playing through the stroke
(its pre-roll, in sync with the J-cut audio), so you land in it on the cut.

This writes <project>/fx/<id>/fx.html + fx.js (+ h.mp4, the next shot's pre-roll) from the table below and the project:
  the word      WORD in the pack's display face, from its real outlines (fontTools): sharp at any scale
  the stem      the letter closest to the middle whose stroke can swallow the frame with the least zoom, measured off
                its outline (the largest frame-shaped box inside its ink)
  the baseline  where the footage reads best through the letters against the plate (darkest band for a light plate),
                near the speaker's chin (work/tracks/track.json), measured on public/clean.mp4 across the window
  the times     the plate lands on SLAM_ON, the letters build while the word is said, the dive ends on the window's end
Run: PY fx/<id>/gen.py <project> [<id>] [--check]
  reads   <project>/edit.py (the FX entry <id>, SRC, FRAMES), timeline.json, words.json, public/clean.mp4,
          work/tracks/track.json (optional), style/ (the pack's display font and colours)
  writes  <project>/fx/<id>/fx.html + fx.js, h.mp4 when a picture cut or reframe ends the window (--check: the plan)
<id> defaults to this script's folder name. Rerun it whenever the window, the cut, the word or the pack changes.
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

try:
    import fxlib                     # the kit's pipeline is on the kit Python's import path (setup writes reel-kit.pth)
except ImportError:                  # any other Python: the kit is a folder above this file
    _d = os.path.dirname(os.path.realpath(__file__))
    while _d != os.path.dirname(_d) and not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        _d = os.path.dirname(_d)
    if not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        sys.exit("run this with the kit's Python (PY: $REEL_KIT_HOME/.venv/bin/python), it has the kit's pipeline on its path")
    sys.path.insert(0, os.path.join(_d, "pipeline"))
    import fxlib
from common import load_edit  # noqa: E402

# ---- the table: the word, its cue words, the beats
WORD = "different."        # the word cut out of the plate, as it should read
SLAM_ON = "little"         # the plate lands on this spoken word (its first frame)
SAY = ""                   # the spoken word the letters build on ('' = WORD without its punctuation)
PLATE = "light"            # the plate: the pack's "light" or "dark" ground
BASELINE = None            # or y px: the word's baseline, instead of the measured one
STEM_LETTER = None         # or the index in WORD of the letter to dive into, instead of the measured one
STEM = None                # or that letter's stem in font units (x0, x1, y0, y1), instead of the measured one
SCALE = None               # or the plate's scale on the cut, instead of MARGIN x what the stem needs
MARGIN = 1.15              # how much past "just covers the frame" the stem ends
SAFE = 35                  # side safe zone: the word's ink runs from SAFE to the frame width - SAFE
DROP = [0.16, 0.58]        # how far down the plate is on the frames before it lands (0..1); only frames inside the window
BUILD = 0.55               # the word is complete this far through the spoken word (0..1)
DIVE = 0.30                # s: the dive, ending on the window's end (a J-cut's next line starts about then)
SWITCH = 0.1667            # s before the cut: the next shot plays through the letters (inside the J-cut lead)
LAND = 1.035               # the next shot leans in to this scale on the dive; add CAMERA punch (cut, LAND) in edit.py
AGES = [1.14, 1.05, 1.0]   # a letter opens a touch big and settles, one size per frame
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))


def frame(t):
    """a time's frame, counted the way the build counts media frames (pipeline/common.py q)"""
    return round(t * FPS)


def off_frame(A, B):
    """the build times media by rounding to the nearest frame (halves to even) and shows the wrapper rounding halves up:
    a window edge between two frames lands a frame apart in the two, so say so"""
    bad = [f"{n} {t:.4f}" for n, t in (("at", A), ("end", B)) if abs(t * FPS - round(t * FPS)) > 0.01]
    if bad:
        print(f"note: the window's {' and '.join(bad)} sits between frames: put it on a frame (a multiple of 1/30 s)")


class Flat(BasePen):
    """a glyph's outline as closed polygons, curves flattened, in font units"""

    def __init__(self, gs, steps=16):
        super().__init__(gs)
        self.polys, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            u = 1 - t
            self.cur.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                             u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.polys.append(self.cur)
        self.cur = []

    _endPath = _closePath


def ink(polys, b, step):
    """the glyph's ink as a boolean raster (nonzero winding, so overlapping contours count once), row 0 at yMin"""
    x0, y0 = b[0] - step, b[1] - step
    w, h = int((b[2] - b[0]) / step) + 3, int((b[3] - b[1]) / step) + 3
    ys = y0 + (np.arange(h) + 0.5) * step
    acc = np.zeros((h, w + 1), np.int32)
    for poly in polys:
        P = np.array(poly + [poly[0]], float)
        for (xa, ya), (xb, yb) in zip(P[:-1], P[1:]):
            if ya == yb:
                continue
            rows = np.where((ys >= min(ya, yb)) & (ys < max(ya, yb)))[0]
            if len(rows):
                xc = xa + (ys[rows] - ya) * (xb - xa) / (yb - ya)
                col = np.clip(np.floor((xc - x0) / step - 0.5).astype(int) + 1, 0, w)
                np.add.at(acc, (rows, col), 1 if yb > ya else -1)
    return np.cumsum(acc, axis=1)[:, :w] != 0, x0, y0


def best_box(m, aspect):
    """the largest box of width:height = aspect fully inside the raster m, centred in the room it has: (x, y, w, h) cells"""
    ii = np.pad(np.cumsum(np.cumsum(m.astype(np.int32), 0), 1), ((1, 0), (1, 0)))

    def fits(h):
        w = max(1, round(h * aspect))
        if h > m.shape[0] or w > m.shape[1]:
            return None
        s = ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]
        ok = np.argwhere(s == w * h)
        return (ok, w) if len(ok) else None
    lo, hi = 0, m.shape[0]
    while lo < hi:                                   # the tallest box that fits
        mid = (lo + hi + 1) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        return None
    h = max(1, int(lo * 0.9))                        # a hair smaller, then the middle of everywhere that fits
    ok, w = fits(h)
    c = ok.mean(axis=0)
    y, x = ok[np.argmin(((ok - c) ** 2).sum(axis=1))]
    return x + w / 2, y + h / 2, lo * aspect, lo      # its centre, and the biggest box's size (cells)


def preroll(E, project, piece, n, W, H, path, extra=3):
    """the next shot's n frames before its piece starts (plus `extra` past it), cut from SRC the way cut.py cuts the
    pieces. On a source that isn't 30 fps the frame grid can land a frame off clean.mp4, so a few starts a fraction of
    a frame apart are tried and the one whose frames after the cut match clean.mp4 best is kept: (frames, mismatch)"""
    w, h, x, y = E.FRAMES[piece["frame"]]
    ref = [rgb.astype(np.float32) for _, rgb in fxlib.frames(project, piece["out_start"], piece["out_start"] + extra / FPS)]
    tmp, best = path + ".try.mp4", None
    for dt in (0.0, -0.008, 0.008, -0.016, 0.016, -0.024, 0.024):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{piece['src'] - n / FPS - 0.3 / FPS + dt:.4f}", "-i", E.SRC, "-an",
                        "-vf", f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1",
                        "-frames:v", str(n + extra), "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-g", "1",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp], check=True)
        got = [rgb for _, rgb in fxlib.frames(project, 0, (n + extra) / FPS, src=os.path.relpath(tmp, project))]
        diff = float(np.mean([np.abs(got[n + k].astype(np.float32) - r).mean() for k, r in enumerate(ref) if n + k < len(got)]))
        if best is None or diff < best[0]:
            best = (diff, got)
            os.replace(tmp, path)
        if diff < 1.5:
            break
    if os.path.exists(tmp):
        os.remove(tmp)
    return best[1], best[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    W, H = E.CANVAS
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    f0, fB = frame(A), frame(B)
    off_frame(A, B)
    TL = json.load(open(os.path.join(project, "timeline.json")))
    words = fxlib.words(project)
    S_ = fxlib.pack(project)

    # ---- times: the plate lands on SLAM_ON, the letters build while the word is said, the dive ends on B
    hit = fxlib.word_at(project, SLAM_ON, A)
    if hit is None or hit >= B:
        sys.exit(f"SLAM_ON {SLAM_ON!r} isn't said inside the window {A:.2f}-{B:.2f}: "
                 f"{' '.join(t for s, e, t in words if A <= s < B)}")
    fs = max(f0 + 1, frame(hit))
    drops = [(fs - len(DROP) + i, p) for i, p in enumerate(DROP) if fs - len(DROP) + i >= f0]
    say = SAY or WORD
    said = fxlib.word_at(project, say, hit)
    span = next(((s, e) for s, e, t in words if said is not None and said < B and abs(s - said) < 1e-6), None)
    n_open = len([c for c in WORD if not c.isspace()])
    first = fs + 1
    if span:
        last = max(first + 1, frame(span[0] + BUILD * (span[1] - span[0])))
    else:
        last = first + n_open
        print(f"note: {say!r} isn't said after {SLAM_ON!r}: the letters open one a frame")
    fd = fB - round(DIVE * FPS)
    if fd < last + 2:
        print(f"WARNING: the dive ({fd / FPS:.2f}) starts before the word has settled ({(last + 2) / FPS:.2f}): "
              f"end the window later, or build faster (BUILD)")
        fd = min(fB - 3, last + 2)
    if fd >= fB - 2:
        sys.exit(f"no room for the dive before {B:.2f}: end the window later")
    cut = next((c for c in TL["picture_cuts"] + TL.get("reframes", []) if abs(c - B) < 0.02), None)
    fsw = fB - round(SWITCH * FPS) if cut is not None else None

    # ---- the word: the pack's display face, as wide as the safe zone
    fpath = S_["fonts"]["display"]["path"]
    font = TTFont(fpath)
    cmap, gs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
    missing = [c for c in WORD if ord(c) not in cmap]
    if missing:
        sys.exit(f"the display face ({os.path.basename(fpath)}) has no {''.join(missing)!r}: change WORD")
    names = [cmap[ord(c)] for c in WORD]
    adv = [hmtx[n][0] for n in names]

    def bounds(name):
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        return bp.bounds

    inked = [i for i, n in enumerate(names) if bounds(n)]
    b_first, b_last = bounds(names[inked[0]]), bounds(names[inked[-1]])
    pen0 = sum(adv[:inked[0]])
    ink_units = (sum(adv[:inked[-1]]) + b_last[2]) - (pen0 + b_first[0])
    S = (W - 2 * SAFE) / ink_units                   # px per font unit
    pen_x = SAFE - (pen0 + b_first[0]) * S
    xs, gx = [], pen_x
    for i in range(len(names)):
        xs.append(gx)
        gx += adv[i] * S
    os2 = font["OS/2"] if "OS/2" in font else None
    xh = getattr(os2, "sxHeight", 0) or (bounds(cmap[ord("x")])[3] if ord("x") in cmap else 0.5 * font["head"].unitsPerEm)
    asc = max(bounds(names[i])[3] for i in inked)
    desc = min(bounds(names[i])[1] for i in inked)

    # ---- the stem: the letter whose ink holds the biggest frame-shaped box, near the middle
    aspect, step = W / H, 2.0
    if STEM is not None and STEM_LETTER is None:
        sys.exit("STEM is the stem of one letter: set STEM_LETTER to its index in WORD too")
    cands = []
    for i, n in enumerate(names):
        b = bounds(n)
        if not b or (STEM_LETTER is not None and i != STEM_LETTER):
            continue
        if STEM is not None:
            x0u, x1u, y0u, y1u = STEM
        else:
            pen = Flat(gs)
            gs[n].draw(pen)
            m, ox, oy = ink(pen.polys, b, step)
            box = best_box(m, aspect)
            if not box:
                continue
            bcx, bcy, bw, bh = box
            x0u, x1u = ox + (bcx - bw / 2) * step, ox + (bcx + bw / 2) * step
            y0u, y1u = oy + (bcy - bh / 2) * step, oy + (bcy + bh / 2) * step
        cx = xs[i] + (x0u + x1u) / 2 * S
        need = max(W / ((x1u - x0u) * S), H / ((y1u - y0u) * S))
        cost = need * (1 + abs(cx - W / 2) / (W / 2)) * (1 if WORD[i].isalnum() else 3)
        cands.append((cost, i, need, (x0u, x1u, y0u, y1u), cx))
    if not cands:
        sys.exit("no letter in WORD has a stroke to dive into: set STEM_LETTER and STEM")
    _, si, need, stem_u, scx = min(cands)
    scale = SCALE or round(need * MARGIN, 1)
    if scale < need:
        print(f"WARNING: SCALE {scale} is under the {need:.1f} the stem needs: the frame won't fully open")

    # ---- the baseline: the band (x-height) where the footage reads best against the plate, near the chin
    plate_rgb = S_["colors"][PLATE][:3]
    lp = 0.2126 * plate_rgb[0] + 0.7152 * plate_rgb[1] + 0.0722 * plate_rgb[2]
    xh_px = xh * S
    lo_y = max(round(220 + asc * S), int(0.36 * H))
    hi_y = min(round(1470 - max(0, -desc) * S), int(0.74 * H))
    chin = None
    tp = os.path.join(project, "work", "tracks", "track.json")
    if os.path.exists(tp):
        T = fxlib.tracks(project)["frames"]
        cs = [T[i]["face"]["chin"] for i in range(first, min(fd, len(T))) if T[i] and T[i].get("face")]
        chin = float(np.median(cs)) if cs else None
    if BASELINE is not None:
        baseline, how = BASELINE, "BASELINE"
    else:
        x_a, x_b = max(0, round(SAFE)), min(W, round(W - SAFE))
        rows = []
        for i, rgb in fxlib.frames(project, first / FPS, fd / FPS):
            if (i - first) % 3 == 0:
                rows.append((rgb[:, x_a:x_b, :].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)))
        Y = np.stack(rows)                           # frames x rows x cols of luma
        mean_r = Y.mean(axis=(0, 2))
        sq_r = (Y ** 2).mean(axis=(0, 2))
        pref = (chin if chin is not None else 0.5 * H)
        near = (pref - xh_px, pref + 2 * xh_px)       # the band's middle stays about the chin: on the mouth, the chin or just under
        best = []
        for y in range(lo_y, hi_y + 1, 4):
            a, b = int(y - xh_px), int(y)
            if not near[0] <= (a + b) / 2 <= near[1]:
                continue
            mu = mean_r[a:b].mean()
            sd = math.sqrt(max(0.0, sq_r[a:b].mean() - mu * mu))
            score = abs(lp - mu) / 255 - 0.5 * sd / 255 - 0.25 * abs((a + b) / 2 - pref) / H
            best.append((score, y, mu, sd))
        if not best:
            sys.exit(f"no room for the word near the chin ({pref:.0f}): set BASELINE")
        best.sort(reverse=True)
        baseline, how = best[0][1], "measured"
    ox_px = scx
    oy_px = baseline - (stem_u[2] + stem_u[3]) / 2 * S
    stem_w = (stem_u[1] - stem_u[0]) * S

    print(f"{fid}: window {A:.3f}-{B:.3f}  plate lands {fs / FPS:.3f} ('{SLAM_ON}')  letters {first / FPS:.3f}-{last / FPS:.3f}"
          f"  dive {fd / FPS:.3f}  " + (f"cut {cut:.3f}, next shot through the letters from {fsw / FPS:.3f}" if cut is not None
                                        else "no picture cut at the end: lands on the live shot"))
    print(f"  '{WORD}' in {os.path.basename(fpath)} at {S * font['head'].unitsPerEm:.0f}px, ink {SAFE}..{W - SAFE}, baseline "
          f"{baseline} ({how}{'; chin %.0f' % chin if chin is not None else ''})")
    if BASELINE is None:
        print("  best baselines (score, y, band luma, spread): " + "  ".join(f"{s:.3f}@{y} ({m:.0f}/{d:.0f})" for s, y, m, d in best[:4])
              + f"  plate luma {lp:.0f}")
    print(f"  dives into '{WORD[si]}' (letter {si}): stroke box {stem_w:.1f}px wide at ({ox_px:.0f}, {oy_px:.0f}), "
          f"needs x{need:.1f}, ends x{scale}")
    if args.check:
        return
    d = os.path.join(project, "fx", fid)
    if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(d)), "LIBRARY.md")):
        sys.exit(f"{d} is a library folder: copy the effect into the project's own fx/{fid}/ and run it there")
    os.makedirs(d, exist_ok=True)

    # ---- the next shot's pre-roll (cut like pipeline/cut.py), so the stroke opens on the shot you land in
    handle = ""
    if cut is not None:
        piece = next(p for p in TL["pieces"] if abs(p["out_start"] - cut) < 0.02)
        keep = next((k for k in TL["keep"] if abs(k["picture_out"] - cut) < 0.002), None)
        n = fB - fsw
        lead = round((keep["picture_out"] - keep["out"]) * FPS) if keep else n
        if n > lead:
            print(f"WARNING: the J-cut lead here is {lead} frames: the next shot's first {n - lead} frames through the "
                  f"letters run ahead of its audio. Shorten SWITCH to {lead / FPS:.3f}")
        _, diff = preroll(E, project, piece, n, W, H, os.path.join(d, "h.mp4"))
        print(f"  pre-roll: {n} frames before the cut, its frames after the cut against clean.mp4: mean diff {diff:.2f}"
              + ("  CHECK THIS" if diff > 3 else ""))
        handle = (f'\n  <video id="{{{{ID}}}}-h" class="{{{{ID}}}}-v g" src="fx/{{{{ID}}}}/h.mp4" muted playsinline '
                  f'data-start="{{{{START+{(fsw - f0) / FPS:.4f}}}}}" data-media-start="0.001" data-duration="{n / FPS:.4f}" '
                  f'data-track-index="{{{{T0}}}}"></video>')
    else:
        for f in ("h.mp4",):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))

    # ---- the letters as glyph paths, one per size a letter passes through as it opens
    def glyph_d(name, gx, grow):
        b = bounds(name)
        cx, cy = gx + (b[0] + b[2]) / 2 * S, baseline - (b[1] + b[3]) / 2 * S
        sp = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        k = S * grow
        gs[name].draw(TransformPen(sp, (k, 0, 0, -k, cx + (gx - cx) * grow, cy + (baseline - cy) * grow)))
        return sp.getCommands()

    paths, opens = [], []
    order = [i for i in range(len(names)) if bounds(names[i])]
    for k, i in enumerate(order):
        paths.append([glyph_d(names[i], xs[i], a) for a in AGES])
        opens.append(round(first + k * (last - first) / max(1, len(order) - 1)) - f0)
    drops_rel = [[f - f0, p] for f, p in drops]

    html = f"""<!-- letter-dive (over). Written by gen.py (rerun it, don't edit this file). A plate in the pack's {PLATE} ground slams
     over the frame with one word cut out of it (a mask from the display face's real outlines, so it stays sharp at any
     scale); a synced copy of the shot plays through the letters. The word builds letter by letter, then the camera
     dives into one letter's stroke until it swallows the frame{", landing in the next shot (its pre-roll, h.mp4) on the picture cut" if cut is not None else ""}. -->
<div id="{{{{ID}}}}-root">
  <video id="{{{{ID}}}}-c" class="{{{{ID}}}}-v g" src="clean.mp4" muted playsinline data-start="{{{{START}}}}" data-media-start="{{{{SYNC}}}}" data-duration="{{{{DUR}}}}" data-track-index="{{{{T1}}}}"></video>{handle}
  <svg id="{{{{ID}}}}-svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
    <defs><mask id="{{{{ID}}}}-m" maskUnits="userSpaceOnUse" x="-400" y="-400" width="{W + 800}" height="{H + 840}">
      <rect x="-400" y="-400" width="{W + 800}" height="{H + 840}" fill="#fff"/><path id="{{{{ID}}}}-p" fill="#000" d=""/>
    </mask></defs>
    <g id="{{{{ID}}}}-g" data-layout-allow-overflow><rect id="{{{{ID}}}}-plate" x="-200" y="-200" width="{W + 400}" height="{H + 440}" mask="url(#{{{{ID}}}}-m)"/></g>
  </svg>
</div>
<style>
#{{{{ID}}}}-root {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; overflow:hidden; }}
#{{{{ID}}}} .{{{{ID}}}}-v {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; object-fit:cover; display:block; }}
#{{{{ID}}}}-svg {{ position:absolute; left:0; top:0; overflow:hidden; }}
#{{{{ID}}}}-plate {{ fill:var(--c-{PLATE}); }}
</style>
"""
    js = f"""// letter-dive: written by gen.py (rerun it, don't edit this file). Every frame is a tl.set: which letters are open
// (the mask path's d) and the plate's transform attribute, so the vector re-rasterises sharp at every scale. Frames count
// from the window's first frame; '{SLAM_ON}' and '{say}' set them (gen.py prints the plan).
var FPS = 30, F0 = {f0};                    // the window's first frame (edit.py at {A:.4f}): rerun gen.py when it moves
function T(f) {{ return q((F0 + f) / FPS); }}
var DROPS = {json.dumps(drops_rel)}, SLAM = {fs - f0}, OPEN = {json.dumps(opens)}, DIVE = {fd - f0}, CUT = {fB - f0}, SWITCH = {(fsw - f0) if fsw is not None else 'null'};
var OX = {ox_px:.3f}, OY = {oy_px:.3f}, CX = {W / 2}, CY = {H / 2}, SCALE = {scale}, LAND = {LAND}, UP = -{H + 440};
var LETTERS = {json.dumps(paths, separators=(',', ':'))};
function pathAt(f) {{
  var d = '';
  for (var i = 0; i < LETTERS.length; i++) {{ var age = f - OPEN[i]; if (age >= 0) d += LETTERS[i][Math.min(age, LETTERS[i].length - 1)]; }}
  return d;
}}
function mat(s, cx, cy) {{ return 'matrix(' + s.toFixed(4) + ' 0 0 ' + s.toFixed(4) + ' ' + (cx - s * OX).toFixed(2) + ' ' + (cy - s * OY).toFixed(2) + ')'; }}
gsap.set('#{{{{ID}}}}-p', {{ attr: {{ d: '' }} }});
gsap.set('#{{{{ID}}}}-g', {{ attr: {{ transform: 'matrix(1 0 0 1 0 ' + UP + ')' }} }});
gsap.set('#{{{{ID}}}}-c', {{ opacity: 0 }});
tl.set('#{{{{ID}}}}-c', {{ opacity: 1 }}, T(DROPS.length ? DROPS[0][0] : SLAM));
// the plate drops in on the frames before it lands
DROPS.forEach(function (d) {{ tl.set('#{{{{ID}}}}-g', {{ attr: {{ transform: 'matrix(1 0 0 1 0 ' + (UP + d[1] * ({H + 240})).toFixed(1) + ')' }} }}, T(d[0])); }});
tl.set('#{{{{ID}}}}-g', {{ attr: {{ transform: 'matrix(1 0 0 1 0 0)' }} }}, T(SLAM));
// the letters open one at a time
for (var f = OPEN[0]; f <= OPEN[OPEN.length - 1] + {len(AGES) - 1}; f++) tl.set('#{{{{ID}}}}-p', {{ attr: {{ d: pathAt(f) }} }}, T(f));
// the dive: expo.in on the plate, drifting so the stroke ends centred on the frame
if (SWITCH !== null) {{
  gsap.set('#{{{{ID}}}}-h', {{ opacity: 0, transformOrigin: '{E.CAM_ORIGIN[0]}px {E.CAM_ORIGIN[1]}px' }});
  tl.set('#{{{{ID}}}}-h', {{ opacity: 1 }}, T(SWITCH));
}}
var RUN = SWITCH === null ? CUT - 1 - DIVE : CUT - DIVE;   // on a cut the next shot takes over mid-zoom; without one the last frame is fully open
for (var g = DIVE; g < CUT; g++) {{
  var p = (g - DIVE) / RUN, v = (Math.pow(2, 10 * (p - 1)) - Math.pow(2, -10)) / (1 - Math.pow(2, -10)), s = 1 + (SCALE - 1) * v;
  tl.set('#{{{{ID}}}}-g', {{ attr: {{ transform: mat(s, OX + (CX - OX) * v, OY + (CY - OY) * v) }} }}, T(g));
  if (SWITCH !== null && g >= SWITCH) tl.set('#{{{{ID}}}}-h', {{ scale: 1 + (LAND - 1) * v }}, T(g));
}}
"""
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(os.path.join(d, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write(js)
    t = lambda f: round(f / FPS, 3)                    # noqa: E731
    print(f"wrote {d}/fx.html + fx.js{' + h.mp4' if cut is not None else ''}")
    if cut is not None:
        print(f"edit.py: CAMERA['punch'] += [({cut:.3f}, {LAND})]   # the next shot lands leaning in and settles")
    print("SFX for edit.SOUND['sfx'] (the hit times):\n"
          f"    ({t(fs)}, \"impact-low\", -13), ({t(fs)}, \"shutter\", -14),   # the plate slams\n"
          + "".join(f"    ({t(o + f0)}, \"tick\", -17),\n" for o in opens)
          + f"    ({t(fB)}, \"whoosh-deep\", -10),   # the landing")


if __name__ == "__main__":
    main()
