#!/usr/bin/env python3
"""impact-frame: the anime impact frame, cut from the live shot. On the word the picture turns to pure ink: two frames
negative, two positive, two negative, each with fresh hand-ruled focus lines exploding off the speaker's face, then the
positive holds with the word stamped over it, then a hard cut back to live. Every frame is the real frame of the
video, so the mouth stays on the words. Paper and ink are the pack's light and dark, the word is the display face.

Run: PY fx/<id>/gen.py <project> [<id>] [--sheet]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, public/clean.mp4, public/subject.webm,
          work/tracks/track.json (pipeline/track.py), public/plates/mic_<FRAME>.webm when there is one, assets/voice.wav,
          the style pack (style/style.json and its fonts)
  writes  <project>/fx/<id>/ink.mp4, fx.html, fx.js
          --sheet: no clip, every frame as a still plus sheet.jpg in <project>/work/<id>/
<id> defaults to this folder's name. Rerun it whenever the window, the cut or the word changes.
"""
import argparse
import os
import re
import sys
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.dont_write_bytecode = True       # nothing but the effect in an fx folder: everything in it gets published
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inkscreen as ink  # noqa: E402

FPS, W, H = 30, 1080, 1920

# ---- the table: everything that belongs to one video. Times come from the FX entry and words.json.
WORD = None                 # the word stamped; None = the spoken word the window starts on (words.json)
UPPER = True                # set it in caps
SECOND_ON = None            # optional: a spoken word inside the window that takes a second hit (fresh lines, a flip, a shove)
STAMP_AT = 6                # frame of the sequence (0 = the first ink frame) the word slams on
STAMP_SCALE = {0: 1.30, 1: 1.07}     # the word's scale on its first frames after it slams, then 1
NEG = {0, 1, 4, 5}          # negative frames of the first hit
WORD_W = 960                # px: the word is fitted to this width...
WORD_SIZE = 288             # ...but never set bigger than this (px, the display face)
WORD_Y = None               # px, the word's cap-height centre; None = the first place under the chin where the speaker covers the whole word
BELOW_CHIN = 0.49           # ...else this many face heights under the chin, else above the head when that doesn't fit
PUNCH = None                # scale about the face; None = push in until the face is FACE_W wide (never out, at most PUNCH_MAX). 1 = off
FACE_W = 470                # px: the face width the ink reads best at, a close shot
PUNCH_MAX = 1.8
CHIN_Y = 1010               # px: where the push puts the chin, as far as the frame allows
FG_BELOW = None             # px: below this y everything is the speaker, solid; None = measured on the matte (the first row under the chin they fill edge to edge), off when they never do
FILL_ROW = 0.92             # ...the share of a row that counts as edge to edge
BODY_BLACK = None           # the clothes go solid below this level (0..1 of the red-sensitive grey); None = measured so BODY_SOLID of them goes black
BODY_SOLID = 0.80
SEED = 4


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


def voice_onset(project, t):
    """where the voice really starts the word whisper puts at t (whisper is often a frame or two out): the steepest rise
    of the voice's 20 ms envelope within 0.12 s of t, read on a fixed grid so the answer doesn't move with the window"""
    p = os.path.join(project, "assets", "voice.wav")
    if not os.path.exists(p):
        return None
    with wave.open(p) as f:
        sr, ch, sw = f.getframerate(), f.getnchannels(), f.getsampwidth()
        hop = sr // 1000
        a0 = max(0, int(round((t - 0.25) * 1000)) * hop)
        f.setpos(min(a0, f.getnframes()))
        raw = f.readframes(int(0.5 * sr))
    if sw != 2 or not raw:
        return None
    x = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, ch).mean(1) / 32768
    env = np.sqrt(np.convolve(x * x, np.ones(hop * 20) / (hop * 20), mode="same"))[::hop]
    d = np.diff(env)
    lo, hi = 130, min(len(d), 370)            # t - 0.12 .. t + 0.12, in ms from a0
    if hi <= lo:
        return None
    return (a0 + (lo + int(np.argmax(d[lo:hi]))) * hop) / sr


