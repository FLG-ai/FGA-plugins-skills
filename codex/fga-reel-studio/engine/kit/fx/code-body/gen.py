#!/usr/bin/env python3
"""code-body: the speaker turns into their own source code. A hairline scans top to bottom on a word: above it every
cell of a monospaced grid is a character of the real text that edited this video, in reading order (edit.py, every
effect's fx.js and generator, the kit's pipeline), so a paused frame reads. Each cell's colour and glyph weight come
from the live frame under it: skin and face in the pack's light, highlights in the accent, the clothes in their own
colour family, the room as sparse dim type on the pack's dark ground. The text climbs a row every few frames, the
face stays put. Cells step down on the words until the face resolves, then the line runs back up. Every frame is
built from the same frame of the video, so the lips stay in sync by construction.

Run: PY fx/<id>/gen.py <project> [<id>] [--still n,n,n]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, public/clean.mp4, public/subject.webm,
          work/tracks/track.json (pipeline/track.py), public/plates/mic_<FRAME>.webm when there is one, every
          fx/*/gen.py and fx.js in the project, the kit's pipeline files, the style pack (mono face, colours)
  writes  <project>/fx/<id>/code.mp4, fx.html, fx.js
          --still: those frames as stills in <project>/work/<id>/ (s_<n>.png the code, t_<n>.png its target)
<id> defaults to this folder's name. Run it last, after every other effect exists, so the code on screen is final.
"""
import argparse
import glob
import os
import re
import sys
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920

# ---- the table: everything that belongs to one video. The window comes from the FX entry, times from words.json.
SCAN_ON = None              # the spoken word the line runs down on; None = the window's first word
SCAN = 0.32                 # s the line takes top to bottom
STEPS_ON = None             # the spoken words the cells step down on (one per size after the first); None = words near STEP_FROM..STEP_TO
STEP_FROM, STEP_TO = 0.39, 0.65   # ...of the way from the scan's end to the line going back up
CELLS = (28, 20, 14, 10)    # cell width px: the scan sets the first, each step the next; the last is where the face resolves
UP_ON = None                # the spoken word the line runs back up on; None = UP_BEFORE s before the window ends
UP_BEFORE = 0.50
UP = 0.45                   # s the line takes back up
ASPECT = 1.72               # cell height / width: tight leading, more picture
ROW_EVERY = {28: 6, 20: 5, 14: 4, 10: 3}     # the text climbs a whole row every this many frames, per cell size
HEAD = 700                  # chars of each generator (its docstring and table) that come first on screen
CLOTHES = None              # the clothes' colour family: None = their own colour, measured on the take; or a pack role ("accent", "s2")
ROOM_Y = None               # the room's level (0..1 luma) where its type starts; None = measured, the room's median less 0.02
WEIGHTS = 7                 # glyph weights from hairline to heavy (the pack's mono files, thinned below the lightest)
LOOK = dict(
    KSCALE={28: 1.25, 20: 1.2, 14: 1.15, 10: 1.1},   # how far the type stands off its cell: more as the cells grow, so big cells read as words
    DARK={28: 0.25, 20: 0.25, 14: 0.0, 10: 0.0},     # big cells lean towards the darkest part of what they cover, so eyes and mouth survive
    INVERT={28: 0.84, 20: 0.84, 14: 0.84, 10: 0.84},  # above the forehead, cells this bright flip to dark type on a light cell
    ROOM_KEEP=0.42,                                  # how many words of the dark room are drawn at all
    GAMMA={28: 0.9, 20: 0.8, 14: 0.7, 10: 0.62},     # the face's key: below 1 lifts the midtones. Big cells need the contrast to read as a face
    LOCAL={28: 1.6, 20: 1.5, 14: 1.3, 10: 1.1},      # local contrast of the face's key
    DETAIL={28: 0.7, 20: 0.8, 14: 0.9, 10: 1.0},     # how much a glyph's strokes sample the frame under them
    BG_DETAIL={28: 0.4, 20: 0.4, 14: 0.45, 10: 0.8},  # how much of the frame shows in the cell behind the type
    BG_MAX={28: 150.0, 20: 158.0, 14: 168.0, 10: 178.0},   # how bright a cell itself may get: past this the picture has to come from the type
)
C = SimpleNamespace()       # filled in main(): the window, the colours, the track


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


def fr(t):
    return round(t * FPS)


