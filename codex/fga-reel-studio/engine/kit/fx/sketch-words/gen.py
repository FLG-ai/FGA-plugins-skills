#!/usr/bin/env python3
"""sketch-words: the words get drawn. The speaker stays live and untouched; each word in WORDS is laid down by a pencil
on the word it is spoken on. Two kinds of word, neither traced by hand:
  comp: a designer's pencil comp of a display word. Two ruled guidelines overshoot across the frame, the letterforms are
        drawn stroke by stroke from the real outlines of the pack's display face (corners split into hand movements,
        stems before bowls before serifs, three light passes, corners overshooting), quick diagonal hatching in the
        accent fills them past their edges, one accent underline last.
  hand: plain handwriting from one single-stroke alphabet, joined where a pen would not lift; down strokes press, up
        strokes lighten. Letters it doesn't have (capitals, digits) come from the medial line of the pack's text face.
The pencil: pressure lands on the paper's tooth (light pressure catches the peaks, heavy fills the valleys), strokes
taper, every drawing holds three frames with its own boil, hatch seeds and sheet offset. The tip moves on ones, the
boil runs on threes, and every word keeps boiling until the hard cut out.

Two grounds, one switch (GROUND, or --ground):
  paper   : a sheet in the pack's light colour, with real tooth, behind the speaker; the speaker live in full colour in
            front of it (matte, mic and desk), moved down the sheet by SHIFT to give the display word headroom.
            Graphite pencil, accent hatching and underline.
  footage : light pencil straight on the live shot, like white charcoal on dark paper, across the chest, behind the mic.

Run: PY fx/<id>/gen.py <project> [<id>] [--ground paper|footage] [--stills t1 t2 ...] [--specimen]
  reads   <project>/edit.py (the FX entry <id>: the window), words.json (when each row is spoken), timeline.json,
          public/clean.mp4, public/subject.webm, style/ (fonts and colours), work/tracks/track.json (optional: the face
          and shoulders for the layout), work/c/room_<FRAME>.npy when the empty room was filmed (optional: the paper
          ground takes the room out of the speaker's edge with it), public/plates/desk_<FRAME>.webm and mic_<FRAME>.webm
  writes  <project>/fx/<id>/<id>.mp4 (frame n = reel frame round(at * 30) + n), audio/<id>-pencil.wav (from the drawn
          motion), work/<id>/ (frames, drawings), and prints the layout and the SFX line
<id> defaults to this script's folder name. --stills renders single frames in about a second each, --specimen the type
alone on paper (is it drawn, or is it a font?). Rerun it whenever the window, the cut, the words or the pack change.
"""
import argparse
import glob
import json
import math
import multiprocessing as mp
import os
import re
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fontTools.pens.basePen import decomposeQuadraticSegment  # noqa: E402
from fontTools.pens.boundsPen import BoundsPen  # noqa: E402
from fontTools.pens.recordingPen import DecomposingRecordingPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from scipy.special import ndtr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
HOLD = 3                    # on threes
SS = 2                      # working pixels per output pixel

# ---- the constants to change per video (the window itself is the edit.py FX entry)
# One row per word or phrase, in the order it is spoken. kind "comp": drawn from the display face, hatched, underlined
# (the word that matters, one per effect); kind "hand": handwritten (the words around it). Optional per row: say (the
# spoken words when they differ from text), x, base, xh (px: the left edge, the baseline, the x-height, to place a row
# by hand), where ("behind" or "front" of the speaker).
WORDS = [
    dict(text="For me,", kind="hand"),
    dict(text="that's", kind="hand"),
    dict(text="ideas", kind="comp"),
]
GROUND = "paper"            # "paper" (a sheet behind the speaker) or "footage" (light pencil on the live shot)
SHIFT = None                # paper: px the speaker moves down the sheet for headroom; None = just enough for the words
SHIFT_MAX = 0.32            # paper: at most this share of the height (a close frame has the head near the top)
GUIDES = (-0.41, -0.21)     # s from the comp word's start: the two ruled lines, in the pause before it
HATCH = (0.20, 0.12)        # s: hatching from this long after the comp word starts to this long after it ends
UNDER = (0.12, 0.24)        # s after the comp word ends: the underline
SOLID_BELOW = None          # y in px below which the frame is all speaker, mic or desk; None = the desk layer's top, if any
UNDER_ROOM = None           # y in px below which pixels that differ from the room and touch the speaker are the speaker
                            # (a matte that loses the dark underside of the arms; needs the room). None = off
BOIL = 2.2                  # px: how far each drawing wanders from the last


def kit_pipeline():
    """KIT/pipeline when PY can't import fxlib by itself (setup normally puts it on PY's path): REEL_KIT_DIR, the kit
    this folder ships in, or an installed copy of the kit"""
    roots = [os.environ.get("REEL_KIT_DIR", ""), os.path.join(HERE, "..", "..")]
    roots += sorted(glob.glob(os.path.expanduser("~/.claude/plugins/cache/*/reel-kit/*/skills/reel-kit")), reverse=True)
    roots += [os.path.expanduser(f"~/{d}/skills/reel-kit") for d in (".claude", ".agents", ".codex")]
    for r in roots:
        if r and os.path.exists(os.path.join(r, "pipeline", "fxlib.py")):
            return os.path.join(os.path.abspath(r), "pipeline")
    sys.exit("can't find the kit's pipeline/fxlib.py: rerun with REEL_KIT_DIR=<the reel-kit skill folder>")


try:
    import fxlib  # noqa: E402  (setup puts the kit's pipeline on PY's import path)
except ImportError:
    sys.path.insert(0, kit_pipeline())
    import fxlib  # noqa: E402
from common import timeline  # noqa: E402  (fxlib's folder is on the path by now)

W, H = 1080, 1920           # the canvas; set from clean.mp4
FONT_COMP = FONT_HAND = None   # the pack's display and text faces (TTF paths); set by configure()
fr = lambda t: round(t * FPS)  # noqa: E731


