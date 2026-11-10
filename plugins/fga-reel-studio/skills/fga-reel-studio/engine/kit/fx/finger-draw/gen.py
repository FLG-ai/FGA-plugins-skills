#!/usr/bin/env python3
"""finger-draw: a grease-pencil line follows the speaker's real fingertip, so they draw in the air.

Two shapes of take (MODE):
  path      the line is whatever the finger draws between pen down and pen up, in real time, its live end on the
            fingertip, drying up just before the window ends. Needs a take filmed for it (README).
  numeral   the finger rises on the cue word ("one"), holds still at the top (the raised finger IS the numeral) and
            whips away: the line rises with it, melts behind the raised finger, and the whip leaves a hand-drawn 1
            hanging exactly where it stood, its flag drawn by the real whip.
The fingertip is read off the skin per frame (the track's landmark lags up to 70px on fast frames). In numeral mode
the hand is matted per frame with depth, so the 1 it leaves hangs behind the hand. The line's own sound (a china
marker on glass, driven by how fast the ink really moves) is synthesized here from noise, nothing recorded.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills T ...] [--tips]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json (the cue words), public/clean.mp4,
          public/subject.webm (only skin on the speaker counts), work/tracks/track.json (hands, face), style/ (the pack)
  writes  <project>/fx/<id>/finger.mp4 and fx.html, <project>/audio/<id>-marker.wav; work/<id>/ holds the depth and
          matte caches (delete it after a recut). --stills T writes PNGs of those output times there and nothing
          else; --tips prints the fingertip it found on every frame (to fill OVERRIDE)
<id> defaults to this script's folder name. Rerun it whenever the window or the cut changes.
"""
import argparse
import os
import shutil
import sys
import wave

sys.dont_write_bytecode = True       # nothing generated may land in an fx folder: everything in it gets published
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- the table: everything that changes per video ------------------------------------------------------------------
MODE = "path"                # path | numeral (above)
PEN_DOWN = ("", 0.10)        # (cue word, fallback s after the window's start). path: the line starts on this word;
                             # numeral: the word the finger is up on ("one"), the rise is found just before it
PEN_UP = ("", 0.50)          # path: (cue word, fallback s before the window's end): the line stops on this word
SIDE = "auto"                # the drawing hand: "auto" = the one whose fingertip travels furthest, or the track's
                             # side label ("Left" / "Right", as track.json writes it)
LABEL = []                   # [(text, cue word)]: lines of a small mono label beside the drawing, each on its spoken
                             # word, e.g. [("one", "one"), ("reel", "reel")]; [] = no label
LABEL_POS = None             # (x, y) px of the label's top left; None = beside the top of the drawing, where there's room
OVERRIDE = {}                # {frame: (x, y)}: the fingertip by hand where the tracker is wrong (reel frame numbers;
                             # --tips prints the path it found). The per-take fix
SKIP = []                    # frames left out of the line (a landmark kink while the hand rolls)
NUMERAL = dict(foot=None, top=None, whip=None, flag=0.44)   # numeral: the frames the rise starts, the finger stops at
                             # the top, and the last still one before the whip (None = read off the fingertip's path);
                             # the flag is cut at this share of the stem's length
WIPE = (0.26, 0.06)          # the line dries up from this long before the window's end until this long before it (s)
WIDTH = None                 # the line's widest, px; None = WIDTH_K face widths
WIDTH_K = 0.072              # 24px on a face 333px wide

# ---- read off the footage, scaled by the face (the track's median face width over the window)
TIP_INSET_K = 0.021          # the live end sits this far back from the very tip, on the finger's pad
REACH_K = 0.45               # the fingertip is searched this far round the landmark
MARGIN_K = 0.90              # the hand matte's box: the hand's path over the window plus this much round it
GROW_K = 0.156               # the hand matte's gate grows this far past the landmarks
STILL_K, WHIP_K, RISE_K = 0.06, 0.35, 0.25   # numeral, in face heights: the most a held finger moves over 3 frames, the
                             # least a whip moves over 3 frames, the least rise
LOOKBACK = 0.6               # numeral: the rise starts at the finger's lowest point at most this long before its word
MIN_TRACKED = 0.6            # the drawing hand has to be tracked on this share of the line's frames
FACE_W0 = 333.0              # the face width the line's wobble and smoothing were tuned on
FPS = 30
W, H = 1080, 1920            # set from public/clean.mp4


try:
    import fxlib  # noqa: E402  (setup puts the kit's pipeline on PY's import path)
except ImportError:                  # another Python, or the library folder itself: KIT/pipeline by hand
    sys.path.insert(0, os.path.join(os.environ.get("REEL_KIT_DIR") or os.path.join(HERE, "..", ".."), "pipeline"))
    try:
        import fxlib  # noqa: E402
    except ImportError:
        sys.exit("run this with the kit's Python (PY): setup puts the kit's pipeline on its import path")
sys.path.insert(0, HERE)
from handmatte import depth_crop, hand_matte  # noqa: E402


