#!/usr/bin/env python3
"""blow-away: the line says the speaker was blown away, so they are. A camera jolt on the word, dust strips off every
windward edge, then a front of wind crosses them lower left to upper right and they come apart as sand: each 2 px cell
of them lets go in its real colour, read from the live frame the moment the front reaches it, and rides a seeded wind
(drag, curl noise that grows with age, heavy grains fall, most pass behind what is still attached), shrinking away,
never fading. What the front has not reached IS the live frame, lips in sync. Then the empty room holds, a few specks
drifting in the settled air. Physics is seeded and stepped at a fixed rate: same run, same film.

The room behind them, best first: the empty room alone (work/c/room_empty_<FRAME>.npy, filmed after the speaker walked
out): on the jolt the room cuts to it, so whatever they leave behind (an empty chair) is simply there when they go, and
the hold carries the empty stretch's own grain (edit.EMPTY), so it is filmed, not frozen. Else the room as the take saw
it (work/c/room_<FRAME>.npy): what the speaker never touches stays live footage, and the patch they always covered is
a smooth guess filled in from the room around it. That shows on a hold, so gen.py prints the time to end the window
by: a window that ends before the last of them goes cuts away mid-dissolve.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>: the window; EMPTY or EMPTY_CLIP and FRAMES for the grain), words.json,
          timeline.json, public/clean.mp4, public/subject.webm, work/tracks/track.json, work/c/room_empty_<FRAME>.npy or
          room_<FRAME>.npy, work/plate/plate.json and hole.png, public/plates/desk_<FRAME>.webm and mic_<FRAME>.webm
  writes  <project>/fx/<id>/<id>.mp4 (frame n = reel frame round(at * 30) + n), audio/<id>-sand.wav, prints the SFX lines
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the words move.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30

# ---- the constants to change per video (the window itself is the edit.py FX entry: start it a frame before HIT_ON)
HIT_ON = ""                 # the word the wind hits on ("blew"); '' = the first word that starts in the window
GONE_ON = ""                # the word the last of the speaker leaves on ("away"): its end; '' = GONE_AFTER after the hit
GONE_AFTER = 0.69           # s from the hit to the last grain letting go, when GONE_ON isn't set
CLEAR_AFTER = 0.28          # s after that the air is empty but for a few specks: from here the room just sits there
SLANT = 0.50                # the front leans: lower left first, the head last (x - SLANT * y)
FRONT_EASE = 1.40           # above 1: the front bites fast on the word, then works through the speaker
DUST = 0.076                # how deep the first gust strips the windward edges, as a share of the face width
DUST_SPREAD = 0.30          # s: over how long that dust lets go
JOLT = [(1.016, 9, -5), (1.007, -3, 2)]   # 2 frames on the hit: scale, dx, dy
CELL = 2                    # px: one grain per cell of the speaker
WIND = 2500.0               # px/s the air reaches once the gust is up
GUST_GROWTH = 0.35          # the gust keeps building through the sweep
BEHIND = 0.72               # share of the grains that pass behind whatever is still attached
WIND_ANGLE = 13.0           # degrees above horizontal
SPECKS = 0.002              # share of the cells that become the specks left hanging at the end
SPECK_DRIFT = (24.0, 16.0)  # px/s: where the air settles once the gust has died, a little right and falling
GRAIN = 0.42                # how much of the empty stretch's own grain rides on the hold (0 = a still)
SEED = 7

SUB = 4                     # physics steps per frame
SHUTTER = 0.14              # of a frame: a fast shutter. Sand reads as grains only if the grains stay sharp


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
from common import load_edit, timeline  # noqa: E402  (fxlib's folder is on the path by now)


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


def room_of(project, frame, empty=False):
    """the room at live levels from the kit's plate tools: as the take saw it, or (empty) the empty room alone"""
    p = os.path.join(project, "work", "c", f"room_empty_{frame}.npy" if empty else f"room_{frame}.npy")
    return np.load(p).astype(np.float32) if os.path.exists(p) else None


def filmed_empty(project):
    """True when the plate tools have the room behind the speaker: a filmed empty room (edit.EMPTY or
    EMPTY_CLIP), or a photo or generated background given to plate_finish.py --fill (mode "filled"). Without one,
    room_empty_<FRAME>.npy is the same as room_<FRAME>.npy, a fill where the speaker always sat"""
    try:
        return json.load(open(os.path.join(project, "work", "plate", "plate.json"))).get("mode") in ("empty", "filled")
    except (OSError, ValueError):
        return False


