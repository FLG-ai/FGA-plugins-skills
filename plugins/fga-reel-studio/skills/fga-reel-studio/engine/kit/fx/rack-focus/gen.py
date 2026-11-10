#!/usr/bin/env python3
"""rack-focus: nothing is added. The room falls out of focus and dims behind the speaker, as if a lens racked to their
eyes and someone brought the lights down. Lens-disc blur in linear light, its size per pixel from depth (the far wall
most, a chair right behind them less, a desk in front some), real focus breathing. The speaker stays the live pixels,
razor sharp; a desk in front of them goes soft over them. Everything is written into one clip of the live shot, so lips
are in sync by construction (each frame is that frame of clean.mp4).

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>: the window), words.json (the cue words), public/clean.mp4,
          public/subject.webm, the room (room_<FRAME>.npy from the plate tools; without one, the window's own frames),
          public/plates/desk_<FRAME>.webm when there is one, work/tracks/track.json (optional)
  writes  <project>/fx/<id>/<id>.mp4, fx.html, fx.js; --stills writes JPGs to <project>/work/fx/<id>/ and nothing else
<id> defaults to this folder's name. Rerun it whenever the window or the cut moves. Needs the depth model (downloaded
by pipeline/depth.py on first use).
"""
import argparse
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
W, H = 1080, 1920           # replaced by clean.mp4's own size in main(): the effect works on any canvas

# ---- the table: every value that is a choice, not a measurement. Geometry and depth are read off the footage.
RACK_ON = (None, None)      # (cue word the rack starts on, cue word it lands on); None = first word / a word near 62% in
RACK_FALLBACK = (0.03, 0.62)  # s after the window start, fraction of the window: where it starts / lands without a cue
R_FAR = None                # lens blur radius on the far wall, px (30 reads about like CSS blur(15px)); None = 30 for a
                            # camera on a tripod, 18 for a phone take (a selfie lens is shallow already)
DIM = 0.30                  # the room's lights come down 30%
BREATH = 0.015              # the room grows 1.5% as focus racks: real lenses breathe
DESK_R = 15.0               # lens blur radius of the desk's edge where it crosses the speaker, px
FOCUS_DEPTH = None          # override: the speaker's depth on depth.infer's scale (0 far .. 1 near); None = measured
HOLE_PAD = 27               # px around everything the speaker covers that gets refilled before the blur
SOLID_FROM_Y = None         # below this y the matte holds what was the speaker for most of the window (a fast hand
                            # can drop chunks of it); None = 100 px under the shoulders, else 62% down the frame
KEEP_NEAR = True            # what the matte missed at the speaker's distance or a little nearer (a book in their hands,
                            # the chair under them) stays sharp: read off each frame's own depth
SEED = 5


def _pipeline():
    """the kit's pipeline on the import path: REEL_KIT, this folder's grandparent when it runs in the library, else
    PY's own (setup puts the pipeline on PY's import path)"""
    for c in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        p = os.path.join(c, "pipeline") if c else ""
        if p and os.path.exists(os.path.join(p, "fxlib.py")):
            sys.path.insert(0, os.path.abspath(p))
            return
    import importlib.util
    if importlib.util.find_spec("fxlib") is None:
        sys.exit("can't import the kit's fxlib: run this with the kit's PY (setup puts the pipeline on its path), or set REEL_KIT=<the kit folder>")


_pipeline()
import fxlib  # noqa: E402
from common import load_edit  # noqa: E402


# ---- the project
def window(project, fid):
    """the edit, the timeline and the effect's window (its edit.FX entry; "end" resolved like the build does)"""
    F = fxlib.entry(project, fid)
    return load_edit(project), json.load(open(os.path.join(project, "timeline.json"))), float(F["at"]), float(F["end"])


def words(project):
    p = os.path.join(project, "words.json")
    return [(w["start"], w["end"], w["text"]) for w in json.load(open(p))] if os.path.exists(p) else []


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def word_at(ws, text, after, before=1e9):
    """the start of the first spoken word `text` at or after `after` (and before `before`), else None: fx.js's wordAt"""
    for s, _, t in ws:
        if after - 0.001 <= s < before and norm(t) == norm(text):
            return s
    return None


def frame_at(TL, E, t):
    shots = [(s["t"], s["frame"]) for s in TL.get("shots", [])] or list(E.SHOTS)
    return [f for a, f in shots if a <= t + 1e-3][-1]