# ---- the drawing
def mic_alpha(project, A):
    """the mic layer (pipeline/plate_finish.py) when the shot has one: it inks with the speaker. Empty without"""
    import fxlib
    p = os.path.join(project, "public", "plates", f"mic_{fxlib.crop_at(project, A)}.webm")
    if not os.path.exists(p):
        return np.zeros((H, W), np.float32)
    for _, c in fxlib.rgba(project, 0, 1 / FPS, src=os.path.relpath(p, project)):
        return c[:, :, 3].astype(np.float32) / 255
    return np.zeros((H, W), np.float32)


def bilateral2(g):
    g8 = np.clip(g * 255, 0, 255).astype(np.uint8)
    b = cv2.bilateralFilter(g8, 11, 24, 7)
    b = cv2.bilateralFilter(b, 11, 24, 7)
    return b.astype(np.float32) / 255


def head_mask(face, h, w):
    """where the fine line work goes: a soft ellipse round the head. The tracker's top is the forehead, so the hair
    (or a hat) is added above it"""
    fh = face["chin"] - face["top"]
    top, bottom = face["top"] - fh * .50, face["chin"] + fh * .05
    m = np.zeros((h, w), np.uint8)
    cv2.ellipse(m, (int(face["cx"]), int((top + bottom) / 2)), (int(face["w"] * .70), int((bottom - top) / 2)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), 16).astype(np.float32) / 255


def contour(fg, seed, lo=2.0, hi=7.0):
    """the silhouette in brush: an ink line just inside the matte, swelling and thinning along its length. Without it a
    light shirt on a light page has no edge"""
    m = (fg > .5).astype(np.uint8)
    d = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    rng = np.random.default_rng(seed)
    n = cv2.resize(rng.standard_normal((48, 27)).astype(np.float32), (m.shape[1], m.shape[0]), interpolation=cv2.INTER_CUBIC)
    n = (n - n.min()) / (n.max() - n.min())
    return (d > 0) & (d < lo + (hi - lo) * n)


def soft_grey(rgb):
    return cv2.GaussianBlur(bilateral2(ink.pan_gray(rgb, .40, .45, .15)), (0, 0), 8.0)


def ink_of(rgb, fg, face, body_black, seed=1):
    """the frame as flat ink, True = black. The head gets fine line work. Everything else is simplified first, because
    knit or print at this scale is only noise: it becomes a black mass with a few big shapes. The room goes: this is a
    drawing."""
    h, w = fg.shape
    g = ink.pan_gray(rgb, .40, .45, .15)
    b = bilateral2(g)
    tx, ty = ink.flow(b, 5)
    fine = ink.xdog(b, sigma=1.55, k=1.6, p=22, tx=tx, ty=ty)
    base = cv2.GaussianBlur(b, (0, 0), 2.0)
    head = ink.clean((fine < base * .93 - .012) | (base < .17), 110)
    soft = cv2.GaussianBlur(b, (0, 0), 8.0)
    txb, tyb = ink.flow(soft, 9)
    coarse = ink.xdog(soft, sigma=3.4, k=1.6, p=26, tx=txb, ty=tyb)
    body = ink.clean((coarse < soft * .92 - .01) | (soft < body_black), 300)
    body = ~ink.clean(~body, 7000)                       # no stray white crumbs in the black: only big shapes survive (a hand, the collar)
    t = head_mask(face, h, w)
    m = (head.astype(np.float32) * t + body.astype(np.float32) * (1 - t)) > .5
    m = ink.round_off(m, .8)
    fgm = fg > .5
    return (m & fgm) | contour(fg, seed), fgm