def plate_hole(project, frame, W, H):
    """where the take never saw the room (work/plate/hole.png, the plate tools' fill), in this crop at the video's size;
    None when there is no hole file"""
    p = os.path.join(project, "work", "plate", "hole.png")
    if not os.path.exists(p):
        return None
    hole = cv2.imread(p, 0)
    E = load_edit(project)
    w, h, x, y = E.FRAMES[frame]
    k = hole.shape[1] / fxlib.size(E.SRC)[0]                    # hole.png is at the source's size
    crop = hole[round(y * k):round((y + h) * k), round(x * k):round((x + w) * k)]
    return cv2.dilate(cv2.resize(crop, (W, H), interpolation=cv2.INTER_NEAREST), np.ones((15, 15), np.uint8)) > 127


def smooth_fill(img, hole, down=6, iters=600):
    """the patch the take never saw, refilled smoothly from the room around it: a plain guess reads better on a hold
    than an inpaint's streaks of whatever the speaker wore"""
    H, W = hole.shape
    sw, sh = W // down, H // down
    known = cv2.resize((~hole).astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA) > 0.99
    if not known.any():
        return img
    low = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
    x = low.copy()
    x[~known] = low[known].mean(axis=0)
    for _ in range(iters):
        avg = (np.roll(x, 1, 0) + np.roll(x, -1, 0) + np.roll(x, 1, 1) + np.roll(x, -1, 1)) / 4
        x = np.where(known[..., None], low, avg)
    up = cv2.GaussianBlur(cv2.resize(x, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), down)
    a = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 6)[..., None]
    return img * (1 - a) + up * a


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


# ------------------------------------------------------------------ the room
def nc(img, mask, sigma):
    m = mask.astype(np.float32)
    a = cv2.GaussianBlur(img * m[..., None], (0, 0), sigma)
    b = cv2.GaussianBlur(m, (0, 0), sigma)
    return a / np.maximum(b[..., None], 1e-4), b


def local_bg(C, a):
    """what is really behind the speaker's soft edge in this frame: the live room just outside it, spread inward (at
    half size: it is smooth anyway). A plate can't say as well: the room right at the outline is what they hide"""
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