# ------------------------------------------------------------------ the pencil's small tools
def st(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def smooth_noise(h, w, scale, seed, octaves=1):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, s = 1.0, 0.0, scale
    for _ in range(octaves):
        gh, gw = max(2, int(h / s) + 3), max(2, int(w / s) + 3)
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        out += amp * cv2.resize(g, (int(gw * s), int(gh * s)), interpolation=cv2.INTER_CUBIC)[:h, :w]
        tot += amp
        amp *= 0.5
        s = max(1.0, s / 2)
    return out / tot


def resample(c, step=1.0):
    d = np.sqrt((np.diff(c, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(d)])
    if s[-1] < step:
        return c.astype(np.float32)
    n = int(s[-1] / step) + 1
    q = np.linspace(0, s[-1], n)
    return np.stack([np.interp(q, s, c[:, 0]), np.interp(q, s, c[:, 1])], 1).astype(np.float32)


def catmull(pts, per=12):
    p = np.asarray(pts, np.float32)
    if len(p) < 3:
        return p
    q = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    t = np.linspace(0, 1, per, endpoint=False)[:, None]
    for i in range(1, len(q) - 2):
        p0, p1, p2, p3 = q[i - 1], q[i], q[i + 1], q[i + 2]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(p[-1:])
    return np.vstack(out).astype(np.float32)


class Layer:
    """one pigment's pressure field. Strokes are samples ~1px apart, splatted into width classes, each class blurred to a pencil's cross-section. Each class only touches the box it needs."""
    CLASSES = (0.55, 0.8, 1.15, 1.6, 2.2, 3.0, 4.2, 6.0, 8.5, 12.0, 17.0)     # gaussian sigma of the line in output px

    def __init__(self):
        self.xs, self.ys, self.ps, self.cs = [], [], [], []

    def add(self, xy, p, width):
        n = len(xy)
        if n == 0:
            return
        p = np.broadcast_to(p, (n,)); width = np.broadcast_to(width, (n,))
        c = np.searchsorted(np.array(self.CLASSES), width).clip(0, len(self.CLASSES) - 1)
        self.xs.append(xy[:, 0]); self.ys.append(xy[:, 1]); self.ps.append(p); self.cs.append(c)

    def render(self):
        Hs, Ws = H * SS, W * SS
        out = np.zeros((Hs, Ws), np.float32)
        if not self.xs:
            return out
        xs = np.concatenate(self.xs) * SS; ys = np.concatenate(self.ys) * SS
        ps = np.concatenate(self.ps); cs = np.concatenate(self.cs)
        for k, sig in enumerate(self.CLASSES):
            m = cs == k
            if not m.any():
                continue
            x, y, p = xs[m], ys[m], ps[m]
            s = sig * SS
            r = int(4 * s) + 3
            x0, x1 = max(0, int(x.min()) - r), min(Ws, int(x.max()) + r + 2)
            y0, y1 = max(0, int(y.min()) - r), min(Hs, int(y.max()) + r + 2)
            if x1 <= x0 or y1 <= y0:
                continue
            hb, wb = y1 - y0, x1 - x0
            wgt = p * math.sqrt(2 * math.pi) * s * SS
            ix = np.floor(x).astype(np.int64); iy = np.floor(y).astype(np.int64)
            fx, fy = x - ix, y - iy
            buf = np.zeros(hb * wb, np.float64)
            for dx, dy, f in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
                jx, jy = ix + dx - x0, iy + dy - y0
                ok = (jx >= 0) & (jx < wb) & (jy >= 0) & (jy < hb)
                buf += np.bincount(jy[ok] * wb + jx[ok], (wgt * f)[ok], minlength=hb * wb)
            out[y0:y1, x0:x1] += cv2.GaussianBlur(buf.reshape(hb, wb).astype(np.float32), (0, 0), s)
        return out


def make_paper(h, w, seed=11):
    """the sheet's tooth: a height map in 0..1, fine cold-press grain + a little long fibre"""
    rng = np.random.default_rng(seed)

    def n(sx, sy=None):
        x = rng.standard_normal((h, w)).astype(np.float32)
        x = cv2.GaussianBlur(x, (0, 0), sigmaX=sx * SS, sigmaY=(sy or sx) * SS, borderType=cv2.BORDER_REFLECT)
        return x / x.std()
    t = n(0.50) * 1.0 + n(1.05) * 0.62 + n(6, 0.6) * 0.20 + n(0.6, 4) * 0.20
    return ndtr(t / t.std()).astype(np.float32)


def lay(pressure, T, grain=0.7, reach=0.26, soft=0.34, gain=1.25, top=0.94):
    """coverage of a pigment on the tooth. Light pressure lands on the peaks and is thin; heavy pressure fills the valleys, but always leaves specks of paper."""
    p = np.clip(pressure, 0, 1.6)
    catch = st(T - (1 - p - reach), 0.0, soft)
    return np.clip(p * gain, 0, 1) * ((1 - grain) + grain * catch) * (top + (1 - top) * T)


# ------------------------------------------------------------------ type: real outlines from the font
class Face:
    """a font file: glyph outlines as hand movements, kerned layout. No shaping library needed, the GPOS pairs are read directly."""

    def __init__(self, name):
        self.font = TTFont(name)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.xh = getattr(self.font["OS/2"], "sxHeight", 0) or self._measured_xh()
        self.kern = self._kerning()
        self._cache = {}

    def _measured_xh(self):
        """a font without an x-height in its OS/2 table: the top of its x"""
        g = self.cmap.get(ord("x"))
        if g:
            bp = BoundsPen(self.gs)
            self.gs[g].draw(bp)
            if bp.bounds:
                return bp.bounds[3]
        return 0.5 * self.upm

    def _kerning(self):
        out = []
        if "GPOS" not in self.font:
            return out
        g = self.font["GPOS"].table
        idx = set()
        for fr_ in g.FeatureList.FeatureRecord:
            if fr_.FeatureTag == "kern":
                idx.update(fr_.Feature.LookupListIndex)
        for i in sorted(idx):
            lk = g.LookupList.Lookup[i]
            for sub in lk.SubTable:
                if sub.LookupType == 9:
                    sub = sub.ExtSubTable
                if sub.LookupType == 2:
                    out.append(sub)
        return out

    def pair(self, a, b):
        for sub in self.kern:
            cov = sub.Coverage.glyphs
            if a not in cov:
                continue
            if sub.Format == 1:
                ps = sub.PairSet[cov.index(a)]
                for r in ps.PairValueRecord:
                    if r.SecondGlyph == b:
                        return (r.Value1.XAdvance or 0) if r.Value1 else 0
            elif sub.Format == 2:
                c1 = sub.ClassDef1.classDefs.get(a, 0)
                c2 = sub.ClassDef2.classDefs.get(b, 0)
                v = sub.Class1Record[c1].Class2Record[c2].Value1
                val = (v.XAdvance or 0) if v else 0
                if val:
                    return val
        return 0

    def layout(self, text):
        """-> [(char, glyph name, pen x in font units)], total advance"""
        x, out, prev = 0, [], None
        for ch in text:
            g = self.cmap.get(ord(ch))
            if g is None:
                raise SystemExit(f"{ch!r} is not in the font")
            if prev:
                x += self.pair(prev, g)
            out.append((ch, g, x))
            x += self.gs[g].width
            prev = g
        return out, x

    def runs(self, g):
        """glyph -> contours -> [(polyline in font units y up, closed flag...)]: one run per movement of the hand. A run ends at a real corner of the outline."""
        if g in self._cache:
            return self._cache[g]
        pen = DecomposingRecordingPen(self.gs)
        self.gs[g].draw(pen)
        contours, cur, last = [], [], None
        for op, a in pen.value:
            if op == "moveTo":
                cur, last = [], a[0]
            elif op == "lineTo":
                cur.append(np.array([last, a[0]], np.float32)); last = a[0]
            elif op == "qCurveTo":
                for c, on in decomposeQuadraticSegment(a):
                    t = np.linspace(0, 1, 18)[:, None]
                    p0, p1, p2 = np.array(last, np.float32), np.array(c, np.float32), np.array(on, np.float32)
                    cur.append(((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2).astype(np.float32)); last = on
            elif op == "curveTo":
                c1, c2, on = a
                t = np.linspace(0, 1, 22)[:, None]
                p0, p1, p2, p3 = (np.array(v, np.float32) for v in (last, c1, c2, on))
                cur.append(((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3).astype(np.float32)); last = on
            elif op in ("closePath", "endPath"):
                if cur:
                    if np.hypot(*(cur[-1][-1] - cur[0][0])) > 0.5:
                        cur.append(np.array([cur[-1][-1], cur[0][0]], np.float32))
                    contours.append(cur)
                cur = []
        out = []
        for segs in contours:
            segs = [s for s in segs if np.hypot(*(s[-1] - s[0])) > 0.5 or len(s) > 2]

            def tan(v):
                n = np.hypot(*v)
                return v / (n + 1e-6)
            corners = []
            for i in range(len(segs)):
                a, b = segs[i - 1], segs[i]
                ta, tb = tan(a[-1] - a[-2]), tan(b[1] - b[0])
                corners.append(float(np.dot(ta, tb)) < math.cos(math.radians(24)))
            if not any(corners):                 # a smooth closed loop (the inside of an o): the hand splits it at top and bottom
                c = np.vstack(segs)
                i0, i1 = int(np.argmax(c[:, 1])), int(np.argmin(c[:, 1]))
                c = np.roll(c[:-1], -i0, axis=0)
                k = (i1 - i0) % len(c)
                out.append((np.vstack([c[:k + 1]]), False, False))
                out.append((np.vstack([c[k:], c[:1]]), False, False))
                continue
            start = corners.index(True)
            order = [(start + i) % len(segs) for i in range(len(segs))]
            run = []
            for j in order:
                if corners[j] and run:
                    out.append((np.vstack(run), True, True))
                    run = []
                run.append(segs[j])
            if run:
                out.append((np.vstack(run), True, True))
        self._cache[g] = out
        return out

    def mask_polys(self, g):
        """the glyph's filled shape as polygons, font units"""
        runs = []
        pen = DecomposingRecordingPen(self.gs)
        self.gs[g].draw(pen)
        last, cur = None, []
        for op, a in pen.value:
            if op == "moveTo":
                cur, last = [np.array([a[0]], np.float32)], a[0]
            elif op == "lineTo":
                cur.append(np.array([a[0]], np.float32)); last = a[0]
            elif op == "qCurveTo":
                for c, on in decomposeQuadraticSegment(a):
                    t = np.linspace(0, 1, 18)[1:, None]
                    p0, p1, p2 = np.array(last, np.float32), np.array(c, np.float32), np.array(on, np.float32)
                    cur.append(((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2).astype(np.float32)); last = on
            elif op == "curveTo":
                c1, c2, on = a
                t = np.linspace(0, 1, 22)[1:, None]
                p0, p1, p2, p3 = (np.array(v, np.float32) for v in (last, c1, c2, on))
                cur.append(((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3).astype(np.float32)); last = on
            elif op in ("closePath", "endPath"):
                if cur:
                    runs.append(np.vstack(cur))
                cur = []
        return runs


_faces = {}
def face(name):
    if name not in _faces:
        _faces[name] = Face(name)
    return _faces[name]


# ------------------------------------------------------------------ the medial line of a glyph: handwriting from any font
_ZS = None
def thin(b):
    """Zhang-Suen thinning, vectorised"""
    global _ZS
    if _ZS is None:
        a = np.zeros((2, 256), bool)
        for v in range(256):
            p = [(v >> i) & 1 for i in range(8)]       # P2..P9, clockwise from north
            B = sum(p)
            A = sum((p[i] == 0 and p[(i + 1) % 8] == 1) for i in range(8))
            c0 = 2 <= B <= 6 and A == 1
            P2, P3, P4, P5, P6, P7, P8, P9 = p
            a[0, v] = c0 and (P2 * P4 * P6 == 0) and (P4 * P6 * P8 == 0)
            a[1, v] = c0 and (P2 * P4 * P8 == 0) and (P2 * P6 * P8 == 0)
        _ZS = a
    img = b.astype(np.uint8).copy()
    ker = np.array([[128, 1, 2], [64, 0, 4], [32, 16, 8]], np.float32)
    for _ in range(60):
        ch = 0
        for sub in (0, 1):
            n = cv2.filter2D(img, cv2.CV_32F, ker, borderType=cv2.BORDER_CONSTANT).astype(np.int32) & 255
            rm = _ZS[sub][n] & (img > 0)
            ch += int(rm.sum())
            img[rm] = 0
        if ch == 0:
            break
    return img > 0


def medial(fc, g, px=120):
    """glyph -> pen strokes [Nx3: x, y (font units y up), half-width (font units)], in writing order. Branches shorter than the stroke is wide are serifs, they go."""
    sc = px / fc.xh
    polys = fc.mask_polys(g)
    if not polys:
        return []
    allp = np.vstack(polys)
    x0, y0 = allp.min(0) - 24 / sc
    x1, y1 = allp.max(0) + 24 / sc
    w, h = int((x1 - x0) * sc) + 2, int((y1 - y0) * sc) + 2
    img = np.zeros((h, w), np.uint8)
    pts = [np.round(np.stack([(p[:, 0] - x0) * sc * 4, (y1 - p[:, 1]) * sc * 4], 1)).astype(np.int32) for p in polys]
    cv2.fillPoly(img, pts, 255, lineType=cv2.LINE_AA, shift=2)
    b = cv2.GaussianBlur(img, (0, 0), 1.2) > 128
    dt = cv2.distanceTransform(b.astype(np.uint8), cv2.DIST_L2, 5)
    sk = thin(b)
    # graph of the skeleton: nodes are ends and junctions
    ys, xs = np.nonzero(sk)
    S = set(zip(xs.tolist(), ys.tolist()))
    nb = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]
    deg = {p: sum(((p[0] + dx, p[1] + dy) in S) for dx, dy in nb) for p in S}
    nodes = {p for p, d in deg.items() if d != 2}
    edges, seen = [], set()
    for s in nodes:
        for dx, dy in nb:
            q = (s[0] + dx, s[1] + dy)
            if q not in S or (s, q) in seen:
                continue
            path = [s, q]
            seen.add((s, q))
            while path[-1] not in nodes:
                x, y = path[-1]
                nxt = [(x + a, y + b_) for a, b_ in nb if (x + a, y + b_) in S and (x + a, y + b_) != path[-2] and (x + a, y + b_) not in path[-3:]]
                if not nxt:
                    break
                path.append(nxt[0])
            seen.add((path[-1], path[-2]))
            edges.append(path)
    if not edges:                                  # a dot: one tiny loop
        if len(S) == 0:
            return []
        c = np.array(sorted(S), np.float32)
        return [np.stack([c[:, 0] / sc + x0, y1 - c[:, 1] / sc, dt[c[:, 1].astype(int), c[:, 0].astype(int)] / sc], 1)]
    # prune spurs: an end branch not much longer than the stroke is wide
    ends = {p for p, d in deg.items() if d == 1}
    keep = []
    for e in edges:
        L = len(e)
        wide = float(dt[e[0][1], e[0][0]] if e[0] not in ends else dt[e[-1][1], e[-1][0]])
        spur = (e[0] in ends) != (e[-1] in ends) and L < max(10, 2.4 * wide)
        if not spur:
            keep.append(e)
    edges = keep or edges
    # the walk: start top-left, follow the straightest continuation through junctions, lift only when nothing is left to follow
    strokes, used = [], [False] * len(edges)

    def direction(path, at_end, n=8):
        a = np.array(path[-1 if at_end else 0], np.float32)
        b_ = np.array(path[max(0, len(path) - n) if at_end else min(len(path) - 1, n)], np.float32)
        v = a - b_
        return v / (np.hypot(*v) + 1e-6)
    while not all(used):
        cand = [(i, e) for i, e in enumerate(edges) if not used[i]]
        best, flip, bs = None, False, 1e12
        for i, e in cand:
            for fl, p in ((False, e[0]), (True, e[-1])):
                score = p[0] * 0.8 + p[1] * 0.45 + (0 if p in ends else 60)   # a pen starts at a free end, up and to the left
                if score < bs:
                    bs, best, flip = score, i, fl
        chain = list(edges[best][::-1] if flip else edges[best])
        used[best] = True
        while True:
            end = chain[-1]
            if end in ends:
                break
            d = direction(chain, True)
            nxt, sc_, nf = None, 0.15, False                   # no sharp hairpins inside one movement
            for i, e in enumerate(edges):
                if used[i]:
                    continue
                for fl, p in ((False, e[0]), (True, e[-1])):
                    if abs(p[0] - end[0]) <= 1 and abs(p[1] - end[1]) <= 1:
                        o = e[::-1] if fl else e
                        v = direction(o, False)
                        s_ = float(np.dot(d, -v))
                        if s_ > sc_:
                            sc_, nxt, nf = s_, i, fl
            if nxt is None:
                break
            chain += list(edges[nxt][::-1] if nf else edges[nxt])[1:]
            used[nxt] = True
        c = np.array(chain, np.float32)
        wd = dt[c[:, 1].astype(int), c[:, 0].astype(int)]
        strokes.append(np.stack([c[:, 0] / sc + x0, y1 - c[:, 1] / sc, wd / sc], 1))
    return strokes


# ------------------------------------------------------------------ strokes
def smooth1d(n, m, amp, rng):
    """low-frequency wander for a path of n samples: m control points through a cubic"""
    if n < 2:
        return np.zeros(n, np.float32)
    m = max(3, m)
    c = rng.normal(0, amp, m)
    x = np.linspace(0, m - 1, n)
    i = np.clip(x.astype(int), 0, m - 2)
    f = x - i
    f = f * f * (3 - 2 * f)
    return (c[i] * (1 - f) + c[i + 1] * f).astype(np.float32)


def speed_times(c, t0, t1):
    """arrival per sample: speed goes as curvature radius ^ (1/3), the two-thirds power law of real hands"""
    if len(c) < 3:
        return np.linspace(t0, t1, len(c))
    v = np.gradient(c, axis=0); a = np.gradient(v, axis=0)
    k = np.abs(v[:, 0] * a[:, 1] - v[:, 1] * a[:, 0]) / (np.power((v ** 2).sum(1), 1.5) + 1e-6)
    k = cv2.GaussianBlur(k.astype(np.float32)[:, None], (0, 0), sigmaX=1, sigmaY=3)[:, 0]
    d = np.power(k + 0.004, 1 / 3)
    return t0 + np.cumsum(d) / d.sum() * (t1 - t0)


class Stroke:
    """one movement of the hand: a base path, when it happens, what it weighs. Each drawing redraws it with its own wander."""
    __slots__ = ("c", "t0", "t1", "p", "w", "pig", "kind", "where", "wander", "taper", "over", "tt", "flick", "prof", "boil")

    def __init__(self, c, t0, t1, p, w, pig, kind, where, wander=0.8, taper=(0.1, 0.22), over=(0.0, 0.0), flick=0.0, prof=None, boil=1.0):
        self.c, self.t0, self.t1, self.p, self.w, self.pig, self.kind, self.where = c, t0, t1, p, w, pig, kind, where
        self.wander, self.taper, self.over, self.flick, self.prof, self.boil = wander, taper, over, flick, prof, boil
        self.tt = speed_times(c, t0, t1) if len(c) > 2 else np.linspace(t0, t1, len(c))

    def drawn(self, rng):
        """-> xy, pressure, width, arrival"""
        c, tt = self.c, self.tt
        n = len(c)
        if n < 2:
            return None
        # corners overshoot: the hand carries on past the end a little, differently each drawing
        o0, o1 = self.over[0] * rng.uniform(0.7, 1.25), self.over[1] * rng.uniform(0.7, 1.25)
        parts, times = [], []
        if o0 > 1:
            v = c[0] - c[min(4, n - 1)]
            v = v / (np.hypot(*v) + 1e-6)
            m = int(o0)
            parts.append(c[0][None] + v[None] * np.linspace(o0, 1, m)[:, None])
            times.append(np.full(m, tt[0]))
        parts.append(c); times.append(tt)
        if o1 > 1:
            v = c[-1] - c[max(0, n - 5)]
            v = v / (np.hypot(*v) + 1e-6)
            m = int(o1)
            parts.append(c[-1][None] + v[None] * np.linspace(1, o1, m)[:, None])
            times.append(np.full(m, tt[-1]) + 0.002)
        xy = np.vstack(parts).astype(np.float32)
        ts = np.concatenate(times)
        n = len(xy)
        s = np.linspace(0, 1, n)
        prof = (np.clip(s / max(self.taper[0], 1e-3), 0, 1) ** 0.6) * (np.clip((1 - s) / max(self.taper[1], 1e-3), 0, 1) ** 0.8)
        if self.flick:
            prof = prof * (1 - self.flick * s)
        lf = smooth1d(n, max(4, n // 40), 1.0, rng)
        if self.prof is not None:
            prof = prof * np.interp(s, np.linspace(0, 1, len(self.prof)), self.prof)
        press = self.p * prof * (1 + 0.26 * lf) * rng.uniform(0.86, 1.12)
        wid = self.w * (0.6 + 0.4 * prof) * (1 + 0.16 * lf) * rng.uniform(0.92, 1.08)
        if self.wander:
            m = max(3, n // 60)
            xy = xy + np.stack([smooth1d(n, m, self.wander, rng), smooth1d(n, m, self.wander, rng)], 1)
        return xy, np.clip(press, 0, None), wid, ts


# the hand: one single-stroke alphabet, drawn once, so any phrase writes itself. Unit = x-height, y up, before slant. Each letter is a list of pen strokes; a letter whose first stroke starts where the last one ended is joined without a lift.
SLANT = 0.17
ALPHABET = {
    "a": [[(.55, .82), (.39, 1.0), (.15, .93), (0, .6), (0, .23), (.15, .02), (.35, .14), (.5, .5), (.58, .98), (.55, .52), (.58, .16), (.71, .01), (.89, .1)]],
    "b": [[(.18, 2.3), (.12, 1.5), (.06, .7), (.05, .25), (.14, .03), (.38, .03), (.6, .25), (.7, .6), (.6, .9), (.38, .98), (.18, .8)]],
    "c": [[(.58, .82), (.42, 1.0), (.18, .92), (.02, .6), (.02, .25), (.18, .03), (.42, .03), (.66, .2)]],
    "d": [[(.54, .84), (.37, 1.01), (.15, .93), (0, .6), (0, .24), (.15, .02), (.35, .1), (.51, .44), (.59, .88), (.65, 1.56), (.69, 2.3), (.66, 1.56), (.61, .86), (.6, .32), (.69, .03), (.87, .09)]],
    "e": [[(0, .09), (.26, .3), (.5, .56), (.58, .82), (.44, 1.01), (.2, .92), (.05, .52), (.12, .14), (.38, 0), (.68, .18)]],
    "f": [[(0, .08), (.22, .6), (.42, 1.3), (.5, 1.9), (.44, 2.25), (.3, 2.2), (.24, 1.5), (.2, .6), (.16, -.2), (.1, -.85), (0, -.95), (-.06, -.75), (.1, -.3), (.3, -.02), (.52, .1)]],
    "g": [[(.55, .84), (.38, 1.0), (.15, .92), (0, .6), (.02, .25), (.18, .04), (.38, .14), (.52, .5), (.6, .98), (.58, .4), (.52, -.3), (.38, -.85), (.16, -.98), (.02, -.8), (.2, -.38), (.5, -.1), (.78, .1)]],
    "h": [[(.16, 2.3), (.1, 1.4), (.05, .6), (.03, 0), (.1, .45), (.28, .88), (.46, 1.0), (.56, .85), (.54, .4), (.58, .1), (.72, 0), (.88, .1)]],
    "i": [[(0, .09), (.14, .55), (.24, .98), (.19, .6), (.21, .22), (.31, .01), (.48, .08)], [(.3, 1.46), (.33, 1.42), (.35, 1.46)]],
    "j": [[(0, .09), (.14, .55), (.24, .98), (.22, .4), (.16, -.3), (.06, -.85), (-.1, -.98), (-.16, -.8), (.05, -.35), (.3, -.05), (.5, .1)], [(.3, 1.46), (.33, 1.42), (.35, 1.46)]],
    "k": [[(.16, 2.3), (.1, 1.4), (.05, .6), (.03, 0)], [(.52, .95), (.34, .72), (.06, .46), (.3, .4), (.44, .12), (.6, .01), (.76, .1)]],
    "l": [[(0, .09), (.26, .7), (.44, 1.5), (.46, 2.2), (.34, 2.3), (.24, 1.6), (.18, .7), (.2, .2), (.3, .01), (.48, .08)]],
    "m": [[(0, .09), (.1, .6), (.14, .98), (.12, .5), (.1, 0), (.2, .55), (.38, .93), (.54, .98), (.6, .75), (.56, .3), (.55, 0), (.66, .55), (.84, .93), (1.0, .98), (1.06, .75), (1.02, .3), (1.06, .08), (1.2, 0), (1.34, .09)]],
    "n": [[(0, .09), (.1, .6), (.14, .98), (.12, .5), (.1, 0), (.2, .55), (.38, .93), (.54, .98), (.6, .75), (.56, .3), (.6, .08), (.74, 0), (.88, .09)]],
    "o": [[(.4, 1.0), (.16, .9), (0, .58), (.02, .22), (.2, 0), (.44, .06), (.6, .4), (.58, .78), (.4, 1.0), (.52, .86), (.72, .84)]],
    "p": [[(0, .09), (.12, .6), (.16, .98), (.12, .2), (.06, -.5), (.02, -.98)], [(.14, .72), (.32, .98), (.54, .92), (.64, .58), (.54, .2), (.32, .03), (.14, .16)]],
    "q": [[(.55, .84), (.38, 1.0), (.15, .92), (0, .6), (.02, .25), (.18, .04), (.38, .14), (.52, .5), (.6, .98), (.56, .3), (.5, -.5), (.48, -.98), (.62, -.4), (.84, .06)]],
    "r": [[(0, .09), (.1, .6), (.14, .98), (.12, .5), (.1, 0), (.2, .55), (.36, .9), (.52, .98), (.62, .86)]],
    "s": [[(0, .09), (.18, .46), (.37, 1.0), (.32, .78), (.45, .46), (.48, .2), (.32, .01), (.11, .04), (.02, .15)]],
    "t": [[(0, .09), (.16, .5), (.28, 1.1), (.34, 1.72), (.3, 1.0), (.26, .4), (.3, .1), (.42, 0), (.58, .1)], [(.04, 1.06), (.3, 1.08), (.56, 1.12)]],
    "u": [[(0, .09), (.1, .6), (.14, .98), (.1, .5), (.1, .18), (.22, .01), (.4, .14), (.56, .6), (.62, .98), (.58, .5), (.6, .16), (.72, .01), (.88, .09)]],
    "v": [[(0, .09), (.1, .6), (.14, .98), (.14, .6), (.22, .18), (.34, 0), (.5, .3), (.6, .72), (.58, .96), (.62, .86), (.78, .84)]],
    "w": [[(0, .09), (.1, .6), (.14, .98), (.12, .5), (.16, .14), (.28, 0), (.42, .2), (.5, .7), (.54, .2), (.66, 0), (.84, .3), (.92, .72), (.9, .96), (.96, .86), (1.1, .84)]],
    "x": [[(0, .09), (.14, .6), (.3, .98), (.44, .5), (.52, .12), (.64, 0), (.78, .1)], [(.62, .96), (.38, .5), (.12, .02)]],
    "y": [[(0, .09), (.1, .6), (.14, .98), (.1, .5), (.1, .18), (.22, .01), (.4, .14), (.56, .6), (.62, .98), (.58, .4), (.5, -.3), (.36, -.85), (.16, -.98), (.04, -.8), (.2, -.38), (.5, -.1), (.78, .1)]],
    "z": [[(0, .96), (.3, 1.0), (.56, .96), (.3, .52), (.02, .04), (.3, 0), (.6, .02)]],
    "F": [[(.3, 1.72), (.2, .9), (.1, 0)], [(.04, 1.7), (.5, 1.76), (.98, 1.84)], [(.16, .86), (.44, .9), (.72, .94)]],
    "I": [[(.26, 1.78), (.16, .9), (.06, 0)]],
    ",": [[(.07, .1), (.09, .0), (.05, -.18), (-.03, -.32)]],
    ".": [[(.05, .07), (.08, .03), (.1, .06)]],
    "'": [[(.12, 1.92), (.1, 1.72), (.04, 1.54)]],
    "-": [[(.04, .5), (.3, .52), (.54, .5)]],
}
ADVANCE = {"a": .89, "b": .78, "c": .66, "d": .87, "e": .68, "f": .52, "g": .78, "h": .88, "i": .48, "j": .5, "k": .76, "l": .48, "m": 1.34, "n": .88, "o": .74, "p": .72, "q": .84, "r": .66, "s": .58, "t": .58,
           "u": .88, "v": .8, "w": 1.12, "x": .78, "y": .78, "z": .62, "F": .9, "I": .36, ",": .16, ".": .2, "'": .16, "-": .6, " ": .62}
BOWL = set("acdgoq")                                 # these start with a lift, up at the top of the bowl


def hand_paths(word):
    """text -> paths in px, in writing order: joined where the pen would not lift, the text face's medial line for anything not in the alphabet"""
    u = word["xh"]
    rng = np.random.default_rng(abs(hash_text(word["text"])) % 100000 + 7)
    x, out = 0.0, []
    prev_end = None
    drift = 0.0
    fc = None
    for ch in word["text"]:
        if ch == " ":
            x += ADVANCE[" "] * rng.uniform(0.92, 1.1)
            prev_end = None
            continue
        grow = rng.uniform(0.95, 1.06)
        drift = 0.72 * drift + rng.normal(0, 0.03)
        gap = 0.06 if ch in BOWL else 0.0
        if ch in ALPHABET:
            for j, pts in enumerate(ALPHABET[ch]):
                p = np.array(pts, np.float32) * np.array([1, grow], np.float32) + rng.normal(0, 0.012, (len(pts), 2)).astype(np.float32)
                p[:, 0] += x + gap
                p[:, 1] += drift
                p[:, 0] += SLANT * p[:, 1]
                if j == 0 and prev_end is not None and np.hypot(*(p[0] - np.array(prev_end[-1]))) < 0.14 and ch not in BOWL:
                    prev_end.extend(map(tuple, p[1:]))
                    continue
                cur = [tuple(q) for q in p]
                out.append(cur)
                if j == 0:
                    prev_end = cur
            x += (ADVANCE[ch] + gap) * rng.uniform(0.98, 1.03)
            if ch in ".,'-":
                prev_end = None
        else:                                        # not in the alphabet: the text face's medial line, still one pen
            fc = fc or face(FONT_HAND)
            g = fc.cmap.get(ord(ch))
            sc = 1.0 / fc.xh
            for c in medial(fc, g):
                q = np.stack([x + c[:, 0] * sc, c[:, 1] * sc + drift], 1).astype(np.float32)
                q[:, 0] += SLANT * q[:, 1]
                out.append([tuple(v) for v in q[:: max(1, len(q) // 14)]])
            x += fc.gs[g].width * sc
            prev_end = None
    paths = []
    for pts in out:
        p = np.array(pts, np.float32) * np.array([u, -u], np.float32) + np.array([word["x"], word["base"]], np.float32)
        paths.append(resample(catmull(p, 12), 1.0))
    return paths, x * u


def hand_word(word):
    """plain handwriting: the alphabet above, a little off the line per letter, leaning on it where the pen comes down"""
    paths, _ = hand_paths(word)
    lens = np.array([len(p) for p in paths], np.float32)
    lift = 0.012
    t0, t1 = word["t"]
    avail = max(0.05, (t1 - t0) - lift * (len(paths) - 1))
    out, t = [], t0
    wid = word.get("pencil", 1.3 if word["xh"] < 40 else 1.45)
    press = word.get("press", 1.05)
    for c, L in zip(paths, lens):
        d = avail * (L ** 0.85) / (lens ** 0.85).sum()
        v = np.gradient(c, axis=0) if len(c) > 2 else np.array([[0, 1]] * len(c), np.float32)
        down = np.clip(v[:, 1] / (np.linalg.norm(v, axis=1) + 1e-6), -1, 1)
        prof = 0.84 + 0.2 * down
        out.append(Stroke(c, t, t + d, press, wid, word.get("pig", "g"), "line", word.get("where", "behind"), wander=0.3, taper=(0.03, 0.08), prof=prof, boil=0.45))
        t += d + lift
    return out


def hash_text(s):
    h = 0
    for ch in s:
        h = (h * 131 + ord(ch)) & 0xFFFFFF
    return h


def word_geometry(word):
    """comp: the display word's runs, per glyph, in reel px"""
    fc = face(word.get("font") or FONT_COMP)
    sc = word["xh"] / fc.xh
    lay_, total = fc.layout(word["text"])
    glyphs = []
    for ch, g, x in lay_:
        if ch == " ":
            continue
        runs = []
        for c, cs, ce in fc.runs(g):
            xy = np.stack([word["x"] + (x + c[:, 0]) * sc, word["base"] - c[:, 1] * sc], 1).astype(np.float32)
            xy = resample(xy, 1.0)
            runs.append((xy, cs, ce))
        polys = [np.stack([word["x"] + (x + p[:, 0]) * sc, word["base"] - p[:, 1] * sc], 1).astype(np.float32) for p in fc.mask_polys(g)]
        glyphs.append(dict(ch=ch, runs=runs, polys=polys))
    return glyphs, total * sc


def natural(c):
    """a right hand pulls down and to the right"""
    d = c[-1] - c[0]
    if abs(d[1]) >= 0.5 * abs(d[0]):
        return c if d[1] >= 0 else c[::-1]
    return c if d[0] >= 0 else c[::-1]


def comp_passes(word):
    """letterforms: passes across the word, each stroke a hand movement along the font's real outline"""
    glyphs, width = word_geometry(word)
    xh = word["xh"]
    t0, t1 = word["t"]
    rng = np.random.default_rng(abs(hash_text(word["text"])) % 100000 + 21)
    where = word.get("where", "behind")
    pig = word.get("pig", "g")
    # (start share, end share, pressure, pencil, wander as a share of xh, overshoot as a share of xh, min run length share of xh)
    table = word.get("passes", ((0.00, 0.50, 0.46, 0.8, 0.012, 0.24, 0.16), (0.20, 0.72, 0.50, 0.8, 0.008, 0.17, 0.08), (0.42, 1.00, 0.86, 1.1, 0.0035, 0.05, 0.0)))
    out = []
    for (a, b, press, pencil, wand, over, minlen) in table:
        ta, tb = t0 + a * (t1 - t0), t0 + b * (t1 - t0)
        items = []
        for gi, g in enumerate(glyphs):
            rs = []
            for c, cs, ce in g["runs"]:
                L = len(c)
                if L < minlen * xh or L < 3:
                    continue
                d = c[-1] - c[0]
                chord = float(np.hypot(*d))
                straight = chord > 0.92 * L
                vert = abs(d[1]) > 1.6 * abs(d[0])
                rank = 0 if (straight and vert and L > 0.3 * xh) else 1 if L > 0.3 * xh else 2
                c2 = natural(c)
                flip = c2 is not c
                rs.append((rank, float(c[:, 0].mean()), c2, ce if flip else cs, cs if flip else ce))
            rs.sort(key=lambda r: (r[0], r[1]))
            items.append(rs)
        lens = [sum((len(r[2]) ** 0.8) for r in rs) for rs in items]
        tot = sum(lens) + 1e-6
        lift = min(0.004, (tb - ta) * 0.02 / max(1, sum(len(r) for r in items)))
        t = ta
        for rs in items:
            for rank, _, c, cs, ce in rs:
                d = (tb - ta) * (len(c) ** 0.8) / tot
                ov = (over * xh * rng.uniform(0.5, 1.2) if cs and len(c) > 0.08 * xh else 0.0, over * xh * rng.uniform(0.5, 1.2) if ce and len(c) > 0.08 * xh else 0.0)
                out.append(Stroke(c, t, t + d, press, pencil, pig, "line", where, wander=max(0.45, wand * xh), taper=(0.03, 0.07), over=ov, boil=min(1.0, xh / 110)))
                t += d + lift
    return out, glyphs, width


def guide_strokes(word, width):
    """two fast ruled lines, overshooting across the space"""
    if not word.get("guides"):
        return []
    g0, g1 = word["guides"]
    xh = word["xh"]
    x0, x1 = word.get("guide_x", (word["x"] - 70, word["x"] + width + 70))
    rng = np.random.default_rng(abs(hash_text(word["text"])) % 100000 + 3)
    where = word.get("where", "behind")
    pig = word.get("guide_pig", word.get("pig", "g"))
    out = []
    n = 2
    for i, y in enumerate((word["base"] + 1, word["base"] - xh)):
        ta = g0 + (g1 - g0) * i / n
        tb = ta + (g1 - g0) / n * 0.92
        A = np.array([x0 + rng.uniform(-10, 30), y + rng.normal(0, 1.5)], np.float32)
        B = np.array([x1 + rng.uniform(-30, 10), y + rng.normal(0, 1.5) - 0.004 * (x1 - x0)], np.float32)
        s = np.linspace(0, 1, max(8, int(np.hypot(*(B - A)) / 40)))[:, None]
        mid = A[None] * (1 - s) + B[None] * s + np.array([0, 1], np.float32)[None] * (4 * s * (1 - s)) * rng.normal(1.2, 0.8)
        c = resample(catmull(mid, 10), 1.0)
        out.append(Stroke(c, ta, tb, word.get("guide_p", 0.5), 0.85, pig, "guide", where, wander=0.2, taper=(0.02, 0.05), flick=0.25, boil=0.25))
    return out


def under_stroke(word, width):
    """one underline in the accent, last"""
    if not word.get("under"):
        return []
    u0, u1 = word["under"]
    xh = word["xh"]
    x0, x1 = word["x"] - 0.04 * xh, word["x"] + width + 0.12 * xh
    y = word["base"] + word.get("under_gap", 0.2) * xh
    pts = np.array([(x0, y + 0.03 * xh), (x0 + 0.3 * (x1 - x0), y - 0.012 * xh), (x0 + 0.68 * (x1 - x0), y - 0.03 * xh), (x1, y + 0.02 * xh)], np.float32)
    c = resample(catmull(pts, 40), 1.0)
    s = np.linspace(0, 1, 40)
    prof = np.minimum(s / 0.05, 1) * (1 - 0.6 * s ** 3)
    w = word.get("under_w", 1.9)
    return [Stroke(c, u0, u1, 1.0, w, "o", "under", word.get("where", "behind"), wander=0.5, taper=(0.01, 0.02), prof=prof, boil=0.6),
            Stroke(c + np.array([0, 3.0], np.float32), u0 + (u1 - u0) * 0.3, u1 + (u1 - u0) * 0.15, 0.7, w * 0.75, "o", "under", word.get("where", "behind"), wander=1.0, taper=(0.04, 0.2), prof=prof, boil=0.6),
            Stroke(c + np.array([0, -2.6], np.float32), u0 + (u1 - u0) * 0.5, u1 + (u1 - u0) * 0.2, 0.55, w * 0.7, "o", "under", word.get("where", "behind"), wander=1.0, taper=(0.1, 0.3), prof=prof, boil=0.6)]


def glyph_mask(glyphs, ss=1):
    img = np.zeros((H * ss, W * ss), np.uint8)
    for g in glyphs:
        polys = [np.round(p * ss * 16).astype(np.int32) for p in g["polys"]]
        if polys:
            sub = np.zeros_like(img)
            cv2.fillPoly(sub, polys, 255, lineType=cv2.LINE_8, shift=4)      # even-odd: the counters stay open
            img = np.maximum(img, sub)
    return img


def hatch_lines(mask, angle, sep, rng, xh, over=(0.012, 0.075), bbox=None):
    """the diagonal fill: parallel strokes across the letterform, each overshooting its edges the way a hand does. Runs in short patches: the wrist resets, the angle wanders, the spacing breathes."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    x0, x1, y0, y1 = xs.min() - 4, xs.max() + 4, ys.min() - 4, ys.max() + 4
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    Hm, Wm = mask.shape
    lines = []
    th = math.radians(angle)
    u = np.array([math.cos(th), -math.sin(th)])          # along the stroke: bottom-left to top-right
    n_ = np.array([math.sin(th), math.cos(th)])          # across
    R = math.hypot(x1 - x0, y1 - y0) / 2 + 4
    off = -R
    patch_left, drift, sep_now = 0, 0.0, sep
    while off < R:
        if patch_left <= 0:
            patch_left = int(rng.integers(5, 15))
            drift = rng.normal(0, 3.2)
            sep_now = sep * rng.uniform(0.82, 1.22)
        patch_left -= 1
        a = math.radians(angle + drift + rng.normal(0, 0.8))
        uu = np.array([math.cos(a), -math.sin(a)])
        o = np.array([cx, cy]) + n_ * off
        s = np.arange(-R, R, 1.0)
        px = (o[0] + uu[0] * s).astype(np.int32)
        py = (o[1] + uu[1] * s).astype(np.int32)
        ok = (px >= 0) & (px < Wm) & (py >= 0) & (py < Hm)
        inside = np.zeros(len(s), bool)
        inside[ok] = mask[py[ok], px[ok]] > 0
        # intervals inside the shape; hairlines the hand would not stop for are skipped
        d = np.diff(np.concatenate([[0], inside.astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        merged = []
        for b, e in zip(starts, ends):
            if merged and b - merged[-1][1] < 0.05 * xh and rng.random() < 0.8:       # across a thin gap the pencil does not lift
                merged[-1][1] = e
            else:
                merged.append([b, e])
        for b, e in merged:
            L = e - b
            if L < 2.5:
                continue
            o0 = abs(rng.normal(over[0], over[0] * 0.7)) * xh + (rng.uniform(0.02, over[1]) * xh if rng.random() < 0.22 else 0)
            o1 = abs(rng.normal(over[0], over[0] * 0.7)) * xh + (rng.uniform(0.02, over[1]) * xh if rng.random() < 0.34 else 0)
            A = o + uu * (s[b] - o0)
            B = o + uu * (s[e - 1] + o1)
            q = np.linspace(0, 1, max(3, int(np.hypot(*(B - A)) / 12)))[:, None]
            bow = (4 * q * (1 - q)) * rng.normal(0, 0.012 * (L + 10))
            c = A[None] * (1 - q) + B[None] * q + n_[None] * bow
            lines.append(resample(c.astype(np.float32), 1.0))
        off += sep_now * rng.uniform(0.85, 1.15)
    return lines


class Word:
    def __init__(self, spec):
        self.spec = spec
        self.kind = spec["kind"]
        self.fixed = []
        self.glyphs, self.width, self.mask = None, 0, None
        if self.kind == "hand":
            self.fixed = hand_word(spec)
        else:
            passes, self.glyphs, self.width = comp_passes(spec)
            self.fixed = guide_strokes(spec, self.width) + passes + under_stroke(spec, self.width)
            self.mask = glyph_mask(self.glyphs)

    def hatch(self, seed):
        """fresh hatching per drawing, same front: which line is down by when depends only on where it is"""
        s = self.spec
        if self.kind != "comp" or not s.get("hatch"):
            return []
        rng = np.random.default_rng(seed)
        xh = s["xh"]
        h0, h1 = s["hatch"]
        pig = s.get("hatch_pig", "b")
        where = s.get("where", "behind")
        out = []
        big = ((58, 0.038, 1.0, 1.15, (0.0, 0.84)), (47, 0.075, 0.62, 0.8, (0.4, 1.0)))
        small = ((58, 0.062, 1.1, 1.2, (0.0, 1.0)),)
        for ang, sep_k, press, pencil, sh in s.get("hatches", big if xh >= 110 else small):
            sep = max(5.0, sep_k * xh)
            lines = hatch_lines(self.mask, ang, sep, rng, xh)
            if not lines:
                continue
            px = np.array([l[:, 0].mean() for l in lines])
            a, b = s["x"], s["x"] + self.width
            ta, tb = h0 + sh[0] * (h1 - h0), h0 + sh[1] * (h1 - h0)
            for l, x in zip(lines, px):
                f = float(np.clip((x - a) / (b - a), 0, 1))
                t_ = ta + (tb - ta) * f
                dur = 0.016 + len(l) * 0.00006
                st_ = Stroke(l, t_, t_ + dur, press, pencil, pig, "hatch", where, wander=0.35, taper=(0.04, 0.2), flick=0.22, boil=min(1.0, xh / 110))
                out.append(st_)
        return out


# ------------------------------------------------------------------ where the effect sits (the same in every layered effect)
def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def place(project, fid):
    """the FX entry's window, the crop on screen in it and the spoken words: (A, B, frame, words)"""
    F = fxlib.entry(project, fid)                      # "end" resolved the way the build does it
    A, B = float(F["at"]), float(F["end"])
    frame = fxlib.crop_at(project, A)
    if any(A + 1e-6 < s["t"] < B - 1e-6 and s["frame"] != frame for s in timeline(project).get("shots", [])):
        print(f"WARNING: the crop changes inside {fid}'s window {A:.2f}-{B:.2f}. Keep the window inside one shot.")
    return A, B, frame, fxlib.words(project)


def filmed_empty(project):
    """True when the plate tools have the room behind the speaker: a filmed empty room (edit.EMPTY or
    EMPTY_CLIP), or a photo or generated background given to plate_finish.py --fill (mode "filled")"""
    try:
        return json.load(open(os.path.join(project, "work", "plate", "plate.json"))).get("mode") in ("empty", "filled")
    except (OSError, ValueError):
        return False


def plate_alpha(project, part, frame):
    """the alpha of public/plates/<part>_<FRAME>.webm (a static layer from the plate tools), or None"""
    src = f"public/plates/{part}_{frame}.webm"
    if not os.path.exists(os.path.join(project, src)):
        return None
    for _, c in fxlib.rgba(project, 0, 1 / FPS, src=src):
        return c[..., 3].astype(np.float32) / 255
    return None


def out_dir(project, fid):
    d = os.path.join(project, "fx", fid)
    if os.path.exists(os.path.join(d, "..", "LIBRARY.md")):
        sys.exit(f"{d} is the effects library itself: copy this folder into <project>/fx/{fid}/ and run that copy")
    os.makedirs(d, exist_ok=True)
    return d


# ------------------------------------------------------------------ the words: when, and where
def spoken(rows, words, A, B):
    """each row matched in order in words.json -> (rows, [(start, end)]). A hand row of several words becomes one row
    per word, each written on its own spoken word. The first may start a little before the window (its first frames
    land mid-writing). A row that isn't spoken gets a share of the window and a warning"""
    toks = [(s, e, norm(w)) for s, e, w in words]
    out_rows, out, after = [], [], A - 0.6
    for k, r in enumerate(rows):
        want = [norm(x) for x in str(r.get("say", r["text"])).split() if norm(x)]
        hit = None
        for i in range(len(toks)):
            if after - 0.001 <= toks[i][0] < B and [t[2] for t in toks[i:i + len(want)]] == want:
                hit = i
                break
        if hit is None:
            n = len(rows)
            span = (A + (k + 0.15) * (B - A) / n, A + (k + 0.75) * (B - A) / n)
            print(f"WARNING: {r['text']!r} isn't spoken in {A:.2f}-{B:.2f}: drawn at {span[0]:.2f}-{span[1]:.2f}")
            out_rows.append(r)
            out.append(span)
            continue
        after = toks[hit][0] + 0.01
        pieces = str(r["text"]).split()
        if r["kind"] != "comp" and len(pieces) == len(want) > 1 and not any(k_ in r for k_ in ("x", "base", "xh")):
            for j, piece in enumerate(pieces):
                out_rows.append(dict(r, text=piece, say=piece))
                out.append((toks[hit + j][0], toks[hit + j][1]))
        else:
            out_rows.append(r)
            out.append((toks[hit][0], toks[hit + len(want) - 1][1]))
    return out_rows, out


def measure(project, A, B):
    """what the layout reads off the footage: the top of the head (matte), the face and the shoulders (track, else the matte)"""
    f0, f1 = fr(A), fr(B)
    TR = []
    if os.path.exists(os.path.join(project, "work", "tracks", "track.json")):
        TR = fxlib.tracks(project)["frames"]
    fcs = [TR[i]["face"] for i in range(f0, min(f1, len(TR))) if TR[i].get("face")]
    pos = [TR[i]["pose"] for i in range(f0, min(f1, len(TR))) if TR[i].get("pose")]
    tops, mats = [], []
    for i, al in fxlib.alpha(project, A, B):
        if (i - f0) % 4:
            continue
        mats.append(al > 128)
        cols = slice(0, W)
        if fcs:
            cx, w = float(np.median([f["cx"] for f in fcs])), float(np.median([f["w"] for f in fcs]))
            cols = slice(max(0, int(cx - 0.35 * w)), min(W, int(cx + 0.35 * w)))
        ys = np.nonzero((al[:, cols] > 128).any(axis=1))[0]
        if len(ys):
            tops.append(int(ys[0]))
    if not tops:
        sys.exit("the matte has nobody in this window")
    m = dict(head_top=float(min(tops)))
    if fcs:
        m.update(cx=float(np.median([f["cx"] for f in fcs])), face_w=float(np.median([f["w"] for f in fcs])),
                 face_h=float(np.median([f["h"] for f in fcs])), chin=float(np.median([f["chin"] for f in fcs])))
    else:                                    # no track: the head from the matte, rough
        mat = mats[0]
        row = mat[min(H - 1, int(m["head_top"] + 0.06 * H))]
        xs = np.nonzero(row)[0]
        hw = float(xs[-1] - xs[0]) if len(xs) else 0.25 * W
        m.update(cx=float(xs.mean()) if len(xs) else W / 2, face_w=0.8 * hw, face_h=hw, chin=m["head_top"] + 1.3 * hw)
    if pos:
        m.update(shoulder_y=float(np.median([(p["ls"][1] + p["rs"][1]) / 2 for p in pos])),
                 shoulder_w=float(np.median([abs(p["ls"][0] - p["rs"][0]) for p in pos])))
    else:
        m.update(shoulder_y=m["chin"] + 0.3 * m["face_h"], shoulder_w=2.4 * m["face_w"])
    return m


def glyph_box(fc, text, xh):
    """the comp word at this x-height: its width, how far it rises and falls past the baseline (px), and the x-runs along
    it where no letter rises past the x-height (room for the handwriting)"""
    lay_, total = fc.layout(text)
    sc = xh / fc.xh
    top = np.zeros(int(total * sc) + 2)
    rise = fall = 0.0
    for ch, g, x in lay_:
        bp = BoundsPen(fc.gs)
        fc.gs[g].draw(bp)
        if not bp.bounds:
            continue
        x0, y0, x1, y1 = bp.bounds
        rise, fall = max(rise, y1 * sc), max(fall, -y0 * sc)
        a, b = int((x + x0) * sc), int((x + x1) * sc) + 1
        top[max(0, a):max(0, b)] = np.maximum(top[max(0, a):max(0, b)], y1 * sc)
    runs, start = [], None
    low = top <= 1.08 * xh
    for i, v in enumerate(np.append(low, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    return total * sc, rise, fall, runs


def hand_width(text, xh):
    """how wide the handwriting comes out: the same pen path the drawing walks (capitals and digits from the text face)"""
    return hand_paths(dict(text=text, xh=xh, x=0.0, base=0.0))[1]


def layout(rows, times, m, ground, A, B):
    """every row's place, read off the footage (a row with x, base and xh keeps them). Paper: the display word big above
    the speaker's head, moved down the sheet for headroom, the handwriting nested beside its short letters or above it.
    Footage: the display word across the chest, the handwriting either side of the neck. -> rows, shift"""
    side, top = 0.056 * W, 220 * H / 1920
    comp = [i for i, r in enumerate(rows) if r["kind"] == "comp"]
    hand = [i for i, r in enumerate(rows) if r["kind"] != "comp"]
    if len(comp) > 1:
        print("WARNING: more than one comp word: one reads best. They stack, the last one nearest the head")
    fc = face(FONT_COMP)
    hand_xh = 38 * H / 1920
    hand_line = " ".join(rows[i]["text"] for i in hand)
    out = [dict(r) for r in rows]
    shift = 0
    if ground == "paper":
        xh_cap = 230 * H / 1920
        sizes = [min(xh_cap, (W - 2 * side) / (glyph_box(fc, rows[i]["text"], 100.0)[0] / 100.0)) for i in comp]
        hw = hand_width(hand_line, hand_xh)

        def stack(sizes):
            """everything placed upward from y = 0, the top of the head: {row: (x, base, xh)} and the height it takes"""
            pos, y, nest = {}, 0.0, None
            for i, xh in zip(comp[::-1], sizes[::-1]):
                wd, rise, fall, runs = glyph_box(fc, rows[i]["text"], xh)
                base = y - 0.13 * xh
                pos[i] = ((W - wd) / 2, base, xh)
                y = base - rise
            high = y
            if hand:
                if comp:
                    runs = glyph_box(fc, rows[comp[0]]["text"], pos[comp[0]][2])[3]
                    fit = [r for r in runs if r[1] - r[0] >= hw + 0.2 * pos[comp[0]][2]]
                    nest = max(fit, key=lambda r: r[1] - r[0]) if fit else None
                if nest:                                   # beside the short letters, just over the x-height
                    x0, b0, xh0 = pos[comp[0]]
                    hx, hb = x0 + nest[0] + 0.1 * xh0, b0 - xh0 - 0.9 * hand_xh
                else:                                      # a line of its own above
                    hx, hb = (W - hw) / 2, high - 1.0 * hand_xh
                for i in hand:
                    pos[i] = (hx, hb, hand_xh)
                    hx += hand_width(rows[i]["text"] + " ", hand_xh)
                high = min(high, hb - 2.3 * hand_xh)
            return pos, -high

        for _ in range(8):
            pos, height = stack(sizes)
            want = top + height - m["head_top"]
            if SHIFT is not None or want <= SHIFT_MAX * H or not comp:
                break
            sizes = [s_ * 0.92 for s_ in sizes]            # no room even moved down the sheet: smaller words
        shift = SHIFT if SHIFT is not None else int(np.clip(want, 0, SHIFT_MAX * H))
        y0 = m["head_top"] + shift
        for i, (x, b, xh) in pos.items():
            out[i].update(x=x, base=y0 + b, xh=xh)
    else:
        xh_cap = 196 * H / 1920
        base = min(m["shoulder_y"] + 0.25 * m["shoulder_w"], 0.705 * H)
        for i in comp[::-1]:
            w_, rise, _, _ = glyph_box(fc, rows[i]["text"], 100.0)
            xh = min(xh_cap, (W - 2 * 0.057 * W) / (w_ / 100.0))
            # its tallest letter stays under the chin: drawing over the face reads as a mistake
            base = min(max(base, m["chin"] + 0.02 * H + rise * xh / 100.0), 0.705 * H)
            xh = min(xh, max(40.0, (base - m["chin"] - 0.02 * H) * 100.0 / rise))
            out[i].update(x=(W - w_ * xh / 100.0) / 2, base=base, xh=xh)
            low = base + 0.35 * xh
            base -= rise * xh / 100.0 + 0.2 * xh
        # the handwriting either side of the neck, just above the chin line, one word after another; under the display
        # word when the face leaves no room beside it
        hb = m["chin"] - 0.027 * m["face_h"]
        left, right = hand[:(len(hand) + 1) // 2], hand[(len(hand) + 1) // 2:]
        lw = hand_width(" ".join(rows[i]["text"] for i in left), hand_xh)
        rw = hand_width(" ".join(rows[i]["text"] for i in right), hand_xh)
        rx = m["cx"] + 0.55 * m["face_w"]
        if left and (0.048 * W + lw < m["cx"] - 0.55 * m["face_w"]) and (rx + rw < W - 0.048 * W):
            groups = [(left, 0.048 * W), (right, rx)]
        else:
            groups = [(hand, (W - hand_width(hand_line, hand_xh)) / 2)]
            hb = (low if comp else hb) + 1.6 * hand_xh
        for ids, hx in groups:
            for i in ids:
                out[i].update(x=hx, base=hb, xh=hand_xh)
                hx += hand_width(rows[i]["text"] + " ", hand_xh)
        for r in out:
            r.setdefault("where", "front")
            r.setdefault("pig", "c")
            r.setdefault("hatch_pig", "c")
    for r, row in zip(out, rows):                      # a row placed by hand keeps its place
        for k in ("x", "base", "xh"):
            if k in row:
                r[k] = row[k]
    for r, (s, e) in zip(out, times):
        r["t"] = (s, e) if r["kind"] != "comp" else (s, max(e, s + 0.25))
        if r["kind"] == "comp":
            r["guides"] = (s + GUIDES[0], s + GUIDES[1])
            r["guide_x"] = (-40, W + 40)
            r["hatch"] = (s + HATCH[0], max(e, s + 0.25) + HATCH[1])
            r["under"] = (min(B - 0.10, max(e, s + 0.25) + UNDER[0]), min(B - 0.03, max(e, s + 0.25) + UNDER[1]))
    return out, shift


# ------------------------------------------------------------------ frames, matte, gear
def prepare(cfg):
    """the window's frames and matte as files the workers read, and the mic and desk layers"""
    work = cfg["work"]
    os.makedirs(os.path.join(work, "frames"), exist_ok=True)
    if not os.path.exists(os.path.join(work, "frames", f"a_{cfg['f1'] - 1}.png")):
        for i, rgb in fxlib.frames(cfg["project"], cfg["a"], cfg["b"]):
            cv2.imwrite(os.path.join(work, "frames", f"f_{i}.png"), rgb[:, :, ::-1])
        for i, al in fxlib.alpha(cfg["project"], cfg["a"], cfg["b"]):
            cv2.imwrite(os.path.join(work, "frames", f"a_{i}.png"), al)
    for part in ("mic", "desk"):
        al = plate_alpha(cfg["project"], part, cfg["frame"])
        if al is not None:
            cv2.imwrite(os.path.join(work, f"{part}.png"), np.clip(al * 255, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ one effect
class Sheet:
    """everything about one effect that holds for all its drawings"""

    def __init__(self, cfg):
        self.cfg = cfg
        self.ground = cfg["ground"]
        self.a, self.b = cfg["a"], cfg["b"]
        self.f0, self.f1 = cfg["f0"], cfg["f1"]
        self.shift = cfg["shift"]
        self.words = [Word(w) for w in cfg["rows"]]
        self.T = make_paper(H * SS, W * SS, 11)
        self.col = {k: np.array(v, np.float32) for k, v in cfg["colours"].items()}

        def gear(part):
            p = os.path.join(cfg["work"], f"{part}.png")
            g = cv2.imread(p, 0) if os.path.exists(p) else None
            return g.astype(np.float32) / 255 if g is not None else np.zeros((H, W), np.float32)
        self.mic, self.desk = gear("mic"), gear("desk")
        line = cfg["solid_below"]
        if line is None:
            self.solid = np.zeros((H, W), np.float32)
        else:
            y = np.asarray(line, np.float32) if np.ndim(line) == 1 else np.full(W, float(line), np.float32)
            self.solid = cv2.GaussianBlur((np.arange(H, dtype=np.float32)[:, None] >= y[None, :]).astype(np.float32), (0, 0), 1.5)
        self.room = np.load(cfg["room"]).astype(np.float32) if self.ground == "paper" and cfg["room"] else None

    def drawing(self, k):
        """drawing k: its strokes, per (where, pigment, kind), plus its boil and its sheet"""
        rng = np.random.default_rng(1000 + 37 * k)
        bx = smooth_noise(H + 8, W + 8, 75, 2000 + k, octaves=2)[:H, :W] * BOIL
        by = smooth_noise(H + 8, W + 8, 75, 3000 + k, octaves=2)[:H, :W] * BOIL
        strokes = []
        for i, w in enumerate(self.words):
            strokes.extend(w.fixed)
            strokes.extend(w.hatch(4000 + 11 * k + i))
        bucket = {}
        for s in strokes:
            d = s.drawn(rng)
            if d is None:
                continue
            xy, pr, wd, ts = d
            ix = np.clip(xy[:, 0], 0, W - 1).astype(np.int32)
            iy = np.clip(xy[:, 1], 0, H - 1).astype(np.int32)
            xy = xy + np.stack([bx[iy, ix], by[iy, ix]], 1) * s.boil
            bucket.setdefault((s.where, s.pig, s.kind), []).append((xy, pr, wd, ts))
        merged = {key: tuple(np.concatenate(v) for v in zip(*vals)) for key, vals in bucket.items()}
        off = np.random.default_rng(500 + k).integers(0, 1500, 2)
        T = np.roll(self.T, (int(off[0]), int(off[1])), (0, 1))
        return merged, T, np.roll(T, (317, 511), (0, 1))

    def pressure(self, merged, t_now):
        """(where, pigment, kind) -> pressure at SS, what has arrived by t_now. A stroke just laid is a touch heavier: the moving tip"""
        out = {}
        for key, (xy, pr, wd, ts) in merged.items():
            m = ts <= t_now
            if not m.any():
                continue
            L = Layer()
            L.add(xy[m], pr[m] * (1 + 0.5 * np.exp(-(t_now - ts[m]) / 0.035)), wd[m])
            out[key] = L.render()
        return out

    def compose(self, f, rgb, al, merged, T, T2):
        maps = self.pressure(merged, (f + 1) / FPS)
        return self.paper(rgb, al, maps, T, T2) if self.ground == "paper" else self.footage(rgb, al, maps, T, T2)

    def layers(self, maps, where, T, T2, palette):
        out = []
        for (wh, pig, kind), pm in sorted(maps.items(), key=lambda kv: {"guide": 0, "hatch": 1, "line": 2, "under": 3}[kv[0][2]]):
            if wh != where:
                continue
            col, op, args, tooth = palette(pig, kind)
            c = cv2.resize(lay(pm, T2 if tooth == 2 else T, **args), (W, H), interpolation=cv2.INTER_AREA)
            out.append((c * op, col))
        return out

    # pigments. g: graphite (a real pencil, it stays graphite), b: the hatching, o: the underline, c: light pencil
    def palette_paper(self, pig, kind):
        C = self.col
        if pig == "o":
            return C["under"], 1.0, dict(grain=0.7, reach=0.26, soft=0.3, gain=1.3, top=0.93), 1
        if pig == "b":
            return C["hatch"], 0.98, dict(grain=0.62, reach=0.3, gain=1.4), 2
        if pig == "c":
            return C["light"], 0.98, dict(grain=0.66, reach=0.28, soft=0.3, gain=1.4, top=0.96), 1
        if kind == "guide":
            return C["graphite"], 0.8, dict(grain=0.72, reach=0.2), 1
        return C["graphite"] * 0.8, 0.98, dict(grain=0.64, reach=0.26, soft=0.3, gain=1.3, top=0.93), 1

    def palette_footage(self, pig, kind):
        C = self.col
        if pig == "c" and kind == "hatch":
            return C["light"], 0.96, dict(grain=0.68, reach=0.28, gain=1.35), 2
        if pig in ("o", "b"):
            return C["accent"], 1.0 if pig == "o" else 0.96, dict(grain=0.62, reach=0.3, soft=0.3, gain=1.4, top=0.95), 1 if pig == "o" else 2
        if kind == "guide":
            return C["light"], 0.5, dict(grain=0.8, reach=0.18), 1
        return C["light"], 0.98, dict(grain=0.64, reach=0.28, soft=0.3, gain=1.4, top=0.95), 1

    def palette_front(self, pig, kind):
        return self.palette_footage(pig if pig != "b" else "c", kind)

    def paper(self, rgb, al, maps, T, T2):
        page = np.ones((H, W, 3), np.float32) * self.col["paper"]
        tone = cv2.resize(0.976 + 0.038 * T, (W, H), interpolation=cv2.INTER_AREA)
        page = page * tone[:, :, None]
        drag = [pm for (wh, pig, _), pm in maps.items() if wh == "behind" and pig == "g"]
        if drag:                                         # graphite dust the hand drags across the sheet
            sm = cv2.GaussianBlur(cv2.resize(sum(drag), (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), 9) * 0.10
            c = cv2.resize(lay(cv2.resize(sm, (W * SS, H * SS), interpolation=cv2.INTER_LINEAR), T, grain=0.8, reach=0.1, soft=0.5), (W, H), interpolation=cv2.INTER_AREA) * 0.6
            page = page * (1 - c[:, :, None]) + self.col["graphite"] * c[:, :, None]
        for c, col in self.layers(maps, "behind", T, T2, self.palette_paper):
            page = page * (1 - c[:, :, None]) + col * c[:, :, None]
        f3, hole = self.lift(rgb, al)
        mic = self.mic
        if self.shift:                                   # the speaker further down the sheet: what falls off the bottom is gone
            S = np.float32([[1, 0, 0], [0, 1, self.shift]])
            f3 = cv2.warpAffine(f3, S, (W, H), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
            hole = cv2.warpAffine(hole, S, (W, H), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            mic = cv2.warpAffine(mic, S, (W, H), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        # the speaker's cast shadow on the sheet, small and soft: it only exists so they stand in front of the page
        sh = cv2.GaussianBlur(cv2.warpAffine(hole, np.float32([[1, 0, 30], [0, 1, 12]]), (W, H), borderMode=cv2.BORDER_CONSTANT, borderValue=0), (0, 0), 20)
        page = page * (1 - 0.18 * sh[:, :, None])
        out = page * (1 - hole[:, :, None]) + f3 * hole[:, :, None]
        for c, col in self.layers(maps, "front", T, T2, self.palette_front):
            c = c * (1 - mic)
            out = out * (1 - c[:, :, None]) + col * c[:, :, None]
        return out

    def lift(self, rgb, al):
        """the speaker off the room: with the room known, what they really are in their soft edge comes out in closed
        form, so dark hair stays dark and a bright cap stays bright on any sheet. Without a room it is estimated from the
        room just around them"""
        a = al.astype(np.float32) / 255
        gear = np.maximum(np.maximum(self.mic, self.desk), self.solid)
        a = np.maximum(a, gear)
        F = rgb.astype(np.float32)
        if self.room is not None and UNDER_ROOM is not None:
            d = np.abs(cv2.GaussianBlur(F, (0, 0), 2) - cv2.GaussianBlur(self.room, (0, 0), 2)).sum(axis=2)
            m = st(d, 26, 38)
            m[:int(UNDER_ROOM)] = 0
            m = cv2.morphologyEx((m > 0.5).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
            n_, lab = cv2.connectedComponents(((a > 0.5) | (m > 0)).astype(np.uint8))
            keep = np.zeros(n_, bool)
            keep[np.unique(lab[a > 0.5])] = True
            m = (m > 0) & keep[lab]
            a = np.maximum(a, cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.5))
        filled = ndi.binary_fill_holes(a > 0.5)          # the sheet can't show through a gap that doesn't reach the frame's edge
        a[cv2.erode(filled.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))) > 0] = 1.0
        room = self.room
        if room is None:                                 # no plate: the room near the speaker, spread in from what isn't them
            out_ = (1 - a) ** 2
            room = cv2.GaussianBlur(F * out_[:, :, None], (0, 0), 14) / np.maximum(cv2.GaussianBlur(out_, (0, 0), 14), 1e-3)[:, :, None]
        fg = (F - (1 - a)[:, :, None] * room) / np.maximum(a, 0.3)[:, :, None]
        fg = np.where((a > 0.985)[:, :, None], F, np.clip(fg, 0, 255))
        dark = np.clip((70 - cv2.GaussianBlur(fg, (0, 0), 3).mean(axis=2)) / 30, 0, 1)   # a soft edge in dark hair reads as a smudge on paper: tighter
        lo, hi = 0.16 + 0.26 * dark, 0.72 - 0.10 * dark
        return fg, np.maximum(np.clip((a - lo) / (hi - lo), 0, 1), gear)

    def footage(self, rgb, al, maps, T, T2):
        out = rgb.astype(np.float32)
        m = np.maximum(np.maximum(cv2.GaussianBlur(al.astype(np.float32) / 255, (0, 0), 1.0), np.maximum(self.mic, self.desk)), self.solid)
        for c, col in self.layers(maps, "behind", T, T2, self.palette_footage):
            c = c * (1 - m)
            out = out * (1 - c[:, :, None]) + col * c[:, :, None]
        for c, col in self.layers(maps, "front", T, T2, self.palette_front):
            c = c * (1 - self.mic)
            out = out * (1 - c[:, :, None]) + col * c[:, :, None]
        return out


_SHEET = None


def _init(cfg):
    global _SHEET
    cv2.setNumThreads(2)
    configure(cfg)
    _SHEET = Sheet(cfg)


def render_hold(k):
    sh = _SHEET
    t0 = time.time()
    merged, T, T2 = sh.drawing(k)
    for f in range(sh.f0 + k * HOLD, min(sh.f1, sh.f0 + (k + 1) * HOLD)):
        rgb = cv2.imread(os.path.join(sh.cfg["work"], "frames", f"f_{f}.png"))[:, :, ::-1]
        al = cv2.imread(os.path.join(sh.cfg["work"], "frames", f"a_{f}.png"), 0)
        out = sh.compose(f, rgb, al, merged, T, T2)
        np.save(os.path.join(sh.cfg["work"], "out", f"f_{f}.npy"), np.clip(out, 0, 255).round().astype(np.uint8))
    return time.time() - t0


def stills(cfg, times):
    prepare(cfg)
    sh = Sheet(cfg)
    for t in times:
        f = min(max(fr(t), sh.f0), sh.f1 - 1)
        merged, T, T2 = sh.drawing((f - sh.f0) // HOLD)
        rgb = cv2.imread(os.path.join(cfg["work"], "frames", f"f_{f}.png"))[:, :, ::-1]
        al = cv2.imread(os.path.join(cfg["work"], "frames", f"a_{f}.png"), 0)
        out = sh.compose(f, rgb, al, merged, T, T2)
        name = os.path.join(cfg["work"], f"still_{cfg['ground']}_{t:.2f}.jpg")
        cv2.imwrite(name, np.clip(out, 0, 255).round().astype(np.uint8)[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(name)


def specimen(cfg):
    """the type engine alone, finished, on paper: is this drawn or is it a font?"""
    xh = 150 * H / 1920
    lines = [dict(text="For me, that's", kind="hand", x=60, base=150, xh=42, t=(0, 1)),
             dict(text="a plain line written by hand", kind="hand", x=60, base=260, xh=30, t=(0, 1)),
             dict(text="ideas", kind="comp", x=60, base=600, xh=xh * 1.3, guides=(0, .1), guide_x=(-40, W + 40), t=(.1, .6), hatch=(.5, .8), under=(.8, .9)),
             dict(text="drafts", kind="comp", x=60, base=900, xh=xh * 0.7, guides=(0, .1), guide_x=(-40, 700), t=(.1, .6), hatch=(.5, .8)),
             dict(text="Writing", kind="comp", x=60, base=1150, xh=xh * 0.6, guides=(0, .1), guide_x=(-40, 900), t=(.1, .6), hatch=(.5, .8), under=(.8, .9))]
    sh = Sheet(dict(cfg, rows=lines, ground="paper", shift=0, room=None, solid_below=None))
    merged, T, T2 = sh.drawing(0)
    maps = sh.pressure(merged, 9.0)
    page = np.ones((H, W, 3), np.float32) * sh.col["paper"] * cv2.resize(0.976 + 0.038 * T, (W, H), interpolation=cv2.INTER_AREA)[:, :, None]
    for c, col in sh.layers(maps, "behind", T, T2, sh.palette_paper):
        page = page * (1 - c[:, :, None]) + col * c[:, :, None]
    p = os.path.join(cfg["work"], "specimen.png")
    cv2.imwrite(p, np.clip(page, 0, 255).astype(np.uint8)[:, :, ::-1])
    print(p)


# ------------------------------------------------------------------ sound: the pencil, from the same motion (synthesized here, CC0)
def wav(path, x, sr=48000):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.stack([x, x * 0.96], 1) * 32767).astype("<i2").tobytes())


def scratch(env, sr=48000, lo=1100, hi=7200, seed=1, body=0.22):
    """graphite on paper: band-limited friction noise, gated by the tooth, plus a little of the desk under the sheet"""
    from scipy.signal import butter, sosfilt
    rng = np.random.default_rng(seed)
    n = len(env)
    x = sosfilt(butter(2, [lo, hi], "band", fs=sr, output="sos"), rng.standard_normal(n))
    tooth = sosfilt(butter(2, 900, "low", fs=sr, output="sos"), rng.standard_normal(n))
    tooth = np.clip(0.55 + 1.6 * tooth / (np.abs(tooth).max() + 1e-6), 0, 1.6)
    rumble = sosfilt(butter(2, [140, 520], "band", fs=sr, output="sos"), rng.standard_normal(n))
    return (x / (np.abs(x).max() + 1e-6) * tooth + body * rumble / (np.abs(rumble).max() + 1e-6)) * env


def sounds(cfg, path):
    """starts at the window's first frame and follows the drawn motion sample for sample: rules swipe, letters scratch,
    hatching chatters at the wrist's rate, the underline swishes"""
    from scipy.signal import butter, sosfilt
    sh = Sheet(cfg)
    sr = 48000
    tt = np.arange(int(((sh.f1 - sh.f0) / FPS + 0.12) * sr)) / sr
    env = {k: np.zeros_like(tt) for k in ("guide", "line", "hatch", "under")}
    for w in sh.words:
        for st_ in w.fixed + w.hatch(4000):
            ts = st_.tt - sh.a
            if ts[-1] < 0 or len(ts) < 3:
                continue
            m = (tt >= max(ts[0], 0)) & (tt <= ts[-1])
            if not m.any():
                continue
            v = 1 / np.maximum(np.gradient(ts), 1e-5)
            v = np.clip(v / (np.percentile(v, 95) + 1e-6), 0, 1.2) ** 0.7
            press = min(1.1, st_.p) * (0.7 + 0.3 * min(1.0, len(ts) / 200))
            env[st_.kind][m] = np.maximum(env[st_.kind][m], np.interp(tt[m], ts, v) * press)
    wrist = 0.5 + 0.5 * np.cos(2 * np.pi * 21 * tt + 0.8 * np.sin(2 * np.pi * 3.1 * tt))        # hatching is a back and forth
    env["hatch"] = env["hatch"] * (0.45 + 0.55 * wrist ** 2)
    smooth = lambda e, hz: sosfilt(butter(1, hz, "low", fs=sr, output="sos"), e)  # noqa: E731
    mix = (scratch(smooth(env["line"], 240), sr, 1500, 8200, 5, 0.12) * 0.72 + scratch(smooth(env["hatch"], 300), sr, 1100, 7200, 7, 0.2) * 0.6 +
           scratch(smooth(env["guide"], 400), sr, 700, 6000, 3, 0.3) * 0.62 + scratch(smooth(env["under"], 300), sr, 900, 6500, 9, 0.25) * 0.8)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wav(path, mix / max(1e-6, np.abs(mix).max()) * 0.8)


def run(cfg):
    t0 = time.time()
    d = out_dir(cfg["project"], cfg["id"])
    prepare(cfg)
    os.makedirs(os.path.join(cfg["work"], "out"), exist_ok=True)
    n = (cfg["f1"] - cfg["f0"] + HOLD - 1) // HOLD
    with mp.Pool(min(8, os.cpu_count() or 4), initializer=_init, initargs=(cfg,)) as pool:
        ts = pool.map(render_hold, range(n))
    print(f"{cfg['id']} {cfg['ground']}: {n} drawings, {sum(ts) / max(1, n):.1f}s each, {time.time() - t0:.0f}s", flush=True)
    w = fxlib.Writer(os.path.join(d, f"{cfg['id']}.mp4"), W, H, crf=15)
    for f in range(cfg["f0"], cfg["f1"]):
        w.write(np.load(os.path.join(cfg["work"], "out", f"f_{f}.npy")))
    w.close()
    sounds(cfg, os.path.join(cfg["project"], "audio", f"{cfg['id']}-pencil.wav"))
    print(os.path.join(d, f"{cfg['id']}.mp4"))


# ------------------------------------------------------------------ the pack
def configure(cfg):
    """the canvas and the pack's faces, in this process (the workers call it too)"""
    global W, H, FONT_COMP, FONT_HAND
    W, H = cfg["size"]
    FONT_COMP, FONT_HAND = cfg["font_comp"], cfg["font_hand"]


def pack_look(project):
    """the faces and pigments from the style pack. Graphite stays graphite: it is the pencil"""
    S = fxlib.pack(project)
    paths = {r: S["fonts"][r].get("path") for r in ("display", "text")}
    for r, p in paths.items():
        if not p or not os.path.exists(p):
            sys.exit(f"the pack's {r} font isn't in {project}/style/fonts/: run the kit's style.py on the pack, then new.py copies it")

    def rgb(role, over="light"):
        r, g, b, a = S["colors"][role]
        base = np.array(S["colors"][over][:3], np.float32)
        return list(np.array([r, g, b], np.float32) * (a / 255) + base * (1 - a / 255))
    colours = dict(paper=rgb("light"), light=rgb("light", "dark"), hatch=rgb("accent_on_light"),
                   under=list(np.array(rgb("accent_on_light")) * 0.88), accent=rgb("accent", "dark"), graphite=[58.0, 56.0, 58.0])
    return paths["display"], paths["text"], colours


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--ground", choices=("paper", "footage", "wall"), help="override GROUND")
    ap.add_argument("--stills", nargs="+", type=float, help="render these reel times as jpgs in work/<id>/ instead of the clip")
    ap.add_argument("--specimen", action="store_true", help="the pack's type drawn alone on paper, to work/<id>/specimen.png")
    a = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(a.project)), a.id
    ground = {"wall": "footage"}.get(a.ground or GROUND, a.ground or GROUND)
    A, B, frame, words = place(project, fid)
    size = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    font_comp, font_hand, colours = pack_look(project)
    cfg = dict(project=project, id=fid, ground=ground, frame=frame, a=A, b=B, f0=fr(A), f1=fr(B), size=size,
               font_comp=font_comp, font_hand=font_hand, colours=colours, work=os.path.join(project, "work", fid))
    configure(cfg)
    os.makedirs(cfg["work"], exist_ok=True)
    if a.specimen:
        specimen(dict(cfg, rows=[], shift=0, room=None, solid_below=None))
        return
    rows = [dict(r) for r in WORDS]
    m = measure(project, A, B)
    rows, times = spoken(rows, words, A, B)
    rows, shift = layout(rows, times, m, ground, A, B)
    solid = SOLID_BELOW
    if solid is None:                                    # below the desk's top edge it is all desk, mic or speaker
        desk = plate_alpha(project, "desk", frame)
        if desk is not None and (desk > 0.5).any():
            hit = (desk > 0.5).any(axis=0)
            solid = [float(v) for v in np.where(hit, np.argmax(desk > 0.5, axis=0), H)]
    # the room behind the speaker's soft edge: the filmed empty room's, else estimated around them. A fallback plate's
    # fill is cut out exactly along where the speaker always sat, so it is least right exactly at their edge
    room = os.path.join(project, "work", "c", f"room_{frame}.npy")
    cfg.update(rows=rows, shift=shift, solid_below=solid, room=room if os.path.exists(room) and filmed_empty(project) else None)
    print(f"{fid}: {ground}, crop {frame}, shift {shift}px, room {'yes' if cfg['room'] else 'estimated near the speaker'}")
    for r in rows:
        extra = f" guides {r['guides'][0]:.2f} hatch {r['hatch'][0]:.2f}-{r['hatch'][1]:.2f} under {r['under'][0]:.2f}" if r["kind"] == "comp" else ""
        print(f"  {r['kind']:<5} {r['text']!r:<12} x {r['x']:.0f} base {r['base']:.0f} xh {r['xh']:.0f}  t {r['t'][0]:.2f}-{r['t'][1]:.2f}{extra}")
    if a.stills:
        stills(cfg, a.stills)
        return
    run(cfg)
    print("SFX (edit.SOUND['sfx']) and captions:")
    print(f'    dict(at={A:.3f}, name="{fid}-pencil", db=-9, align="start"),   # audio/{fid}-pencil.wav, from the drawn motion')
    print(f"    KARAOKE['hide'] += [({A:.2f}, {B:.2f})]     # the drawing carries the words")


if __name__ == "__main__":
    main()
