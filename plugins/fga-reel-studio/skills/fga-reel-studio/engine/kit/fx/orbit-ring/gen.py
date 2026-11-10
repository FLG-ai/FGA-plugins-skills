#!/usr/bin/env python3
"""orbit-ring: a Saturn ring of type round the speaker's head. A real perspective circle in 3D, tilted, locked to the
face track (centre and roll). Letters on the far half live in <id> (layer behind, under the cutout), letters on the
near half in <id>-front (layer top, over the speaker): the same letter hands over at the two extremes, where nothing
overlaps the head. Each word lights in the accent as it is spoken, then the ring whips round and reels into the back
of the head like a tape measure, so nothing ever crosses the face. Every letter has its own pose per frame and is
rendered with true motion blur (a shutter that opens from 72 degrees at cruise to 180 on the spiral in and the reel
out) into two all-intra clips; the near clip also carries the letters' soft shadow, on the speaker only.
DOM = True writes crisp elements and one tl.set per letter per frame instead (no blur).

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (FX entries <id> on layer behind and <id>-front on layer top, same window, plus a
          CUT_WINDOWS entry over it), words.json, work/tracks/track.json (pipeline/track.py), public/subject.webm,
          the style pack (display face, light and accent)
  writes  <project>/fx/<id>/smear.webm + fx.html + fx.js, <project>/fx/<id>-front/ (the same three)
<id> defaults to this folder's name. Rerun it whenever the window, the cut or the words change.
"""
import argparse
import json
import math
import os
import re
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920

# ---- the table: everything that belongs to one video. The window comes from the FX entry, times from words.json.
TEXT = "FILMING · WRITING · BEING ON CAMERA · "   # the ring in caps: items split by " · ", ending with one so it loops
LIGHT = None                # [(ring word, spoken word)] in order; None = every word of TEXT lights on itself, spoken in the window
CENTRE_LAG = 0.15           # s after an item's first word lights, the item is dead centre at the front
SPIN = 3.0                  # s per turn when only one item is named (two or more set the spin themselves)
IN_AFTER = 0.10             # s after the window starts, the letters start spiralling in
ENTRY = 0.46                # s a letter takes to settle
STAGGER = 0.15              # s: the last letter starts spiralling this much after the first
SHUT_ON = None              # the spoken word the ring reels in on; None = the last word that lights
REEL = 0.48                 # s from the reel starting to the ring gone
COLLAPSE = 0.11             # s a letter takes to pull in behind the head at the end
R = None                    # ring radius, px at the plane of the head; None = R_FACE face widths, kept inside the frame
R_FACE = 1.45
TILT = None                 # degrees we look down on it; None = the tilt that puts the near arc under the chin and the far
                            # arc FAR_AT of the way down from the top of the head (32 on the shipped take), 24 to 56
FAR_AT = 0.2
NEAR_FAR = 1.5              # near letters / far letters
CY_OFF = None               # ring centre relative to the face centre, px; None = the near arc's letters just clear the chin
CHIN_CLEAR = 0.06           # ...by this many face widths
CX_OFF = 0.0                # px: the ring sits this far right of the head (negative = left), to dodge something on screen
KAPPA = 0.20                # spreads letters at the extremes, where a tilted circle would bunch them
EDGE_SCALE = 0.20           # and they get this much smaller at the extremes, seen edge on
FONT_NEAR = None            # px, the display face on the near arc; None = FONT_FACE face widths
FONT_FACE = 0.415
TRACK = 0.035               # em between letters
RHO0, SWIRL = 2.7, 1.5      # entry: starts this many radii out, this many radians behind
SHUTTER = (72.0, 180.0, 34.0, 70.0)    # the shutter opens from this to this (degrees), between these speeds (px per frame)
SHADOW = (0, 15, 11, 0.5)   # near letters on the speaker: dx, dy, blur, strength
MARGIN = 35                 # px: the ring's extremes stay this far inside the frame
MIN_GAP = 0.06              # em: the least room between two neighbouring letters anywhere on the ring
DOM = False                 # True: crisp elements + tl.set instead of the clips (no motion blur)


