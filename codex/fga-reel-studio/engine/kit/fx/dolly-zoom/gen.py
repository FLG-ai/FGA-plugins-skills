#!/usr/bin/env python3
"""dolly-zoom: the Vertigo shot on a locked-off talking head. The speaker holds their size and place, lips in sync,
while the room behind them rushes forward. It is the real camera move computed from the room's depth: the camera pulls
back while the lens zooms in, so everything at the speaker's distance stays put and the further back something is, the
more it grows. The wall is fitted as a plane (a true homography: a picture frame stays straight as it grows), furniture
in front of it moves by its own distance (barely, near the speaker: that is what keeps them in the room instead of
pasted on it) and the desk falls back a touch. Motion blur on the room only. It lands on the word, holds, and goes home
before the window ends.

The room is revealed as it grows, so it needs a clean one: work/c/room_<FRAME>.npy (the room as the take saw it) from
the kit's plate tools, and when the empty room was filmed (edit.EMPTY), work/c/room_empty_<FRAME>.npy, which the wall
hands over to in the first part of the move (no seam where the plate's fill meets the real room, and it is the sharper
picture). Without a filmed empty room the patch the speaker always covered (work/plate/hole.png) is treated as wall and
filled smoothly from the wall around it: it grows into view, and it shows. The depth of the room comes from the kit's
depth model, calibrated on a live frame: the speaker is distance 1,
the wall WALL_DIST. Until the move starts the clip is the live frame bit for bit; the speaker is always the live pixel,
with the real room behind their soft edge swapped for the moved one (no foreground colour estimate).

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>: the window), words.json (MOVE_ON), timeline.json (the crop),
          public/clean.mp4, public/subject.webm, work/tracks/track.json, work/c/room_<FRAME>.npy, room_empty_<FRAME>.npy
          (optional), public/plates/desk_<FRAME>.webm, mic_<FRAME>.webm (optional), the depth model (pipeline/depth.py)
  writes  <project>/fx/<id>/<id>.mp4 (frame n = reel frame round(at * 30) + n), audio/<id>-riser.wav (a short move),
          work/<id>/ (the depth and layers, cached), and prints the SFX lines
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the words move.
"""
import argparse
import glob
import json
import os
import re
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30

# ---- the constants to change per video (the window itself is the edit.py FX entry: start it where the move starts)
MOVE_ON = ""                # the word the move lands on; '' = the last word that starts before 70% of the window
RETURN = (0.20, 0.03)       # s: the room goes home over this long, ending this far before the window does
SCALE = 1.62                # how much the far wall grows
CENTER = None               # the point the room rushes out of, reel px; None = behind the head (track)
WALL_DIST = 2.4             # how many times further from the camera the wall is than the speaker
NEAR = 1.25                 # 1/distance above this is foreground (a desk): it falls back a touch, never grows
MID_GAP = 0.18              # 1/distance this much above the wall's is furniture in front of it: it moves on its own
DESK_SCALE = 0.982          # the foreground falls back this much (its true value would drop it out of the frame)
PURE_AT = 0.15              # by this much of the move the wall has handed over to the empty room (when there is one)
SHUTTER = 0.5               # of a frame: motion blur on the room, like a real lens moving


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
PIPE = os.path.dirname(os.path.abspath(fxlib.__file__))
sys.path.insert(0, PIPE)
import depth  # noqa: E402
from common import load_edit, timeline  # noqa: E402


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
    w, h, x, y = load_edit(project).FRAMES[frame]
    k = hole.shape[1] / fxlib.size(load_edit(project).SRC)[0]   # hole.png is at the source's size
    crop = hole[round(y * k):round((y + h) * k), round(x * k):round((x + w) * k)]
    return cv2.dilate(cv2.resize(crop, (W, H), interpolation=cv2.INTER_NEAREST), np.ones((15, 15), np.uint8)) > 127


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


# ------------------------------------------------------------------ image tools
def nc(img, mask, sigma):
    m = mask.astype(np.float32)
    a = cv2.GaussianBlur(img * m[..., None], (0, 0), sigma)
    b = cv2.GaussianBlur(m, (0, 0), sigma)
    return a / np.maximum(b[..., None], 1e-4), b