# ---- the text
def source_text(project, pipeline):
    """the real text in reading order: this video's edit.py, the head of every generator, then the generators whole,
    every fx.js and the kit's pipeline that ran them"""
    gens = sorted(glob.glob(os.path.join(project, "fx", "*", "gen.py")))
    txt = [open(os.path.join(project, "edit.py"), encoding="utf-8", errors="ignore").read()]
    txt += [open(f, encoding="utf-8", errors="ignore").read()[:HEAD] for f in gens]
    files = gens + sorted(glob.glob(os.path.join(project, "fx", "*", "fx.js")))
    files += [os.path.join(pipeline, f) for f in ("build.py", "cut.py", "words.py", "mix.py", "render.py", "qa.py")]
    for f in files:
        if os.path.exists(f):
            txt.append(open(f, encoding="utf-8", errors="ignore").read())
    s = " ".join(txt)
    s = s.replace(os.path.expanduser("~"), "~")            # no home folder (and user name) on screen
    s = re.sub(r"([\"'])(?:~|/)[^\"'\n]*/([^\"'/\n]*)\1", r"\1\2\1", s)     # nor anyone's folders: a quoted path shows its file name
    for a, b in ((chr(0x2014), "-"), (chr(0x2013), "-"), (chr(0x2192), "->"), (chr(0x2026), "..."), (chr(0x2018), "'"), (chr(0x2019), "'"), (chr(0x201c), '"'), (chr(0x201d), '"')):
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"((?:-?[\d.]+,\s*){6})(?:[-\d.\[\], ]*?,\s*){10,}", r"\1... ", s)     # long runs of generated numbers fold like an editor folds them: a paused frame reads as code
    return "".join(c for c in s if 32 <= ord(c) < 127)          # the atlas is printable ASCII


def mono_faces(pack):
    """the pack's mono face as [(path, weight)] from light to heavy: the files style.py downloaded for its family"""
    f = pack["fonts"]["mono"]
    if not f.get("path"):
        sys.exit(f"no font file for the pack's mono face ({f['family']}): run PY pipeline/style.py on the pack, or copy its fonts into <project>/style/fonts/")
    d = os.path.dirname(f["path"])
    fam = f["family"].replace(" ", "")
    style = "italic" if f.get("italic") else "normal"
    files = []
    for p in glob.glob(os.path.join(d, f"{fam}-{style}-*.ttf")) or glob.glob(os.path.join(d, f"{fam}-normal-*.ttf")):
        m = re.search(r"-(\d+)\.ttf$", p)
        if m:
            files.append((p, int(m.group(1))))
    return sorted(files, key=lambda x: x[1]) or [(f["path"], f.get("weight", 400))]