# ---- the kit and the project
def kit_pipeline():
    """fxlib and the rest of the kit's pipeline: PY has them on its path (setup puts them there). Run from the kit's
    library folder itself, they are two folders up"""
    try:
        import fxlib  # noqa: F401
    except ImportError:
        up = os.path.abspath(os.path.join(HERE, "..", "..", "pipeline"))
        if not os.path.exists(os.path.join(up, "fxlib.py")):
            sys.exit("can't import fxlib: run this with the kit's Python (PY), which has the kit's pipeline on its path")
        sys.path.insert(0, up)


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def spoken(words, w, after, before=1e9):
    """start of the first spoken word w in [after, before) (as wordAt in fx.js), or None"""
    for s, e, text in words:
        if after - 0.001 <= s < before and norm(text) == norm(w):
            return s
    return None


def out_dir(project, fid):
    d = os.path.join(project, "fx", fid)
    if os.path.realpath(d) == os.path.realpath(HERE) and os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "build.py")):
        sys.exit("that is the kit's library folder: copy it to <project>/fx/<id>/ and run the copy")
    os.makedirs(d, exist_ok=True)
    return d


# ---- the timing, from the words
def timing(words, text, A, B):
    """(lights [(ring word index in text, start, end)], centre keys [(span in text, t)], IN, SHUT, GONE)"""
    items = [it.strip() for it in text.split("·") if it.strip()]
    pairs = LIGHT or [(w, w) for it in items for w in it.split()]
    lit, after, pos = [], A, 0
    for ring_word, said in pairs:
        m = re.compile(r"(?<![^\W_])" + re.escape(ring_word) + r"(?![^\W_])").search(text, pos)
        if not m:
            sys.exit(f"LIGHT: {ring_word!r} is not in TEXT after the words before it")
        i = m.start()
        t = spoken(words, said, after, B)
        if t is None:
            print(f"warning: {said!r} is not spoken in {A:.2f}-{B:.2f} after the words before it: {ring_word} never lights")
            pos = i + len(ring_word)
            continue
        lit.append([i, len(ring_word), t])
        after, pos = t + 0.01, i + len(ring_word)
    if not lit:
        sys.exit("no ring word is spoken in the window: set LIGHT (ring word, spoken word) at the top of gen.py")
    # a word goes back to light when the next item lights; the last item stays lit to the end
    item_of = []
    for i, n, t in lit:
        item_of.append(text[:i].count("·"))
    lights = []
    for k, (i, n, t) in enumerate(lit):
        nxt = [lit[j][2] for j in range(k + 1, len(lit)) if item_of[j] != item_of[k]]
        lights.append((i, n, t, nxt[0] if nxt else 99.0))
    keys, seen = [], set()
    for k, (i, n, t) in enumerate(lit):
        if item_of[k] in seen:
            continue
        seen.add(item_of[k])
        members = [lit[j] for j in range(len(lit)) if item_of[j] == item_of[k]]
        a, b = members[0][0], members[-1][0] + members[-1][1] - 1
        keys.append(((a, b), t + CENTRE_LAG))
    t_in = A + IN_AFTER
    shut = spoken(words, SHUT_ON, A, B) if SHUT_ON else lit[-1][2]
    if shut is None:
        sys.exit(f"SHUT_ON {SHUT_ON!r} is not spoken in the window")
    gone = min(shut + REEL, B - 0.05)
    return lights, keys, t_in, shut, gone


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    kit_pipeline()
    import fxlib
    from scipy.interpolate import PchipInterpolator
    from scipy.ndimage import gaussian_filter1d
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    front = fid + "-front"
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    from common import load_edit, timeline
    E = load_edit(project)
    TL = timeline(project)
    inside = [c for c in TL.get("picture_cuts", []) + TL.get("reframes", []) if A + 0.5 / FPS < c < B - 0.5 / FPS]
    if inside:
        sys.exit(f"the picture cuts at {', '.join(f'{c:.2f}' for c in inside)}, inside the window {A:.2f}-{B:.2f}: the ring rides one "
                 f"continuous shot (the cutout can't cross a cut either). Start the window on the cut or end it before")
    ids = {F["id"]: F for F in getattr(E, "FX", [])}
    if front not in ids:
        print(f'add the near half to edit.FX: dict(id="{front}", layer="top", at={A:.4f}, end={B:.4f})')
    elif (float(ids[front]["at"]), ids[front]["end"]) != (A, ids[fid]["end"]):
        print(f"warning: {front} should have the same window as {fid} ({A:.2f}-{B:.2f})")
    if ids[fid].get("layer") != "behind":
        print(f"warning: {fid} belongs on layer behind (with a CUT_WINDOWS entry over its window)")
    if not any(a <= A + 1e-3 and (b == "end" or float(b) >= B - 1e-3) for a, b in getattr(E, "CUT_WINDOWS", [])):
        print(f"add a CUT_WINDOWS entry over {A:.2f}-{B:.2f}: the far half sits behind the speaker's cutout")
    S_ = fxlib.pack(project)
    LIGHT_RGB = tuple(S_["colors"]["light"][:3])
    ACC_RGB = tuple(S_["colors"]["accent"][:3])
    words = fxlib.words(project)

    # the head, smoothed: centre and roll per frame, missing frames filled from their neighbours
    tr = fxlib.tracks(project)["frames"]
    n0, n1 = round(A * FPS), round(B * FPS)
    rows = [tr[n].get("face") if 0 <= n < len(tr) else None for n in range(n0 - 2, n1 + 3)]
    if not any(rows):
        sys.exit("no face in work/tracks/track.json inside this window: run pipeline/track.py")

    def col(key):
        a = np.array([f[key] if f else np.nan for f in rows], float)
        bad = np.isnan(a)
        a[bad] = np.interp(np.where(bad)[0], np.where(~bad)[0], a[~bad])
        return a
    cx = gaussian_filter1d(col("cx"), 2.0, mode="nearest") + CX_OFF
    cy = gaussian_filter1d(col("cy"), 2.0, mode="nearest")
    roll = gaussian_filter1d(col("roll"), 3.0, mode="nearest")
    fw = float(np.median(col("w")))
    chin_off = float(np.median(col("chin") - col("cy")))

    # the ring's size from the head, its extremes kept inside the frame
    font_near = FONT_NEAR or FONT_FACE * fw
    radius = R or R_FACE * fw
    room = min(cx.min() - MARGIN, W - MARGIN - cx.max())
    if radius + .35 * font_near > room:
        k = room / (radius + .35 * font_near)
        radius, font_near = radius * k, font_near * k
        print(f"the ring is held to the frame: radius {radius:.0f}px, letters {font_near:.0f}px")
    # the tilt: the near arc just under the chin, the far arc behind the top of the head (the top of the matte). A
    # close-up's head is big against a ring the frame holds small, so it looks down on the ring more steeply
    tops = []
    for k, (n, al) in enumerate(fxlib.alpha(project, A, B)):
        fc = tr[n].get("face") if n < len(tr) else None
        if k % 6 == 0 and fc:
            c = al[:, int(np.clip(fc["cx"], 0, W - 1))] > 128
            if c.any():
                tops.append(int(np.argmax(c)) - fc["cy"])
    top_off = float(np.median(tops)) if tops else -1.6 * chin_off       # no matte to read: about where hair ends
    if TILT is None:
        span = (chin_off + CHIN_CLEAR * fw + .42 * font_near) - (top_off + FAR_AT * (chin_off - top_off))
        st0 = span / (radius * ((NEAR_FAR + 1) / 2 + (NEAR_FAR + 1) / (2 * NEAR_FAR)))
        tilt = math.radians(float(np.clip(math.degrees(math.asin(min(1.0, max(0.0, st0)))), 24.0, 56.0)))
    else:
        tilt = math.radians(TILT)
    st, ct = math.sin(tilt), math.cos(tilt)
    f = radius * ct * (NEAR_FAR + 1) / (NEAR_FAR - 1)      # near/far ratio sets the camera distance: (f + Rc) / (f - Rc) = NEAR_FAR
    p_near = f / (f - radius * ct)
    near_dy = radius * st * p_near
    far_dy = radius * st * f / (f + radius * ct)

    # the text, in em of the display face: missing glyphs come out as boxes, so swap the separator
    fpath = S_["fonts"]["display"]["path"]
    text = TEXT
    try:
        from fontTools.ttLib import TTFont
        cmap = TTFont(fpath).getBestCmap()
        if ord("·") not in cmap:
            text = text.replace("·", "-")
        missing = sorted({ch for ch in text if ch != " " and ord(ch) not in cmap})
        if missing:
            print(f"warning: the display face has no {''.join(missing)!r}: they show as boxes")
    except Exception:
        pass
    ref = fxlib.font(project, "display", 200)
    adv = [ref.getlength(ch) / 200 for ch in text]
    ink = []
    for ch in text:                                       # each glyph's ink box in em (a dot is small, a W is wide)
        l_, t_, r_, b_ = ref.getbbox(ch) if ch != " " else (0, 0, 0, 0)
        ink.append(((r_ - l_) / 200, (b_ - t_) / 200))
    s, pos = 0.0, []
    for ch, a in zip(text, adv):
        pos.append(s + a / 2)
        s += a + TRACK
    S = s
    glyphs = [(i, ch, pos[i]) for i, ch in enumerate(text) if ch != " "]
    NN = len(glyphs)

    # the letters fit their share of the ring: on a still ring at every turn, no two neighbours on the near front (where
    # they read, biggest) closer than MIN_GAP em. A narrow serif keeps the size the head gives it; a wide heavy face
    # gets smaller letters instead of touching ones. The sides crowd a little more, as shipped: the warp spreads them
    def warp0(a):
        return a + KAPPA * math.sin(2 * a)
    fit = 1e9
    for th in np.linspace(0, 2 * math.pi, 96, endpoint=False):
        pts = []
        for i, ch, sp in glyphs:
            phi = warp0(th - 2 * math.pi * sp / S)
            d = math.sin(phi)
            p = f / (f - radius * ct * d)
            pts.append((radius * math.cos(phi) * p, radius * st * d * p, p / p_near * (1 - EDGE_SCALE * abs(math.cos(phi)) ** 3), ink[i], d))
        for (x1, y1, s1, k1, d1), (x2, y2, s2, k2, d2) in zip(pts, pts[1:]):
            if d1 < .5 or d2 < .5:
                continue
            g = MIN_GAP * min(s1, s2)
            fit = min(fit, max(abs(x1 - x2) / ((k1[0] * s1 + k2[0] * s2) / 2 + g), abs(y1 - y2) / ((k1[1] * s1 + k2[1] * s2) / 2 + g)))
    if fit < font_near:
        print(f"letters {font_near:.0f}px would touch on this ring in this face: set at {fit:.0f}px")
        font_near = fit
    cy_off = CY_OFF if CY_OFF is not None else chin_off + CHIN_CLEAR * fw + .42 * font_near - near_dy
    if (cy + cy_off - far_dy).min() - .42 * font_near / NEAR_FAR < 100:
        print("warning: the far arc runs off the top of the frame: set TILT lower, or R")
    ss = 2
    font_big = fxlib.font(project, "display", int(font_near * ss))
    lights, keys, IN, SHUT, GONE = timing(words, TEXT, A, B)          # same length as text: the indexes match
    print(f"{NN} letters, {S:.2f} em round; radius {radius:.0f}px, letters {font_near:.0f}px, tilt {math.degrees(tilt):.0f}, near arc {cy_off + near_dy:+.0f}px "
          f"and far arc {cy_off - far_dy:+.0f}px from the face centre; in {IN:.2f}, reel {SHUT:.2f}, gone {GONE:.2f}")

    def head(t):
        v = t * FPS - (n0 - 2)
        k = int(math.floor(v))
        k = max(0, min(k, len(cx) - 2))
        u = v - k
        return cx[k] + (cx[k + 1] - cx[k]) * u, cy[k] + (cy[k + 1] - cy[k]) * u, roll[k] + (roll[k + 1] - roll[k]) * u

    # the spin: each item reaches the front while it is said
    kt = [t for _, t in keys]
    kth = [math.pi / 2 + 2 * math.pi * (pos[a] + pos[b]) / 2 / S for (a, b), _ in keys]
    if len(kt) == 1:
        sl = 2 * math.pi / SPIN
        kt, kth = [kt[0] - 1.0, kt[0], kt[0] + 1.0], [kth[0] - sl, kth[0], kth[0] + sl]
    else:
        slope0 = (kth[1] - kth[0]) / (kt[1] - kt[0])
        slope1 = (kth[-1] - kth[-2]) / (kt[-1] - kt[-2])
        kt, kth = [kt[0] - 1.0] + kt + [kt[-1] + 1.0], [kth[0] - slope0] + kth + [kth[-1] + slope1]
    if any(b <= a for a, b in zip(kt, kt[1:])):
        sys.exit("two items centre at the same moment: space their words out or set LIGHT")
    spin = PchipInterpolator(kt, kth)

    def theta0(t):
        v = float(spin(t))
        if t > SHUT:                          # the reel: the spin keeps building until the tail is round the back
            u = (t - SHUT) / (GONE - SHUT)
            v += 3.6 * u * u * u              # cubic: the last word stays readable for a beat, then it whips
        return v

    def warp(a):
        return a + KAPPA * math.sin(2 * a)

    # from SHUT each letter runs on along the near arc to the far end, then pulls straight in behind the head. It never
    # comes round again, so the near arc empties from one side and nothing crosses the face
    tcol, phicol = {}, {}
    for gi, (i, ch, sp) in enumerate(glyphs):
        t = SHUT + 0.07                       # the whole ring still stands when the last word lights
        while t < GONE + 0.5:
            if math.sin(warp(theta0(t) - 2 * math.pi * sp / S)) < 0.3:
                break
            t += 1 / 480
        tcol[gi] = t
        phicol[gi] = warp(theta0(t) - 2 * math.pi * sp / S)
    late = max(tcol.values()) + COLLAPSE
    print(f"letters round the back from {min(tcol.values()):.3f} to {max(tcol.values()):.3f}, gone at {late:.3f}")
    if late > B + 0.5 / FPS:
        print(f"warning: the last letter is still pulling in at the window's end ({B:.2f}): end the window later or SHUT earlier")

    def pose(gi, t):
        """x, y, scale (1 = font_near), opacity, layer of letter gi at time t"""
        i, ch, sp = glyphs[gi]
        base = theta0(t) - 2 * math.pi * sp / S
        tau = float(np.clip((t - (IN + (gi / NN) * STAGGER)) / ENTRY, 0.0, 1.0))
        e = 1 - (1 - tau) ** 3
        rho = 1 + (RHO0 - 1) * (1 - e)
        base -= SWIRL * (1 - e)
        o = float(np.clip(tau / 0.12, 0, 1))
        phi = warp(base)
        pulled = t >= tcol[gi]
        shrink = 1.0 - 0.07 * min(1.0, (t - SHUT) / (GONE - SHUT)) if t > SHUT else 1.0   # the ring tightens
        if pulled:
            phi = phicol[gi]
            cc = min(1.0, (t - tcol[gi]) / COLLAPSE)
            rho *= 1 - 0.86 * cc * cc
            if cc >= 1.0:
                o = 0.0
        d = math.sin(phi)
        rr = radius * rho * shrink
        p = f / (f - rr * ct * d)
        x_, y_ = rr * math.cos(phi) * p, rr * st * d * p
        hx, hy, hr = head(t)
        r = math.radians(hr)
        X = hx + x_ * math.cos(r) - y_ * math.sin(r)
        Y = hy + cy_off + x_ * math.sin(r) + y_ * math.cos(r)
        sc = p / p_near * (1 - EDGE_SCALE * abs(math.cos(phi)) ** 3)
        return X, Y, sc, o * (0.66 + 0.34 * (d + 1) / 2), ("n" if d >= 0 and not pulled else "f")

    def lit_at(gi, t):
        i = glyphs[gi][0]
        return any(a <= i < a + n and t0 <= t < t1 for a, n, t0, t1 in lights)

    def glyph_sprite(ch, rgb):
        """a letter at font_near x ss as premultiplied RGBA, centred the way the CSS element is (advance x line height)"""
        w = font_big.getlength(ch)
        pad = int(font_near * ss * 0.3)
        h = int(font_near * ss)
        im = Image.new("RGBA", (int(w) + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        asc, desc = font_big.getmetrics()
        base = pad + (h - (asc + desc)) / 2 + asc         # CSS line-height 1: the content area is centred on the line box
        ImageDraw.Draw(im).text((pad, base), ch, font=font_big, fill=tuple(rgb) + (255,), anchor="ls")
        arr = np.asarray(im, np.float32) / 255.0
        arr[:, :, :3] *= arr[:, :, 3:4]
        return arr, (im.width / 2.0, im.height / 2.0)

    sprites = {}

    def sprite(gi, on):
        k = (glyphs[gi][1], on)
        if k not in sprites:
            sprites[k] = glyph_sprite(glyphs[gi][1], ACC_RGB if on else LIGHT_RGB)
        return sprites[k]

    def stamp(canvas, spr, c, X, Y, sc, w):
        k = sc / ss
        Hh, Ww = spr.shape[:2]
        rad = math.hypot(Ww, Hh) * k / 2 + 3
        x0, y0 = int(max(0, X - rad)), int(max(0, Y - rad))
        x1, y1 = int(min(W, X + rad + 1)), int(min(H, Y + rad + 1))
        if x1 <= x0 or y1 <= y0:
            return
        M = np.array([[k, 0, X - x0 - c[0] * k], [0, k, Y - y0 - c[1] * k]], np.float32)
        canvas[y0:y1, x0:x1] += cv2.warpAffine(spr, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0) * w

    def smoothstep(a, b, x):
        u = min(1.0, max(0.0, (x - a) / (b - a)))
        return u * u * (3 - 2 * u)

    # proof for the rule: the closest a near-side letter ever gets to the eyes and mouth
    closest = (1e9, None)
    for n in range(n0, n1):
        fc = tr[n].get("face") if n < len(tr) else None
        if not fc:
            continue
        for gi in range(NN):
            X, Y, sc, op, layer = pose(gi, n / FPS)
            if layer != "n" or op <= 0:
                continue
            hw = font_near * sc * 0.42
            for nm, (px, py) in (("eye", fc["eyes"][0]), ("eye", fc["eyes"][1]), ("mouth", fc["mouth"])):
                dd = math.hypot(max(abs(px - X) - hw, 0), max(abs(py - Y) - hw, 0))
                if dd < closest[0]:
                    closest = (dd, (round(n / FPS, 2), glyphs[gi][1], nm))
    print("closest near letter to the eyes and mouth:", round(closest[0]), "px", closest[1])
    if closest[0] < 10:
        print("warning: a near letter touches the face: raise CHIN_CLEAR or TILT")

    d_far, d_near = out_dir(project, fid), out_dir(project, front)
    far_rows = {g: [] for g in range(NN)}
    near_rows = {g: [] for g in range(NN)}
    prev_layer = {}
    if not DOM:
        wf = fxlib.Writer(os.path.join(d_far, "smear.webm"), alpha=True, crf=14)
        wn = fxlib.Writer(os.path.join(d_near, "smear.webm"), alpha=True, crf=14)
        mattes = fxlib.alpha(project, A, B)
    maxspeed = 0
    for n in range(n0, n1):
        t = n / FPS
        if not DOM:
            cf = np.zeros((H, W, 4), np.float32)
            cn = np.zeros((H, W, 4), np.float32)
            got = next(mattes, None)
            al = got[1] if got else np.zeros((H, W), np.uint8)
        for gi in range(NN):
            X, Y, sc, op, layer = pose(gi, t)
            X1, Y1 = pose(gi, t + 1 / FPS / 4)[:2]
            X0, Y0 = pose(gi, t - 1 / FPS / 4)[:2]
            speed = math.hypot(X1 - X0, Y1 - Y0) * 2                 # px per frame
            maxspeed = max(maxspeed, speed)
            if DOM:
                row = [n, round(X, 1), round(Y, 1), round(sc, 3), round(op, 2)]
                if prev_layer.get(gi) != layer:
                    if prev_layer.get(gi) is not None:
                        (far_rows if layer == "n" else near_rows)[gi].append([n, 0, 0, 0, 0])
                    prev_layer[gi] = layer
                (near_rows if layer == "n" else far_rows)[gi].append(row)
                continue
            if op <= 0 and pose(gi, t + 0.25 / FPS)[3] <= 0 and pose(gi, t - 0.25 / FPS)[3] <= 0:
                continue
            shutter = SHUTTER[0] + (SHUTTER[1] - SHUTTER[0]) * smoothstep(SHUTTER[2], SHUTTER[3], speed)
            span = shutter / 360.0 / FPS
            N = int(min(48, max(1, math.ceil(speed * shutter / 360.0 / 0.8))))
            spr, c = sprite(gi, lit_at(gi, t))
            for j in range(N):
                tj = t + ((j + 0.5) / N - 0.5) * span
                xj, yj, sj, oj, lj = pose(gi, tj)
                if oj > 0:
                    stamp(cn if lj == "n" else cf, spr, c, xj, yj, sj, oj / N)
        if DOM:
            continue

        def straight(pm, shadow=None):
            a_ = np.clip(pm[:, :, 3], 0, 1)
            al_ = a_ if shadow is None else a_ + shadow * (1 - a_)
            out = np.zeros((H, W, 4), np.uint8)
            with np.errstate(divide="ignore", invalid="ignore"):
                rgb = np.where(al_[:, :, None] > 1e-4, pm[:, :, :3] / al_[:, :, None], 0)
            out[:, :, :3] = np.clip(rgb * 255 + 0.5, 0, 255)
            out[:, :, 3] = np.clip(al_ * 255 + 0.5, 0, 255)
            return out
        wf.write(straight(cf))
        M = np.float32([[1, 0, SHADOW[0]], [0, 1, SHADOW[1]]])
        sh = cv2.GaussianBlur(cv2.warpAffine(np.clip(cn[:, :, 3], 0, 1), M, (W, H)), (0, 0), SHADOW[2]) * SHADOW[3] * (al.astype(np.float32) / 255.0)
        wn.write(straight(cn, sh))
    print("max speed", round(maxspeed), "px/frame")
    if not DOM:
        wf.close()
        wn.close()

    def letter_divs():
        return "\n".join(f'<div data-layout-allow-overlap class="{{{{ID}}}}-l" id="{{{{ID}}}}-l{gi}">{ch}</div>' for gi, (i, ch, sp) in enumerate(glyphs))

    def style(shadow):
        return ("<style>\n#{{ID}} .{{ID}}-l { position:absolute; left:0; top:0; font-family:var(--font-display); "
                f"font-weight:var(--display-weight); font-style:var(--display-style); font-size:{font_near:.0f}px; line-height:1; "
                f"color:var(--c-light); white-space:nowrap;{shadow} }}\n</style>")

    def js(rows_):
        colour = [[[gi for gi, (ii, ch, sp) in enumerate(glyphs) if a <= ii < a + n], t0, t1] for a, n, t0, t1 in lights]
        data = {str(g): sum((r for r in rows_[g]), []) for g in rows_ if rows_[g]}
        return "\n".join([
            "// generated by orbit-ring/gen.py. Per letter, per frame: video frame, x, y, scale, opacity. Billboarded, on a real tilted circle locked to the face track.",
            "var L = " + json.dumps(data, separators=(",", ":")) + ";",
            "var LIT = " + json.dumps(colour, separators=(",", ":")) + ";   // [letters, lights in the accent, back to light]",
            "function tok(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }",
            "var C = { light: tok('--c-light'), accent: tok('--c-accent') };",
            "gsap.set('#{{ID}} .{{ID}}-l', { xPercent: -50, yPercent: -50, opacity: 0 });",
            "Object.keys(L).forEach(function (g) {",
            "  var s = '#{{ID}}-l' + g, r = L[g];",
            "  for (var k = 0; k < r.length; k += 5) tl.set(s, { x: r[k + 1], y: r[k + 2], scale: r[k + 3], opacity: r[k + 4] }, q(r[k] / 30));",
            "});",
            "LIT.forEach(function (w) {",
            "  w[0].forEach(function (g) {",
            "    tl.set('#{{ID}}-l' + g, { color: C.accent }, q(w[1]));",
            "    if (w[2] < B) tl.set('#{{ID}}-l' + g, { color: C.light }, q(w[2]));",
            "  });",
            "});"])

    vid = "position:absolute;left:0;top:0;width:1080px;height:1920px;"
    if DOM:
        open(os.path.join(d_far, "fx.html"), "w", encoding="utf-8").write(f"<!-- orbit-ring: the far half, behind the speaker. Written by gen.py. -->\n{letter_divs()}\n{style('')}\n")
        open(os.path.join(d_far, "fx.js"), "w", encoding="utf-8").write(js(far_rows) + "\n")
        open(os.path.join(d_near, "fx.html"), "w", encoding="utf-8").write(f"<!-- orbit-ring: the near half, over the speaker. Written by ../{fid}/gen.py. -->\n{letter_divs()}\n{style(' text-shadow:0 12px 16px rgba(0,0,0,.38);')}\n")
        open(os.path.join(d_near, "fx.js"), "w", encoding="utf-8").write(js(near_rows) + "\n")
    else:
        open(os.path.join(d_far, "fx.html"), "w", encoding="utf-8").write(
            f"<!-- orbit-ring: the far half of the ring, behind the speaker. smear.webm from gen.py. -->\n"
            f"{fxlib.tag('{{ID}}-mb', 'fx/{{ID}}/smear.webm', A, B, '', '{{T0}}', vid)}\n")
        open(os.path.join(d_far, "fx.js"), "w", encoding="utf-8").write("// orbit-ring: everything is in smear.webm (gen.py: per-letter poses, motion blur per letter).\n")
        open(os.path.join(d_near, "fx.html"), "w", encoding="utf-8").write(
            f"<!-- orbit-ring: the near half of the ring, over the speaker. smear.webm from ../{fid}/gen.py. -->\n"
            f"{fxlib.tag('{{ID}}-mb', 'fx/{{ID}}/smear.webm', A, B, '', '{{T0}}', vid)}\n")
        open(os.path.join(d_near, "fx.js"), "w", encoding="utf-8").write(f"// orbit-ring: everything is in smear.webm (../{fid}/gen.py).\n")
        print("webm", os.path.getsize(os.path.join(d_far, "smear.webm")), os.path.getsize(os.path.join(d_near, "smear.webm")))
    # the sound: a whoosh in, a low pass per item, a tick on every word that lights, the whip and the snap shut
    sfx = [(IN + 0.19, "whoosh-soft", -17, "letters spiral in")] + [(t, "whoosh-deep", -18, "an item passes the front") for _, t in keys]
    sfx += [(t0, "tick", -12, "a word lights") for a, n, t0, t1 in lights]
    sfx += [(SHUT + 0.29, "whoosh", -15, "the whip"), (GONE, "pop", -19, "the ring snaps shut behind the head")]
    print("SFX (time, name, dB, what):", [(round(t, 3), n, db, x) for t, n, db, x in sorted(sfx)])
    print("captions: hide them over the window if they repeat the ring's words (KARAOKE hide)")


if __name__ == "__main__":
    main()