def room_npy(project, frame, empty=False):
    """the room behind the speaker on this crop at live levels (plate_finish.py: work/c/room_<FRAME>.npy), or None"""
    p = os.path.join(project, "work", "c", f"room_{'empty_' if empty else ''}{frame}.npy")
    return fxlib.room(project, frame, empty=empty).astype(np.float32) if os.path.exists(p) else None


def plate_mode(project):
    """'empty' (the plate came from a real empty room), 'fallback' (the patch the speaker always covered is inpainted and
    shows once they move) or None (no plate tools run)"""
    p = os.path.join(project, "work", "plate", "plate.json")
    return json.load(open(p)).get("mode") if os.path.exists(p) else None


def plate_alpha(project, name, frame):
    """the alpha of a static plate layer (desk_<FRAME>.webm, mic_<FRAME>.webm) as float32 0..1, or None"""
    p = os.path.join(project, "public", "plates", f"{name}_{frame}.webm")
    if not os.path.exists(p):
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", p, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         capture_output=True).stdout
    if len(raw) < W * H * 4:
        return None
    a = np.frombuffer(raw[:W * H * 4], np.uint8).reshape(H, W, 4)[..., 3].astype(np.float32) / 255
    return a if a.max() > 0.05 else None


def tracks_or_none(project):
    """work/tracks/track.json's frames (track.py), or None: everything that uses it has a fallback"""
    p = os.path.join(project, "work", "tracks", "track.json")
    return fxlib.tracks(project)["frames"] if os.path.exists(p) else None


# ---- image helpers
def nc(img, mask, sigma):
    m = mask.astype(np.float32)
    a = cv2.GaussianBlur(img * m[..., None], (0, 0), sigma)
    b = cv2.GaussianBlur(m, (0, 0), sigma)
    return a / np.maximum(b[..., None], 1e-4), b


def membrane(img, ok, down=4, iters=500):
    """a smooth surface stretched across the hole from what is around it"""
    h, w = img.shape[:2]
    sw, sh = w // down, h // down
    weight = cv2.resize(ok.astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA)
    low = cv2.resize(img * ok[..., None], (sw, sh), interpolation=cv2.INTER_AREA) / np.maximum(weight[..., None], 1e-3)
    known = weight > 0.85
    if not known.any():
        return img
    x = low.copy()
    x[~known] = low[known].mean(axis=0)
    for _ in range(iters):
        avg = (np.roll(x, 1, 0) + np.roll(x, -1, 0) + np.roll(x, 1, 1) + np.roll(x, -1, 1)) / 4
        x = np.where(known[..., None], low, avg)
    up = cv2.GaussianBlur(cv2.resize(x, (w, h), interpolation=cv2.INTER_LINEAR), (0, 0), down)
    a = np.clip(cv2.GaussianBlur((~ok).astype(np.float32), (0, 0), 4)[..., None] * 1.6, 0, 1)
    return img * (1 - a) + up * a


def local_bg(C, a):
    """what is really behind the speaker's soft edge in this frame: the live room just outside it"""
    out = C.copy()
    todo = np.ones(a.shape, bool)
    ok = a < 0.01
    for s_ in (5, 12, 30, 80):
        f_, b_ = nc(C, ok, s_)
        take = todo & (b_ > 0.03)
        out[take] = f_[take]
        todo &= ~take
    return out


def near_extra(live, a1, desk, face, state):
    """pixels the matte missed that are as near as the speaker (a held book, the chair they sit in), from this frame's
    depth smoothed over frames. Thin bands round their outline are dropped: kept sharp, they would read as a halo"""
    import depth
    d = depth.infer(live, side=518)
    state["d"] = d if state.get("d") is None else 0.6 * d + 0.4 * state["d"]
    d = state["d"]
    spk = a1 > 0.95
    if face:
        band = np.zeros_like(spk)
        band[int(max(0, face["top"])):int(min(H, face["chin"] + 0.3 * face["h"]))] = True
        if (spk & band).sum() > 500:
            spk &= band
    if spk.sum() < 500:
        return None
    focus, far, near = float(np.median(d[spk])), float(np.percentile(d, 5)), float(np.percentile(d, 99.5))
    lo, hi = focus - 0.35 * max(0.02, focus - far), focus + 0.6 * max(0.02, near - focus)
    fg = (d > lo) & (d < hi) & (a1 < 0.95)              # missed, or only half there (a matte unsure of a lap or a chair)
    if desk is not None:
        fg &= desk < 0.3
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] < 1500:
            fg[lab == k] = 0
    return cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 2.0) if fg.any() else None