def focus_lines(seed, cx, cy, rx, ry, h, w, ss=2, density=1.0, thin=1.0):
    """focus lines, ruled the way a manga page rules them: a thick end off the page, a long taper to a point that stops
    short of the face, spaced in bursts, plus a dense pass of short strokes round the frame edge. Float mask, output size"""
    rng = np.random.default_rng(seed)
    S = np.zeros((h * ss, w * ss), np.uint8)
    far = 1.15 * np.hypot(max(cx, w - cx), max(cy, h - cy))

    def stroke(th, r0, r1, wd):
        # r0 inner tip (a factor on the face ellipse), r1 outer end in px, wd width at the outer end; width grows as a power of the distance from the tip
        c, s = np.cos(th), np.sin(th)
        base = np.hypot(rx * c, ry * s) * r0
        rs = np.linspace(0, 1, 9)
        radii = base + (r1 - base) * rs
        widths = wd * rs ** 1.5 * .5
        nx, ny = -s, c
        left = [((cx + c * r + nx * wi) * ss, (cy + s * r + ny * wi) * ss) for r, wi in zip(radii, widths)]
        right = [((cx + c * r - nx * wi) * ss, (cy + s * r - ny * wi) * ss) for r, wi in zip(radii, widths)]
        cv2.fillPoly(S, [np.array(left + right[::-1], np.int32)], 255, cv2.LINE_AA)

    th = rng.uniform(0, 2 * np.pi)                       # long strokes in bursts: uneven, like a hand with a ruler
    while th < 2 * np.pi * 2:
        for _ in range(rng.integers(2, 7)):
            kind = rng.random()
            wd = rng.uniform(1.6, 5) if kind < .62 else rng.uniform(6, 15) if kind < .92 else rng.uniform(18, 40)
            stroke(th, rng.uniform(1.06, 1.75), far, wd * thin)
            th += rng.uniform(.006, .022) / density
        th += rng.uniform(.03, .10) / density
    for _ in range(int(150 * density)):                  # short strokes round the edge: the density that makes the centre white hot
        stroke(rng.uniform(0, 2 * np.pi), rng.uniform(2.4, 3.6), far, rng.uniform(2, 9) * thin)
    return cv2.resize(S, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def word_mask(word, fnt, y, scale=1.0):
    """the word in the display face at 2x, centred on x 540 with its cap-height centre on y"""
    im = Image.new("L", (W * 2, H * 2), 0)
    d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), word, font=fnt)
    d.text((W - (l + r) / 2, y * 2 - (t + b) / 2), word, font=fnt, fill=255)
    a = np.asarray(im, np.float32) / 255
    if scale != 1.0:
        M = cv2.getRotationMatrix2D((W, y * 2), 0, scale)
        a = cv2.warpAffine(a, M, (W * 2, H * 2), flags=cv2.INTER_LINEAR)
    return cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA)


def fit_word(project, word):
    """the display face sized so the word is WORD_W wide, never above WORD_SIZE: (font at 2x, size, cap height)"""
    import fxlib
    size = WORD_SIZE
    for _ in range(3):
        f = fxlib.font(project, "display", size * 2)
        l, t, r, b = ImageDraw.Draw(Image.new("L", (8, 8))).textbbox((0, 0), word, font=f)
        size = min(WORD_SIZE, max(40, int(size * WORD_W * 2 / max(1, r - l))))
    f = fxlib.font(project, "display", size * 2)
    l, t, r, b = ImageDraw.Draw(Image.new("L", (8, 8))).textbbox((0, 0), word, font=f)
    return f, size, (b - t) / 4                         # half the cap height, at 1x


def shake(k, hits, rng):
    """the camera takes the hit: a shove and a little scale on each strobe frame, decaying through the hold; the word
    slamming hits it again, and so does a second hit"""
    first = {0: 26, 1: 20, 2: 16, 3: 12, 4: 14, 5: 10}.get(k, 0)
    s = k - STAMP_AT
    slam = {0: 20, 1: 11, 2: 5, 3: 2}.get(s, 0)
    again = max([{0: 24, 1: 14, 2: 8, 3: 4, 4: 1}.get(k - h, 0) for h in hits[1:]] + [0])
    amp = max(first, slam, again)
    dx, dy = rng.uniform(-1, 1) * amp, rng.uniform(-1, 1) * amp
    return dx, dy, max(1.0 + .07 * .72 ** k, 1.0 + amp / 470)      # always enough scale that a shove never shows an edge