def room_grain(project, frame, n, W, H):
    """the empty stretch's real frames minus their own mean, luma only: the grain and tiny life of the actual room, so the
    hold is filmed, not a freeze. The stretch the plate tools used (work/plate/plate.json), cropped like the video"""
    E = load_edit(project)
    try:
        info = json.load(open(os.path.join(project, "work", "plate", "plate.json")))["empty"]
        src, a0, a1 = info["source"], float(info["start"]), float(info["end"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not os.path.isabs(src):
        src = os.path.join(project, src)
    at = a0 + min(0.5, max(0.0, (a1 - a0 - n / FPS) / 2))
    w, h, x, y = E.FRAMES[frame]
    sw, sh = fxlib.size(E.SRC)
    cw, ch = fxlib.size(src)
    if (cw, ch) != (sw, sh):                             # a separate empty clip at another size: the same framing, scaled
        k = cw / sw
        w, h, x, y = round(w * k), round(h * k), round(x * k), round(y * k)
    vf = (f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos+accurate_rnd+full_chroma_int:in_color_matrix=bt709:"
          f"in_range=tv:out_range=pc,format=gray")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.3f}", "-i", src, "-frames:v", str(n), "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    k = len(raw) // (W * H)
    if k < 2:
        print("WARNING: couldn't read the empty stretch for the grain: the hold is a still")
        return None
    F = np.frombuffer(raw[:k * W * H], np.uint8).reshape(k, H, W)
    mean = F.mean(axis=0, dtype=np.float32)
    return [((F[i % k].astype(np.float32) - mean) * GRAIN)[..., None] for i in range(n)]


# ------------------------------------------------------------------ the sand
def fbm(rng, h, w, scales, weights):
    out = np.zeros((h, w), np.float32)
    for s, a in zip(scales, weights):
        g = rng.standard_normal((h // s + 4, w // s + 4)).astype(np.float32)
        out += a * cv2.resize(g, (w + 2 * s, h + 2 * s), interpolation=cv2.INTER_CUBIC)[s:s + h, s:s + w]
    return out


def curl_field(rng, size, sx, sy):
    """a divergence-free velocity field on a torus: filtered noise as a stream function. sx, sy in field px: streaks along the wind"""
    n = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.rfftfreq(size)[None, :]
    psi = np.fft.irfft2(np.fft.rfft2(n) * np.exp(-2 * (np.pi ** 2) * ((fx * sx) ** 2 + (fy * sy) ** 2)), s=(size, size))
    u = (np.roll(psi, -1, 0) - np.roll(psi, 1, 0)) / 2
    v = -(np.roll(psi, -1, 1) - np.roll(psi, 1, 1)) / 2
    k = np.sqrt((u ** 2 + v ** 2).mean())
    return (u / k).astype(np.float32), (v / k).astype(np.float32)


def sample(f, x, y, size, per):
    """bilinear lookup with wrap. per = reel px per field px"""
    fx, fy = x / per, y / per
    x0, y0 = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    ax, ay = (fx - x0).astype(np.float32), (fy - y0).astype(np.float32)
    x0 %= size
    y0 %= size
    x1, y1 = (x0 + 1) % size, (y0 + 1) % size
    return (f[y0, x0] * (1 - ax) + f[y0, x1] * ax) * (1 - ay) + (f[y1, x0] * (1 - ax) + f[y1, x1] * ax) * ay


class Splat:
    """grains as axis-aligned boxes with exact coverage, on a 2x grid, through a difference image: O(grains), not
    O(area). Colours average, they never add, so no grain can glow: where sand overlaps you see sand"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.Wg, self.Hg = W * 2, H * 2
        self.n = (self.Wg + 1) * (self.Hg + 1)
        self.d = [np.zeros(self.n) for _ in range(4)]

    def add(self, x0, y0, x1, y1, cover, col):
        X0, X1 = np.clip(np.round(x0 * 2), 0, self.Wg).astype(np.int64), np.clip(np.round(x1 * 2), 0, self.Wg).astype(np.int64)
        Y0, Y1 = np.clip(np.round(y0 * 2), 0, self.Hg).astype(np.int64), np.clip(np.round(y1 * 2), 0, self.Hg).astype(np.int64)
        k = (X1 > X0) & (Y1 > Y0)
        if not k.any():
            return
        X0, X1, Y0, Y1, cover, col = X0[k], X1[k], Y0[k], Y1[k], cover[k], col[k]
        st = self.Wg + 1
        idx = np.concatenate([Y0 * st + X0, Y0 * st + X1, Y1 * st + X0, Y1 * st + X1])
        for c in range(4):
            w = cover * (col[:, c - 1] if c else 1.0)
            self.d[c] += np.bincount(idx, np.concatenate([w, -w, -w, w]), self.n)

    def get(self):
        st = self.Wg + 1
        arr = [np.cumsum(np.cumsum(d.reshape(self.Hg + 1, st), axis=0), axis=1)[:-1, :-1].astype(np.float32) for d in self.d]
        arr = [cv2.resize(a, (self.W, self.H), interpolation=cv2.INTER_AREA) for a in arr]
        A = np.maximum(arr[0], 0)
        a = np.clip(A, 0, 1)[..., None]
        c = np.dstack(arr[1:]) / np.maximum(A, 1e-5)[..., None]
        return a, c


def dots(x, y, sz, col, W, H):
    """round soft specks at sub-pixel positions: a bilinear splat of each speck's area, then a small gaussian"""
    k = sz > 0.05
    x, y, sz, col = x[k], y[k], sz[k], col[k]
    A = np.zeros((H, W), np.float32)
    C = np.zeros((H, W, 3), np.float32)
    fx, fy = x - 0.5, y - 0.5
    x0, y0 = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    ax, ay = (fx - x0).astype(np.float32), (fy - y0).astype(np.float32)
    area = sz * sz * 0.785
    for dx, dy, w in ((0, 0, (1 - ax) * (1 - ay)), (1, 0, ax * (1 - ay)), (0, 1, (1 - ax) * ay), (1, 1, ax * ay)):
        i, j = y0 + dy, x0 + dx
        ok = (i >= 0) & (i < H) & (j >= 0) & (j < W)
        wt = (w * area)[ok]
        np.add.at(A, (i[ok], j[ok]), wt)
        for c in range(3):
            np.add.at(C[..., c], (i[ok], j[ok]), wt * col[ok, c])
    A = cv2.GaussianBlur(A, (0, 0), 0.8)
    C = cv2.GaussianBlur(C, (0, 0), 0.8)
    return np.clip(A, 0, 1)[..., None], C / np.maximum(A, 1e-5)[..., None]


def sand_sound(stats, path, t_hit, t_clear, W):
    """the sound of this sand, from this sand (synthesized here, CC0): hiss follows how many grains let go each frame,
    grit is one tiny click per few hundred of them, the air follows how much is in flight, and all of it pans with where
    the sand is. Silent by the hold, so the room is quiet"""
    from scipy.signal import butter, sosfilt
    import wave
    sr = 48000
    rng = np.random.default_rng(SEED + 1)
    fr = np.array([s[0] for s in stats], float)
    fresh = np.array([s[1] for s in stats], float)
    flying = np.array([s[2] for s in stats], float)
    cx_ = np.array([s[3] for s in stats], float)
    n = int((fr[-1] / FPS - t_hit + 0.15) * sr)
    tt = t_hit + np.arange(n) / sr
    env_fresh = np.interp(tt, fr / FPS, fresh)
    env_fly = np.interp(tt, fr / FPS, flying)
    pan = np.clip(np.interp(tt, fr / FPS, cx_) / W, 0, 1)

    def smooth_env(x, ms):
        k = max(1, int(ms / 1000 * sr))
        return np.convolve(x, np.ones(k) / k, mode="same")
    env_fresh = smooth_env(env_fresh, 40) / max(env_fresh.max(), 1)
    env_fly = smooth_env(env_fly, 60) / max(env_fly.max(), 1)
    hiss = sosfilt(butter(2, [3200, 12000], "band", fs=sr, output="sos"), rng.standard_normal(n)) * (env_fresh ** 0.6)
    air = sosfilt(butter(2, [350, 1900], "band", fs=sr, output="sos"), rng.standard_normal(n)) * (env_fly ** 0.8)
    grit = np.zeros(n)
    hits = np.nonzero(rng.random(n) < env_fresh * 2600.0 / sr)[0]          # clicks per second at the peak
    burst = np.exp(-np.arange(70) / 14.0)
    for i in hits:
        j = min(n, i + 70)
        grit[i:j] += burst[:j - i] * rng.uniform(0.2, 1.0) * rng.choice([-1, 1])
    grit = sosfilt(butter(2, 2400, "high", fs=sr, output="sos"), grit)
    mono = (0.55 * hiss / max(np.abs(hiss).max(), 1e-6) + 0.75 * air / max(np.abs(air).max(), 1e-6)
            + 0.45 * grit / max(np.abs(grit).max(), 1e-6))
    mono *= np.clip((t_clear + 0.02 - tt) / 0.10, 0, 1) ** 1.5                 # gone with the sand
    st = np.vstack([mono * np.cos(pan * np.pi / 2), mono * np.sin(pan * np.pi / 2)])
    st = st / max(np.abs(st).max(), 1e-6) * 0.7
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((st.T * 32767).astype("<i2").tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="+", type=float, help="write these reel times as jpgs in work/<id>/ instead of the clip")
    a = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(a.project)), a.id
    A, B, frame, words = place(project, fid)
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    FIRST, LAST = fxlib.fr(A), fxlib.fr(B)
    n = LAST - FIRST
    hit = word_at(words, HIT_ON, A, B)
    T_HIT = hit[0] if hit else A + 1 / FPS
    gone = word_at(words, GONE_ON, T_HIT + 0.05, B + 1.0) if GONE_ON else None
    T_GONE = gone[1] if gone else T_HIT + GONE_AFTER
    T_CLEAR = T_GONE + CLEAR_AFTER
    if (HIT_ON and not hit) or (GONE_ON and not gone):
        print(f"WARNING: a cue word isn't spoken in {A:.2f}-{B:.2f}: hit {T_HIT:.2f}, gone {T_GONE:.2f}")
    if B < T_CLEAR:                                       # a short window cuts away mid-way, by choice (no empty room)
        print(f"the window ends at {B:.2f}, before the last of the speaker is gone ({T_GONE:.2f}): a hard cut mid-way")
    rng = np.random.default_rng(SEED)
    stats = []

    # ---- the room: the empty room alone if it was filmed, else the room as the take saw it, else a guess
    F = np.stack([f for _, f in fxlib.frames(project, A, B)])
    Al = np.stack([al for _, al in fxlib.alpha(project, A, B)])
    n = min(n, len(F), len(Al))
    empty = room_of(project, frame, empty=True) if filmed_empty(project) else None
    mode = "empty" if empty is not None else "take"
    if empty is None:
        empty = room_of(project, frame)
        hole = plate_hole(project, frame, W, H) if empty is not None else None
        if hole is not None:
            empty = smooth_fill(empty, hole)
    if empty is None:
        mode = "guess"
        hole = cv2.dilate((Al.max(axis=0) > 8).astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
        empty = smooth_fill(F[0].astype(np.float32), hole)
    if mode != "empty":
        print(f"WARNING: no filmed empty room, so where the speaker sat is a smooth guess and it shows as soon as they're "
              f"gone. End the window by {max(A + 0.3, T_GONE - 0.25):.2f} (cut away while some of them is still there), or "
              "film the empty room: tripod untouched, walk out for the last 5 s (edit.EMPTY), rerun the plate tools")
    grain = room_grain(project, frame, n, W, H) if mode == "empty" else None
    desk_a, mic_a = plate_alpha(project, "desk", frame), plate_alpha(project, "mic", frame)
    front = np.maximum(desk_a if desk_a is not None else 0, mic_a if mic_a is not None else 0)
    occl = (1 - front * np.ones((H, W), np.float32))[..., None]       # nothing of the speaker passes in front of the desk or the mic
    print(f"{fid}: hit {T_HIT:.2f}, gone {T_GONE:.2f}, clear {T_CLEAR:.2f}, crop {frame}, room: {mode}"
          + (", filmed hold" if grain else ""))

    Hc, Wc = H // CELL, W // CELL
    Ac = np.stack([cv2.resize(al, (Wc, Hc), interpolation=cv2.INTER_AREA) for al in Al[:n]]).astype(np.float32) / 255
    mic_c = cv2.resize(cv2.dilate(mic_a, np.ones((5, 5), np.uint8)), (Wc, Hc), interpolation=cv2.INTER_AREA) if mic_a is not None else None
    not_mic = mic_c < 0.2 if mic_c is not None else np.ones((Hc, Wc), bool)   # the matte can take the mic for the speaker: it sheds nothing
    tp = os.path.join(project, "work", "tracks", "track.json")
    TR = fxlib.tracks(project)["frames"] if os.path.exists(tp) else []
    if not TR:
        print("no work/tracks/track.json: the dust depth and the solid body line are guessed from the frame (run track.py for better)")
    fcs = [TR[i]["face"] for i in range(FIRST, min(LAST, len(TR))) if TR[i].get("face")]
    pos = [TR[i]["pose"] for i in range(FIRST, min(LAST, len(TR))) if TR[i].get("pose")]
    face_w = float(np.median([f["w"] for f in fcs])) if fcs else 0.28 * W
    if pos:
        sy = float(np.median([(p["ls"][1] + p["rs"][1]) / 2 for p in pos]))
        sw = float(np.median([abs(p["ls"][0] - p["rs"][0]) for p in pos]))
        solid_from = sy + 0.17 * sw
    elif fcs:
        solid_from = float(np.median([f["chin"] for f in fcs])) + 0.6 * float(np.median([f["h"] for f in fcs]))
    else:
        solid_from = 0.62 * H
    # the matte drops chunks of a top under a fast hand. Low in the frame, what is the speaker for most of their time here stays them
    n_on = max(1, min(n, round((T_GONE - A) * FPS)))
    solid = np.percentile(Al[:n_on:2], 75, axis=0).astype(np.float32) / 255
    solid *= np.clip((np.arange(H, dtype=np.float32)[:, None] - solid_from) / 80, 0, 1)
    never = cv2.dilate((Al.max(axis=0) > 8).astype(np.uint8), np.ones((61, 61), np.uint8)) == 0
    never = cv2.GaussianBlur(never.astype(np.float32), (0, 0), 16)[..., None]      # what the speaker never touches (take mode)

    # ---- when the front reaches each cell: distance along the wind, lobes the front eats in, fray on the outline
    ys, xs = np.mgrid[0:Hc, 0:Wc].astype(np.float32)
    xs, ys = (xs + 0.5) * CELL, (ys + 0.5) * CELL
    body = Ac[:n_on].max(axis=0) > 0.5
    if not body.any():
        sys.exit("the matte has nobody in this window")
    s = xs - SLANT * ys
    lo, hi = np.percentile(s[body], 0.2), np.percentile(s[body], 99.9)
    u = np.clip((s - lo) / (hi - lo), -0.2, 1.2)
    lobes = fbm(rng, Hc, Wc, (110, 55, 26, 12), (1.0, 0.7, 0.42, 0.24))
    lobes /= lobes.std()
    dist = cv2.distanceTransform(body.astype(np.uint8), cv2.DIST_L2, 5) * CELL
    fray = np.exp(-dist / 34.0)
    T = T_HIT + (T_GONE - T_HIT) * (np.maximum(u, 0) ** FRONT_EASE + np.minimum(u, 0) + 0.052 * lobes - 0.045 * fray)
    # clumps: neighbours break off together, then crumble as the air gets to them
    seeds = np.column_stack([rng.uniform(0, W, 15000), rng.uniform(0, H, 15000)])
    clump = cKDTree(seeds).query(np.column_stack([xs.ravel(), ys.ravel()]), workers=-1)[1].reshape(Hc, Wc)
    tc = np.bincount(clump.ravel(), T.ravel(), len(seeds)) / np.maximum(np.bincount(clump.ravel(), minlength=len(seeds)), 1)
    T = 0.45 * T + 0.55 * tc[clump] + rng.normal(0, 0.006, (Hc, Wc)).astype(np.float32)
    # the first gust: every edge that faces the wind sheds dust at once, ahead of the front, so the hit reads on the word
    bu = body.astype(np.uint8)
    rag = fbm(rng, Hc, Wc, (9, 4), (1.0, 0.8))
    rag = (rag - rag.min()) / (rag.max() - rag.min())
    depth = (DUST * face_w / CELL * (0.25 + 1.5 * rag)).astype(np.float32)
    run = np.zeros((Hc, Wc), np.float32)                 # cells from the nearest air on the left, along the row
    for x_ in range(1, Wc):
        run[:, x_] = np.where(bu[:, x_] > 0, run[:, x_ - 1] + 1, 0)
    dust = (bu > 0) & (run < depth) & (np.arange(Wc)[None, :] > 3)
    dust &= rng.random((Hc, Wc)) < 0.62                   # thin it: dust, not a peel
    Td = T_HIT + DUST_SPREAD * rng.random((Hc, Wc)).astype(np.float32) ** 1.6 + 0.10 * (ys / H)
    T = np.where(dust, np.minimum(T, Td), T)
    Kick = np.where(dust, rng.uniform(500, 1300, (Hc, Wc)), rng.uniform(40, 220, (Hc, Wc))).astype(np.float32)
    T = np.clip(T, T_HIT, None)
    T_full = cv2.resize(T, (W, H), interpolation=cv2.INTER_NEAREST)

    # ---- what each grain is made of: seeded per cell, so a grain is the same grain on every run
    clump_tau = np.exp(rng.normal(0, 0.28, len(seeds))).astype(np.float32)
    Tau = 0.40 * clump_tau[clump] * np.exp(rng.normal(0, 0.16, (Hc, Wc))).astype(np.float32)
    Size = rng.uniform(1.8, 3.2, (Hc, Wc)).astype(np.float32)
    Life = rng.uniform(0.22, 0.62, (Hc, Wc)).astype(np.float32)
    Back = rng.random((Hc, Wc)) < BEHIND
    Tone = np.exp(rng.normal(0, 0.11, (Hc, Wc))).astype(np.float32)       # every grain catches the light its own way
    Kind = rng.choice([0, 1, 2], (Hc, Wc), p=[0.9, 0.1 - SPECKS, SPECKS]).astype(np.int8)
    Tau[Kind == 1] *= 2.6
    Life[Kind == 1] = rng.uniform(0.5, 0.9, (Kind == 1).sum())
    Tau[Kind == 2] *= 6.0
    Life[Kind == 2] = rng.uniform(1.0, 3.2, (Kind == 2).sum())             # the specks: some still in the air at the end
    Size[Kind == 2] *= 1.05
    # the frame clears on time whatever a grain drew: grains still in the air at T_CLEAR have shrunk away by then
    Clear = (T_CLEAR + rng.uniform(-0.06, 0.05, (Hc, Wc))).astype(np.float32)

    # ---- the air: long streaks along the wind plus eddies, frozen and carried downwind
    fs = 1024
    u1, v1 = curl_field(rng, fs, 110, 30)
    u2, v2 = curl_field(rng, fs, 34, 28)
    ang = np.deg2rad(WIND_ANGLE)
    wx, wy = np.cos(ang), -np.sin(ang)

    def gust(t):
        p = np.clip((t - T_HIT) / (T_GONE - T_HIT), 0, 1)
        rise = np.clip((t - T_HIT) / 0.14, 0, 1)
        dies = 1 - np.clip((t - (T_GONE + 0.12)) / 0.22, 0, 1) * 0.88
        return WIND * (0.72 + 0.28 * rise) * (1 + GUST_GROWTH * p) * dies

    zero = np.zeros(0, np.float32)
    x, y, vx, vy, born, tau, size, life, tone = (zero.copy() for _ in range(9))
    kind = np.zeros(0, np.int8)
    back = np.zeros(0, bool)
    col = np.zeros((0, 3), np.float32)
    total = 0
    want = {fxlib.fr(t) for t in a.stills} if a.stills else None
    d = out_dir(project, fid)
    work = os.path.join(project, "work", fid)
    out = None if want else fxlib.Writer(os.path.join(d, f"{fid}.mp4"), W, H, crf=14)
    for f in range(FIRST, FIRST + n):
        k = f - FIRST
        t = f / FPS
        frame_ = F[k].astype(np.float32)
        # ---- who leaves now. Colour is read from THIS frame, the moment the grain lets go
        fresh = (T > t - 1 / FPS) & (T <= t) & (Ac[k] > 0.5)
        if k:
            fresh |= (T <= t - 1 / FPS) & (T > t - 0.14) & (Ac[k] > 0.5) & (Ac[k - 1] <= 0.5)     # a hand moving into air that just passed
        fresh &= not_mic
        if fresh.any():
            small = cv2.resize(frame_, (Wc, Hc), interpolation=cv2.INTER_AREA)
            m = int(fresh.sum())
            x = np.concatenate([x, xs[fresh] + rng.uniform(-0.5, 0.5, m).astype(np.float32)])
            y = np.concatenate([y, ys[fresh] + rng.uniform(-0.5, 0.5, m).astype(np.float32)])
            vx = np.concatenate([vx, Kick[fresh] * wx])
            vy = np.concatenate([vy, Kick[fresh] * wy])
            born = np.concatenate([born, np.minimum(T[fresh], t)])
            tau = np.concatenate([tau, Tau[fresh]])
            size = np.concatenate([size, Size[fresh]])
            lf = Life[fresh]
            c_new = small[fresh]
            k_new = Kind[fresh].copy()
            dark = (k_new == 2) & (c_new.mean(axis=1) < 45)          # dark specks read as dirt on the furniture: plain sand
            k_new[dark] = 0
            lf[dark] = np.minimum(lf[dark], 0.6)
            nk = k_new != 2
            lf[nk] = np.minimum(lf[nk], np.maximum(Clear[fresh][nk] - np.minimum(T[fresh], t)[nk], 0.06))
            life = np.concatenate([life, lf])
            back = np.concatenate([back, Back[fresh]])
            tone = np.concatenate([tone, Tone[fresh]])
            kind = np.concatenate([kind, k_new])
            col = np.vstack([col, c_new])
            total += m
        # ---- step the sand through this frame's interval, drawing the part of it the shutter sees
        spf, spb = Splat(W, H), Splat(W, H)
        dot = None
        dt = 1 / FPS / SUB
        for s_ in range(SUB):
            tn = t + s_ * dt
            age = np.maximum(tn - born, 0)
            U = gust(tn)
            is2 = kind == 2
            settle = float(np.clip((tn - T_GONE) / max(T_CLEAR - T_GONE, 1e-3), 0, 1))   # the gust dies, the specks hang in still air
            grav = np.where(kind == 1, 3200.0, np.where(is2, 120.0 * (1 - settle), 40.0)).astype(np.float32)
            drift = np.where(is2, 0.34, 1.0).astype(np.float32)
            gx, gy = U * wx * drift, U * wy * drift
            gx = np.where(is2, gx * (1 - settle) + SPECK_DRIFT[0] * settle, gx).astype(np.float32)
            gy = np.where(is2, gy * (1 - settle) + SPECK_DRIFT[1] * settle, gy).astype(np.float32)
            tau_e = np.where(is2, tau * (1 - settle) + 0.3 * settle, tau).astype(np.float32)
            vx += (gx - vx) / tau_e * dt
            vy += ((gy - vy) / tau_e + grav) * dt
            # turbulence grows with age: a clump leaves as a clump, then the air gets into it
            grow = np.clip(age / 0.30, 0, 1) ** 1.5 * np.where(is2, 0.45 * (1 - 0.93 * settle), 1.0)
            fx = x - 0.7 * WIND * min(tn, T_CLEAR) - 18.0 * max(0.0, tn - T_CLEAR)
            tx = sample(u1, fx, y, fs, 2.0) * 620 + sample(u2, fx, y, fs, 2.0) * 340
            ty = sample(v1, fx, y, fs, 2.0) * 620 + sample(v2, fx, y, fs, 2.0) * 340
            vtx, vty = vx + tx * grow, vy + ty * grow
            if s_ == 0:
                # a grain shrinks away, it never fades. Below a pixel it just stops covering one
                sz = size * np.maximum(1 - (age / life) ** 2.2, 0)
                ex, ey = vtx * SHUTTER / FPS, vty * SHUTTER / FPS
                x0, x1 = np.minimum(x, x + ex) - sz / 2, np.maximum(x, x + ex) + sz / 2
                y0, y1 = np.minimum(y, y + ey) - sz / 2, np.maximum(y, y + ey) + sz / 2
                cover = sz * sz / np.maximum((x1 - x0) * (y1 - y0), 1e-3)
                c_ = col * tone[:, None]
                soft = is2 & (t >= T_GONE)                   # the hanging specks are round and sub-pixel: they drift, they don't step
                dot = dots(x[soft], y[soft], sz[soft], c_[soft], W, H) if soft.any() else None
                nb, bb = ~back & ~soft, back & ~soft
                spf.add(x0[nb], y0[nb], x1[nb], y1[nb], cover[nb], c_[nb])
                spb.add(x0[bb], y0[bb], x1[bb], y1[bb], cover[bb], c_[bb])
            x += vtx * dt
            y += vty * dt
        gaf, gcf = spf.get()
        gab, gcb = spb.get()
        # ---- the frame: the live picture before the hit; from the jolt on, what the front has not reached is the
        # speaker, live, over the room behind them. Far grains hide only behind the part still attached, near grains
        # go over everything, the desk and the mic stay in front of all of it
        if t < T_HIT - 0.5 / FPS:
            img = frame_                                 # the live frame, bit for bit
            body_now = np.zeros((H, W, 1), np.float32)
        else:
            attached = (T_full > t)[..., None]
            if mode != "empty":
                # the room hasn't changed: what is still attached is simply the live frame, soft edges and all
                room_now = empty * (1 - never) + frame_ * never
                img = np.where(attached, frame_, room_now)
                body_now = attached * (Al[k].astype(np.float32) / 255)[..., None]
            elif attached.any():
                # the room has cut to the empty one: the speaker's soft edge comes off the live room behind it
                room_now = empty + (grain[k] if grain else 0)
                al = np.maximum(Al[k].astype(np.float32) / 255, solid)
                a3 = al[..., None]
                fg = np.maximum(frame_ - (1 - a3) * local_bg(frame_, al), 0) * np.clip(a3 / 0.03, 0, 1) + (1 - a3) * room_now
                img = np.where(attached, fg, room_now)
                body_now = attached * a3
            else:
                img = empty + (grain[k] if grain else 0)
                body_now = np.zeros((H, W, 1), np.float32)
        gab = gab * occl * (1 - body_now)
        img = img * (1 - gab) + gcb * gab
        gaf = gaf * occl
        img = img * (1 - gaf) + gcf * gaf
        if dot is not None:
            gad = dot[0] * occl
            img = img * (1 - gad) + dot[1] * gad
        jk = round((t - T_HIT) * FPS)
        if 0 <= jk < len(JOLT):
            sc, dx_, dy_ = JOLT[jk]
            M = np.array([[sc, 0, W / 2 * (1 - sc) + dx_], [0, sc, H * 0.45 * (1 - sc) + dy_]], np.float32)
            img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        res = np.clip(np.round(img), 0, 255).astype(np.uint8)
        if out is not None:
            out.write(res)
        elif f in want:
            os.makedirs(work, exist_ok=True)
            p = os.path.join(work, f"still_{t:.2f}.jpg")
            cv2.imwrite(p, cv2.cvtColor(res, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(p)
        stats.append((f, int(fresh.sum()), len(x), float(np.mean(x)) if len(x) else W))
        # prune what has left the frame or the world
        alive = (x < W + 60) & (y > -60) & (y < H + 60) & (x > -60) & ((t + 1 / FPS - born) < life)
        x, y, vx, vy, born, tau, size, life, tone, kind, col, back = (v[alive] for v in (x, y, vx, vy, born, tau, size, life, tone, kind, col, back))
        print(f"\r  f{f} {t:.3f}  grains on screen {len(x):7d}  total {total:7d}", end="", flush=True)
    print()
    if out is None:
        return
    out.close()
    sand_sound(stats, os.path.join(project, "audio", f"{fid}-sand.wav"), T_HIT, T_CLEAR, W)
    print(os.path.join(d, f"{fid}.mp4"))
    print("SFX (edit.SOUND['sfx']):")
    print(f'    ({T_HIT:.3f}, "impact-low", -14),              # the hit')
    print(f'    dict(at={T_HIT:.3f}, name="{fid}-sand", db=-8, align="start"),   # audio/{fid}-sand.wav: the sand\'s own sound, written by gen.py')
    print(f'    ({T_HIT + 0.29:.3f}, "whoosh-deep", -14),             # the gust')
    print(f'    ({T_GONE:.3f}, "whoosh-soft", -15),             # the last of them goes')


if __name__ == "__main__":
    main()
