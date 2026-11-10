#!/usr/bin/env python3
"""shockwave: the room takes a hit on one word. A single refractive ring is born inside the speaker's head and radiates
out across the frame: pure displacement of the real picture (cv2.remap), nothing added, no colour, no flash. A thin band
of lens distortion expands, its strength falling as it travels, plus a 2-frame shove on the hit. BODY sets how much of
it the speaker takes below the head (0 = the room ripples behind a solid speaker, 1 = the whole picture ripples);
HEAD_STEADY keeps the head out of it either way, so the face stays readable and the ring really comes from behind it.

The image is the matte equation: the speaker with their share of the field, plus the room's own change behind whatever
alpha they have there. Zero displacement is the live frame bit for bit (every frame outside the ring is copied as it
is), and nothing estimates a foreground colour. The room behind the speaker's edge is the filmed empty room's
(work/c/room_<FRAME>.npy when work/plate/plate.json says "empty"); otherwise it is read off the live frame just outside
the edge, every frame: a fallback plate is jagged exactly there (it is where the speaker always sat) and would tear.

Run: PY fx/<id>/gen.py <project> [<id>] [--body 0.6] [--steady 0|1] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>: the window), words.json (HIT_ON), timeline.json (the crop),
          public/clean.mp4, public/subject.webm, work/tracks/track.json (the head), work/c/room_<FRAME>.npy (optional)
          and work/plate/plate.json (was the empty room filmed)
  writes  <project>/fx/<id>/<id>.mp4 (frame n = reel frame round(at * 30) + n) and prints the SFX line
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

# ---- the constants to change per video (the window itself is the edit.py FX entry)
HIT_ON = ""                 # the spoken word the ring lands on; '' = the first word that starts inside the window
HIT_AFTER = 0.0333          # s after the window start when HIT_ON isn't spoken in it (start the window a frame early)
CENTER = None               # impact point in reel px, None = behind the head (track: a little above the face centre)
BODY = 0.55                 # how much of the ring the speaker takes below the head: 0 room only, 1 the whole picture
HEAD_STEADY = True          # the head does not move at all
RING_FRAMES = 13            # frames the ring takes to leave the frame
BIRTH = 0.27                # where the ring is born, as a share of the face height: inside the head, nobody sees it start
RING_EASE = 1.35            # how much it slows as it travels: 1 = constant speed
WIDTH = (46.0, 120.0)       # px: half width of the band, at birth and at the end
STRENGTH = (17.0, 3.2)      # px of displacement, at birth and at the end. If you can see the band as a shape it's too much
STRENGTH_POW = 1.15         # how fast the strength falls along the way
SHOVE = [(0, 7.0, -3.0), (1, 2.5, -1.0)]   # (frames after the hit, dy, dx): the room is shoved, then back


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


def filmed_empty(project):
    """True when the plate tools have the room behind the speaker: a filmed empty room (edit.EMPTY or
    EMPTY_CLIP), or a photo or generated background given to plate_finish.py --fill (mode "filled"). Without one the
    patch the speaker always covered is a fill, and its edge is exactly where the speaker's own edge is"""
    try:
        return json.load(open(os.path.join(project, "work", "plate", "plate.json"))).get("mode") in ("empty", "filled")
    except (OSError, ValueError):
        return False


def room_of(project, frame):
    """the room as the take saw it, at live levels, when it comes from a filmed empty room; else None"""
    p = os.path.join(project, "work", "c", f"room_{frame}.npy")
    return np.load(p).astype(np.float32) if os.path.exists(p) and filmed_empty(project) else None


def nc(img, mask, sigma):
    m = mask.astype(np.float32)
    a = cv2.GaussianBlur(img * m[..., None], (0, 0), sigma)
    b = cv2.GaussianBlur(m, (0, 0), sigma)
    return a / np.maximum(b[..., None], 1e-4), b


def local_bg(C, a):
    """the room behind the speaker's soft edge in this frame: the live room just outside it, spread inward (at half size:
    it is smooth anyway)"""
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


def face_near(TR, i):
    """the track's face on frame i, else the nearest frame that has one"""
    for k in range(0, len(TR)):
        for j in (i - k, i + k):
            if 0 <= j < len(TR) and TR[j].get("face"):
                return TR[j]["face"]
    sys.exit("work/tracks/track.json has no face in it: run the kit's track.py on this project first")