def frame(k, rgb, fg, face, rng, G):
    """one ink frame. G: everything measured once for the window (word, its mask, body level, hits)"""
    h, w = H, W
    if G["fg_below"] is not None:
        fg = fg.copy()
        fg[G["fg_below"]:] = 1                            # they fill the bottom of the frame: the matte has holes there
    m, fgm = ink_of(rgb, fg, face, G["body_black"], seed=SEED + k // 2)
    if G["fg_below"] is not None:
        m[G["fg_below"]:] = True                          # solid down there: hands under the word would only fight it
    if k >= STAMP_AT:
        m[G["box"] & fgm] = True                          # and the speaker is solid black behind the word: it reads clean
    cx, cy = face["cx"], face["cy"]
    rx, ry = face["w"] * .62, face["h"] * .70
    im = m.astype(np.float32)
    hits = G["hits"]
    last = max(x for x in hits if x <= k)
    hold = k >= STAMP_AT
    since = k - (STAMP_AT if last == 0 else last)
    decay = 1.0 if not hold else max(.0, 1 - since / 8)
    L = focus_lines(SEED + k // 2 * 7, cx, cy, rx, ry, h, w, density=.75 if hold else 1.0, thin=.4 + .6 * decay if hold else 1.0)
    # the lines stay off the head. On the strobes everything else takes them and flips, the way a white pen crosses a
    # black shirt; on the hold they are only on the page behind, and on the black under the word
    hd = np.zeros((h, w), np.uint8)
    cv2.ellipse(hd, (int(cx), int(cy - face["h"] * .12)), (int(face["w"] * .62), int(face["h"] * .80)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    L = L * (1 - cv2.GaussianBlur(hd, (0, 0), 6).astype(np.float32) / 255)
    if hold:
        keep = (~fgm).astype(np.float32)
        below = np.clip((np.arange(h, dtype=np.float32)[:, None] - (G["word_y"] + G["cap"] + 16)) / 3, 0, 1)
        L = L * np.maximum(keep, below) * (1 - G["word_box"])
    im = im * (1 - L) + (1 - im) * L
    if hold and G["word"]:
        scale = STAMP_SCALE.get(k - STAMP_AT, 1.0)
        for hh in hits[1:]:
            if k == hh:
                scale = max(scale, 1.07)
        Wm = word_mask(G["word"], G["font"], G["word_y"], scale)
        # every letter solid, in the tone opposite to what is mostly round it: paper out of the black (the usual
        # case), ink where a letter reaches the page past the speaker
        n_, lab = cv2.connectedComponents((Wm > .5).astype(np.uint8))
        dark = cv2.GaussianBlur(im, (0, 0), 14)
        tone = np.zeros(max(n_, 1), np.float32)
        for c in range(1, n_):
            tone[c] = 0.0 if dark[lab == c].mean() > .5 else 1.0
        lab = cv2.dilate(lab.astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.int32)   # the antialiased rim takes its letter's tone
        im = im * (1 - Wm) + tone[lab] * Wm
    neg = (k in NEG) or any(k - hh in (0, 1) for hh in hits[1:])
    if neg:
        im = 1 - im
    dx, dy, s = shake(k, hits, rng)
    M = cv2.getRotationMatrix2D((cx, cy), 0, s)
    M[0, 2] += dx
    M[1, 2] += dy
    im = cv2.warpAffine(im, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    a = im[..., None]
    return np.clip(ink.for_renderer(G["paper"] * (1 - a) + G["ink"] * a), 0, 255).astype(np.uint8)


# ---- the window, measured once
def faces(tr, n0, n1):
    """track.json faces for frames n0..n1, a missing frame filled from the nearest one that has a face"""
    got = {n: tr[n]["face"] for n in range(n0, n1) if n < len(tr) and tr[n].get("face")}
    if not got:
        sys.exit("no face in work/tracks/track.json inside this window: run pipeline/track.py, or pick a line where the face shows")
    return [got[min(got, key=lambda m: abs(m - n))] for n in range(n0, n1)]


def punch(fcs):
    """the push-in: (S, tx, ty) taking frame px to output px, from the median face"""
    cx = float(np.median([f["cx"] for f in fcs]))
    chin = float(np.median([f["chin"] for f in fcs]))
    fw = float(np.median([f["w"] for f in fcs]))
    S = float(PUNCH) if PUNCH else float(np.clip(FACE_W / max(fw, 1), 1.0, PUNCH_MAX))
    tx = float(np.clip(W / 2 - S * cx, W - W * S, 0))
    ty = float(np.clip(CHIN_Y - S * chin, H - H * S, 0))
    return S, tx, ty


def moved(face, S, tx, ty):
    f = dict(face)
    for k in ("cx", "top", "chin", "cy"):
        f[k] = face[k] * S + (tx if k == "cx" else ty)
    f["w"], f["h"] = face["w"] * S, face["h"] * S
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--sheet", action="store_true", help="stills and a contact sheet in work/<id>/, no clip")
    args = ap.parse_args()
    kit_pipeline()
    import fxlib
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    n0, n1 = round(A * FPS), round(B * FPS)
    if n1 - n0 < STAMP_AT + 3:
        sys.exit(f"the window is {n1 - n0} frames: the strobes take {STAMP_AT} and the word needs a few more to read (14 is the shipped length)")
    words = fxlib.words(project)
    word = WORD
    if word is None:
        on = [w for w in words if A - 0.12 <= w[0] < B]
        if not on:
            sys.exit("no spoken word in the window: set WORD at the top of gen.py")
        word = re.sub(r"[^\w'%$-]", "", on[0][2])
    word = word.upper() if UPPER else word
    hits = [0]
    if SECOND_ON:
        t2 = spoken(words, SECOND_ON, A + 0.1, B)
        if t2 is None:
            print(f"warning: SECOND_ON {SECOND_ON!r} is not spoken inside the window: one hit")
        else:
            hits.append(round(t2 * FPS) - n0)
    S_ = fxlib.pack(project)
    paper = np.array(S_["colors"]["light"][:3], np.float32)
    inkc = np.array(S_["colors"]["dark"][:3], np.float32)
    tr = fxlib.tracks(project)["frames"]
    fcs = faces(tr, n0, n1)
    S, tx, ty = punch(fcs)
    M = np.float32([[S, 0, tx], [0, S, ty]])
    fcs = [moved(f, S, tx, ty) for f in fcs]
    micA = mic_alpha(project, A)

    def warp(a, interp=cv2.INTER_LINEAR):
        return a if S == 1.0 and tx == 0 and ty == 0 else cv2.warpAffine(a, M, (W, H), flags=interp, borderMode=cv2.BORDER_REPLICATE)

    micW = warp(micA)
    rgbs = [warp(rgb, cv2.INTER_CUBIC) for _, rgb in fxlib.frames(project, A, B)]
    fgs = [np.maximum(warp(al.astype(np.float32) / 255), micW) for _, al in fxlib.alpha(project, A, B)]
    k_n = min(len(rgbs), len(fgs), n1 - n0)
    if k_n < n1 - n0:
        print(f"warning: only {k_n} of {n1 - n0} frames read")
    # where they fill the frame edge to edge, the body level, the word's place: all off the footage
    chin = float(np.median([f["chin"] for f in fcs]))
    fh = float(np.median([f["chin"] - f["top"] for f in fcs]))
    mean_fg = np.mean(fgs[:k_n], axis=0)
    fg_below = FG_BELOW
    if fg_below is None:
        rows = np.where((np.arange(H) > chin + .2 * fh) & ((mean_fg > .5).mean(1) >= FILL_ROW))[0]
        fg_below = int(rows[0]) if len(rows) else None
    body = (mean_fg > .5) & (np.arange(H)[:, None] > chin + .15 * fh)
    body_black = BODY_BLACK
    if body_black is None:
        g = soft_grey(rgbs[0])
        body_black = float(np.clip(np.quantile(g[body], BODY_SOLID) + .03, .2, .95)) if body.sum() > 5000 else .58
    font, size, cap = fit_word(project, word)
    word_y = WORD_Y
    if word_y is None:
        # on the chest: the first place under the chin where the speaker covers the word's whole box, so it stamps
        # out of solid black; else a fixed drop under the chin; else (a big selfie) above the head
        wm0 = word_mask(word, font, H / 2)
        xs = np.where(wm0.max(0) > .05)[0]
        x0, x1 = (int(xs.min()), int(xs.max())) if len(xs) else (60, W - 60)
        cover = (mean_fg[:, x0:x1 + 1] > .5).mean(1)
        word_y = None
        for y in range(int(chin + cap + 40), int(H - cap - 60), 4):
            if cover[int(y - cap):int(y + cap)].min() >= .9:
                word_y = float(y)
                break
        if word_y is None:
            word_y = chin + BELOW_CHIN * fh
            if word_y + cap + 60 > H:
                word_y = max(cap + 120, min(f["top"] for f in fcs) - .55 * fh - cap - 30)
    box = np.zeros((H, W), np.uint8)
    wm = word_mask(word, font, word_y)
    if wm.max() > 0:
        ys, xs = np.where(wm > .05)
        cv2.rectangle(box, (int(xs.min()) - 22, int(ys.min()) - 22), (int(xs.max()) + 22, int(ys.max()) + 22), 255, -1)
    G = dict(word=word, font=font, word_y=word_y, cap=cap, box=box > 0, word_box=cv2.GaussianBlur(box, (0, 0), 6).astype(np.float32) / 255,
             body_black=body_black, fg_below=fg_below, hits=hits, paper=paper, ink=inkc)
    print(f"{fid}: {word!r} at {size}px, y {word_y:.0f}; push {S:.2f}x; body solid below {body_black:.2f}"
          + (f", the speaker fills the frame from y {fg_below}" if fg_below is not None else ", never edge to edge")
          + (f"; second hit on frame {hits[1]}" if len(hits) > 1 else ""))
    t_word = spoken(words, word, A - 0.15, B)              # whisper's start for the stamped word, if it is spoken here
    on = voice_onset(project, t_word) if t_word is not None else None
    if on is not None and round(on * FPS) != n0:
        print(f"the voice starts {word!r} at {on:.3f}, the window at {n0 / FPS:.3f}: move the FX entry's at to {round(on * FPS) / FPS:.4f} for the hit to land on it")
    rng = np.random.default_rng(SEED)
    work = os.path.join(project, "work", fid)
    os.makedirs(work, exist_ok=True)
    d = out_dir(project, fid)
    w = None if args.sheet else fxlib.Writer(os.path.join(d, "ink.mp4"), crf=14)
    out = []
    for k in range(k_n):
        f = frame(k, rgbs[k], fgs[k], fcs[k], rng, G)
        out.append(f)
        if w:
            w.write(f)
        else:
            cv2.imwrite(os.path.join(work, f"f{k:02d}.png"), cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
    if w:
        w.close()
        vid = fxlib.tag("{{ID}}-clip", "fx/{{ID}}/ink.mp4", A, B, track="{{T0}}", style="position:absolute;left:0;top:0;width:1080px;height:1920px;")
        open(os.path.join(d, "fx.html"), "w", encoding="utf-8").write(
            f"<!-- impact-frame: written by gen.py. A full-frame ink pre-render: frame n of the clip is frame n of the video. -->\n{vid}\n")
        open(os.path.join(d, "fx.js"), "w", encoding="utf-8").write(
            "// impact-frame: everything is in the pre-rendered clip (gen.py). Hard in, hard out. Nothing to tween.\n")
    cols, tw, th = 7, 300, 533
    sheet = np.zeros((th * ((len(out) + cols - 1) // cols), tw * cols, 3), np.uint8)
    for k, f in enumerate(out):
        sheet[(k // cols) * th:(k // cols + 1) * th, (k % cols) * tw:(k % cols + 1) * tw] = cv2.resize(f, (tw, th), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(work, "sheet.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(os.path.join(work, "sheet.jpg"))
    a = n0 / FPS
    sfx = [(a, "impact-low", -12, "the hit"), (a + 2 / FPS, "tick", -12, "flip"), (a + 4 / FPS, "tick", -12, "flip"),
           (a + STAMP_AT / FPS, "stamp", -11, "the word slams")] + [(a + hh / FPS, "impact-low", -13, "second hit") for hh in hits[1:]]
    print("SFX (time, name, dB, what):", [(round(t, 3), n, db, x) for t, n, db, x in sfx])
    print(f'KARAOKE hide: ({A:.2f}, <the next line\'s start>), so that line starts under the print and shows on the cut back')


if __name__ == "__main__":
    main()
