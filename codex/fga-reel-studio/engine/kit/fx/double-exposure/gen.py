#!/usr/bin/env python3
"""double-exposure: the title-sequence look, pre-rendered for one window.

A hard cut to a flat field in the creator's ground, the speaker's live silhouette on it in high-contrast mono, and real
footage screened into their body per pixel: strongest in the chest and shoulders, nothing across the face, so the eyes
and mouth stay clear and in sync. The figure fades off into the field at the chest. The mono is a colour-filter mix
picked per take so the speaker's top goes dark and works as the window; the mic and boom (when the project has a mic
layer) are painted out of them with cloth cloned along the clothes' own repeat. The inner footage hard-cuts on the
words. The line itself runs over it as title credits (fx.js, CREDITS there).

Run: PY fx/<id>/gen.py <project> [<id>] [--look dark|light] [--stills T ...]
     PY fx/<id>/gen.py --survey FILE ...        the windows of each clip with the most motion in the chest band
  reads   <project>/edit.py (the FX entry <id>: at, end), timeline.json (the crop the window is in), words.json (the cue
          words), public/clean.mp4, public/subject.webm, work/tracks/track.json (the face), style/ (the pack), the
          INNER clips, public/plates/mic_<FRAME>.webm when there is one
  writes  <project>/fx/<id>/exposure.mp4 and fx.html; --stills T writes PNGs of those output times to
          <project>/work/<id>/ and nothing else
<id> defaults to this script's folder name. Rerun it whenever the window, the cut, INNER or the look changes.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True       # nothing generated may land in an fx folder: everything in it gets published
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- the table: everything that changes per video ------------------------------------------------------------------
LOOK = "dark"        # dark: a field of the pack's dark ground, the speaker printed in its light (the film-title look).
                     # light: the paper version on the pack's light ground: more photographic, far louder in a dark
                     # video, and any dark fringe in the matte shows
# What plays inside the speaker, in order. Each slot starts on its cue word (`on`, searched in order from the window's
# start) or `at` seconds after the start when the word isn't spoken, and runs until the next slot (the last one to the
# window's end). Before the first slot the figure is empty: that's the moment the role line reads alone.
#   src    the creator's clip, a file in the project (its path relative to the project). "" = the next file in
#          <project>/fx/<id>/inner/ (by name); none there either = a labelled placeholder page until the real clip is in
#   t0     the clip's second to start from; None = its busiest stretch (--survey prints them)
#   scale  1 = the clip as wide as the frame; dx, dy shift it (px); dy None = centred on the chest
#   gamma  None = read off the clip, so its mids land where the others' do; a number pins it (over 1 darkens a
#          bright clip's mids, under 1 lifts a dark one)
#   kind="type": a page typed live in the pack's text face instead of a clip: `done` lines already set, `typed` typing
#          on. Only the creator's real words (a script line, a caption they wrote)
# Choose clips with visible motion and a wide frame: a talking head at full size fights the speaker's real face.
INNER = [
    dict(on="", at=0.60, src="", t0=None, scale=1.0, dx=0, dy=None, gamma=None),
    dict(on="", at=1.20, src="", t0=None, scale=1.0, dx=0, dy=None, gamma=None),
    dict(on="", at=1.90, src="", t0=None, scale=1.0, dx=0, dy=None, gamma=None),
    # dict(on="writing", at=1.20, kind="type", done=["A real line of", "the creator's script."], typed="Typed live."),
]
PLACEHOLDER = ["PLACEHOLDER", "your clip {n}"]   # the page a slot shows until it has a clip ({n} = the slot's number)

# ---- where things sit: read off the footage (the face track over the window). Rows are in face heights below the chin;
# the px overrides pin one by hand, measured on a still.
FADE_K = (0.74, 1.44)          # the silhouette fades off into the field across these rows (the chest)
FADE = None                    # (y0, y1) px override
HAND_FADE_K = (0.41, 1.12)     # the speaker's own image (hands, clothes) fades earlier, so the chest ends up pure footage
HAND_FADE = None               # (y0, y1) px override
BODY_START_K = (-0.03, 0.32)   # the footage ramps in over these rows below the chin, frame by frame
SIDE_FADE = 0.18               # and fades out toward the frame's left and right edges over this share of its width, so
                               # on a close-up whose shoulders fill the frame it sits in the body, not in a band
CLIP_Y = 0.50                  # a clip with dy None is centred this far down the chest (0 = the shoulders, read off the
                               # matte; 1 = where the figure has faded out)
TYPE_K = dict(size=0.27, max=96, lead=1.10, width=2.4)   # the typed page: size in face widths (at most max px, and
                                                         # small enough that every line sits between the shoulders
                                                         # and the fade), line height in sizes, widest line in face
                                                         # widths
FACE_CLEAR = (0.92, 1.20)      # footage is gone inside this normalized face ellipse, full outside it
FACE_ELLIPSE = (0.62, 0.66)    # the clear zone's half width / half height, in the track's face width / height
CREDIT_Y = 0.719               # fx.html: the top of the credits as a share of the frame height (1380 on 1920)
FRAME = None                   # the crop the window is in (an edit.FRAMES name) for the mic layer; None = timeline.json
MONO_MIX = None                # (r, g, b) override of the colour filter; None = picked from FILTERS for the clothes
FILTERS = {                    # a b/w photographer's filters: the one that sends the clothes darkest against the face wins
    "green": (0.12, 0.70, 0.18),   # red and warm clothes go dark
    "red": (0.70, 0.22, 0.08),     # blue and green clothes go dark
    "blue": (0.10, 0.25, 0.65),    # yellow and orange clothes go dark
    "none": (0.30, 0.59, 0.11),
}
KNIT_REPEAT = None             # [(dx, dy)] px override of the clothes' repeat (cloth cloned over the mic); None = measured

# ---- the print: the same on every take
FOOT_LEVELS = (0.05, 0.86, 0.85)     # inner footage: black, white, gamma
CLIP_MID = 0.30                      # where a clip's median lands after its gamma (gamma None): bright clips darken
MONO_LEVELS = (0.055, 0.80, 0.86)    # the speaker's mono: black, white (lifted when the face would clip), gamma
CONTRAST = 1.12                      # S-curve around .5
KNIT = 0.55                          # the speaker's own mono is dimmed to this in the chest, so the footage leads there
CLARITY = 0.18                       # large-radius local contrast: the photographic bite on the face
GRAIN = (0.9, 3.4)                   # levels of grain on the field, on the figure
TRIM = (6, 3, 6)                     # the renderer lands a dark flat colour this far low (measured through fxclip): the
                                     # darks are sent this much brighter so the field reads as the pack's colour
INK_K = 0.5                          # the figure's blacks in the dark look: the field colour times this
NEAR_BLACK, INK_LIFT = 32, 0.12      # a dark ground under this luma (0-255) is near-black: the figure's blacks print
                                     # this far from it toward the pack's light, so dark clothes still read
SEED = 11
FPS = 30
W, H = 1080, 1920                    # set from public/clean.mp4


try:
    import fxlib  # noqa: E402  (setup puts the kit's pipeline on PY's import path)
except ImportError:                  # another Python, or the library folder itself: KIT/pipeline by hand
    sys.path.insert(0, os.path.join(os.environ.get("REEL_KIT_DIR") or os.path.join(HERE, "..", ".."), "pipeline"))
    try:
        import fxlib  # noqa: E402
    except ImportError:
        sys.exit("run this with the kit's Python (PY): setup puts the kit's pipeline on its import path")

fr = fxlib.fr


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- the project
def cue(project, text, after, before):
    """the start of the spoken word `text` at or after `after` (like wordAt in fx.js), None when it isn't spoken
    before `before` or the project has no words.json yet"""
    if not text or not os.path.exists(os.path.join(project, "words.json")):
        return None
    t = fxlib.word_at(project, text, after)
    return t if t is not None and t < before else None


class Face:
    """the face over the window from the track: per frame (nearest frame with a face when one is missing) and the
    median, which places the rows that hold still (the fades, the typed page, the clips)"""

    def __init__(self, project, A, B):
        frames = fxlib.tracks(project)["frames"]
        n0, n1 = fr(A), max(fr(B), fr(A) + 1)
        self.by = {n: (frames[n] or {}).get("face") for n in range(n0, min(n1, len(frames)))}
        have = sorted(n for n, f in self.by.items() if f)
        if not have:
            sys.exit(f"no face in work/tracks/track.json between {A:.2f} and {B:.2f}: the effect keeps the face clear "
                     "by the track")
        self.have = have
        med = lambda k: float(np.median([self.by[n][k] for n in have]))   # noqa: E731
        self.cx, self.cy, self.w, self.h, self.chin = med("cx"), med("cy"), med("w"), med("h"), med("chin")
        self.chest = self.chin + 0.25 * self.h       # the top of the chest: measured on the matte by chest_from()

    def chest_from(self, al):
        """the first row below the chin where the speaker's silhouette is two faces wide: the shoulders"""
        rows = (al > 127).sum(axis=1)
        y0 = int(self.chin + 0.1 * self.h)
        wide = np.nonzero(rows[y0:] >= 2.0 * self.w)[0]
        if len(wide):
            self.chest = float(y0 + wide[0])

    def at(self, n):
        if self.by.get(n):
            return self.by[n]
        return self.by[min(self.have, key=lambda k: abs(k - n))]

    def rows(self, k, px):
        """a (y0, y1) pair: the px override, else face heights below the median chin"""
        return tuple(px) if px else (self.chin + k[0] * self.h, self.chin + k[1] * self.h)