# ------------------------------------------------------------------ the ring
def ring_field(k, cx, cy, r0, r_end, X, Y):
    """the sampling offset k frames after the hit: a derivative-of-gaussian radial push, so the band is a lens (it bunches
    the picture up on one side and stretches it on the other, zero net shift), plus the shove. None when it is all over"""
    u = k / float(RING_FRAMES)
    dx, dy = 0.0, 0.0
    for f, sy, sx in SHOVE:
        if f == k:
            dx, dy = sx, sy
    if u >= 1 and dx == 0 and dy == 0:
        return None
    fx_, fy_ = np.full(X.shape, -dx, np.float32), np.full(X.shape, -dy, np.float32)
    if u < 1:
        ease = 1 - (1 - u) ** RING_EASE
        R = r0 + (r_end - r0) * ease
        w = WIDTH[0] + (WIDTH[1] - WIDTH[0]) * ease
        s = (STRENGTH[0] + (STRENGTH[1] - STRENGTH[0]) * u ** (1 / STRENGTH_POW)) * min(1.0, (1 - u) * 6)
        rx, ry = X - cx, Y - cy
        r = np.sqrt(rx * rx + ry * ry) + 1e-3
        x = (r - R) / w
        d = s * 1.6487 * x * np.exp(-0.5 * x * x)           # the peak of |x exp(-x^2/2)| is at 1, value 0.6065
        fx_ -= d * rx / r
        fy_ -= d * ry / r
    return fx_, fy_


def head_mask(fc, shape):
    """1 on the head, soft into the neck: the displacement field stays continuous, so nothing tears"""
    m = np.zeros(shape, np.float32)
    cx, cy = fc["cx"], (fc["top"] + fc["chin"]) / 2 - 0.10 * fc["h"]
    cv2.ellipse(m, (int(cx), int(cy)), (int(fc["w"] * 0.74), int(fc["h"] * 1.02)), 0, 0, 360, 1.0, -1)
    return cv2.GaussianBlur(m, (0, 0), max(8.0, 0.062 * fc["h"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--body", type=float, default=BODY, help="0 room only .. 1 the whole picture")
    ap.add_argument("--steady", type=int, choices=(0, 1), default=int(HEAD_STEADY), help="1 keeps the head still")
    ap.add_argument("--stills", nargs="+", type=float, help="write these reel times as jpgs in work/<id>/ instead of the clip")
    a = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(a.project)), a.id
    A, B, frame, words = place(project, fid)
    hit = word_at(words, HIT_ON, A, B)
    t_hit = hit[0] if hit else A + HIT_AFTER
    if HIT_ON and not hit:
        print(f"WARNING: {HIT_ON!r} isn't spoken in {A:.2f}-{B:.2f}: the ring lands at {t_hit:.2f}")
    n_hit = fxlib.fr(t_hit)
    if fxlib.fr(B) - n_hit < RING_FRAMES + 2:
        print(f"WARNING: the window ends {fxlib.fr(B) - n_hit} frames after the hit; the ring needs {RING_FRAMES + 2}")
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    TR = track_of(project)
    fc = face_near(TR, n_hit)
    cx, cy = CENTER if CENTER else (fc["cx"], fc["cy"] - 0.12 * fc["h"])
    r0 = BIRTH * fc["h"]
    r_end = max(np.hypot(px - cx, py - cy) for px in (0, W) for py in (0, H)) + WIDTH[1]
    room = room_of(project, frame)
    body, steady = a.body, bool(a.steady)
    if room is None:
        print("no filmed empty room: the room behind the speaker's edge is read off each live frame")
    print(f"{fid}: hit {t_hit:.3f} (frame {n_hit}) from {cx:.0f},{cy:.0f}, crop {frame}, body {body}, head steady {steady}")
    want = {fxlib.fr(t) for t in a.stills} if a.stills else None
    d = out_dir(project, fid)
    work = os.path.join(project, "work", fid)
    out = None if want else fxlib.Writer(os.path.join(d, f"{fid}.mp4"), W, H, crf=14)
    Al = {i: al for i, al in fxlib.alpha(project, A, B)}
    for i, c in fxlib.frames(project, A, B):
        if want is not None and i not in want:
            continue
        k = i - n_hit
        fld = ring_field(k, cx, cy, r0, r_end, X, Y) if k >= 0 else None
        if fld is None:
            img = c                                       # the live frame, bit for bit
        else:
            fx_, fy_ = fld
            s = np.full((H, W), body, np.float32)
            if steady:
                s *= 1 - head_mask(face_near(TR, i), (H, W))
            mx, my = X + s * fx_, Y + s * fy_
            Cw = cv2.remap(c, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
            R = room if room is not None else local_bg(c.astype(np.float32), Al[i].astype(np.float32) / 255)
            # the speaker with their share of the field, plus the room's own change behind whatever alpha they have
            aw = (cv2.remap(Al[i], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32) / 255)[..., None]
            Rs = cv2.remap(R, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            Rf = cv2.remap(R, X + fx_, Y + fy_, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            img = np.clip(np.round(Cw + (1 - aw) * (Rf - Rs)), 0, 255).astype(np.uint8)
        if out is not None:
            out.write(img)
        else:
            os.makedirs(work, exist_ok=True)
            p = os.path.join(work, f"still_{i / FPS:.2f}.jpg")
            cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(p)
    if out is None:
        return
    out.close()
    print(os.path.join(d, f"{fid}.mp4"))
    print("SFX (edit.SOUND['sfx']):")
    print(f'    ({t_hit:.3f}, "impact-low", -14),       # the hit, under the voice')


if __name__ == "__main__":
    main()
