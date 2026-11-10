#!/usr/bin/env python3
"""day-dial: the frame is a clock face and the speaker's head is its hub. On the first word an hour hand in the pack's
accent comes out from behind the head and ticks clockwise, one hour per spoken word, so the clock runs on the voice.
Everything it has passed becomes a flat sheet in the pack's light colour between the speaker and the wall, printed in
the pack's ink: rings, minute ticks, numerals in the display face, WORD in every swept hour. The speaker's own shadow
falls on the sheet, its leading edge throws a thin contact shadow on the real room, a thin minute hand whirls under it
with exact motion blur, and the room still showing gets darker as the day runs out. The last wedge of real room carries
LABEL, painted in the light colour, and closes on its word with a small shove. Hold on the full dial, then the hand
spins back and unwinds to the live room. Outside the sheet the live frame is untouched, and the speaker is the live
frame (the soft edge comes off the room just outside it), so the lips stay in sync.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>: the window), words.json (the hours), timeline.json (the crop),
          public/clean.mp4, public/subject.webm, work/tracks/track.json (the hub, the neck), style/ (fonts and colours),
          public/plates/desk_<FRAME>.webm, mic_<FRAME>.webm (optional: the desk and the mic stay in front of the sheet)
  writes  <project>/fx/<id>/<id>.mp4 (frame n = reel frame round(at * 30) + n), audio/<id>-unwind.wav, and prints the
          SFX lines
<id> defaults to this script's folder name. Rerun it whenever the window, the cut, the words or the pack change.
"""
import argparse
import glob
import os
import re
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30

# ---- the constants to change per video (the window itself is the edit.py FX entry)
WORD = "editing"            # set in every swept hour: what the day went to
LABEL = "ideating"          # painted on the last wedge of real room: what got no time
HAND_ON = ""                # the word the hand comes out on; '' = the first word in the window
CLOSE_ON = ""               # the word the last wedge closes on; '' = the hand's twelfth word (or the end of the sweep)
MIN_WORDS = 8               # fewer spoken words than this after the hand: the hours run on a clock instead (SWEEP)
SWEEP = (0.37, 0.19)        # s: eleven hours in the first, then the last wedge holds its label for the second and closes
UNWIND = (0.245, 0.06)      # s: the hand spins back over this long, done this far before the window ends (its last frame is live)
HUB = None                  # the hub in reel px; None = the middle of the head over the window (track)
DIAL_SCALE = None           # None = sized from the face, kept inside the sides of the frame
NIGHT = 0.62                # how far the room still showing falls as the day runs out
SHADOW = dict(dx=52, dy=30, blur=20, op=0.36)     # the speaker's shadow on the sheet: the same soft key as the footage
LOWER = 1.5                 # the sheet stops this many face heights below the chin: the lap, the chair and the desk stay
                            # live (a matte is weakest down there); a number above 10 is a y in px; None = no stop
NECK = 0                    # a matte that reads the shadowed side of the neck as room: close notches this wide (share of
                            # the face width, about 0.3) between jaw and shoulders. 0 = off: on a good matte it fills real
                            # room between the ear and the shoulder and shows it as a patch on the sheet
SEED = 5

# the dial at scale 1 (sized on a face 357 px tall): rings, px from the hub, and type sizes
R_HOUR0, R_TEXT, R_LINE, R_NUM, R_TICK0, R_TICK1 = 232, 338, 388, 436, 472, 497
F_NUM, F_WORD, F_LABEL = 88, 58, 66
REF_FACE = 357.0
SHUT = 0.5                  # shutter, of a frame
MIN_SHUT = 0.7              # of that shutter, for the fast minute hand


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


def word_at(words, text, after, before):
    """(start, end) of the first spoken `text` at or after `after` and before `before` (wordAt in fx.js), or None"""
    for s, e, w in words:
        if after - 0.001 <= s < before and (not text or norm(w) == norm(text)):
            return s, e
    return None


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