def smooth(a, b, x):
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


# ---------------------------------------------------------------- the fingertip
def skin_model(rgb, face):
    """skin colour read off the speaker's own face (the middle of the face box, Lab), so the fingertip is found on any
    skin under any light. None when the face is too small to sample"""
    if not face:
        return None
    x0, x1 = int(face["cx"] - 0.22 * face["w"]), int(face["cx"] + 0.22 * face["w"])
    y0, y1 = int(face["cy"] - 0.05 * face["h"]), int(face["cy"] + 0.20 * face["h"])     # cheeks and nose, under the eyes
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 - x0 < 12 or y1 - y0 < 12:
        return None
    lab = cv2.cvtColor(np.ascontiguousarray(rgb[y0:y1, x0:x1]), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    L, a, b = lab[:, 0] * 100 / 255, lab[:, 1] - 128, lab[:, 2] - 128
    a0, b0 = float(np.median(a)), float(np.median(b))
    spread = float(np.median(np.hypot(a - a0, b - b0)))
    return dict(a=a0, b=b0, s=max(6.0, 2.5 * spread), L=float(np.percentile(L, 10)))


def skin_prob(rgb, model):
    lab = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2LAB).astype(np.float32)
    L, a, b = lab[..., 0] * 100 / 255, lab[..., 1] - 128, lab[..., 2] - 128
    if model:
        d2 = ((a - model["a"]) ** 2 + (b - model["b"]) ** 2) / (2 * model["s"] ** 2)
        return np.exp(-d2) * smooth(model["L"] - 22, model["L"] - 8, L)
    hue = np.degrees(np.arctan2(b, a))                     # no face to sample: a warm-skin default
    return smooth(24, 34, hue) * smooth(18, 30, L) * smooth(6, 12, np.hypot(a, b))