def fill(img, ok):
    """extend what's known across what isn't, nearest scale first"""
    out = img.copy()
    todo = ~ok
    for s in (6, 14, 32, 80, 200):
        f, b = nc(img, ok, s)
        take = todo & (b > 0.04)
        out[take] = f[take]
        todo &= ~take
    return out


def membrane(img, ok, down=6, iters=700):
    """the wall behind what stood in front of it: a smooth surface stretched across the hole from the wall around it.
    The brightest wall pixels (lamps, windows, a print) stay out of it, or their light bleeds in as a ghost"""
    h, w = img.shape[:2]
    luma = img.mean(axis=2)
    if not ok.any():
        return img
    dark = float(np.percentile(luma[ok], 85)) + 4
    src = ok & (luma < dark)
    sw, sh = w // down, h // down
    weight = cv2.resize(src.astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA)
    low = cv2.resize(img * src[..., None], (sw, sh), interpolation=cv2.INTER_AREA) / np.maximum(weight[..., None], 1e-3)
    known = weight > 0.85
    if not known.any():
        return img
    x = low.copy()
    x[~known] = low[known].mean(axis=0)
    for _ in range(iters):
        avg = (np.roll(x, 1, 0) + np.roll(x, -1, 0) + np.roll(x, 1, 1) + np.roll(x, -1, 1)) / 4
        x = np.where(known[..., None], low, avg)
    up = cv2.GaussianBlur(cv2.resize(x, (w, h), interpolation=cv2.INTER_LINEAR), (0, 0), down)
    a = cv2.GaussianBlur((~ok).astype(np.float32), (0, 0), 6)[..., None]
    a = np.clip(a * 1.6, 0, 1) * (1 - np.clip((luma[..., None] - dark) / 20, 0, 1) * ok[..., None])   # never over the bright things themselves
    return img * (1 - a) + up * a


def guided(I, p, r, eps):
    """edge-aware smoothing of a mask p along the picture I (the guided filter): object edges come from the picture,
    not from the soft depth map"""
    k = (2 * r + 1, 2 * r + 1)
    mean = lambda x: cv2.boxFilter(x, -1, k)          # noqa: E731
    mI, mp = mean(I), mean(p)
    a = (mean(I * p) - mI * mp) / (mean(I * I) - mI * mI + eps)
    b = mp - a * mI
    return np.clip(mean(a) * I + mean(b), 0, 1)


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
    out[todo] = c2[ok].mean(axis=0) if ok.any() else 0
    return cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)