# ---------------------------------------------------------------- the inner footage
def clip_frames(src, t0, n):
    """n frames of src from second t0 (fewer when it ends sooner), scaled to the frame's width, as rgb; a clip taller
    than the frame keeps its middle"""
    w, h = fxlib.size(src)
    hh = max(2, int(round(h * W / w / 2)) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", src, "-frames:v", str(n), "-an",
                          "-vf", f"scale={W}:{hh}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    out = np.frombuffer(raw, np.uint8)
    k = len(out) // (hh * W * 3)
    out = out[:k * hh * W * 3].reshape(k, hh, W, 3)
    if hh > H:
        y0 = (hh - H) // 2
        out = out[:, y0:y0 + H]
    return out


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def motion(path):
    """per-frame motion (15 fps) in the chest band of a clip, hard cuts left out, so a window is judged by what moves"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "fps=15,scale=108:192", "-an", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    g = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108).astype(np.float32)[:, 55:150]
    if len(g) < 2:
        return np.zeros(1, np.float32)
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
    return np.where(d > 25, 0, d)


def busiest(path, length):
    """the start (s) of the stretch of `length` seconds with the most motion"""
    d = motion(path)
    k = max(1, round(length * 15))
    if len(d) <= k:
        return 0.0
    s = np.convolve(d, np.ones(k) / k, "valid")
    return round(int(np.argmax(s)) / 15, 2)


def survey(paths):
    """the windows of each clip with the most motion in the chest band, by frame difference, ignoring hard cuts"""
    for p in paths:
        d = motion(p)
        s = np.convolve(d, np.ones(18) / 18, "valid") if len(d) > 18 else d
        top = []
        for i in np.argsort(-s):
            if all(abs(i - j) > 30 for j in top):
                top.append(int(i))
            if len(top) == 6:
                break
        print(p, [(round(i / 15, 2), round(float(s[i]), 1)) for i in top])


def to_mono_footage(f, gamma=1.0):
    g = (0.30 * f[..., 0] + 0.59 * f[..., 1] + 0.11 * f[..., 2]) / 255.0
    b, w, gm = FOOT_LEVELS
    return np.clip((g - b) / (w - b), 0, 1) ** (gm * gamma)


def place(g, scale, dx, dy):
    M = np.float32([[scale, 0, dx + W * (1 - scale) / 2], [0, scale, dy]])
    return cv2.warpAffine(g, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=0.0)


class Inner:
    """what's inside the speaker at frame i, as mono 0..1 on the frame, or None. Clips load once; pages are drawn per
    frame"""

    def __init__(self, project, fid, A, B, face, fade, credit_top):
        self.project, self.face, self.cache, self.fade, self.fade_end = project, face, {}, fade, fade[1]
        self.credit_top = credit_top
        folder = sorted(p for p in glob.glob(os.path.join(project, "fx", fid, "inner", "*"))
                        if p.lower().endswith((".mp4", ".mov", ".m4v", ".webm", ".mkv")))
        starts, prev = [], A
        for e in INNER:
            t = cue(project, e.get("on"), prev, B)
            if t is None:
                if e.get("on"):
                    print(f"  cue word {e['on']!r} not spoken in the window: slot at {A + e.get('at', 0):.2f}")
                t = A + e.get("at", 0)
            t = max(t, prev if not starts else starts[-1] + 1 / FPS)
            starts.append(t)
            prev = t
        self.slots = []
        for k, e in enumerate(INNER):
            a, b = starts[k], (starts[k + 1] if k + 1 < len(INNER) else B)
            if a >= B - 1 / FPS or b <= a:
                continue
            e = dict(e)
            if e.get("kind") != "type":
                src = os.path.expanduser(e.get("src") or "")
                if src and not os.path.isabs(src):
                    src = os.path.join(project, src)
                if not src and folder:
                    src = folder.pop(0)
                if not src or not os.path.exists(src):
                    if src:
                        print(f"  slot {k + 1}: {src} not found")
                    e = dict(kind="type", done=[PLACEHOLDER[0]], typed=PLACEHOLDER[1].format(n=k + 1), placeholder=True)
                else:
                    e["src"] = src
                    if e.get("t0") is None:
                        e["t0"] = busiest(src, b - a)
                    if e["t0"] + (b - a) > duration(src) + 1e-3:
                        e["t0"] = max(0.0, duration(src) - (b - a))
            e["a"], e["b"] = a, b
            self.slots.append(e)
        self.font_size = max(36, min(TYPE_K["max"], round(TYPE_K["size"] * face.w)))

    def report(self):
        for k, e in enumerate(self.slots):
            what = ("PLACEHOLDER (no clip yet)" if e.get("placeholder") else
                    "typed page" if e.get("kind") == "type" else f"{e['src']} from {e['t0']:.2f}s")
            print(f"  inside {e['a']:.2f}-{e['b']:.2f}: {what}")
        return sum(1 for e in self.slots if e.get("placeholder"))

    def typed(self, e, i):
        f0, f1 = fr(e["a"]), fr(e["b"])
        done, typing = list(e.get("done") or []), e.get("typed") or ""
        n = int(round(len(typing) * min(1.0, (i - f0 + 1) / max(1, (f1 - f0) * 0.82))))
        lines = done + [typing[:n]]
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        top = max(self.face.chest, self.face.chin + 0.75 * BODY_START_K[1] * self.face.h)   # on the chest, where the
                                                                                       # footage is at full strength
        if "_font" not in e:                  # sized once per slot: every line between the shoulders and the fade
            n = len(done) + 1
            bottom = min(self.fade[0] + 0.4 * (self.fade[1] - self.fade[0]), self.credit_top - 12)
            size = int(min(self.font_size, (bottom - top) / (1.05 + TYPE_K["lead"] * (n - 1))))
            font = fxlib.font(self.project, "text", max(12, size))
            widest = max(d.textlength(x, font=font) for x in done + [typing])
            room = min(W - 120, TYPE_K["width"] * self.face.w)
            if widest > room:
                size = int(size * room / widest)
                font = fxlib.font(self.project, "text", max(12, size))
                widest = max(d.textlength(x, font=font) for x in done + [typing])
            if size < 28:
                print(f"  WARNING the typed page sets at {size}px: too little chest in this framing for "
                      f"{n} lines; fewer or shorter lines")
            e["_font"], e["_size"], e["_widest"] = font, max(12, size), widest
        font, size, widest = e["_font"], e["_size"], e["_widest"]
        lead = size * TYPE_K["lead"]
        y0 = top + 0.8 * size
        x0 = round(W / 2 - widest / 2)
        for k, ln in enumerate(lines):
            d.text((x0, y0 + k * lead), ln, font=font, fill=255, anchor="ls")
        x1 = x0 + d.textlength(lines[-1], font=font) + 8
        y = y0 + (len(lines) - 1) * lead
        d.rectangle([x1, y - size * 0.70, x1 + max(3, size // 15), y + size * 0.10], fill=255)
        return np.asarray(im, np.float32) / 255

    def at(self, i):
        for k, e in enumerate(self.slots):
            f0, f1 = fr(e["a"]), fr(e["b"])
            if f0 <= i < f1:
                if e.get("kind") == "type":
                    return self.typed(e, i) * e.get("gain", 1.0)
                if k not in self.cache:
                    got = clip_frames(e["src"], e["t0"], f1 - f0)
                    if not len(got):
                        sys.exit(f"{e['src']}: no frames from {e['t0']:.2f}s")
                    self.cache[k] = got
                    if e.get("gamma") is None:       # exposed like the others: its mids land on CLIP_MID
                        m = float(np.median(to_mono_footage(got[::max(1, len(got) // 6)].astype(np.float32))))
                        e["gamma"] = float(np.clip(np.log(CLIP_MID) / np.log(min(max(m, 0.05), 0.95)), 0.6, 4.5))
                        print(f"  {os.path.basename(e['src'])}: mids at {m:.2f}, gamma {e['gamma']:.2f}")
                f = self.cache[k][min(i - f0, len(self.cache[k]) - 1)]
                scale = e.get("scale", 1.0)
                dy = e.get("dy")
                if dy is None:                       # centred on the chest
                    dy = self.face.chest + CLIP_Y * (self.fade_end - self.face.chest) - f.shape[0] * scale / 2
                return place(to_mono_footage(f.astype(np.float32), e["gamma"]), scale, e.get("dx", 0), dy) \
                    * e.get("gain", 1.0)
        return None


# ---------------------------------------------------------------- the speaker in mono
def gear_mask(project, crop):
    """the mic and boom from the project's mic layer (plate_finish.py), or None: without one nothing is painted out"""
    path = os.path.join(project, "public", "plates", f"mic_{crop}.webm")
    if not os.path.exists(path):
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-ss", "1", "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True).stdout
    if len(raw) != W * H * 4:
        print(f"  {path} is not {W}x{H}: no gear mask")
        return None
    a = np.frombuffer(raw, np.uint8).reshape(H, W, 4)[..., 3]
    m = cv2.dilate((a > 18).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    return m if m.any() else None


def nc(img, ok, s):
    """normalized convolution, falling back to a wider reach in the middle of a big hole"""
    m = ok.astype(np.float32)
    a = cv2.GaussianBlur(img * m, (0, 0), s)
    b = cv2.GaussianBlur(m, (0, 0), s)
    a2 = cv2.GaussianBlur(img * m, (0, 0), s * 4)
    b2 = cv2.GaussianBlur(m, (0, 0), s * 4)
    w = np.clip(b * 6, 0, 1)
    return (a / np.maximum(b, 1e-3)) * w + (a2 / np.maximum(b2, 1e-3)) * (1 - w)


def knit_offsets(detail, bad, cloth, chin, face_w):
    """the clothes' own repeat (a knit's lattice), so detail cloned over the mic lines up with the cloth round it: the
    strongest peaks of the detail's autocorrelation in the clean cloth near the hole. Plain cloth has no repeat: then a
    ring of offsets in face widths, any clean cloth nearby carries the same grain"""
    D, V = round(0.69 * face_w), round(0.50 * face_w)
    ring = [(D, 0), (-D, 0), (0, V), (2 * D, 0), (-2 * D, 0), (D, V), (-D, V), (0, 2 * V)]
    ys, xs = np.nonzero(bad)
    if not len(ys):
        return ring
    pad = int(1.6 * face_w)
    y0, y1 = max(int(chin), int(ys.min()) - pad), min(H, int(ys.max()) + pad)
    x0, x1 = max(0, int(xs.min()) - pad), min(W, int(xs.max()) + pad)
    if y1 - y0 < 64 or x1 - x0 < 64:
        return ring
    good = (cloth[y0:y1, x0:x1] & ~bad[y0:y1, x0:x1]).astype(np.float32)
    if good.sum() < 4000:
        return ring
    d = detail[y0:y1, x0:x1] * good
    h, w = d.shape
    shp = (2 * h, 2 * w)
    Fd, Fg = np.fft.rfft2(d, s=shp), np.fft.rfft2(good, s=shp)
    num = np.fft.fftshift(np.fft.irfft2(Fd * np.conj(Fd), s=shp))
    cnt = np.fft.fftshift(np.fft.irfft2(Fg * np.conj(Fg), s=shp))
    c0 = num[h, w] / max(cnt[h, w], 1)
    if c0 <= 1e-9:
        return ring
    ac = num / np.maximum(cnt, 1) / c0
    oy, ox = np.mgrid[-h:h, -w:w]
    r = np.hypot(ox, oy)
    ok = (cnt > 0.25 * cnt[h, w]) & (r >= 0.08 * face_w) & (r <= 1.5 * face_w)
    peaks = (ac == ndi.maximum_filter(ac, size=9)) & ok & (ac > 0.3)
    cand = sorted(zip(ac[peaks].tolist(), ox[peaks].tolist(), oy[peaks].tolist()), reverse=True)[:8]
    return [(int(x), int(y)) for _, x, y in cand] if len(cand) >= 4 else ring


class Mono:
    """the speaker's high-contrast mono with the mic and boom painted out of it: cloth shading from round the hole,
    detail cloned from clean cloth along its repeat. A hand in front of the mic keeps its real pixels"""

    def __init__(self, gear, mix, face, white=None):
        self.gear, self.mix, self.face, self.repeat = gear, mix, face, None
        self.white = white or MONO_LEVELS[1]

    def __call__(self, rgb, al):
        f = rgb.astype(np.float32) / 255
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        L = self.mix[0] * r + self.mix[1] * g + self.mix[2] * b
        if self.gear is not None:
            skin = ((r > 0.33) & (r - b > 0.10) & (r < 2.4 * g + 0.03)).astype(np.uint8)
            skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            n, lab, st, _ = cv2.connectedComponentsWithStats(skin)
            for k in range(1, n):
                if st[k, cv2.CC_STAT_AREA] < 900:                 # a glint on the mic, not a hand
                    skin[lab == k] = 0
            skin = skin.astype(bool)
            hole = (self.gear > 0) & ~skin
            low = nc(L, ~hole, 15)
            detail = L - cv2.GaussianBlur(L, (0, 0), 15)
            bad = cv2.dilate((hole | skin).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
            if self.repeat is None:
                self.repeat = KNIT_REPEAT or knit_offsets(detail, bad, al > 127, self.face.chin, self.face.w)
                print(f"  clothes repeat (cloned over the mic): {self.repeat}")
            # detail cloned along the repeat, each pixel from the first clean candidate, so the patch has the same
            # contrast as the cloth round it
            clone = np.zeros_like(L)
            todo = hole.copy()
            for dx_, dy_ in self.repeat:
                src_ok = ~np.roll(np.roll(bad, dy_, 0), dx_, 1)
                take = todo & src_ok
                clone[take] = np.roll(np.roll(detail, dy_, 0), dx_, 1)[take]
                todo &= ~take
            soft = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.6)
            L = L * (1 - soft) + (low + clone) * soft
        # phone and 4K sources carry compression blocks: iron them out before the contrast finds them, edges stay
        L = cv2.bilateralFilter(L, 5, 0.025, 1.6)
        bp, _, gm = MONO_LEVELS
        wp = self.white
        t = np.clip((L - bp) / (wp - bp), 0, 1) ** gm
        t = np.clip(t + CLARITY * (t - cv2.GaussianBlur(t, (0, 0), 36)), 0, 1)
        t = np.clip(0.5 + (t - 0.5) * CONTRAST, 0, 1)
        return t * t * (3 - 2 * t) * 0.5 + t * 0.5


def pick_filter(rgb, al, face, fade):
    """the colour filter that sends the speaker's clothes darkest against their face, the way a b/w photographer
    picks one: their top has to go dark to work as the window"""
    f = rgb.astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fm = (((xx - face.cx) / (0.40 * face.w)) ** 2 + ((yy - face.cy) / (0.45 * face.h)) ** 2) < 1
    torso = (al > 127) & (yy > face.chin + 0.3 * face.h) & (yy < fade[0] + 0.5 * (fade[1] - fade[0]))

    def lum(mix):
        return f[..., 0] * mix[0] + f[..., 1] * mix[1] + f[..., 2] * mix[2]

    def high(mix):                                   # the face's highlights under this filter
        return float(np.percentile(lum(mix)[fm], 97)) if fm.sum() >= 200 else MONO_LEVELS[1]
    if MONO_MIX:
        return tuple(MONO_MIX), "MONO_MIX", high(MONO_MIX)
    if fm.sum() < 200 or torso.sum() < 2000:
        return FILTERS["green"], "green (too little clothes in frame to choose)", high(FILTERS["green"])

    def score(mix):
        L = lum(mix)
        face_ = L[fm]
        # the clothes darkest against the face, but never a filter that blows the face out: highlights near the mono's
        # white point turn to flat paper (dark clothes read the same under every filter, so the face decides)
        return float(face_.mean() - L[torso].mean()) - 3 * max(0.0, float(np.percentile(face_, 90)) - (MONO_LEVELS[1] - 0.10))
    name = max(FILTERS, key=lambda k: score(FILTERS[k]))
    return FILTERS[name], name, high(FILTERS[name])


def guided(I, p, r, eps):
    """fast guided filter: pulls the soft matte onto the footage's real edges"""
    k = (2 * r + 1, 2 * r + 1)
    box = lambda x: cv2.boxFilter(x, cv2.CV_32F, k)   # noqa: E731
    mI, mp = box(I), box(p)
    a = (box(I * p) - mI * mp) / (box(I * I) - mI * mI + eps)
    b = mp - a * mI
    return box(a) * I + box(b)


def silhouette(rgb, al):
    """one clean bust: holes filled, biggest blob, then the soft matte snapped to the footage's real edges"""
    b = al > 127
    b = ndi.binary_fill_holes(b)
    lab, n = ndi.label(b)
    if n > 1:
        b = lab == (1 + int(np.argmax(ndi.sum(b, lab, range(1, n + 1)))))
    a = cv2.GaussianBlur(al.astype(np.float32) / 255, (0, 0), 0.8) * cv2.GaussianBlur(
        cv2.dilate(b.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 1.2)
    a = np.maximum(a, cv2.erode(b.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32))
    I = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    g = guided(I, a, 4, 1e-4)
    return np.clip((g - 0.5) * 1.7 + 0.5, 0, 1)


def looks(S):
    """field / ink / paper for each look, from the pack: the field is a ground, the speaker's blacks print in a deeper
    shade of it (dark look) or in ink (light look), their whites in the pack's light. A near-black ground has no
    deeper shade to give: dark clothes would vanish into it, so their blacks print a step toward the light instead
    and the silhouette reads as a dark grey figure on the black"""
    C = S["colors"]
    rgb = lambda k: np.array(C[k][:3], np.float32)   # noqa: E731
    dark, light = rgb("dark"), rgb("light")
    near_black = float(dark @ np.array([0.299, 0.587, 0.114], np.float32)) < NEAR_BLACK
    ink = dark + (light - dark) * INK_LIFT if near_black else dark * INK_K
    return {"dark": dict(field=dark, ink=ink, paper=light),
            "light": dict(field=light, ink=rgb("ink"), paper=light)}


class Composer:
    def __init__(self, face, mono, look, rows):
        self.face, self.mono, self.look = face, mono, look
        self.yy, self.xx = np.mgrid[0:H, 0:W].astype(np.float32)
        y = np.arange(H, dtype=np.float32)
        self.fade = (1 - sstep(rows["fade"][0], rows["fade"][1], y))[:, None]
        self.hand = (1 - sstep(rows["hand"][0], rows["hand"][1], y))[:, None]
        x = np.arange(W, dtype=np.float32)
        self.sides = (sstep(0, SIDE_FADE * W, x) * sstep(W, W * (1 - SIDE_FADE), x))[None, :]

    def face_mask(self, e):
        rx, ry = e["w"] * FACE_ELLIPSE[0], e["h"] * FACE_ELLIPSE[1]
        r = np.sqrt(((self.xx - e["cx"]) / rx) ** 2 + ((self.yy - e["cy"]) / ry) ** 2)
        return sstep(FACE_CLEAR[0], FACE_CLEAR[1], r), e["chin"], e["h"]

    def __call__(self, rgb, al, inner, e, rng):
        field, ink, paper = (self.look[k] for k in ("field", "ink", "paper"))
        a = silhouette(rgb, al)
        K_face, chin, fh = self.face_mask(e)
        y = np.arange(H, dtype=np.float32)
        K = K_face * sstep(chin + BODY_START_K[0] * fh, chin + BODY_START_K[1] * fh, y)[:, None] * self.sides
        M = self.mono(rgb, al) * self.hand * (1 - (1 - KNIT) * K)
        F = (inner * K) if inner is not None else 0.0
        t = 1 - (1 - M) * (1 - F)                    # screen, per pixel: two exposures on one negative
        t = t[..., None]
        fig = ink * (1 - t) + paper * t
        A_ = (a * self.fade)[..., None]
        out = field * (1 - A_) + fig * A_
        g = rng.standard_normal((H, W)).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 0.7) * 1.9
        amp = GRAIN[0] + (GRAIN[1] - GRAIN[0]) * A_[..., 0]
        out = out + (g * amp)[..., None]
        return out + np.array(TRIM, np.float32) * (1 - np.clip(out.mean(axis=2, keepdims=True) / 255 * 1.6, 0, 1))


# ---------------------------------------------------------------- fx.html
def write_html(d, look, n_frames):
    light = look == "light"
    top = round(H * CREDIT_Y)
    tag = (f'<video id="{{{{ID}}}}-v" src="fx/{{{{ID}}}}/exposure.mp4" muted playsinline data-start="{{{{START}}}}" '
           f'data-media-start="0.0010" data-duration="{n_frames / FPS:.4f}" data-track-index="{{{{T0}}}}" '
           f'style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;"></video>')
    css = "\n".join([
        "<style>",
        f"#{{{{ID}}}}-credits {{ position:absolute; left:0; top:{top}px; width:{W}px; height:110px; }}",
        f"#{{{{ID}}}} .{{{{ID}}}}-credit {{ position:absolute; left:0; top:0; width:{W}px; text-align:center; opacity:0; }}",
        "#{{ID}} .{{ID}}-role { display:inline-block; font-family:var(--font-text); font-weight:400; font-size:36px;"
        f" line-height:44px; white-space:nowrap; color:var({'--c-muted-light' if light else '--c-muted-dark'}); }}",
        "#{{ID}} .{{ID}}-name { display:inline-block; font-family:var(--font-display); font-style:var(--display-style);"
        " font-weight:var(--display-weight); font-size:50px; line-height:56px; letter-spacing:.26em;"
        f" padding-left:.26em; white-space:nowrap; color:var({'--c-ink' if light else '--c-light'}); }}",
        "#{{ID}} .{{ID}}-line { display:block; height:auto; }",
        "</style>",
    ])
    head = ("<!-- double-exposure (cam): written by gen.py. exposure.mp4 is the picture for this window, pre-rendered "
            "(frame 0 is the window's first frame,\n     the speaker's lips are the live frames); fx.js sets the line "
            "over it as title credits on the words. -->")
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(f"{head}\n{tag}\n<div id=\"{{{{ID}}}}-credits\"></div>\n{css}\n")


def sound_lines(A, inner):
    """the house mix, in kit sounds: a deep whoosh on the cut to the field, projector chatter under the first clip,
    keys under a typed page, a shutter on the last slot"""
    out = [f"    ({A:.3f}, \"whoosh-deep\", -16),   # the hard cut to the field"]
    clips = [e for e in inner.slots if e.get("kind") != "type"]
    for e in inner.slots:
        if e.get("kind") == "type" and not e.get("placeholder"):
            out.append(f"    dict(at={e['a']:.3f}, name=\"typing\", db=-12, max_len={e['b'] - e['a']:.2f}, align=\"start\"),   # keys under the page")
    if clips:
        e = clips[0]
        out.append(f"    dict(at={e['a']:.3f}, name=\"clicks-run\", db=-18, max_len={min(0.6, e['b'] - e['a']):.2f}, align=\"start\"),   # projector chatter")
    if len(inner.slots) > 1:
        out.append(f"    ({inner.slots[-1]['a']:.3f}, \"shutter\", -14),   # the last slot cuts in")
    return out


def keep_js(out_dir):
    """run from the library folder on a project that has no copy yet: its fx.js comes along with the clip"""
    if not os.path.exists(os.path.join(out_dir, "fx.js")) and os.path.realpath(out_dir) != os.path.realpath(HERE):
        shutil.copy(os.path.join(HERE, "fx.js"), os.path.join(out_dir, "fx.js"))


# ---------------------------------------------------------------- run
def main():
    global W, H
    if "--survey" in sys.argv:
        return survey(sys.argv[sys.argv.index("--survey") + 1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--look", choices=("dark", "light"), default=LOOK)
    ap.add_argument("--stills", nargs="+", type=float, metavar="T", help="output times to write as PNGs, nothing else")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    S = fxlib.pack(project)
    face = Face(project, A, B)
    for _, al in fxlib.alpha(project, A, A + 1 / FPS):
        face.chest_from(al)
    rows = dict(fade=face.rows(FADE_K, FADE), hand=face.rows(HAND_FADE_K, HAND_FADE))
    credits = round(H * CREDIT_Y)
    if not FADE and rows["fade"][1] > credits + 70:    # a big or low figure: it fades out across the credits, as shot
        k = (credits + 70 - face.chin) / max(1.0, rows["fade"][1] - face.chin)
        rows["fade"] = (face.chin + (rows["fade"][0] - face.chin) * k, credits + 70)
        if not HAND_FADE:
            rows["hand"] = (face.chin + (rows["hand"][0] - face.chin) * k, face.chin + (rows["hand"][1] - face.chin) * k)
    if face.chin > credits:
        print(f"  WARNING the chin (y {face.chin:.0f}) is below the credits (y {credits}): frame the speaker higher, "
              "or lower CREDIT_Y")
    crop = FRAME or fxlib.crop_at(project, A)
    gear = gear_mask(project, crop)
    inner = Inner(project, fid, A, B, face, rows["fade"], credits)
    print(f"double-exposure {fid}: {A:.2f}-{B:.2f}, {W}x{H}, look {args.look}, crop {crop}, "
          f"mic layer {'yes' if gear is not None else 'none (nothing painted out)'}")
    print(f"  face: chin y {face.chin:.0f}, {face.w:.0f}x{face.h:.0f}px; shoulders y {face.chest:.0f}; "
          f"fade rows {rows['fade'][0]:.0f}-{rows['fade'][1]:.0f}")
    placeholders = inner.report()
    out_dir = os.path.join(project, "fx", fid)
    work = os.path.join(project, "work", fid)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    want = None if not args.stills else {fr(t) for t in args.stills}
    look, mono, comp, wr = looks(S)[args.look], None, None, None
    n0, n1 = fr(A), max(fr(B), fr(A) + 1)
    tmp = os.path.join(work, "exposure.tmp.mp4")
    if want is None:
        wr = fxlib.Writer(tmp, w=W, h=H, crf=15)
    written = 0
    for (i, rgb), (_, al) in zip(fxlib.frames(project, A, B), fxlib.alpha(project, A, B)):
        if mono is None:                   # the filter is chosen once, on the window's first frame
            mix, why, high = pick_filter(rgb, al, face, rows["fade"])
            bp = MONO_LEVELS[0]
            wp = max(MONO_LEVELS[1], bp + (high - bp) / 0.93)      # lifted, never lowered: the face never clips
            print(f"  mono filter: {why} {tuple(round(v, 2) for v in mix)}, white point {wp:.2f}")
            mono = Mono(gear, mix, face, wp)
            comp = Composer(face, mono, look, rows)
        written += 1
        if want is not None and i not in want:
            continue
        rng = np.random.default_rng([SEED, i])
        out = comp(rgb, al, inner.at(i), face.at(i), rng)
        u8 = np.clip(out + 0.5, 0, 255).astype(np.uint8)
        if wr:
            wr.write(u8)
        else:
            path = os.path.join(work, f"{args.look}_{i / FPS:.2f}.png")
            cv2.imwrite(path, u8[..., ::-1])
            print(path)
    if wr is None:
        return
    wr.close()
    if written < n1 - n0:
        sys.exit(f"only {written} of {n1 - n0} frames could be read from public/clean.mp4 and subject.webm: "
                 "is the window inside the video?")
    os.replace(tmp, os.path.join(out_dir, "exposure.mp4"))
    write_html(out_dir, args.look, n1 - n0)
    keep_js(out_dir)
    print(f"wrote {out_dir}/exposure.mp4 ({n1 - n0} frames) and fx.html")
    if placeholders:
        print(f"  {placeholders} slot(s) still show a PLACEHOLDER page: put the creator's clips in "
              f"fx/{fid}/inner/ or set INNER src, then rerun")
    print(f"edit.py: KARAOKE hide over the credits, e.g. ({A:.2f}, {B:.2f}); SOUND sfx to start from:")
    print("\n".join(sound_lines(A, inner)))


if __name__ == "__main__":
    main()