def track_of(project):
    """work/tracks/track.json from the kit's track.py: the head, face and shoulders on every frame"""
    p = os.path.join(project, "work", "tracks", "track.json")
    if not os.path.exists(p):
        sys.exit(f"no {p}: run the kit's track.py on this project first (it reads the head and shoulders off the footage)")
    return fxlib.tracks(project)["frames"]


def colour(S, role, over=None):
    """a pack colour as float RGB 0-255; one with alpha is laid over `over` (default the light ground)"""
    r, g, b, a = S["colors"][role]
    c = np.array([r, g, b], np.float32)
    if a < 255:
        base = np.array(S["colors"]["light"][:3], np.float32) if over is None else np.asarray(over, np.float32)
        c = c * (a / 255) + base * (1 - a / 255)
    return c


# ------------------------------------------------------------------ small math
def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def back_out(u, s=2.0):
    u = np.clip(u, 0, 1) - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def nc(img, mask, sigma):
    m = mask.astype(np.float32)
    a = cv2.GaussianBlur(img * m[..., None], (0, 0), sigma)
    b = cv2.GaussianBlur(m, (0, 0), sigma)
    return a / np.maximum(b[..., None], 1e-4), b


def local_bg(C, a):
    """what is really behind the speaker's soft edge in this frame: the live room just outside it, spread inward. A
    plate can't say as well: the room right at the outline is the part the speaker hides. Worked at half size, it is
    smooth anyway"""
    h, w = a.shape
    c2 = cv2.resize(C, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    ok = cv2.resize((a < 0.01).astype(np.float32), (w // 2, h // 2), interpolation=cv2.INTER_AREA) > 0.99
    out = c2.copy()
    todo = np.ones(ok.shape, bool)
    for s_ in (2.5, 6, 15, 40):
        f_, b_ = nc(c2, ok, s_)
        take = todo & (b_ > 0.03)
        out[take] = f_[take]
        todo &= ~take
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)


class Dial:
    """everything that holds for the whole window: the geometry around the hub, the printed sheet, the clock"""

    def __init__(self, project, A, B, frame, words, S, W, H):
        self.W, self.H = W, H
        self.S = S
        TR = track_of(project)
        self.tr = TR
        f0, f1 = fxlib.fr(A), fxlib.fr(B)
        fcs = [TR[i]["face"] for i in range(f0, min(f1, len(TR))) if TR[i].get("face")]
        if not fcs:
            sys.exit("no face in work/tracks/track.json over this window: run the kit's track.py, or set HUB and DIAL_SCALE")
        fh = float(np.median([f["h"] for f in fcs]))
        self.face_w = float(np.median([f["w"] for f in fcs]))
        self.hub = HUB or (float(np.median([f["cx"] for f in fcs])), float(np.median([f["cy"] - 0.19 * f["h"] for f in fcs])))
        hx, hy = self.hub
        k = DIAL_SCALE or float(np.clip(min(fh / REF_FACE, (min(hx, W - hx) - 30) / R_TICK1), 0.5, 1.4))
        self.k = k
        self.r = dict(hour0=R_HOUR0 * k, text=R_TEXT * k, line=R_LINE * k, num=R_NUM * k, tick0=R_TICK0 * k, tick1=R_TICK1 * k)
        # the head's top from the matte: the label starts just above it
        tops = []
        for i, al in fxlib.alpha(project, A, B):
            if (i - f0) % 6:
                continue
            col = al[:, max(0, int(hx - 0.25 * self.face_w)):int(hx + 0.25 * self.face_w)].max(axis=1)
            ys = np.nonzero(col > 128)[0]
            if len(ys):
                tops.append(int(ys[0]))
        self.head_up = hy - (min(tops) if tops else hy - 0.68 * fh)
        if self.r["text"] < self.head_up + 20:
            print(f"WARNING: the hour words (radius {self.r['text']:.0f}) sit behind the head (top {self.head_up:.0f} above the hub): "
                  "a frame with more room above the shoulders shows more of the dial")
        # geometry around the hub
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        DX, DY = xx + .5 - hx, yy + .5 - hy
        self.ANG = (np.degrees(np.arctan2(DX, -DY)) % 360).astype(np.float32)
        self.RAD = np.hypot(DX, DY).astype(np.float32)
        self.DEG_PX = np.degrees(1.0 / np.maximum(self.RAD, 1.0)).astype(np.float32)   # degrees per px at this radius
        low = None if LOWER is None else LOWER if LOWER > 10 else float(np.median([f["chin"] for f in fcs])) + LOWER * fh
        self.LOWER = smooth(low - 15, low + 15, yy).astype(np.float32) if low is not None and low < H else None
        # what stands in front of the speaker never gets the sheet: the desk and the mic layers from the plate tools
        front = [x for x in (plate_alpha(project, "desk", frame), plate_alpha(project, "mic", frame)) if x is not None]
        self.front = np.maximum.reduce(front) if front else None
        self.ink, self.light, self.accent = colour(S, "ink"), colour(S, "light"), colour(S, "accent")
        self.rule = colour(S, "muted_light")
        self.clock(A, B, words)
        self.art = self.dial_art(project)
        self.label = self.label_layer(project)
        self.rng = np.random.default_rng(SEED)

    # ---- the clock: when the hand moves, from the words
    def clock(self, A, B, words):
        hand = word_at(words, HAND_ON, A, B)
        self.t_hand = hand[0] if hand else A + 0.08
        self.t_unwind = (B - UNWIND[1] - UNWIND[0], B - UNWIND[1])
        close = word_at(words, CLOSE_ON, self.t_hand + 0.05, self.t_unwind[0]) if CLOSE_ON else None
        limit = close[0] if close else self.t_unwind[0] - 0.25
        starts = [s for s, e, w in words if self.t_hand + 0.05 < s < limit - 0.03]
        hours = starts[:12] + [close[0]] if close else starts[:13]     # the last one closes the dial
        if len(hours) >= MIN_WORDS:
            # one hour per word; the word before the close takes half of the last hour, so the wedge shrinks to a sliver
            n = len(hours) - 2
            self.ticks = [(t, 330.0 * (i + 1) / n) for i, t in enumerate(hours[:n])] + [(hours[-2], 345.0), (hours[-1], 360.0)]
            self.tick_d, self.per_hour = 0.135, 1.0
            label_word = word_at(words, LABEL, self.t_hand, self.t_unwind[0])
            self.label_bright = label_word[0] if label_word else self.ticks[n - 1][0] - 0.06
        else:
            # a short line: eleven hours go by on a clock, the last wedge holds its label for a beat and closes
            t0 = self.t_hand + 0.05
            end = close[0] if close else t0 + SWEEP[0] + SWEEP[1]
            run = max(0.12, min(SWEEP[0], end - t0 - 0.08))     # closing on a word: the hours fit in before it
            self.ticks = [(t0 + run * i / 10, 30.0 * (i + 1)) for i in range(11)] + [(end, 360.0)]
            self.tick_d, self.per_hour = 0.09, 1 / 3                  # one turn per hour aliases at this speed
            label_word = word_at(words, LABEL, self.t_hand, self.t_unwind[0])
            self.label_bright = label_word[0] if label_word else t0 + 0.2
        if self.ticks[-1][0] >= self.t_unwind[0] - 0.05:
            sys.exit(f"the dial closes at {self.ticks[-1][0]:.2f} but the unwind starts at {self.t_unwind[0]:.2f}: "
                     "move the FX end later or CLOSE_ON earlier")
        self.label_on = self.t_hand + 0.12
        self.last_angle = self.ticks[-2][1]
        print("hours at " + " ".join(f"{t:.2f}" for t, _ in self.ticks) + f", unwind {self.t_unwind[0]:.2f}-{self.t_unwind[1]:.2f}")

    def hour_angle(self, t):
        """degrees clockwise from 12: the hand's true position"""
        a, prev = 0.0, 0.0
        for tk, ang in self.ticks:
            if t < tk:
                break
            u = (t - tk) / self.tick_d
            a = prev + (ang - prev) * float(back_out(u, 2.0 if ang < 360 else 1.1))
            prev = ang
        if t >= self.t_unwind[0]:
            u = np.clip((t - self.t_unwind[0]) / (self.t_unwind[1] - self.t_unwind[0]), 0, 1)
            return 360.0 * (1 - float(u ** 1.9))
        return a

    def minute_angle(self, t):
        """a fixed number of turns per hour, whatever length the hour got; it stops dead when the day closes"""
        if t < self.t_hand + 0.03:
            return 0.0
        ts = [self.t_hand + 0.03] + [x[0] for x in self.ticks]
        turns = [0.0] + [(i + 1.0) * self.per_hour for i in range(len(self.ticks))]
        if t >= self.ticks[-1][0]:
            base = 360.0 * turns[-1]
            if t < self.t_unwind[0]:
                return base
            u = np.clip((t - self.t_unwind[0]) / (self.t_unwind[1] - self.t_unwind[0]), 0, 1)
            return base - 360.0 * (4 if self.per_hour == 1 else 2) * float(u ** 1.6)
        return 360.0 * float(np.interp(t, ts, turns))

    # ---- the printed sheet and the label
    def glyph_arc(self, canvas, text, font, r, center_deg, fill, ss, flip=False):
        """text along a circle, baseline at radius r, centred on an angle, one real glyph at a time; flip: tops to the centre"""
        hx, hy = self.hub
        adv = [font.getlength(text[:i + 1]) for i in range(len(text))]
        total = adv[-1]
        for i, ch in enumerate(text):
            mid = (adv[i - 1] if i else 0.0) + (adv[i] - (adv[i - 1] if i else 0.0)) / 2
            off = np.degrees((mid - total / 2) / (r * ss))
            a = center_deg - off if flip else center_deg + off
            rad = np.radians(a)
            px, py = hx * ss + np.sin(rad) * r * ss, hy * ss - np.cos(rad) * r * ss
            size = int(font.size * 2.2)
            g = Image.new("L", (size, size), 0)
            ImageDraw.Draw(g).text((size / 2, size / 2), ch, font=font, fill=255, anchor="ms")
            rot = g.rotate(-(a + 180 if flip else a), resample=Image.BICUBIC, center=(size / 2, size / 2))
            canvas.paste(tuple(int(v) for v in fill), (int(px - size / 2), int(py - size / 2)), rot)

    def dial_art(self, project):
        """the printed sheet at 3x: light ground, ink rings, ticks, numerals in the display face, WORD in every hour"""
        ss, W, H, R = 3, self.W, self.H, self.r
        hx, hy = self.hub
        ink = tuple(int(v) for v in self.ink)
        a = np.array(Image.new("RGB", (W * ss, H * ss), tuple(int(v) for v in self.light)))
        cx, cy = hx * ss, hy * ss
        pts = lambda r, deg: (np.sin(np.radians(deg)) * r * ss + cx, -np.cos(np.radians(deg)) * r * ss + cy)   # noqa: E731
        for r, th in ((R["tick1"], 2.0), (R["line"], 1.4)):
            cv2.circle(a, (int(cx * 8), int(cy * 8)), int(r * ss * 8), ink, max(1, int(th * ss * self.k)), lineType=cv2.LINE_AA, shift=3)
        for m in range(60):
            deg, h = m * 6, m % 5 == 0
            p0, p1 = pts(R["tick1"] - (R["tick1"] - R["tick0"] if h else 12 * self.k), deg), pts(R["tick1"], deg)
            cv2.line(a, (int(p0[0] * 8), int(p0[1] * 8)), (int(p1[0] * 8), int(p1[1] * 8)), ink,
                     max(1, int((3 if h else 1.4) * ss * self.k)), lineType=cv2.LINE_AA, shift=3)
        for k_ in range(12):              # fine hour rules out from behind the head: the hand lands on them
            p0, p1 = pts(R["hour0"], k_ * 30), pts(R["line"], k_ * 30)
            cv2.line(a, (int(p0[0] * 8), int(p0[1] * 8)), (int(p1[0] * 8), int(p1[1] * 8)), tuple(int(v) for v in self.rule),
                     max(1, int(1.2 * ss)), lineType=cv2.LINE_AA, shift=3)
        im = Image.fromarray(a)
        fn = fxlib.font(project, "display", round(F_NUM * self.k * ss))
        d = ImageDraw.Draw(im)
        for k_ in range(12):
            x, y = pts(R["num"], k_ * 30)
            d.text((x, y + 2 * ss), "12" if k_ == 0 else str(k_), font=fn, fill=ink, anchor="mm")
        # WORD in every hour, sized so it fits its 30 degrees of arc
        size = F_WORD * self.k
        fw = fxlib.font(project, "text", round(size * ss))
        room = 0.80 * R["text"] * np.pi / 6 * ss
        if fw.getlength(WORD) > room:
            size *= room / fw.getlength(WORD)
            fw = fxlib.font(project, "text", round(size * ss))
        for k_ in range(12):
            deg = k_ * 30 + 15
            lower = 90 < deg < 270
            self.glyph_arc(im, WORD, fw, R["text"] + (round(40 * self.k) if lower else 0), deg, ink, ss, flip=lower)
        return np.asarray(im.resize((self.W, self.H), Image.LANCZOS), np.float32)

    def label_layer(self, project):
        """the last wedge's label: painted on the wall in the light colour, reading outward from just above the head"""
        ss, W, H = 3, self.W, self.H
        hx, hy = self.hub
        deg = (self.last_angle + 360.0) / 2 - 3
        r0 = self.head_up + 0.12 * REF_FACE * self.k
        rad = np.radians(deg)
        # how far the wall runs along this angle before the frame edge: the label has to fit in it
        dx, dy = np.sin(rad), -np.cos(rad)
        reach = min(v for v in ((-hx / dx) if dx < -1e-3 else 1e9, ((W - hx) / dx) if dx > 1e-3 else 1e9,
                                (-hy / dy) if dy < -1e-3 else 1e9, ((H - hy) / dy) if dy > 1e-3 else 1e9))
        size = F_LABEL * self.k
        f = fxlib.font(project, "display", round(size * ss))
        room = max(60.0, reach - r0 - 30)
        if f.getlength(LABEL) / ss > room:
            size *= room / (f.getlength(LABEL) / ss)
            f = fxlib.font(project, "display", round(size * ss))
        im = Image.new("L", (W * ss, H * ss), 0)
        g = Image.new("L", (int(f.getlength(LABEL)) + 40 * ss, int(size * 1.7) * ss), 0)
        ImageDraw.Draw(g).text((20 * ss, int(size * 1.1) * ss), LABEL, font=f, fill=255, anchor="ls")
        rot = g.rotate(90 - (deg - 360), expand=True, resample=Image.BICUBIC)   # the baseline runs out along the radius
        mid = r0 + f.getlength(LABEL) / ss / 2
        cx, cy = (hx + np.sin(rad) * mid) * ss, (hy - np.cos(rad) * mid) * ss
        im.paste(rot, (int(cx - rot.width / 2), int(cy - rot.height / 2)))
        return np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255

    # ---- per-pixel closed-form coverage
    def blade(self, ang0, ang1, half_px):
        """exact motion blur of a thin ray swept from ang0 to ang1 over the open shutter: the share of the shutter the
        ray covers each pixel"""
        lo, hi = min(ang0, ang1), max(ang0, ang1)
        span = min(hi - lo, 180.0)
        hw = half_px * self.DEG_PX
        sp = np.maximum(span, self.DEG_PX)               # never narrower than one px of smear: that is the anti-aliasing
        rel = ((self.ANG - lo + (sp - span) / 2 + 180.0) % 360.0) - 180.0
        ov = np.clip(np.minimum(rel + hw, sp) - np.maximum(rel - hw, 0.0), 0, None)
        return np.clip(ov / sp, 0, 1).astype(np.float32)

    def sheet_cover(self, phi0, phi1):
        """how much of the shutter each pixel spends under the sheet: 12 o'clock to the hand, its edge blurred exactly"""
        lo, hi = min(phi0, phi1), max(phi0, phi1)
        if lo >= 360.0 - 1e-4:
            return np.ones(self.ANG.shape, np.float32)
        if hi <= 1e-4:
            return np.zeros(self.ANG.shape, np.float32)
        w = np.maximum(hi - lo, self.DEG_PX)
        cov = np.clip(0.5 + ((lo + hi) / 2 - self.ANG) / w, 0, 1)
        start = np.clip(0.5 + self.ANG / self.DEG_PX, 0, 1)   # the fixed edge at 12: a clean anti-aliased line
        wrap = np.clip(0.5 + (hi - 360.0 - self.ANG) / self.DEG_PX, 0, 1) if hi > 360 else 0.0
        return np.clip(np.maximum(cov * start, wrap), 0, 1).astype(np.float32)

    def edge_shadow(self, phi, strength=0.62, reach=16.0):
        """the thin contact shadow the sheet's leading edge throws on the room, and the fixed edge at 12 on the other side"""
        dist = np.minimum(self.RAD * np.radians(np.clip(self.ANG - phi, 0, 180)), 400.0)
        s = np.exp(-dist / reach) * (self.ANG >= phi) * smooth(0.0, 20.0, self.RAD)
        dist2 = np.minimum(self.RAD * np.radians(np.clip(360.0 - self.ANG, 0, 180)), 400.0)
        s2 = np.exp(-dist2 / reach) * (self.ANG >= phi)
        return np.clip(strength * np.maximum(s, s2), 0, 1).astype(np.float32)

    def neck_fill(self, al, f):
        """the matte can read the shadowed side of the neck as room, which a bright sheet would show through: close the
        notch between jaw and shoulders, only there"""
        if not NECK or f >= len(self.tr) or not self.tr[f].get("face") or not self.tr[f].get("pose"):
            return al
        p, fc = self.tr[f]["pose"], self.tr[f]["face"]
        mx, my = (p["ls"][0] + p["rs"][0]) / 2, (p["ls"][1] + p["rs"][1]) / 2
        half = 0.46 * abs(p["ls"][0] - p["rs"][0])
        x0, x1 = max(0, int(mx - half)), min(self.W, int(mx + half))
        y0, y1 = max(0, int(fc["chin"] - 0.48 * fc["h"])), min(self.H, int(my + 20))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return al
        n = max(3, int(NECK * fc["w"]) | 1)
        crop = al[y0:y1, x0:x1]
        closed = cv2.morphologyEx(crop, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n)))
        out = al.copy()
        out[y0:y1, x0:x1] = np.maximum(crop, cv2.GaussianBlur(closed, (0, 0), 1.2))
        return out

    def render(self, f, live, matte):
        t = f / FPS
        if t < self.t_hand - 1 / FPS or t >= self.t_unwind[1] + 0.5 / FPS:
            return live                                     # before the hand and after the unwind: the live frame
        L = live.astype(np.float32)
        phi0, phi1 = self.hour_angle(t), self.hour_angle(t + SHUT / FPS)
        psi0, psi1 = self.minute_angle(t), self.minute_angle(t + SHUT / FPS)
        phi = (phi0 + phi1) / 2
        M = matte.astype(np.float32) / 255
        # inside the speaker the matte's dips mean nothing (a dark top can read as room): only the outline stays soft
        inside = cv2.erode(ndi.binary_fill_holes(M > 0.5).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        al = np.maximum(self.neck_fill(np.where(inside > 0, 1.0, M).astype(np.float32), f), 0)
        for x in (self.LOWER, self.front):
            if x is not None:
                al = np.maximum(al, x)
        cov = self.sheet_cover(phi0, phi1)
        out = L.copy()
        # ---- room side: night falls on the wall, the label, the sheet edge's contact shadow, all behind the speaker
        bgk = 1 - al
        night = float(smooth(270.0, 332.0, phi)) * NIGHT
        if night > 0:
            out = out * (1 - (night * bgk)[..., None])
        la = self.label * float(0.72 * smooth(self.label_on, self.label_on + 0.1, t) + 0.28 * smooth(self.label_bright, self.label_bright + 0.12, t))
        la = la * (t < self.ticks[-1][0] + self.tick_d)
        if np.any(la):
            k = (la * bgk)[..., None]
            out = out * (1 - k) + self.paint(out) * k
        if 0.5 < phi < 359.5:
            es = self.edge_shadow(phi)
            out = out * (1 - (es * bgk)[..., None])
        # ---- sheet side: the speaker, unmixed from the room right behind the edge, over the sheet and their shadow
        if cov.max() > 0:
            def shift(a, dx, dy):
                return cv2.warpAffine(a, np.float32([[1, 0, dx], [0, 1, dy]]), (self.W, self.H), borderMode=cv2.BORDER_REPLICATE)
            s1 = cv2.GaussianBlur(shift(M, SHADOW["dx"], SHADOW["dy"]), (0, 0), SHADOW["blur"]) * SHADOW["op"]
            s2 = cv2.GaussianBlur(shift(M, 12, 8), (0, 0), 7) * 0.24
            shade = 1 - np.clip(s1 + s2 - s1 * s2, 0, 1)
            sheet = self.art * shade[..., None] + self.ink * ((1 - shade) * 0.25)[..., None]
            grain = self.rng.normal(0, 1.3, (self.H // 2, self.W // 2)).astype(np.float32)
            sheet = sheet + cv2.resize(grain, (self.W, self.H), interpolation=cv2.INTER_LINEAR)[..., None]
            # a soft hair edge is fine on a dark room; on a bright sheet it greys, so it gets a tighter curve
            tight = smooth(0.20, 0.78, al)
            fg = np.clip(L - (1 - tight)[..., None] * local_bg(L, M), 0, 255) * tight[..., None]
            comp = fg + (1 - tight)[..., None] * sheet
        else:
            comp = out
        k = cov[..., None]
        img = out * (1 - k) + comp * k
        # ---- the hands, behind the speaker. The minute hand first: ink on the sheet, light on the room
        if psi0 != psi1:
            psi_e = psi0 + (psi1 - psi0) * MIN_SHUT
            psi_l = psi0 + (psi_e - psi0) * 0.78
            m = 0.62 * self.blade(psi0, psi_e, 3.2 * self.k) + 0.38 * self.blade(psi_l, psi_e, 3.2 * self.k)
            mk = (m * bgk)[..., None]
            col = self.ink * k + self.paint(img) * (1 - k)
            w = 0.92 * k + 0.75 * (1 - k)
            img = img * (1 - mk * w) + col * mk * w
        # the hour hand: an accent hairline out of the head, grows on its word, leaves with the unwind
        grow = float(smooth(self.t_hand - 1 / FPS, self.t_hand + 4 / FPS, t))
        fade = float(1 - smooth(self.t_unwind[1] - 0.02, self.t_unwind[1] + 0.01, t))
        if grow > 0 and fade > 0:
            h = self.blade(phi0, phi1, 1.9 * max(1.0, self.k)) * smooth(0, 6, grow * 1400 - self.RAD) * fade
            hk = (h * bgk)[..., None]
            img = img * (1 - hk) + self.accent * hk
        return np.clip(img + 0.5, 0, 255).astype(np.uint8)

    def paint(self, img):
        """paint on the real room: light on a dark wall, ink on a bright one, per pixel, so it reads on any room and
        through the night falling on it"""
        lum = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114) / 255
        k = smooth(0.42, 0.58, cv2.GaussianBlur(lum, (0, 0), 6))[..., None]
        return self.ink * k + self.light * (1 - k)

    def jolt(self, img, f):
        """the wedge closing lands: one small shove of the picture"""
        n = f - fxlib.fr(self.ticks[-1][0])
        if n in (0, 1):
            dy = (5.0, -2.0)[n]
            s = 1.004
            M = np.float32([[s, 0, self.W / 2 * (1 - s)], [0, s, self.H / 2 * (1 - s) + dy]])
            return cv2.warpAffine(img, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return img


def unwind_sound(path, dur):
    """the hand spinning back: a ratchet that speeds up, synthesized here (CC0). Click rate rises from about 14 to 70 a
    second as the hand does, each click a short burst of filtered noise on a small wooden body"""
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt
    sr = 48000
    n = int((dur + 0.06) * sr)
    rng = np.random.default_rng(SEED)
    out = np.zeros(n)
    t, k = 0.0, 0
    while t < dur:
        u = t / dur
        rate = 14 + 56 * u ** 1.4
        i = int(t * sr)
        m = min(n - i, int(0.012 * sr))
        burst = rng.standard_normal(m) * np.exp(-np.arange(m) / (0.0018 * sr)) * (0.7 + 0.3 * (k % 2))
        out[i:i + m] += burst
        t += 1 / rate
        k += 1
    click = sosfilt(butter(2, [1800, 7500], "band", fs=sr, output="sos"), out)
    body = sosfilt(butter(2, [380, 900], "band", fs=sr, output="sos"), out) * 0.5
    y = click + body
    y *= np.minimum(1, np.linspace(0, 6, n)) * np.minimum(1, np.linspace(10, 0, n))
    y = y / max(1e-6, np.abs(y).max()) * 0.8
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavfile.write(path, sr, (np.stack([y, y * 0.94], 1) * 32767).astype(np.int16))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="+", type=float, help="write these reel times as jpgs in work/<id>/ instead of the clip")
    a = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(a.project)), a.id
    A, B, frame, words = place(project, fid)
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    S = fxlib.pack(project)
    dial = Dial(project, A, B, frame, words, S, W, H)
    print(f"{fid}: hub {dial.hub[0]:.0f},{dial.hub[1]:.0f}, scale {dial.k:.2f}, crop {frame}, word {WORD!r}, label {LABEL!r}")
    want = {fxlib.fr(t) for t in a.stills} if a.stills else None
    d = out_dir(project, fid)
    work = os.path.join(project, "work", fid)
    wr = None if want else fxlib.Writer(os.path.join(d, f"{fid}.mp4"), W, H, crf=15)
    for (n, live), (_, matte) in zip(fxlib.frames(project, A, B), fxlib.alpha(project, A, B)):
        if want is not None and n not in want:
            continue
        img = dial.jolt(dial.render(n, live, matte), n)
        if wr is not None:
            wr.write(img)
        else:
            os.makedirs(work, exist_ok=True)
            p = os.path.join(work, f"still_{n / FPS:.2f}.jpg")
            cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(p)
    if wr is None:
        return
    wr.close()
    unwind_sound(os.path.join(project, "audio", f"{fid}-unwind.wav"), dial.t_unwind[1] - dial.t_unwind[0])
    print(os.path.join(d, f"{fid}.mp4"))
    tk = dial.ticks
    print("SFX (edit.SOUND['sfx']):")
    print(f'    ({dial.t_hand + 0.06:.3f}, "whoosh-soft", -15),          # the hand comes out from behind the head')
    print(f'    ({tk[0][0]:.3f}, "click", -13),                # the movement engages')
    print(f'    ({tk[0][0]:.3f}, "clicks-run", -24, {tk[-1][0] - tk[0][0]:.2f}),     # the gear under the whirl, to the close')
    for i, (t, _) in enumerate(tk[:-1]):
        print(f'    ({t:.3f}, "tick", {-15 if i % 2 == 0 else -18}),')
    print(f'    ({tk[-1][0]:.3f}, "tick", -9),                 # the wedge closes')
    print(f'    ({tk[-1][0]:.3f}, "impact-low", -14, 0.9),     # and lands, cut short so its tail stays off the next line')
    print(f'    dict(at={dial.t_unwind[0]:.3f}, name="{fid}-unwind", db=-9, align="start"),   # audio/{fid}-unwind.wav')


if __name__ == "__main__":
    main()