def disc(r):
    """an anti-aliased lens disc of radius r"""
    n = int(np.ceil(r)) + 1
    s = 4
    y, x = np.mgrid[-n * s:n * s + 1, -n * s:n * s + 1] / s
    m = ((x * x + y * y) <= r * r).astype(np.float32)
    k = cv2.resize(m, (2 * n + 1, 2 * n + 1), interpolation=cv2.INTER_AREA)
    return k / k.sum()


def smoother(u):
    u = np.clip(u, 0, 1)
    return u * u * u * (u * (u * 6 - 15) + 10)


# ---- what gets blurred
def background(project, frame, A, B, al_list, desk, work):
    """the room to blur. What this window's own frames show of it wins (a stale plate, or a fallback plate's inpainted
    patch, never shows); the plate fills only what the window never sees; then the patch the speaker covers is refilled
    from what is around it: a blur reaches about R_FAR px, so anything hidden behind them (a chair, the plate's fill)
    would bleed out round their outline"""
    cache = os.path.join(work, f"room_{frame}_{fxlib.fr(A)}_{fxlib.fr(B)}.npy")
    if os.path.exists(cache):
        return np.load(cache)
    acc, cnt = np.zeros((H, W, 3), np.float64), np.zeros((H, W), np.float64)
    for k, (_, rgb) in enumerate(fxlib.frames(project, A, B)):
        if k % 2 or k >= len(al_list):
            continue
        vis = cv2.dilate((al_list[k] > 8).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0
        acc[vis] += rgb[vis]
        cnt += vis
    seen = (acc / np.maximum(cnt, 1)[..., None]).astype(np.float32)
    covered = np.max(np.stack(al_list), axis=0) > 8
    room = room_npy(project, frame)
    if plate_mode(project) == "fallback":
        print("note: a fallback plate (no empty room filmed). The speaker stays put and the patch they cover is refilled "
              "from the room around it before the blur, so it holds; only an object they move a long way could show it")
    if room is None:                    # no plate: the window's own frames only (a locked-off shot)
        print("no room_<FRAME>.npy: the room comes from the window's own frames (locked-off shots only)")
        room = seen
        covered |= cnt == 0
    else:
        w = np.clip(cv2.GaussianBlur((cnt >= 2).astype(np.float32), (0, 0), 3) * 1.5 - 0.25, 0, 1)[..., None]
        room = room * (1 - w) + seen * w
    hole = cv2.dilate(covered.astype(np.uint8), np.ones((HOLE_PAD, HOLE_PAD), np.uint8)) > 0
    keep = desk > 0.5 if desk is not None else np.zeros((H, W), bool)
    out = membrane(room, ~hole & ~keep)
    out = np.where(keep[..., None], room, out).astype(np.float32)
    np.save(cache, out)
    return out


def depth_field(rgb_room, live, al, tr, n0, desk):
    """0 where the speaker is in focus, 1 on the far wall (more in front of them). The room's depth is mapped onto the
    scale of a live frame (depth.infer normalises each image) through the room both of them see, and the speaker's own
    depth is measured on that live frame"""
    import depth
    d_room = cv2.GaussianBlur(depth.infer(np.clip(rgb_room, 0, 255).astype(np.uint8), side=770), (0, 0), 6)
    d_live = cv2.GaussianBlur(depth.infer(live, side=770), (0, 0), 3)
    a = al.astype(np.float32) / 255
    seen = cv2.dilate((a > 0.03).astype(np.uint8), np.ones((41, 41), np.uint8)) == 0
    if desk is not None:
        seen &= desk < 0.05
    if seen.sum() > 5000:
        k, c = np.polyfit(d_room[seen][::7], d_live[seen][::7], 1)
        if k > 0.05:
            d_room = d_room * k + c
    spk = a > 0.95
    if tr and n0 < len(tr) and tr[n0].get("face"):            # focus is on the face, not the hands or the chest
        f = tr[n0]["face"]
        band = np.zeros_like(spk)
        band[int(max(0, f["top"])):int(min(H, f["chin"] + 0.6 * f["h"]))] = True
        if (spk & band).sum() > 500:
            spk &= band
    focus = FOCUS_DEPTH if FOCUS_DEPTH is not None else float(np.median(d_live[spk])) if spk.sum() > 500 else float(np.percentile(d_room, 70))
    far = min(focus - 0.05, float(np.percentile(d_room, 2)))
    near = max(focus + 0.2, float(np.percentile(d_room, 99.5)))
    field = np.where(d_room < focus, (focus - d_room) / (focus - far), (d_room - focus) / (near - focus))
    print(f"depth: the speaker {focus:.3f}, far wall {far:.3f}, nearest {near:.3f}")
    return np.clip(field, 0, 1.1).astype(np.float32)


def rack_times(ws, A, B):
    """(start, land): the cue words when they are spoken in the window, else the first word and the word nearest 62% in"""
    span = B - A
    if RACK_ON[0]:
        t0 = word_at(ws, RACK_ON[0], A, B)
        if t0 is None:
            print(f"WARNING: cue word {RACK_ON[0]!r} is not spoken in the window: the rack starts {RACK_FALLBACK[0]}s in")
    else:
        t0 = next((s for s, _, _ in ws if A - 0.001 <= s < B), None)
    t0 = A + RACK_FALLBACK[0] if t0 is None else t0
    want = A + RACK_FALLBACK[1] * span
    if RACK_ON[1]:
        t1 = word_at(ws, RACK_ON[1], t0 + 0.05, B)
        if t1 is None:
            print(f"WARNING: cue word {RACK_ON[1]!r} is not spoken after the start: it lands {RACK_FALLBACK[1]:.0%} into the window")
            t1 = want
    else:
        cands = [s for s, _, _ in ws if t0 + 0.2 <= s < B - 0.1]
        t1 = min(cands, key=lambda s: abs(s - want)) if cands else want
    if t1 - t0 < 0.15:
        t1 = min(B - 0.05, t0 + 0.5 * span)
    return t0, t1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="*", type=float, help="seconds on the output timeline: write these frames as JPGs only")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    global W, H
    E, TL, A, B = window(project, fid)
    W, H = fxlib.size(os.path.join(project, "public", "clean.mp4"))
    frame = frame_at(TL, E, A)
    if any(A + 0.5 / FPS < c < B - 0.5 / FPS for c in TL.get("picture_cuts", []) + TL.get("reframes", [])):
        print("WARNING: the window spans a picture change: the room only matches one framing. End it on the cut.")
    out_dir, work = os.path.join(project, "fx", fid), os.path.join(project, "work", "fx", fid)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    ws = words(project)
    R0, R1 = rack_times(ws, A, B)
    src_w, src_h = fxlib.size(E.SRC) if os.path.exists(getattr(E, "SRC", "")) else (W, H)
    r_far = R_FAR if R_FAR is not None else (30.0 if src_w > src_h else 18.0)
    print(f"{fid}: {A:.3f}-{B:.3f} on {frame}, the rack starts {R0:.3f} and lands {R1:.3f}, R_FAR {r_far:.0f} px")

    Al = [a.copy() for _, a in fxlib.alpha(project, A, B)]
    if not Al:
        sys.exit("public/subject.webm has no frames in the window: run pipeline/cutout.py (or matte.py) first")
    desk = plate_alpha(project, "desk", frame)
    tr = tracks_or_none(project)
    n0 = fxlib.fr(A)
    rgb = background(project, frame, A, B, Al, desk, work)
    live0 = next(fxlib.frames(project, A, A + 1 / FPS))[1]
    field = depth_field(rgb, live0, Al[0], tr, n0, desk)
    lin = (np.clip(rgb, 0, 255) / 255) ** 2.2
    # a table of lens blurs in linear light; each frame picks per pixel between neighbours
    radii = [0, 1.5, 3, 5, 7.5, 10.5, 14, 18, 22.5, 27, 32, 37]
    while radii[-1] < r_far * 1.1:
        radii.append(radii[-1] + 5.5)
    pad = int(radii[-1]) + 8
    big = cv2.copyMakeBorder(lin.astype(np.float32), pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    table = np.stack([lin.astype(np.float32)] + [cv2.filter2D(big, -1, disc(r), borderType=cv2.BORDER_REPLICATE)[pad:-pad, pad:-pad] for r in radii[1:]])
    radii = np.array(radii, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    desk_mask = desk if desk is not None else np.zeros((H, W), np.float32)
    # a fast hand can drop chunks of the matte low in the frame: what was the speaker for most of the window stays the speaker
    solid_y = SOLID_FROM_Y
    if solid_y is None:
        p = tr[n0].get("pose") if tr and n0 < len(tr) else None
        solid_y = (max(p["ls"][1], p["rs"][1]) + 100) if p else 0.62 * H
    solid = np.percentile(np.stack(Al[::2]), 75, axis=0).astype(np.float32) / 255
    solid *= np.clip((np.arange(H, dtype=np.float32)[:, None] - solid_y) / 80, 0, 1)
    want = None if args.stills is None else {fxlib.fr(t) for t in args.stills}
    wr = None if want is not None else fxlib.Writer(os.path.join(out_dir, f"{fid}.mp4"), w=W, h=H, crf=13)
    rng = np.random.default_rng(SEED)
    near_state = {}
    for (n, live), al8 in zip(fxlib.frames(project, A, B), Al):
        t = n / FPS
        noise = rng.normal(0, 0.9, (H, W, 1))       # drawn every frame, stills included, so a still is the frame the clip has
        if want is not None and n not in want:
            continue
        C = live.astype(np.float32)
        p = float(smoother((t - R0) / (R1 - R0)))
        if p <= 0:
            img = C                                  # the live frame, bit for bit
        else:
            rad = field * r_far * p
            i = np.clip(np.searchsorted(radii, rad) - 1, 0, len(radii) - 2)
            f = np.clip((rad - radii[i]) / (radii[i + 1] - radii[i]), 0, 1)[..., None]
            out = table[i, yy, xx] * (1 - f) + table[i + 1, yy, xx] * f
            out = out ** (1 / 2.2) * 255 * (1 - DIM * p)
            s = 1 + BREATH * p
            M = np.array([[s, 0, (1 - s) * W / 2], [0, s, (1 - s) * H / 2]], np.float32)
            out = cv2.warpAffine(out.astype(np.float32), M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            out = out + noise * min(1, p * 4)        # the sensor's noise doesn't go out of focus; it also keeps the dark blur from banding
            a1 = np.maximum(al8.astype(np.float32) / 255, solid)
            if KEEP_NEAR:
                face = tr[n]["face"] if tr and n < len(tr) and tr[n].get("face") else None
                extra = near_extra(live, a1, desk, face, near_state)
                if extra is not None:
                    a1 = np.maximum(a1, extra)
            a3 = a1[..., None]
            gate = np.clip(a3 / 0.03, 0, 1)
            img = np.maximum(C - (1 - a3) * local_bg(C, a1), 0) * gate + (1 - a3) * out
            if desk is not None:                     # the desk in front of them is out of focus too: its edge melts over them.
                front = desk_mask * (1 - a1)         # only where it hides them: hands resting on it stay sharp
                Da = cv2.filter2D(front, -1, disc(max(DESK_R * p, 0.5)), borderType=cv2.BORDER_REPLICATE)[..., None]
                img = img * (1 - Da) + out * Da
            w0 = float(np.clip(1 - p / 0.03, 0, 1))    # the live frame hands over to the room while the rack has barely started
            img = img * (1 - w0) + C * w0
        res = np.clip(img + 0.5, 0, 255).astype(np.uint8)
        if wr is not None:
            wr.write(res)
            print(f"\r{n} p={p:.3f}", end="", flush=True)
        else:
            path = os.path.join(work, f"still_{t:.2f}.jpg")
            cv2.imwrite(path, cv2.cvtColor(res, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(path)
    if wr is None:
        return
    wr.close()
    print()
    st = f"position:absolute;left:0;top:0;width:{W}px;height:{H}px;"
    with open(os.path.join(out_dir, "fx.html"), "w") as fh:
        fh.write(f"<!-- {fid} [rack-focus] (cam). Written by gen.py for the window {A:.3f}-{B:.3f}: rerun it if the window or the cut moves. -->\n"
                 + fxlib.tag(f"{fid}-v", f"fx/{fid}/{fid}.mp4", A, B, "g", "{{T0}}", st) + "\n")
    with open(os.path.join(out_dir, "fx.js"), "w") as fh:
        fh.write("// rack-focus: everything is in the clip (class g takes the live grade). The build shows this layer from A to B.\n")
    print(f"wrote {out_dir}/{fid}.mp4, fx.html, fx.js. No sound on purpose: nobody should know why it suddenly felt expensive.")


if __name__ == "__main__":
    main()