def find_tip(rgb, h, face, model, R, matte=None):
    """the farthest skin from the wrist, in the blob that holds the palm, inside a cone round palm -> landmark, near
    the landmark. Only skin on the speaker counts (their matte, a little grown): a warm wall or a wooden frame behind
    the finger is skin-coloured too"""
    palm, idx, wrist = np.array(h["palm"]), np.array(h["index"]), np.array(h["wrist"])
    Rb = int(np.linalg.norm(idx - palm) + R + 40)
    x0, x1 = int(max(0, palm[0] - Rb)), int(min(rgb.shape[1], palm[0] + Rb))
    y0, y1 = int(max(0, palm[1] - Rb)), int(min(rgb.shape[0], palm[1] + Rb))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return idx
    p = skin_prob(rgb[y0:y1, x0:x1], model)
    if matte is not None:
        p = p * matte[y0:y1, x0:x1]
    if face is not None:
        yy, xx = np.mgrid[y0:y1, x0:x1]
        e = ((xx - face["cx"]) / (face["w"] * 0.75)) ** 2 + ((yy - face["cy"]) / (face["h"] * 0.78)) ** 2
        p = p * (e > 1)
    p = cv2.GaussianBlur(p.astype(np.float32), (0, 0), 1.5)
    m = cv2.morphologyEx((p > 0.35).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n < 2:
        return idx
    px, py = int(palm[0] - x0), int(palm[1] - y0)
    win = lab[max(0, py - 30):py + 30, max(0, px - 30):px + 30]
    ids = win[win > 0]
    best = np.bincount(ids).argmax() if len(ids) else np.argmax(st[1:, cv2.CC_STAT_AREA]) + 1
    ys, xs = np.nonzero(lab == best)
    pts = np.stack([xs + x0, ys + y0], 1).astype(np.float32)
    v = idx - palm
    v = v / max(1e-3, np.linalg.norm(v))
    d_ = pts - palm
    cosang = (d_ @ v) / (np.linalg.norm(d_, axis=1) + 1e-3)
    ok = (cosang > 0.72) & (np.linalg.norm(pts - idx, axis=1) < R)
    if ok.sum() < 10:
        return idx
    d = np.linalg.norm(pts[ok] - wrist, axis=1)
    return pts[ok][d >= np.percentile(d, 99.5)].mean(0)


def settle(tips, U):
    """keep real moves, calm the jitter while the finger is still: a speed-adaptive low pass, run both ways"""
    def run(v):
        out = v.copy()
        for i in range(1, len(v)):
            sp = np.linalg.norm(v[i] - out[i - 1])
            a = smooth(1.5 * U, 14.0 * U, sp) * 0.75 + 0.25
            out[i] = out[i - 1] + a * (v[i] - out[i - 1])
        return out
    return 0.5 * (run(tips) + run(tips[::-1])[::-1])


def pick_side(F, n0, n1):
    """the hand whose index fingertip travels furthest over the stretch, by the track's side label"""
    if SIDE != "auto":
        return SIDE
    travel = {}
    last = {}
    for n in range(n0, min(n1, len(F))):
        for h in (F[n] or {}).get("hands") or []:
            s = h["side"]
            if s in last:
                travel[s] = travel.get(s, 0.0) + float(np.linalg.norm(np.array(h["index"]) - last[s]))
            last[s] = np.array(h["index"])
    if not travel:
        sys.exit(f"finger-draw: no hand is tracked between {n0 / FPS:.2f} and {n1 / FPS:.2f} s, so there is no finger to "
                 "draw with. It needs a take filmed for it: the drawing hand in frame, one finger moving slowly (README, "
                 "Film this). Pick another line or another effect.")
    side = max(travel, key=travel.get)
    seen = sum(1 for n in range(n0, min(n1, len(F))) if any(h["side"] == side for h in (F[n] or {}).get("hands") or []))
    if seen < MIN_TRACKED * max(1, n1 - n0):
        sys.exit(f"finger-draw: the drawing hand is tracked on only {seen} of {n1 - n0} frames between {n0 / FPS:.2f} and "
                 f"{n1 / FPS:.2f} s: the line would jump. It needs the hand in frame the whole time (README, Film this).")
    return side


def numeral_beats(tips, land, k_word, fh):
    """frame indexes: the foot of the rise (the finger's lowest point shortly before its word), the top (the first frame
    it holds still, risen) on the path read off the skin, and the last held frame before the whip on the landmark path
    (the skin reading jumps once the hand turns, the landmark rides through a fast move). Judged over 3 frames, not 1: a
    held finger drifts and footage repeats frames; a whip covers a lot of ground fast"""
    lo = max(0, k_word - round(LOOKBACK * FPS))
    foot = lo + int(np.argmax(tips[lo:k_word + 1, 1]))

    def d3(p, k):
        return float(np.linalg.norm(p[min(k + 3, len(p) - 1)] - p[k]))
    top = whip = None
    for k in range(foot + 1, len(tips) - 3):
        if tips[foot][1] - tips[k][1] >= RISE_K * fh and d3(tips, k) < STILL_K * fh:
            top = k
            break
    if top is not None:
        for k in range(top + 3, len(land) - 3):
            if d3(land, k) > WHIP_K * fh:
                step = [float(np.linalg.norm(land[j + 1] - land[j])) for j in range(k, k + 3)]
                whip = k + int(np.argmax(step))          # the frame before the biggest jump: the hold's last
                break
    return foot, top, whip


def on_the_rise(frames, tips, n0, fh):
    """a raised finger rises in a near straight line: keyframes the skin reading threw off it (motion blur at the
    bottom) are left out, the foot and the top always stay"""
    a, b = tips[frames[0] - n0].copy(), tips[frames[-1] - n0].copy()
    d = b - a
    L = max(1e-3, float(np.linalg.norm(d)))
    keep = [frames[0]]
    for f in frames[1:-1]:
        p = tips[f - n0] - a
        if abs(p[0] * d[1] - p[1] * d[0]) / L <= 0.12 * fh:
            keep.append(f)
    keep.append(frames[-1])
    for f in range(frames[0], frames[-1] + 1):       # the line's live end rides the same path: thrown frames move too
        if f not in keep:
            i = max(k for k in keep if k < f)
            j = min(k for k in keep if k > f)
            tips[f - n0] = tips[i - n0] + (tips[j - n0] - tips[i - n0]) * (f - i) / (j - i)
    return keep


# ---------------------------------------------------------------- the line
def catmull(pts, step=2.0):
    """a smooth curve through the points, plus for each sample the fractional index along the input, so frames map to
    arc"""
    pts = np.asarray(pts, np.float64)
    if len(pts) == 1:
        pts = np.vstack([pts, pts + [0, 1]])
    P_ = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    out, idx = [], []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        n = max(2, int(np.linalg.norm(p2 - p1) / step))
        for j in range(n):
            t = j / n
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
            out.append(q)
            idx.append(i - 1 + t)
    out.append(P_[-2])
    idx.append(len(pts) - 1)
    return np.array(out), np.array(idx)


def value_noise(shape, sigma, seed):
    r = np.random.default_rng(seed).random(shape, np.float32)
    n = cv2.GaussianBlur(r, (0, 0), sigma)
    return (n - n.min()) / (n.max() - n.min())


def wobble_1d(n, wave_, seed):
    r = np.random.default_rng(seed).normal(0, 1, n + 400)
    k = np.exp(-0.5 * (np.arange(-3 * wave_, 3 * wave_ + 1) / wave_) ** 2)
    return np.convolve(r, k / np.sqrt((k ** 2).sum()), mode="same")[200:n + 200]


class Ink:
    """a dry china marker: the line is a bundle of waxy bristles that skip along their own noise, more toward the edges,
    more where it is pressed lightly. A fixed tooth breaks it further"""

    def __init__(self, width):
        self.width = width
        self.fine = value_noise((H, W), 0.7, 11)
        self.mid = value_noise((H, W), 2.6, 12)
        rng = np.random.default_rng(21)
        self.nb = 21
        self.lat = np.linspace(-1, 1, self.nb) + rng.normal(0, 0.03, self.nb)
        self.val = 0.93 + 0.14 * rng.random(self.nb)
        self.skip, self.wander = [], []
        for i in range(self.nb):
            edge = abs(self.lat[i])
            n = wobble_1d(6000, float(rng.uniform(5, 14) * (1.0 - 0.6 * edge)), 100 + i)   # the edges skip in shorter, drier runs
            self.skip.append((n - n.min()) / (n.max() - n.min()))
            w_ = wobble_1d(6000, float(rng.uniform(18, 40)), 300 + i)
            self.wander.append(0.06 * w_ / (np.abs(w_).max() + 1e-6) * 3)

    def stroke(self, mask, pts, arc, press, wipe, ss, box):
        """adds one stroke to the mask (at ss x, inside box)"""
        x0, y0 = box[0], box[1]
        tang = np.gradient(cv2.GaussianBlur(pts.astype(np.float32), (1, 9), 0), axis=0).astype(np.float64)
        nrm = np.stack([-tang[:, 1], tang[:, 0]], 1) / (np.linalg.norm(tang, axis=1, keepdims=True) + 1e-3)
        half = self.width * 0.5 * (0.30 + 0.70 * press)
        ai = np.clip(arc.astype(int), 0, 5999)
        for b in range(self.nb):
            q = pts + nrm * ((self.lat[b] + self.wander[b][ai]) * half)[:, None]
            edge = abs(self.lat[b])
            on = self.skip[b][ai] > (0.14 + 0.46 * edge ** 2.0 + 0.30 * (1 - press) + wipe * 1.05)
            q8 = np.round((q - [x0, y0]) * ss * 8).astype(np.int32)
            thick = max(1, int(round((self.width / self.nb) * 1.7 * ss * (0.75 + 0.5 * press.mean()))))
            i = 0
            val = int(255 * self.val[b] / 1.07)
            while i < len(q8):
                if not on[i]:
                    i += 1
                    continue
                j = i
                while j + 1 < len(q8) and on[j + 1]:
                    j += 1
                if j > i:
                    cv2.polylines(mask, [q8[i:j + 1].reshape(-1, 1, 2)], False, val, thick, cv2.LINE_AA, 3)
                i = j + 1

    def render(self, strokes, wipe=0.0):
        """strokes: list of (pts Nx2, arc N, press N) -> float alpha HxW"""
        allp = np.vstack([s_[0] for s_ in strokes])
        x0, y0 = np.floor(allp.min(0) - self.width * 2).astype(int)
        x1, y1 = np.ceil(allp.max(0) + self.width * 2).astype(int)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        out = np.zeros((H, W), np.float32)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return out
        ss = 2
        mask = np.zeros(((y1 - y0) * ss, (x1 - x0) * ss), np.uint8)
        for pts, arc, press in strokes:
            self.stroke(mask, pts, arc, press, wipe, ss, (x0, y0))
        a = cv2.resize(mask, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        a = cv2.GaussianBlur(a, (0, 0), 0.7)
        tooth = smooth(0.62, 0.82, 0.6 * self.fine[y0:y1, x0:x1] + 0.45 * self.mid[y0:y1, x0:x1])
        out[y0:y1, x0:x1] = a * (1 - 0.6 * tooth)
        return out


# ---------------------------------------------------------------- the label
def label_layer(project):
    """each label line in the pack's mono face, set at twice the size and halved for a crisp edge"""
    f = fxlib.font(project, "mono", 68)
    out = []
    for text, _ in LABEL:
        w = int(f.getlength(text)) + 8
        im = Image.new("L", (w, 96), 0)
        ImageDraw.Draw(im).text((2, 4), text, font=f, fill=255)
        out.append(cv2.resize(np.asarray(im, np.float32) / 255, (max(1, w // 2), 48), interpolation=cv2.INTER_AREA))
    return out


# ---------------------------------------------------------------- the line's sound
def marker_sound(path, tips, ink_frames, n0):
    """a china marker on glass, driven by how fast the ink's end really moved: band-passed noise with a slow flutter,
    synthesized here (no recording). Starts at the window's start"""
    sr = 48000
    N = len(tips)
    ink_on = np.zeros(N)
    for f in ink_frames:
        if 0 <= f - n0 < N:
            ink_on[f - n0] = 1
    sp = np.r_[0, np.linalg.norm(np.diff(tips, axis=0), axis=1)] * ink_on
    t_a = np.arange(int(N / FPS * sr)) / sr
    env = np.interp(t_a, np.arange(N) / FPS, sp)
    env = np.convolve(env, np.hanning(int(0.03 * sr)) / (0.015 * sr), mode="same")
    env = (env / max(env.max(), 1e-3)) ** 0.7
    r = np.random.default_rng(5).normal(0, 1, (len(t_a), 2)).astype(np.float32)
    # wax on glass: mostly 1.5 to 7 kHz, some grit from a slow amplitude flutter
    spec = np.fft.rfft(r, axis=0)
    fr_ = np.fft.rfftfreq(len(t_a), 1 / sr)
    spec *= (smooth(900, 2200, fr_) * (1 - smooth(5500, 9500, fr_)))[:, None]
    n_ = np.fft.irfft(spec, n=len(t_a), axis=0)
    n_ /= max(np.abs(n_).max(), 1e-9)
    flutter = 0.72 + 0.28 * np.sin(2 * np.pi * 61 * t_a + 3 * np.sin(2 * np.pi * 7 * t_a))
    out = n_ * (env * flutter)[:, None]
    out = out / max(np.abs(out).max(), 1e-3) * 0.6
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = wave.open(path, "wb")
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(pcm.tobytes())
    w.close()


def keep_js(out_dir):
    """run from the library folder on a project that has no copy yet: its fx.js comes along with the clip"""
    if not os.path.exists(os.path.join(out_dir, "fx.js")) and os.path.realpath(out_dir) != os.path.realpath(HERE):
        shutil.copy(os.path.join(HERE, "fx.js"), os.path.join(out_dir, "fx.js"))


# ---------------------------------------------------------------- build
def build(project, fid, stills=None, show_tips=False):
    global W, H
    entry = fxlib.entry(project, fid)
    A, B = float(entry["at"]), float(entry["end"])
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    S = fxlib.pack(project)
    F = fxlib.tracks(project)["frames"]
    n0, n1 = fxlib.fr(A), max(fxlib.fr(B), fxlib.fr(A) + 1)
    N = n1 - n0
    faces = [(F[n] or {}).get("face") if n < len(F) else None for n in range(n0, n1)]
    have = [f for f in faces if f]
    if not have:
        sys.exit(f"no face in work/tracks/track.json between {A:.2f} and {B:.2f}: the line is sized and the skin "
                 "read off the face")
    fw, fh = float(np.median([f["w"] for f in have])), float(np.median([f["h"] for f in have]))
    U = fw / FACE_W0
    width = WIDTH or max(10.0, min(40.0, WIDTH_K * fw))

    # ---- when the pen goes down and up
    t_down = cue(project, PEN_DOWN[0], A, B)
    if t_down is None:
        t_down = A + PEN_DOWN[1]
    wipe = (B - WIPE[0], B - WIPE[1])
    t_up = None
    if MODE == "path":
        t_up = cue(project, PEN_UP[0], t_down + 0.1, B)
        if t_up is None:
            t_up = B - PEN_UP[1]
        t_up = min(t_up, wipe[0] - 1 / FPS)
        if t_up <= t_down + 0.2:
            sys.exit(f"pen down {t_down:.2f}, pen up {t_up:.2f}: the window is too short to draw in")
    s0 = max(n0, fxlib.fr(t_down))
    if MODE == "numeral":                    # the rise comes just before the word the finger is up on
        side = pick_side(F, max(n0, s0 - round(LOOKBACK * FPS)), n1)
    else:
        side = pick_side(F, s0, fxlib.fr(t_up))

    # ---- pass 1: the fingertip on every frame, read off the skin (on the speaker's matte) and from the landmark
    land, refined, model = np.zeros((N, 2)), [None] * N, None
    hands = [None] * N
    has_matte = os.path.exists(os.path.join(project, "public", "subject.webm"))
    if not has_matte:
        print("  no public/subject.webm: the fingertip is read off the skin without the speaker's matte")
    mattes = fxlib.alpha(project, A, B) if has_matte else iter(())
    grow = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
    for i, rgb in fxlib.frames(project, A, B):
        al = next(mattes, (None, None))[1]
        k = i - n0
        if not 0 <= k < N:
            continue
        h = [x for x in (F[i] or {}).get("hands") or [] if x["side"] == side] if i < len(F) else []
        if model is None and faces[k]:
            model = skin_model(rgb, faces[k])
        if h:
            hands[k] = h[0]
            land[k] = h[0]["index"]
            on = cv2.dilate((al > 96).astype(np.uint8), grow).astype(np.float32) if al is not None else None
            q = find_tip(rgb, h[0], faces[k], model, REACH_K * fw, on)
            back = np.array(h[0]["palm"]) - q
            refined[k] = q + TIP_INSET_K * fw * back / max(1e-3, np.linalg.norm(back))
        elif k:
            land[k] = land[k - 1]

    def path(refine):
        tips = np.zeros((N, 2))
        for k in range(N):
            n = n0 + k
            if n in OVERRIDE:
                tips[k] = OVERRIDE[n]
            elif refined[k] is not None and refine[0] <= n <= refine[1]:
                tips[k] = refined[k]
            elif hands[k] is not None:
                tips[k] = land[k]
            elif k:
                tips[k] = tips[k - 1]
            else:
                tips[k] = next((land[j] for j in range(N) if hands[j] is not None), (W / 2, H / 2))
        return settle(tips, U)

    if MODE == "numeral":
        tips = path((0, 10 ** 9))
        if show_tips:
            print("  the path the numeral is read from (the fingertip off the skin on every frame):")
            for k in range(N):
                print(f"  read {n0 + k} ({(n0 + k) / FPS:.2f}s): {tips[k][0]:.0f}, {tips[k][1]:.0f}")
        lm = np.array([land[k] if hands[k] is not None else (np.nan, np.nan) for k in range(N)], np.float64)
        for k in range(N):                           # frames without the hand hold the last landmark
            if np.isnan(lm[k, 0]):
                lm[k] = lm[k - 1] if k else next((land[j] for j in range(N) if hands[j] is not None), (W / 2, H / 2))
        foot_, t_, w_ = numeral_beats(tips, settle(lm, U), s0 - n0, fh)
        s0 = NUMERAL["foot"] if NUMERAL["foot"] is not None else n0 + foot_
        top = NUMERAL["top"] if NUMERAL["top"] is not None else (n0 + t_ if t_ is not None else None)
        whip = NUMERAL["whip"] if NUMERAL["whip"] is not None else (n0 + w_ if w_ is not None else None)
        if top is None or whip is None:
            sys.exit(f"finger-draw: no {'raised finger held still' if top is None else 'whip away from the top'} "
                     f"found after {s0 / FPS:.2f} s ({'rise ' + str(s0) + '-' + str(top) if top else 'no rise'}). The "
                     "numeral needs one finger up on its word, held about half a second, then flicked away (README). Run "
                     "--tips to see the path, then set NUMERAL foot/top/whip by hand, or use path mode.")
        whip = min(whip, n1 - 4)
        top = min(top, whip - 1)
        hold, flag_end, front_until = (top, whip), whip + 1, (top, top + 5)
        tips = path((s0 + 1, whip))
        stem_frames = on_the_rise([f for f in range(s0, top + 1) if f not in SKIP], tips, n0, fh)
        print(f"  numeral: rise {s0}-{top}, hold to {whip}, whip {whip}-{flag_end} (NUMERAL foot/top/whip pin them)")
    else:
        tips = path((0, 10 ** 9))
        stem_frames = [f for f in range(s0, fxlib.fr(t_up) + 1) if f not in SKIP]
        hold = flag_end = front_until = None
    if len(stem_frames) < 2:
        sys.exit("the line has fewer than two frames: move PEN_DOWN earlier or the window later")
    if show_tips:
        for k in range(N):
            print(f"  frame {n0 + k} ({(n0 + k) / FPS:.2f}s): tip {tips[k][0]:.0f}, {tips[k][1]:.0f}"
                  f"{'  (override)' if n0 + k in OVERRIDE else ''}")

    # ---- the stem: the real path, frame by frame, repeats dropped
    stem_key = [tips[stem_frames[0] - n0]]
    for f in stem_frames[1:]:
        if np.linalg.norm(tips[f - n0] - stem_key[-1]) > 3:
            stem_key.append(tips[f - n0])
    stem, _ = catmull(stem_key)
    arcs = np.r_[0, np.cumsum(np.linalg.norm(np.diff(stem, axis=0), axis=1))]
    L_stem = max(arcs[-1], 1.0)
    # where the line's end is on each frame: the arc at that frame's tip, repeats hold
    frame_arc = {}
    for f in range(stem_frames[1], stem_frames[-1] + 1):
        d = np.linalg.norm(stem - tips[f - n0], axis=1)
        frame_arc[f] = arcs[np.argmin(d)]
    frame_arc[stem_frames[-1]] = L_stem
    last = 0
    for f in sorted(frame_arc):
        frame_arc[f] = last = max(last, frame_arc[f])
    # numeral: the flag is the real whip away from the top, cut at a share of the stem's length
    flag = arc_f = None
    if flag_end:
        flag_pts = [tips[f - n0] for f in range(hold[1], min(n1 - 1, flag_end + 3))]
        flag, _ = catmull(flag_pts)
        arc_f = np.r_[0, np.cumsum(np.linalg.norm(np.diff(flag, axis=0), axis=1))]
        cut = int(np.searchsorted(arc_f, NUMERAL["flag"] * L_stem))
        flag, arc_f = flag[:max(2, cut)], arc_f[:max(2, cut)]
    print(f"  stem {L_stem:.0f}px from {stem[0].round()} to {stem[-1].round()}"
          + (f", flag {arc_f[-1]:.0f}px to {flag[-1].round()}" if flag is not None else "") + f", hand {side}")
    wob_s = wobble_1d(len(stem), 26, 3) * 1.6 * U
    wob_f = wobble_1d(len(flag), 18, 5) * 1.4 * U if flag is not None else None
    ink = Ink(width)
    labels = label_layer(project) if LABEL else []
    label_times, prev = [], A
    for text, word in LABEL:
        t = cue(project, word, prev, B)
        if t is None:
            t = (label_times[-1] + 0.3) if label_times else t_down + 0.2
        label_times.append(t)
        prev = t
    # the label sits beside the top of the drawing (its highest stretch), on the side with room, inside the safe zone
    shape = np.vstack([stem] + ([flag] if flag is not None else []))
    lw = max([x.shape[1] for x in labels] + [1])
    lh = 44 * max(1, len(labels))
    if LABEL_POS:
        lx, ly = LABEL_POS
    else:
        y0s = shape[:, 1].min()
        near = shape[shape[:, 1] <= y0s + 0.5 * fw]
        right, left = near[:, 0].max() + 0.042 * fw, near[:, 0].min() - 0.042 * fw - lw
        lx = right if right + lw < W - 100 else left
        ly = y0s - 0.43 * fw
        lx, ly = int(max(35, min(W - 35 - lw, lx))), int(max(220, min(H - 450 - lh, ly)))
    label_ink = None
    # the hand's matte box: where the drawing hand goes over the window, plus a margin
    pts = [np.array(hd[key]) for hd in hands if hd for key in ("wrist", "palm", "thumb", "index", "middle", "pinky")]
    pts = np.array(pts + [shape.min(0), shape.max(0)])
    mg = MARGIN_K * fw
    box = (int(max(0, pts[:, 0].min() - mg)), int(max(0, pts[:, 1].min() - mg)),
           int(min(W, pts[:, 0].max() + mg)), int(min(H, pts[:, 1].max() + mg)))
    work = os.path.join(project, "work", fid)
    cache = os.path.join(work, f"cache_{n0}_{n1}_{box[0]}_{box[1]}_{box[2]}_{box[3]}")
    os.makedirs(cache, exist_ok=True)

    def hand_of(k, rgb):
        """the hand's matte on the box, cached. The hull takes the true fingertip, the landmark lags it"""
        n = n0 + k
        p = os.path.join(cache, f"m{n:05d}.npy")
        if os.path.exists(p):
            return np.load(p).astype(np.float32) / 255
        x0, y0, x1, y1 = box
        crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
        d = depth_crop(os.path.join(cache, "depth", f"f{n:05d}.npy"), crop)
        hd = dict(hands[k]) if hands[k] else None
        if hd:
            hd["index"] = tips[k].tolist()
        m = hand_matte(crop, d, [hd] if hd else [], None, y0, x0, grow=round(GROW_K * fw))
        np.save(p, (m * 255).astype(np.uint8))
        return m

    def stroke_at(f):
        """the whole line on frame f: a list of (pts, arc, pressure)"""
        if f < stem_frames[1]:
            return None
        upto = frame_arc[min(f, stem_frames[-1])]
        m = max(2, int(np.searchsorted(arcs, upto + 1e-6)))
        pts = stem[:m].copy()
        # the live end sits exactly on the fingertip on every frame: the upper part of the stem gives, no scribble
        head = tips[min(f, hold[1] if hold else stem_frames[-1]) - n0]
        u = np.clip(arcs[:m] / max(arcs[m - 1], 1), 0, 1) ** 1.5
        pts = pts + u[:, None] * (head - pts[-1])[None]
        tang = np.gradient(pts, axis=0)
        nrm = np.stack([-tang[:, 1], tang[:, 0]], 1) / (np.linalg.norm(tang, axis=1, keepdims=True) + 1e-3)
        live = (not hold) or f <= hold[1]
        dist_end = arcs[m - 1] - arcs[:m]
        # the wobble dies toward the live end, so the end is exactly on the fingertip
        pts = pts + nrm * (wob_s[:m] * (smooth(0, 40, dist_end) if live else 1.0))[:, None]
        # pressure: starts light, digs in as the finger slows into the end
        pr = 0.34 + 0.62 * smooth(0.0, 0.8, arcs[:m] / L_stem) + 0.13 * np.sin(arcs[:m] / 41.0 + 0.7)
        pr = pr * smooth(0, 30, arcs[:m])
        if live:
            pr = pr * (0.72 + 0.28 * smooth(0, 26, dist_end))        # no ball on the fingertip
        out = [(pts, arcs[:m], np.clip(pr, 0.02, 1))]
        if flag is not None and f > hold[1]:
            frac = 1.0 if f >= flag_end else (f - hold[1]) / max(1, flag_end - hold[1])
            mf = max(2, int(len(flag) * frac))
            fp = flag[:mf].copy()
            tf = np.gradient(fp, axis=0)
            nf = np.stack([-tf[:, 1], tf[:, 0]], 1) / (np.linalg.norm(tf, axis=1, keepdims=True) + 1e-3)
            fp = fp + nf * (wob_f[:mf] * smooth(0, 20, arc_f[:mf]))[:, None]
            pf = 0.86 - 0.42 * (arc_f[:mf] / max(1, arc_f[-1])) + 0.09 * np.sin(arc_f[:mf] / 23.0)
            pf = pf * smooth(arc_f[-1], arc_f[-1] - 40, arc_f[:mf])
            out.append((fp, arc_f[:mf] + 2000, np.clip(pf, 0.02, 1)))
        return out

    accent = np.array(S["colors"]["accent"][:3], np.float32)

    def compose(k, rgb):
        nonlocal label_ink
        n = n0 + k
        t = n / FPS
        st = stroke_at(n)
        if st is None or t >= wipe[1]:
            return rgb
        dry = smooth(wipe[0], wipe[1], t)
        a = ink.render(st, dry)
        out = rgb.astype(np.float32)
        col = accent[None, None] * (0.94 + 0.12 * ink.mid[..., None])
        if front_until and hold and front_until[0] <= n <= hold[1]:
            # it melts into the raised finger: they hold up a clean finger, nothing peeks out round it
            a = a * (1 - smooth(front_until[0] - 0.5, front_until[1], n))
        out = out * (1 - a[..., None]) + col * a[..., None]
        # numeral: from the whip on the line hangs behind the hand, the hand uncovers it
        if front_until and n >= front_until[0]:
            x0, y0, x1, y1 = box
            hm = hand_of(k, rgb)
            if n <= hold[1]:
                hm = hm * smooth(front_until[0] - 0.5, front_until[1], n)
            reg = out[y0:y1, x0:x1]
            reg[:] = reg * (1 - hm[..., None]) + rgb[y0:y1, x0:x1].astype(np.float32) * hm[..., None]
        for i, (tex, t_on) in enumerate(zip(labels, label_times)):
            if t < t_on - 1e-3:
                continue
            if label_ink is None:            # light or ink, against what is behind the label when it first lands
                reg = rgb[ly:ly + lh, lx:lx + lw].astype(np.float32) / 255
                luma = float(np.median(0.2126 * reg[..., 0] + 0.7152 * reg[..., 1] + 0.0722 * reg[..., 2])) if reg.size else 0
                label_ink = np.array(S["colors"]["ink" if luma > 0.55 else "light"][:3], np.float32)
            e = np.clip((t - t_on) / 0.16, 0, 1)
            h_vis = int(round(tex.shape[0] * (1 - (1 - e) ** 3)))    # a masked rise
            if h_vis < 2:
                continue
            part = tex[:h_vis]
            yy = ly + i * 44 + (tex.shape[0] - h_vis)
            part = part[:max(0, H - yy), :max(0, W - lx)]
            al = part[..., None] * (1 - dry)
            reg = out[yy:yy + part.shape[0], lx:lx + part.shape[1]]
            reg[:] = reg * (1 - al) + label_ink[None, None] * al
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)

    # ---- pass 2: compose, streaming
    out_dir = os.path.join(project, "fx", fid)
    os.makedirs(out_dir, exist_ok=True)
    want = None if not stills else {fxlib.fr(t) for t in stills}
    tmp = os.path.join(work, "finger.tmp.mp4")
    wr = fxlib.Writer(tmp, w=W, h=H) if want is None else None
    for i, rgb in fxlib.frames(project, A, B):
        k = i - n0
        if not 0 <= k < N:
            continue
        if want is not None:
            if i in want:
                p = os.path.join(work, f"still_{i / FPS:.2f}.png")
                cv2.imwrite(p, compose(k, rgb)[:, :, ::-1])
                print(p)
            continue
        wr.write(compose(k, rgb))
    if wr is None:
        return
    wr.close()
    os.replace(tmp, os.path.join(out_dir, "finger.mp4"))
    snd = os.path.join(project, "audio", f"{fid}-marker.wav")
    marker_sound(snd, tips, list(stem_frames[1:]) + ([flag_end] if flag_end else []), n0)
    tag = (f'<video id="{{{{ID}}}}-v" class="g" src="fx/{{{{ID}}}}/finger.mp4" muted playsinline data-start="{{{{START}}}}" '
           f'data-media-start="0.0010" data-duration="{N / FPS:.4f}" data-track-index="{{{{T0}}}}" '
           f'style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;"></video>')
    with open(os.path.join(out_dir, "fx.html"), "w", encoding="utf-8") as fh_:
        fh_.write("<!-- finger-draw (cam): written by gen.py. finger.mp4 is the live footage for this window with the "
                  "line drawn on it\n     (frame 0 is the window's first frame, class g keeps the live grade). -->\n"
                  f"{tag}\n")
    keep_js(out_dir)
    print(f"wrote {out_dir}/finger.mp4 ({N} frames), fx.html and {snd}")
    print("edit.py SOUND sfx to start from:")
    print(f"    dict(at={A:.3f}, name=\"{fid}-marker\", db=-7, align=\"start\"),   # the line's own sound, from the window's start")
    for t_on in label_times:
        print(f"    ({t_on:.3f}, \"tick\", -15),   # a label line lands")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="+", type=float, metavar="T", help="output times to write as PNGs, nothing else")
    ap.add_argument("--tips", action="store_true", help="print the fingertip on every frame")
    args = ap.parse_args()
    if MODE not in ("path", "numeral"):
        sys.exit(f"MODE is {MODE!r}: path or numeral")
    print(f"finger-draw {args.id}: {MODE}")
    build(os.path.abspath(os.path.expanduser(args.project)), args.id, args.stills, args.tips)


if __name__ == "__main__":
    main()