def smooth(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def build_curve():
    """the move: a long acceleration, a firm landing on the word. Integrates to 0..1"""
    us = np.linspace(0, 1, 2001)
    speed = us ** 1.7 * (1 - smooth((us - 0.86) / 0.14))
    p = np.cumsum(speed)
    return us, (p - p[0]) / (p[-1] - p[0])


US, PS = build_curve()


def riser_sound(path, dur):
    """the move is shorter than the kit's riser takes to peak, and the mix can't start a file partway: its last `dur`
    seconds up to the peak, with a short fade in"""
    from scipy.io import wavfile
    src = os.path.join(os.path.dirname(PIPE), "audio", "sfx", "riser.wav")
    sr, y = wavfile.read(src)
    y = y.astype(np.float32) / 32768
    if y.ndim == 1:
        y = np.stack([y, y], 1)
    env = np.convolve((y ** 2).mean(axis=1), np.ones(480) / 480, mode="same")
    peak = int(np.argmax(env))
    seg = y[max(0, peak - int(dur * sr)):peak + int(0.06 * sr)].copy()
    k = min(len(seg), int(0.03 * sr))
    seg[:k] *= np.linspace(0, 1, k)[:, None]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavfile.write(path, sr, (np.clip(seg, -1, 1) * 32767).astype(np.int16))
    return (peak - max(0, peak - int(dur * sr))) / sr


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="+", type=float, help="write these reel times as jpgs in work/<id>/ instead of the clip")
    a = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(a.project)), a.id
    A, B, frame, words = place(project, fid)
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    work = os.path.join(project, "work", fid)
    os.makedirs(work, exist_ok=True)

    # ---- the move, keyed to the words
    MOVE_FROM = A
    RETURN_TO = B - RETURN[1]
    RETURN_FROM = RETURN_TO - RETURN[0]
    land = word_at(words, MOVE_ON, A + 0.15, RETURN_FROM - 0.12) if MOVE_ON else None
    if not land:
        cands = [s for s, e, w in words if A + 0.25 <= s <= A + 0.7 * (B - A) and s < RETURN_FROM - 0.12]
        land = (cands[-1], None) if cands else (A + 0.6 * (B - A), None)
        if MOVE_ON:
            print(f"WARNING: {MOVE_ON!r} isn't spoken in the window: the move lands at {land[0]:.2f}")
    MOVE_TO = land[0]
    if not MOVE_FROM + 0.2 <= MOVE_TO <= RETURN_FROM - 0.1:
        sys.exit(f"the move ({MOVE_FROM:.2f} to {MOVE_TO:.2f}) and the return ({RETURN_FROM:.2f}) don't fit the window: "
                 "make it longer or pick another MOVE_ON")

    def progress(t):
        if t <= MOVE_FROM:
            return 0.0
        if t < MOVE_TO:
            return float(np.interp((t - MOVE_FROM) / (MOVE_TO - MOVE_FROM), US, PS))
        if t < RETURN_FROM:
            return 1.0
        if t < RETURN_TO:
            u = (t - RETURN_FROM) / (RETURN_TO - RETURN_FROM)
            return float(1 - (u * u * (3 - 2 * u)))
        return 0.0

    # ---- the room, at the live frame's levels
    room = room_of(project, frame)
    if room is None:
        sys.exit(f"dolly-zoom needs the room: work/c/room_{frame}.npy is missing. Film on a tripod, walk out for the "
                 "last 5 s (edit.EMPTY), and run the kit's plate tools")
    pure = room_of(project, frame, empty=True) if filmed_empty(project) else None
    TR = track_of(project)
    n_land = fxlib.fr(MOVE_TO)
    fc = next((TR[j]["face"] for k in range(len(TR)) for j in (n_land - k, n_land + k) if 0 <= j < len(TR) and TR[j].get("face")), None)
    if fc is None:
        sys.exit("work/tracks/track.json has no face: run the kit's track.py on this project first")
    cx_, cy_ = CENTER or (fc["cx"], fc["cy"] - 0.12 * fc["h"])
    C_ref = next(fxlib.frames(project, MOVE_TO, MOVE_TO + 1 / FPS))[1]
    al_ref = next(fxlib.alpha(project, MOVE_TO, MOVE_TO + 1 / FPS))[1].astype(np.float32) / 255

    # ---- depth: the room's, mapped onto a live frame's, where the speaker stands at distance 1 and the wall at WALL_DIST
    cache = os.path.join(work, "depth.npz")
    key = f"{frame} {n_land} " + " ".join(str(os.path.getmtime(p)) for p in glob.glob(os.path.join(project, "work", "c", f"room*_{frame}.npy")))
    z = np.load(cache) if os.path.exists(cache) else None
    if z is not None and str(z["key"]) == key:             # the depth is cached until the room or the landing frame changes
        disp_r, disp_p, disp_l = z["r"], z["p"], z["l"]
    else:
        print("depth: the room, the empty room, a live frame")
        disp_r = depth.infer(np.clip(room, 0, 255).astype(np.uint8), side=1036)
        disp_p = depth.infer(np.clip(pure, 0, 255).astype(np.uint8), side=1036) if pure is not None else disp_r
        disp_l = depth.infer(C_ref, side=1036)
        np.savez(cache, r=disp_r, p=disp_p, l=disp_l, key=key)
    seen = cv2.dilate((al_ref > 0.01).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0     # room the live frame shows

    def onto_live(d):
        """the room's depth in the live frame's units: a robust straight-line fit on the room both of them see"""
        x, y = d[seen][::7], disp_l[seen][::7]
        k = np.ones(len(x), bool)
        for _ in range(3):
            s, o = np.polyfit(x[k], y[k], 1)
            r = np.abs(s * x + o - y)
            k = r < max(np.median(r) * 2.5, 1e-3)
        return s * d + o
    disp_r, disp_p = onto_live(disp_r), onto_live(disp_p)
    box = (slice(int(fc["cy"] - 0.3 * fc["h"]), int(fc["cy"] + 0.3 * fc["h"])), slice(int(fc["cx"] - 0.3 * fc["w"]), int(fc["cx"] + 0.3 * fc["w"])))
    d_me = float(np.median(disp_l[box][al_ref[box] > 0.9])) if (al_ref[box] > 0.9).any() else float(np.median(disp_l[al_ref > 0.9]))
    d_wall = float(np.percentile(disp_r, 12))
    if d_me <= d_wall + 0.02:
        sys.exit(f"the depth model can't tell the speaker ({d_me:.3f}) from the wall ({d_wall:.3f}) here: this room has "
                 "too little depth for a dolly zoom")
    b_ = (1 - 1 / WALL_DIST) / (d_me - d_wall)
    a_ = 1 - b_ * d_me
    inv_r, inv_p = a_ + b_ * disp_r, a_ + b_ * disp_p
    print(f"depth: speaker {d_me:.3f}, wall {d_wall:.3f} -> 1/distance = {a_:.3f} + {b_:.3f} * depth")

    # ---- the room's layers. Foreground: nearer than the speaker, or the plate tools' desk
    desk_a, mic_a = plate_alpha(project, "desk", frame), plate_alpha(project, "mic", frame)
    near = cv2.morphologyEx((inv_r > NEAR).astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0
    # without a filmed empty room the patch the speaker always covered is a fill that depth reads as a speaker-shaped
    # object; it is wall the take never saw: it grows with the wall, smoothed in from the wall around it
    hole = None if pure is not None else plate_hole(project, frame, W, H)
    if hole is not None:
        near &= ~hole
        print(f"no filmed empty room: {100 * hole.mean():.0f}% of the crop is a fill the wall grows over, and it shows")
    if desk_a is not None:
        near |= desk_a > 0.5
    luma = cv2.cvtColor(np.clip(room, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    near_a = guided(luma, near.astype(np.float32), 4, 1e-3)
    gear = near | (mic_a > 0.1) if mic_a is not None else near      # never part of the wall: it stays where it is
    YS, XS = np.mgrid[0:H, 0:W].astype(np.float32)

    def fit_wall(ok):
        """the wall as a plane in 1/distance (affine in the image, so the move is a true homography)"""
        ys, xs = np.nonzero(ok)
        pick = np.linspace(0, len(xs) - 1, min(len(xs), 40000)).astype(int)
        xs, ys = xs[pick].astype(np.float64), ys[pick].astype(np.float64)
        M = np.column_stack([xs, ys, np.ones_like(xs)])
        v = inv_r[ys.astype(int), xs.astype(int)]
        c = np.linalg.lstsq(M, v, rcond=None)[0]
        for _ in range(3):
            r = np.abs(M @ c - v)
            keep = r < np.median(r) * 2.5 + 1e-4
            c = np.linalg.lstsq(M[keep], v[keep], rcond=None)[0]
        return c
    mid = (inv_r > 1 / WALL_DIST + MID_GAP) & ~near
    if hole is not None:
        mid &= ~hole
    for _ in range(2):                                    # furniture: well in front of the wall's own plane
        ok = ~cv2.dilate((mid | gear).astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool)
        coef = fit_wall(ok & ~hole if hole is not None else ok)      # a fill's depth says nothing about the wall
        plane = coef[0] * XS + coef[1] * YS + coef[2]
        mid = (inv_r > plane + MID_GAP) & ~near
    if hole is not None:
        mid &= ~hole
    mid = cv2.morphologyEx(mid.astype(np.uint8), cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) > 0
    mid_a = guided(luma, mid.astype(np.float32), 6, 1e-3) * cv2.dilate(mid.astype(np.uint8), np.ones((25, 25), np.uint8))
    wall_ok = cv2.dilate(((mid_a > 0.02) | gear).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0
    if hole is not None:
        wall_ok &= ~hole                                  # the membrane fills it from the real wall around it

    def wall_inv(qx, qy):
        return coef[0] * qx + coef[1] * qy + coef[2]

    # furniture moves by its own distance: grouped into a few depths, one scale each
    n_lab, lab = cv2.connectedComponents((mid_a > 0.5).astype(np.uint8))
    groups = []
    if n_lab > 1:
        med = np.array([np.median(inv_r[lab == i]) if (lab == i).any() else 0 for i in range(n_lab)])
        edges = np.quantile(med[1:], [0.25, 0.5, 0.75]) if n_lab > 4 else np.array([])
        bins = np.digitize(med, edges)
        for b in range(len(edges) + 1):
            ids = [i for i in range(1, n_lab) if bins[i] == b]
            if ids:
                m = np.isin(lab, ids)
                groups.append((float(np.median(med[ids])), guided(luma, m.astype(np.float32), 6, 1e-3) * cv2.dilate(m.astype(np.uint8), np.ones((25, 25), np.uint8))))
    groups.sort(key=lambda g: g[0])                       # far to near
    print("layers: the wall behind everything, the furniture")
    wall_h = membrane(room, wall_ok)
    if pure is not None:
        mid_p = (inv_p > (coef[0] * XS + coef[1] * YS + coef[2]) + MID_GAP) & (inv_p <= NEAR)
        ok_p = cv2.dilate((mid_p | (mid_a > 0.02) | gear).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0
        wall_p = membrane(pure, ok_p)
    else:
        wall_p = wall_h
    mid_img = fill(room, (mid_a > 0.9) & ~near)
    cv2.imwrite(os.path.join(work, "layers.jpg"), np.hstack([cv2.resize(np.clip(x, 0, 255).astype(np.uint8)[..., ::-1], (270, 480))
                                                             for x in (wall_p, mid_img * mid_a[..., None], np.dstack([near_a * 255] * 3))]))

    # how far back the camera pulls to grow the wall SCALE times behind the head
    pic = float(wall_inv(cx_, cy_))
    if SCALE * pic >= 1:
        sys.exit("the wall reads as nearly as close as the speaker: raise WALL_DIST or lower SCALE")
    z_max = (SCALE - 1) / (1 - SCALE * pic)               # SCALE = (1 + z) / (1 + z * pic)
    print(f"pull-back z = {z_max:.3f} speaker-distances; wall behind the head at {1 / pic:.2f}; "
          f"{len(groups)} furniture depth(s): " + ", ".join(f"{1 / g[0]:.2f}" for g in groups))
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))

    def remap(img, m):
        qx, qy = (cx_ + (X - cx_) / m).astype(np.float32), (cy_ + (Y - cy_) / m).astype(np.float32)
        return cv2.remap(img, qx, qy, cv2.INTER_CUBIC if img.ndim == 3 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def warp(z, q):
        """the room for a pull-back z: the wall (handing over to the empty room by q), furniture, back to front"""
        qx, qy = X.copy(), Y.copy()
        for _ in range(4):                                # the fixed point of p = c + (q - c) * m(q)
            m = (1 + z) / (1 + z * wall_inv(qx, qy))
            qx = cx_ + (X - cx_) / m
            qy = cy_ + (Y - cy_) / m
        mx, my = qx.astype(np.float32), qy.astype(np.float32)
        out = cv2.remap(wall_p, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE) * q
        if q < 1:
            out = out + cv2.remap(wall_h, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE) * (1 - q)
        for inv_g, ga in groups:
            m = (1 + z) / (1 + z * inv_g)
            ag = remap(ga, m)[..., None]
            out = out * (1 - ag) + remap(mid_img, m) * ag
        return out

    def desk(p):
        """the foreground: a touch, in the true direction (it is nearer than the speaker, so it falls back)"""
        m = 1 + (DESK_SCALE - 1) * p
        return remap(room, m), remap(near_a, m)[..., None]

    # the matte drops chunks of a top under a fast hand. Low in the frame, what is the speaker most of the window stays them
    n = fxlib.fr(B) - fxlib.fr(A)
    F = list(fxlib.frames(project, A, B))
    Al = [al for _, al in fxlib.alpha(project, A, B)]
    pos = [TR[i]["pose"] for i in range(fxlib.fr(A), min(fxlib.fr(B), len(TR))) if TR[i].get("pose")]
    if pos:
        solid_from = float(np.median([(p["ls"][1] + p["rs"][1]) / 2 for p in pos])) + 0.17 * float(np.median([abs(p["ls"][0] - p["rs"][0]) for p in pos]))
    else:
        solid_from = fc["chin"] + 0.6 * fc["h"]
    solid = np.percentile(np.stack(Al[::2]), 75, axis=0).astype(np.float32) / 255
    solid *= np.clip((np.arange(H, dtype=np.float32)[:, None] - solid_from) / 80, 0, 1)
    in_front = near_a[..., 0] if near_a.ndim == 3 else near_a        # where the original foreground is: the speaker there is in front of it
    want = {fxlib.fr(t) for t in a.stills} if a.stills else None
    d = out_dir(project, fid)
    out = None if want else fxlib.Writer(os.path.join(d, f"{fid}.mp4"), W, H, crf=14)
    for i, (f, C8) in enumerate(F[:n]):
        if want is not None and f not in want:
            continue
        t = f / FPS
        p_now, p_end = progress(t), progress(t + SHUTTER / FPS)
        C = C8.astype(np.float32)
        if p_now <= 0 and p_end <= 0:
            img = C                                         # the live frame, bit for bit
        else:
            # the shutter: the room averaged over the part of the interval it is open, as many samples as the move needs
            reach = abs(p_end - p_now) * z_max * 0.5 * 1000 * 0.45
            samples = int(np.clip(np.ceil(reach / 1.5), 1, 16))
            rm = 0
            for s_ in range(samples):
                pp = p_now + (p_end - p_now) * (s_ + 0.5) / samples if samples > 1 else p_now
                rm = rm + warp(z_max * pp, float(smooth(pp / PURE_AT)) if pure is not None else 0.0)
            rm = rm / samples
            al = np.maximum(Al[i].astype(np.float32) / 255, solid)
            if mic_a is not None:
                al = np.maximum(al, mic_a)                  # the mic doesn't move at all
            a3 = al[..., None]
            # the speaker: the live pixel, minus the real room behind their soft edge, over the moved room
            img = np.maximum(C - (1 - a3) * local_bg(C, al), 0) * np.clip(a3 / 0.03, 0, 1) + (1 - a3) * rm
            # the foreground falls back over the speaker, except where they were already in front of it (hands on a desk)
            Dn, Da = desk(p_now)
            Da = Da * (1 - (al * in_front)[..., None])
            img = img * (1 - Da) + Dn * Da
            # the live picture hands over to the moved room in the first 2% of the wall's growth, while it barely moves
            scale_far = (1 + z_max * p_now) / (1 + z_max * p_now * pic)
            w0 = float(np.clip(1 - (scale_far - 1) / 0.02, 0, 1))
            img = img * (1 - w0) + C * w0
        res = np.clip(np.round(img), 0, 255).astype(np.uint8)
        if out is not None:
            out.write(res)
        else:
            p = os.path.join(work, f"still_{t:.2f}.jpg")
            cv2.imwrite(p, cv2.cvtColor(res, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(p)
    if out is None:
        return
    out.close()
    print(os.path.join(d, f"{fid}.mp4"))
    print("SFX (edit.SOUND['sfx']):")
    move = MOVE_TO - MOVE_FROM
    if move < 0.95:
        lead = riser_sound(os.path.join(project, "audio", f"{fid}-riser.wav"), move)
        print(f'    dict(at={MOVE_TO - lead:.3f}, name="{fid}-riser", db=-12, align="start"),   # audio/{fid}-riser.wav: the riser\'s last {move:.2f} s, peak on the landing')
    else:
        print(f'    ({MOVE_TO:.3f}, "riser", -12),                 # under the move, peak on the landing')
    print(f'    ({MOVE_TO:.3f}, "impact-low", -14),             # the landing')
    print(f'    ({RETURN_FROM + 0.11:.3f}, "whoosh-soft", -15),            # the room goes home')


if __name__ == "__main__":
    main()