class Atlas:
    """one cell size: every printable ASCII glyph in WEIGHTS weights, antialiased from 4x. The pack's mono files give
    the regular to heavy end; below the lightest file the strokes are thinned (eroded at 4x) for the hairlines"""

    def __init__(self, cw, faces):
        self.cw, self.ch = cw, round(cw * ASPECT)
        size, S = cw / 0.6, 4
        # hairline, thin and light: the lightest file with its strokes eroded by these fractions of the em (a regular
        # stroke is about 0.08 em, so these land near weights 100, 200 and 300)
        light = [(faces[0][0], max(1, int(round(e * size * S)))) for e in (0.0275, 0.02, 0.01)]
        steps = light + [(p, 0) for p, _ in faces]
        pick = [steps[int(round(i * (len(steps) - 1) / (WEIGHTS - 1)))] for i in range(WEIGHTS)]
        self.a = np.zeros((WEIGHTS, 96, self.ch, self.cw), np.float32)
        for wi, (path, erode) in enumerate(pick):
            font = ImageFont.truetype(path, int(round(size * S)))
            # the em is fitted to the cell: a mono face 0.6 em wide fills it, a wider one is squeezed
            adv = font.getlength("0") / S
            sx = min(1.0, cw / max(1e-3, adv))
            kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode * 2 + 1, erode * 2 + 1)) if erode else None
            for k in range(96):
                c = chr(32 + k)
                if c == " ":
                    c = "·"          # whitespace shown as a mid dot, like an editor: every cell carries a mark
                im = Image.new("L", (int(self.cw * S / sx), self.ch * S), 0)
                d = ImageDraw.Draw(im)
                d.text((im.width / 2, int(self.ch * S * 0.79)), c, font=font, fill=255, anchor="ms")    # the em sits a little high so descenders stay inside
                g = np.asarray(im, np.uint8)
                if kern is not None:
                    g = cv2.erode(g, kern)
                g = cv2.resize(g, (self.cw, self.ch), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
                self.a[wi, k] = g
        self.cov = self.a.mean((2, 3))     # the ink of every glyph and weight

    def grid(self):
        cols = int(np.ceil(W / self.cw))
        rows = int(np.ceil(H / self.ch))
        return cols, rows, (cols * self.cw - W) // 2, (rows * self.ch - H) // 2


# ---- the picture every cell averages to
def st(x, a, b):
    u = np.clip((x - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


def ramp(t, stops):
    """piecewise linear colour ramp: t HxW, stops [(t, (r,g,b))...]"""
    xs = np.array([s[0] for s in stops], np.float32)
    cs = np.array([s[1] for s in stops], np.float32)
    return np.stack([np.interp(t, xs, cs[:, i]) for i in range(3)], -1).astype(np.float32)


def skin_model(samples):
    """the speaker's own skin, from their face: mean and inverse covariance of (Cr, Cb), so a neck or an arm is not
    taken for clothes whatever the shirt is"""
    px = []
    for rgb, f in samples:
        m = np.zeros((H, W), np.uint8)
        cv2.ellipse(m, (int(f["cx"]), int(f["cy"])), (int(f["w"] * .30), int(f["h"] * .30)), 0, 0, 360, 1, -1)
        ycc = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)[m > 0].astype(np.float32)
        if len(ycc):
            ycc = ycc[ycc[:, 0] > np.median(ycc[:, 0]) * .6]       # no beard, brows or nostrils in the model
            px.append(ycc[:, 1:])
    if not px:
        return None
    v = np.concatenate(px)
    cov = np.cov(v.T) + np.eye(2) * 4.0
    return v.mean(0), np.linalg.inv(cov)


def analyse(rgb, al, mic, entry):
    """-> f (0..1), Y, clothes (soft), person, room, skin: the speaker split into skin and face, clothes and the room"""
    f = rgb.astype(np.float32) / 255
    Y = 0.2126 * f[:, :, 0] + 0.7152 * f[:, :, 1] + 0.0722 * f[:, :, 2]
    a = al.astype(np.float32) / 255
    block = np.zeros((H, W), np.uint8)
    fc = entry["face"] if entry else None
    if fc:
        # the whole head with its hair (or a hat): an ellipse from above the forehead to the chin. Clothes are outside it
        fh = fc["chin"] - fc["top"]
        top = fc["top"] - 0.6 * fh
        cv2.ellipse(block, (int(fc["cx"]), int((top + fc["chin"]) / 2)), (int(fc["w"] * 0.80), int((fc["chin"] - top) / 2 * 1.05)), 0, 0, 360, 1, -1)
    hb = np.zeros((H, W), np.uint8)
    for hd in (entry or {}).get("hands", []):
        pts = np.array([hd["wrist"], hd["palm"], hd["thumb"], hd["index"], hd["middle"], hd["pinky"]], np.float32)
        cv2.fillConvexPoly(hb, cv2.convexHull(pts).astype(np.int32), 1)
    block = block | cv2.dilate(hb, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    skin = np.zeros((H, W), bool)
    if C.skin is not None:
        mu, inv = C.skin
        d = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)[:, :, 1:].astype(np.float32) - mu
        skin = (np.einsum("...i,ij,...j->...", d, inv, d) < 9.0) & (Y > .08)
    sw = (a > 0.4) & (block == 0) & ~skin
    sw = cv2.morphologyEx(sw.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    sw = cv2.morphologyEx(sw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    n, lab, stt, _ = cv2.connectedComponentsWithStats(sw)
    if n > 1:
        keep = np.zeros(n, bool)
        keep[1:] = stt[1:, cv2.CC_STAT_AREA] > 8000
        sw = keep[lab].astype(np.uint8)
    micm = mic.astype(np.float32) / 255
    sws = cv2.GaussianBlur(sw.astype(np.float32), (0, 0), 1.5) * (1 - micm)
    person = np.clip(np.maximum(a, micm) - sws, 0, 1)
    room = np.clip(1 - np.maximum(a, micm), 0, 1)
    return f, Y, sws, person, room, skin


def target(f, Y, sws, person, room, cw=10):
    """-> I (HxWx3, the stylised frame), T (tone 0..1), K (how far the type stands off the cell), Hue (the type's hue)"""
    R = f[:, :, 0]
    # a portrait key: a little red so skin lifts away from hair, local contrast so the features survive big cells. The
    # speaker's own range (measured on the take) maps onto the range the look was tuned on, so a brightly lit face
    # keeps its features instead of blowing out, and a dim one isn't murky
    K0 = 0.5 * Y + 0.5 * R
    K0 = np.clip(0.05 + (K0 - C.k_lo) / max(1e-3, C.k_hi - C.k_lo) * 0.62, 0, 1)
    blur = cv2.GaussianBlur(K0, (0, 0), 26)
    t0 = np.clip(K0 + LOOK["LOCAL"][cw] * (K0 - blur), 0, 1)
    th = np.clip((t0 - 0.05) / 0.62, 0, 1) ** LOOK["GAMMA"][cw]
    I_h = ramp(th, C.PERSON)
    # the accent only on what really shines: small bright spots and lines (eyes, a nose, a lip, a buckle), not a white
    # hat, a white shirt or the lit edge of a cheek (a top-hat keeps only what is narrower than about 15 px)
    fine = cv2.GaussianBlur(K0, (0, 0), 2)
    hat = fine - cv2.morphologyEx(fine, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    spec = np.clip((hat - 0.06) / 0.08, 0, 1) * np.clip((fine - 0.5) / 0.2, 0, 1)
    inside = cv2.erode((room < 0.5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))).astype(np.float32)
    spec = cv2.GaussianBlur(spec * inside, (0, 0), 1.5)[:, :, None]          # inside the speaker only: no rim where they meet the room
    I_h = I_h * (1 - spec) + C.ACCENT * spec
    # the clothes: their own range, driven by the brightest channel (a blue top's light is in its blue)
    Ys = cv2.GaussianBlur(f.max(axis=2), (0, 0), 1.2)
    ts = np.clip((Ys - C.cloth_lo) / (C.cloth_hi - C.cloth_lo), 0, 1) ** 0.9
    I_s = ramp(ts, C.CLOTH)
    # the room: lit things lift a little in the muted tone, lamps and windows go to the accent
    tr = np.clip((Y - C.room_y) / 0.6, 0, 1)
    I_r = C.FIELD[None, None] + (C.MUTED - C.FIELD)[None, None] * (tr[:, :, None] ** 1.1) * 0.42
    gold = np.clip((Y - C.room_y - 0.48) / 0.28, 0, 1)[:, :, None]
    I_r = I_r * (1 - gold) + C.ACCENT * 0.95 * gold
    h, s, r = person[:, :, None], sws[:, :, None], room[:, :, None]
    I = I_h * h + I_s * s + I_r * r
    T = th * person + ts * 0.82 * sws + tr * 0.5 * room
    # how far the type stands off its cell. In the dark features it stays dim, or the eyes and mouth fill up with bright letters
    K = 0.30 * person * (0.28 + 0.72 * st(th, 0.12, 0.62)) + 0.30 * sws * (0.5 + 0.5 * st(ts, 0.1, 0.6)) + 0.05 * room + 0.14 * room * tr
    Hue = C.HUE_H[None, None] * h + C.HUE_S[None, None] * s + C.HUE_R[None, None] * r
    return I, T, K.astype(np.float32), Hue.astype(np.float32)


def ease(u):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(u, 0, 1))


def line_y(n):
    """where the scan line is on frame n, or None: down on the scan word, up on the up word. -> y, direction"""
    a, b = fr(C.scan0), fr(C.scan1)
    if a <= n < b:
        return float(H * ease((n - a + 1) / (b - a))), 1
    a, b = fr(C.up0), fr(C.up1)
    if a <= n < b:
        return float(H * (1 - ease((n - a + 1) / (b - a)))), -1
    return None, 0


def cell_size(n):
    t = n / FPS
    cw = C.steps[0][1]
    for ts, c in C.steps:
        if t + 1e-4 >= fr(ts) / FPS:
            cw = c
    return cw


_starts = {}


def text_start(n, cw, cols, text):
    """first character on screen: climbs a row every few frames, carried across the cell-size changes so the reading
    order never breaks"""
    if not _starts:
        pos, held = 0, 0
        for m in range(fr(C.scan0), C.n1 + 1):
            c = cell_size(m)
            _starts[m] = pos
            held += 1
            if held >= ROW_EVERY.get(c, 4):
                pos += int(np.ceil(W / c))
                held = 0
    return _starts.get(n, 0)


_wid = {}


def word_id(text):
    if "w" not in _wid:
        _wid["w"] = np.cumsum(np.frombuffer(text.encode("ascii"), np.uint8) == 32).astype(np.int64)
    return _wid["w"]


def render(n, rgb, al, mic, atlases, text, raw=False):
    cw = cell_size(n)
    A = atlases[cw]
    ch = A.ch
    cols, rows, ox, oy = A.grid()
    entry = C.track[n] if n < len(C.track) else None
    face = C.face_at(n)
    f, Y, sws, person, room, skin = analyse(rgb, al, mic, dict(entry or {}, face=face))
    I, T, K, Hue = target(f, Y, sws, person, room, cw)
    if raw:
        return np.clip(I, 0, 255).astype(np.uint8)
    pad = lambda m: cv2.copyMakeBorder(m, oy, rows * ch - H - oy, ox, cols * cw - W - ox, cv2.BORDER_REPLICATE)  # noqa: E731
    I_p, T_p, K_p, Hue_p = pad(I), pad(T), pad(K), pad(Hue)
    T_c = cv2.resize(T_p, (cols, rows), interpolation=cv2.INTER_AREA)
    I_c = cv2.resize(I_p, (cols, rows), interpolation=cv2.INTER_AREA)
    dk = LOOK["DARK"].get(cw, 0.0)
    if dk > 0:
        kx, ky = max(3, cw // 2 | 1), max(3, ch // 2 | 1)
        Tm = cv2.erode(T_p, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky)))
        Im = cv2.erode(I_p, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky)))
        T_c = (1 - dk) * T_c + dk * cv2.resize(Tm, (cols, rows), interpolation=cv2.INTER_AREA)
        I_c = (1 - dk) * I_c + dk * cv2.resize(Im, (cols, rows), interpolation=cv2.INTER_AREA)
    d = LOOK["DETAIL"].get(cw, 0.9)
    I_cell = np.repeat(np.repeat(I_c, ch, 0), cw, 1)
    C_fg = I_cell * (1 - d) + cv2.GaussianBlur(I_p, (0, 0), max(0.8, cw / 8)) * d     # the strokes of a glyph sample the frame under them
    bgd = LOOK["BG_DETAIL"].get(cw, 0.45)
    C_bg = I_cell * (1 - bgd) + cv2.GaussianBlur(I_p, (0, 0), max(1.0, cw / 6)) * bgd
    # the character on every cell, in reading order, climbing a row at a time
    start = text_start(n, cw, cols, text)
    idx = (start + np.arange(rows)[:, None] * cols + np.arange(cols)[None, :]) % len(text)
    codes = np.frombuffer(text.encode("ascii"), np.uint8)[idx].astype(np.int32) - 32
    # glyph ink: hairline in the dark, heavy in the light, thin again once a cell has flipped to dark-on-light
    capzone = (np.arange(rows)[:, None] * ch - oy) < (face["top"] + 8 if face else -1)        # above the forehead (hair, a hat), never the face
    near_skin = cv2.dilate(skin.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * cw + 1, 2 * cw + 1)))
    skin_c = cv2.resize(pad(near_skin.astype(np.float32)), (cols, rows), interpolation=cv2.INTER_AREA)
    inv = (T_c > LOOK["INVERT"].get(cw, 0.84)) & capzone & (skin_c < 0.05)                      # a light hat or blond hair, never a forehead
    want = np.where(inv, 0.22, np.clip(T_c / 0.86, 0, 1) ** 0.85)
    wi = np.clip((want * (WEIGHTS - 0.001)).astype(np.int32), 0, WEIGHTS - 1)
    glyphs = A.a[wi, codes]                                  # rows, cols, ch, cw
    # the room is sparse: in the dark whole words are simply not there, and no dots for spaces. Where it is lit they all come back
    R_c = cv2.resize(pad(room), (cols, rows), interpolation=cv2.INTER_AREA)
    Y_c = cv2.resize(pad(Y), (cols, rows), interpolation=cv2.INTER_AREA)
    hash_ = ((word_id(text)[idx] * 2654435761) >> 12 & 1023) / 1023.0
    keep = np.clip(LOOK["ROOM_KEEP"] + (Y_c - C.room_y - 0.03) / 0.16, 0, 1)
    gone = (R_c > 0.75) & ((hash_ > keep) | (codes == 0))
    glyphs = glyphs * (~gone)[:, :, None, None]
    inkm = glyphs.transpose(0, 2, 1, 3).reshape(rows * ch, cols * cw)
    cov = A.cov[wi, 40] * ~gone                               # the ink of a typical letter in that weight, so neighbouring cells stay even
    cov_p = np.repeat(np.repeat(cov, ch, 0), cw, 1)[:, :, None].astype(np.float32)
    inv_p = np.repeat(np.repeat(inv, ch, 0), cw, 1)[:, :, None]
    fg = C_fg + Hue_p * 255 * K_p[:, :, None] * LOOK["KSCALE"].get(cw, 1.15)
    fg = np.where(inv_p, np.minimum(C_fg * 0.16, C.FIELD * 1.6), fg)
    bg = (C_bg - cov_p * np.clip(fg, 0, 255)) / (1 - cov_p)
    # the cell's own colour only goes so far: past this the picture has to come from the type, or the speaker stops being made of it
    lum = (bg * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(-1, keepdims=True)
    bg = np.where(inv_p, bg, bg / np.maximum(lum / LOOK["BG_MAX"].get(cw, 168.0), 1.0))    # keeps the hue: a light cell never goes grey
    bg = np.clip(bg, C.FIELD * 0.55, 255)
    # the type flares where the line has just been, and on every step down
    ly, _dir = line_y(n)
    flare = np.zeros((rows * ch, cols * cw, 1), np.float32)
    if ly is not None:
        ys = (np.arange(rows)[:, None] * ch + ch / 2 - oy).astype(np.float32)   # row centres on the frame
        fl = np.exp(-np.clip(ly - ys, 0, None) / 150) * (ys <= ly)
        flare += np.repeat(np.repeat(fl[:, :, None].astype(np.float32), ch, 0), cols * cw, 1)
    for ts, c in C.steps[1:]:
        age = n - fr(ts)
        if 0 <= age < 4:
            flare += 0.42 * (1 - age / 4)
    fg = fg + flare * (C.LIGHT - fg) * 0.8
    img = bg * (1 - inkm[:, :, None]) + fg * inkm[:, :, None]
    return np.clip(img[oy:oy + H, ox:ox + W], 0, 255).astype(np.uint8)


def mic_alpha(project, t):
    import fxlib
    p = os.path.join(project, "public", "plates", f"mic_{fxlib.crop_at(project, t)}.webm")
    if os.path.exists(p):
        for _, c in fxlib.rgba(project, 0, 1 / FPS, src=os.path.relpath(p, project)):
            return c[:, :, 3]
    return np.zeros((H, W), np.uint8)        # no mic on this shot


def write_fx(d, T_B):
    """fx.html + fx.js: the clip above a per-frame clip-path, the line a real element, every position set on its frame"""
    import fxlib
    a0, b0 = fr(C.scan0), fr(C.scan1)
    a1, b1 = fr(C.up0), fr(C.up1)
    html = fxlib.tag("{{ID}}-clip", "fx/{{ID}}/code.mp4", C.scan0, T_B, track="{{T0}}", style="position:absolute;left:0;top:0;width:1080px;height:1920px;")
    html = ("<!-- code-body: written by gen.py. The code clip above a per-frame clip-path; below the line the speaker is live. -->\n"
            + html + "\n<div id=\"{{ID}}-line\"></div>\n<style>\n#{{ID}}-line { position:absolute; left:0; top:0; width:1080px; height:2px; "
            "background:var(--c-light); opacity:0; }\n</style>\n")
    open(os.path.join(d, "fx.html"), "w", encoding="utf-8").write(html)
    js = ["// code-body: written by gen.py. Per frame: how much of the code clip shows, and where the line is. Above the line the speaker is code, below it live.",
          "gsap.set('#{{ID}}-clip', { clipPath: 'inset(0px 0px 1920px 0px)' });",
          "gsap.set('#{{ID}}-line', { y: 0, opacity: 0 });",
          f"tl.set('#{{{{ID}}}}-line', {{ opacity: 1 }}, q({a0 / FPS:.4f}));"]
    for n in list(range(a0, b0)) + list(range(a1, b1)):
        y, _d = line_y(n)
        js.append(f"tl.set('#{{{{ID}}}}-clip', {{ clipPath: 'inset(0px 0px {H - y:.1f}px 0px)' }}, q({n / FPS:.4f})); "
                  f"tl.set('#{{{{ID}}}}-line', {{ y: {y - 1:.1f} }}, q({n / FPS:.4f}));")
    js += [f"tl.set('#{{{{ID}}}}-line', {{ opacity: 0 }}, q({b0 / FPS:.4f}));",
           f"tl.set('#{{{{ID}}}}-clip', {{ clipPath: 'inset(0px 0px 0px 0px)' }}, q({b0 / FPS:.4f}));",
           f"tl.set('#{{{{ID}}}}-line', {{ opacity: 1 }}, q({a1 / FPS:.4f}));",
           f"tl.set('#{{{{ID}}}}-line', {{ opacity: 0 }}, q({b1 / FPS:.4f}));",
           f"tl.set('#{{{{ID}}}}-clip', {{ clipPath: 'inset(0px 0px 1920px 0px)' }}, q({b1 / FPS:.4f}));"]
    open(os.path.join(d, "fx.js"), "w", encoding="utf-8").write("\n".join(js) + "\n")


def lum255(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def mix(a, b, t):
    return np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--still", help="frames n,n,n: stills in work/<id>/ instead of the clip")
    args = ap.parse_args()
    kit_pipeline()
    import fxlib
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    words = fxlib.words(project)
    inside = [s for s, e, t in words if A - 0.05 <= s < B]
    # the beats, from the words
    scan0 = spoken(words, SCAN_ON, A - 0.05, B) if SCAN_ON else (inside[0] if inside else A + 0.03)
    if scan0 is None:
        sys.exit(f"SCAN_ON {SCAN_ON!r} is not spoken in the window")
    scan0 = max(scan0, A + 1 / FPS)
    up0 = spoken(words, UP_ON, scan0 + SCAN, B) if UP_ON else B - UP_BEFORE
    if up0 is None:
        sys.exit(f"UP_ON {UP_ON!r} is not spoken after the scan")
    up0 = min(up0, B - UP - 1 / FPS)
    # the coarsest cells hold a beat after the scan, then the steps come about a third of the way to the line going
    # back up, a word each (as shipped: 39%, 52% and 65% of the way), so the face holds resolved before it goes live
    steps, after = [(scan0, CELLS[0])], scan0 + SCAN
    fracs = np.linspace(STEP_FROM, STEP_TO, len(CELLS) - 1) if len(CELLS) > 2 else [STEP_FROM]
    for k, cw in enumerate(CELLS[1:]):
        if STEPS_ON:
            t = spoken(words, STEPS_ON[k], after, up0) if k < len(STEPS_ON) else None
        else:
            aim = scan0 + SCAN + fracs[k] * (up0 - scan0 - SCAN)
            t = next((s for s in sorted(words) if max(aim - 0.12, after) <= s[0] < up0 - 0.2), (None,))[0]
        if t is None:
            t = max(after + 0.1, scan0 + SCAN + fracs[k] * (up0 - scan0 - SCAN))
            print(f"no word for the {cw}px step: it lands at {t:.2f}")
        steps.append((t, cw))
        after = t + 0.08
    if steps[-1][0] > up0 - 0.3:
        print("warning: the face resolves less than 0.3 s before the line runs back up: widen the window or step earlier")
    C.scan0, C.scan1, C.up0, C.up1, C.steps = scan0, scan0 + SCAN, up0, up0 + UP, steps
    C.n1 = fr(B)
    # the pack's colours: ground, the speaker's light, the accent, the muted room type
    P = fxlib.pack(project)
    col = P["colors"]
    C.FIELD = np.array(col["dark"][:3], np.float32)
    C.LIGHT = np.array(col["light"][:3], np.float32)
    C.ACCENT = np.array(col["accent"][:3], np.float32)
    md = col["muted_dark"]
    C.MUTED = mix(C.FIELD, md[:3], md[3] / 255 if len(md) > 3 else 1.0)
    lift = mix(C.LIGHT, (255, 255, 255), .25)
    C.PERSON = [(0.0, C.FIELD), (0.18, mix(C.FIELD, C.LIGHT, .196)), (0.42, mix(C.FIELD, C.LIGHT, .54)),
             (0.68, mix(C.FIELD, C.LIGHT, .87)), (0.88, C.LIGHT), (1.0, mix(C.LIGHT, lift, .3))]
    C.HUE_H, C.HUE_R = C.LIGHT / 255, C.MUTED / 255
    # the track: a face on every frame (a missing one borrowed from the nearest frame that has it)
    C.track = fxlib.tracks(project)["frames"]
    n0, n1 = fr(A), fr(B)
    have = [n for n in range(max(0, n0 - 15), min(len(C.track), n1 + 15)) if C.track[n].get("face")]
    if not have:
        sys.exit("no face in work/tracks/track.json near this window: run pipeline/track.py")
    C.face_at = lambda n: C.track[n]["face"] if n < len(C.track) and C.track[n].get("face") else C.track[min(have, key=lambda m: abs(m - n))]["face"]
    mic = mic_alpha(project, A)
    # measured once on the take: the skin, the clothes' colour and range, the room's level
    samples = []
    for i, (n, rgb) in enumerate(fxlib.frames(project, A, B)):
        if i % 8 == 0:
            samples.append((n, rgb.copy()))
    mats = {n: al.copy() for n, al in fxlib.alpha(project, A, B) if n in {s[0] for s in samples}}
    C.skin = skin_model([(rgb, C.face_at(n)) for n, rgb in samples])
    cloth_px, room_y, keys = [], [], []
    C.cloth_lo, C.cloth_hi = 0.04, 0.56
    C.k_lo, C.k_hi = 0.05, 0.67                            # the shipped take's own range: the look was tuned on it
    C.CLOTH = [(0, C.FIELD), (1, C.LIGHT)]
    C.room_y = 0.02
    C.HUE_S = C.LIGHT / 255
    for n, rgb in samples:
        if n not in mats:
            continue
        f, Y, sws, person, room, _skin = analyse(rgb, mats[n], mic, dict(C.track[n] if n < len(C.track) else {}, face=C.face_at(n)))
        m = sws > .5
        if m.sum() > 2000:
            cloth_px.append(f[m])
        room_y.append(np.median(Y[room > .9]) if (room > .9).sum() > 1000 else np.nan)
        pm = (person > .9) & (sws < .1)
        if pm.sum() > 2000:
            keys.append((0.5 * Y + 0.5 * f[:, :, 0])[pm])
    if keys:
        kv = np.concatenate(keys)
        C.k_lo, C.k_hi = float(np.quantile(kv, .02)), float(max(np.quantile(kv, .98), np.quantile(kv, .02) + .3))
    seen = [v for v in room_y if np.isfinite(v)]
    C.room_y = ROOM_Y if ROOM_Y is not None else (float(np.clip(np.median(seen) - 0.02, 0, .9)) if seen else 0.02)
    if cloth_px:
        px = np.concatenate(cloth_px)
        mx = px.max(axis=1)
        med = float(np.median(mx))                               # a flat, evenly lit shirt still spans the middle of the ramp
        C.cloth_lo, C.cloth_hi = float(min(np.quantile(mx, .05), med - .15)), float(max(np.quantile(mx, .95), med + .15))
        base = np.median(px, axis=0) * 255
    else:
        base = None
        print("no clothes found under the chin: the body reads as skin")
    if CLOTHES:
        g = np.array(col[CLOTHES][:3] if CLOTHES in col else col["series"][int(CLOTHES[1]) - 1][:3], np.float32)
    elif base is not None:
        g = base * (97.0 / max(lum255(base), 1.0))             # the clothes' own hue at a mid level, so dark clothes still read
        g = g * min(1.0, 235.0 / max(g.max(), 1.0))
    else:
        g = mix(C.FIELD, C.LIGHT, .45)
    top = mix(np.minimum(g * 1.25, 255), C.LIGHT, .15)
    C.CLOTH = [(0.0, g * 0.15), (0.3, g * 0.37), (0.62, g * 0.72), (0.85, g), (1.0, top)]
    C.HUE_S = mix(top, C.LIGHT, .45) / 255
    text = source_text(project, os.path.dirname(os.path.abspath(fxlib.__file__)))
    faces = mono_faces(P)
    print(f"{fid}: scan {scan0:.2f}, steps " + ", ".join(f"{c}px {t:.2f}" for t, c in steps[1:]) + f", up {up0:.2f}; "
          f"{len(text)} chars of code; clothes {np.round(g).astype(int).tolist()} (range {C.cloth_lo:.2f}-{C.cloth_hi:.2f}); "
          f"room level {C.room_y:.2f}; the speaker's key {C.k_lo:.2f}-{C.k_hi:.2f}; mono {os.path.basename(faces[0][0])}..{os.path.basename(faces[-1][0])}")
    atlases = {c: Atlas(c, faces) for _, c in steps}
    want = [int(x) for x in args.still.split(",")] if args.still else None
    work = os.path.join(project, "work", fid)
    os.makedirs(work, exist_ok=True)
    d = out_dir(project, fid)
    w = None if want else fxlib.Writer(os.path.join(d, "code.mp4"), crf=int(os.environ.get("CRF", "15")))
    T_CLIP = scan0
    for (n, rgb), (_, al) in zip(fxlib.frames(project, T_CLIP, B), fxlib.alpha(project, T_CLIP, B)):
        if want is not None:
            if n not in want:
                continue
            cv2.imwrite(os.path.join(work, f"s_{n}.png"), render(n, rgb, al, mic, atlases, text)[:, :, ::-1])
            cv2.imwrite(os.path.join(work, f"t_{n}.png"), render(n, rgb, al, mic, atlases, text, raw=True)[:, :, ::-1])
            continue
        w.write(render(n, rgb, al, mic, atlases, text))
    if w:
        w.close()
        write_fx(d, B)
        print("->", d)
    else:
        print("stills in", work)
    sfx = [(scan0 + 0.14, "whoosh-soft", -16, "the line scans down")]
    sfx += [(t, "click", -15, f"cells step to {c}px") for t, c in steps[1:-1]]
    sfx += [(steps[-1][0], "impact-low", -18, "the face resolves"), (steps[-1][0], "ding", -22, "the face resolves")]
    sfx += [(scan0 + SCAN, "typing", -24, "the code being written, trim it to the hold with max_len"), (up0 + 0.2, "whoosh-soft", -16, "the line runs back up")]
    print("SFX (time, name, dB, what):", [(round(t, 3), n_, db, x) for t, n_, db, x in sfx])


if __name__ == "__main__":
    main()
