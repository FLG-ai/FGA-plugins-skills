#!/usr/bin/env python3
"""live-cursor: a multiplayer cursor with a name flag walks into the shot and edits the video while the speaker keeps
talking: rubber-bands them, the box snaps to their real silhouette with a live pixel readout, drags them across the
room (the room, the desk and a mic stay, they come forward a touch while held, snap to a guide through their face),
fetches a 9:16 card of the creator's own clip from off frame, drops it in the gap, one last click, then everything
clears and they are back on the live pixels. Everything moves on per-frame values computed from the BEATS table.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  writes  <project>/fx/<id>/       the overlay (layer top): cursor, flag, marquee, the box, guides, cards
          <project>/fx/<id>-room/  the room with the speaker moved on it (layer cam), one filmed clip, only when BEATS
                                   has a drag and the project has a room (room_<FRAME>.npy from the plate tools)
          and prints the edit.FX entry for <id>-room and the SOUND lines
  reads   <project>/edit.py (the FX entry <id>: the cursor enters at `at`, everything is home by `end`), words.json,
          timeline.json, public/clean.mp4, public/subject.webm, work/tracks/track.json (the guide; optional),
          public/plates/desk_<FRAME>.webm and mic_<FRAME>.webm, the style pack, the card's clip (`src` in BEATS)
<id> defaults to this folder's name. Rerun it whenever the window, the cut or BEATS change.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
from fractions import Fraction
from html import escape

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30

# ---- the table: all that changes on another video. Times: a cue word (str, the first time it is spoken after the
# previous beat) or seconds after the window's start (float); the times inside a beat are seconds after its `at`.
# Positions read off the speaker; give one as (x, y) px to pin it.
NAME = None                          # the flag. None = the creator's first name from the pack, else their handle, else no flag.
                                     # Set "Claude" (or the AI they name) when the line says the AI does the work
NOTE = "a cursor walks in, selects the speaker with a live pixel readout, drags them across the room, drops a card of their clip in the gap"
BEATS = [
    dict(act="enter",  at=0.0,  arrive=0.65),                  # a curved glide in, a correction, a hover above the head
    dict(act="select", at=0.83, release=0.15),                 # a marquee across them; on release the box snaps to their silhouette
    dict(act="drag",   at=1.05, snap=0.20, dx=None),           # presses on them, they follow, snap to a guide; dx None = 21% of
                                                               # the width, away from the side they sit nearer
    dict(act="drop",   at=1.27, grab=0.14, land=0.31,          # fetches a 9:16 card from off frame and drops it in the gap
         src="", src_at=0.0, src_on=None, label="one reel"),   # src: the creator's own clip (a project path); its src_at
                                                               # second plays on src_on (a cue word; None = the last click).
                                                               # No src: a labelled placeholder card
    dict(act="click",  at=1.91),                               # one last click, the selection lets go
    dict(act="exit",   at=2.18),                               # cursor out, cards out, the speaker slides home by the end
]
# a window under 2 s has no time for the card: the cursor walks in, selects them, drags them, leaves (fits 1.23 s)
SHORT_BEATS = [
    dict(act="enter",  at=0.03, arrive=0.13),
    dict(act="select", at=0.16, release=0.13),
    dict(act="drag",   at=0.46, snap=0.27, dx=None),
    dict(act="exit",   at=1.03),
]
SHORT_UNDER = 2.0                    # s: windows shorter than this run SHORT_BEATS
FLOOR = 1272                         # the box's bottom edge stops here (the caption band starts at 1300)
HEIGHT = 930                         # box height from the top of the head, until FLOOR stops it
BAND = None                          # the box is the matte's bbox above this y (below it sleeves leave the frame); None = the shoulders
LIFT = 0.02                          # how much they come forward while the cursor holds them
SHUTTER = 0.5                        # 180 degrees: they smear on the fast frames like they were filmed moving
CARD = (396, 704)                    # the card's size, px (9:16)
CARD_MARGIN = 42                     # the card hugs the frame's edge on the open side, this far in
WIDE = True                          # re-cut the speaker wider from the source when the drag would show the crop's edge
DRAG_ON_FALLBACK = False             # a fallback plate (no empty room filmed) has an inpainted patch where the speaker sat:
                                     # it shows the moment they move, so the drag is left out unless this is True


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
from common import HF, load_edit  # noqa: E402


def nf(t):
    return int(round(t * FPS))


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def ell(s):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s, s))


# ---- the project
class P:
    """everything read off the project once"""

    def __init__(self, project, fid):
        self.project, self.fid = project, fid
        self.E = load_edit(project)
        F = fxlib.entry(project, fid)
        self.TL = json.load(open(os.path.join(project, "timeline.json")))
        self.A, self.B = float(F["at"]), float(F["end"])
        shots = [(s["t"], s["frame"]) for s in self.TL.get("shots", [])] or list(self.E.SHOTS)
        self.frame = [f for a, f in shots if a <= self.A + 1e-3][-1]
        wp = os.path.join(project, "words.json")
        self.words = [(w["start"], w["text"]) for w in json.load(open(wp))] if os.path.exists(wp) else []
        tp = os.path.join(project, "work", "tracks", "track.json")
        self.tracks = fxlib.tracks(project)["frames"] if os.path.exists(tp) else None
        self.S = fxlib.pack(project)

    def word_at(self, text, after):
        return next((s for s, t in self.words if s >= after - 0.001 and norm(t) == norm(text) and s < self.B), None)

    def has_room(self):
        return os.path.exists(os.path.join(self.project, "work", "c", f"room_{self.frame}.npy"))

    def room(self, empty=False):
        """the room from the plate tools: as the take saw it (the speaker covers the edge of the patch they always sat
        in on every frame of a drag to their left), or the empty room alone (a drag to their right uncovers that edge)"""
        return fxlib.room(self.project, self.frame, empty=empty).astype(np.float32)

    def plate(self, name):
        """a static plate layer (desk, mic) as RGBA uint8, or None"""
        p = os.path.join(self.project, "public", "plates", f"{name}_{self.frame}.webm")
        if not os.path.exists(p):
            return None
        raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", p, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                             capture_output=True).stdout
        if len(raw) < W * H * 4:
            return None
        a = np.frombuffer(raw[:W * H * 4], np.uint8).reshape(H, W, 4).copy()
        return a if a[..., 3].max() > 12 else None


def resolve(p, beats):
    """BEATS with absolute times (cue words looked up in order) and every position the table leaves to the footage"""
    out, after = [], p.A
    span = p.B - p.A
    fits = 1.23 if beats is SHORT_BEATS else 2.33                      # the rhythm each table is timed for
    scale = min(1.0, (span - 0.12) / fits) if span < fits + 0.12 else 1.0   # a shorter window runs it faster
    for b in beats:
        b = dict(b)
        at = b["at"]
        if isinstance(at, str):
            t = p.word_at(at, after)
            if t is None:
                print(f"WARNING: {b['act']} cue word {at!r} is not spoken after {after:.2f}: it falls back to the rhythm")
                t = after + 0.2
        else:
            t = p.A + float(at) * scale
        b["at"] = t
        for k in ("arrive", "release", "snap", "grab", "land"):
            if k in b:
                b[k] = t + float(b[k]) * scale
        out.append(b)
        after = t + 0.01
    clicks = [c["at"] for c in out if c["act"] == "click"]
    for b in out:
        if b["act"] == "drop":                     # the moment of the card's clip lands on this word (default: the last click)
            on = b.get("src_on")
            t = p.word_at(on, b["at"]) if isinstance(on, str) else (p.A + float(on) * scale if on is not None else None)
            b["src_on"] = t if t is not None else (clicks[-1] if clicks else b["land"])
    end = p.B - 1 / FPS
    if out and out[-1]["act"] == "exit" and out[-1]["at"] > end - 4 / FPS:
        out[-1]["at"] = end - 4 / FPS
    return out


# ---- the speaker, wider than the crop when the drag needs it
def matte_edges(al_stack, band):
    """which frame edges the speaker touches above `band` (where a drag would show a flat cut)"""
    m = al_stack[:, :int(band)].max(axis=0) > 64
    return bool(m[:, :3].any()), bool(m[:, -3:].any())


def wide_cut(p, a, b, need_l, need_r, work):
    """the speaker cut wider from the source at exactly the crop's own scale and phase, keyed with the kit's own
    background remover, so a dragged speaker has no flat edge where the crop ends. Inside the crop the pixels are
    clean.mp4's (checked). Returns (rgb frames, alpha frames, PAD) or None"""
    E, TL = p.E, p.TL
    cw, ch, cx, cy = E.FRAMES[p.frame]
    try:
        SW, SH = fxlib.size(E.SRC)
    except Exception:
        return None
    sx = Fraction(W, cw)
    step = sx.denominator * (2 if sx.numerator % 2 else 1)      # whole steps keep the resampling phase and an even width
    ext_r = min(int(math.ceil(need_r / float(sx) / step)) * step if need_r else 0, (SW - (cx + cw)) // step * step)
    ext_l = min(int(math.ceil(need_l / float(sx) / step)) * step if need_l else 0, cx // step * step)
    if ext_l <= 0 and ext_r <= 0:
        return None
    cw2 = cw + ext_l + ext_r
    W2, off = int(cw2 * sx), int(ext_l * sx)
    piece = [q for q in TL["pieces"] if q["out_start"] - 1e-3 <= a < q["out_end"] - 1e-3]
    if not piece or piece[0]["out_end"] < b - 1e-3:
        print("the drag spans a picture cut: no wider re-cut")
        return None
    src0 = piece[0]["src"] + (a - piece[0]["out_start"])
    N, WARM = nf(b) - nf(a), 6
    tmp = os.path.join(work, "wide.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, src0 - 0.3 / FPS - WARM / FPS):.4f}", "-i", E.SRC, "-an", "-vf",
                    f"crop={cw2}:{ch}:{cx - ext_l}:{cy},scale={W2}:{H}:flags=lanczos,fps={FPS},setsar=1", "-frames:v", str(N + 2 * WARM),
                    "-c:v", "libx264", "-crf", "10", "-preset", "medium", "-pix_fmt", "yuv420p", tmp], check=True)     # 4:2:0 like clean.mp4
    keyed = os.path.join(work, "wide.webm")
    r = subprocess.run(HF + ["remove-background", tmp, "-o", keyed, "--quality", "best"], cwd=work, capture_output=True, text=True)
    if r.returncode or not os.path.exists(keyed):
        print("the background remover failed on the wider cut:", (r.stdout + r.stderr)[-400:])
        return None
    rgb = [f for _, f in _decode(tmp, W2, "rgb24", 3)]
    al = [f[..., 3] for _, f in _decode(keyed, W2, "rgba", 4, dec=("-c:v", "libvpx-vp9"))]
    live = [f.copy() for _, f in fxlib.frames(p.project, a, b)]
    best, bo = 1e9, 0
    for o in range(0, max(1, len(rgb) - N + 1)):
        e = np.mean([np.abs(rgb[o + k][::4, off:off + W:4].astype(np.float32) - live[k][::4, ::4].astype(np.float32)).mean()
                     for k in range(0, min(N, len(rgb) - o), 5)])
        if e < best:
            best, bo = e, o
    if best > 3 or len(rgb) < bo + N or len(al) < bo + N:
        print(f"the wider cut does not line up with clean.mp4 (mean error {best:.1f}): no wider re-cut")
        return None
    print(f"speaker cut {W2} px wide from the source (home at x {off}), lines up within {best:.2f} levels")
    return np.stack(rgb[bo:bo + N]), np.stack(al[bo:bo + N]), off


def _decode(path, w, pix, ch, dec=()):
    vf = ["-vf", fxlib.ACCURATE] if pix == "rgb24" else []          # the same conversion fxlib.frames reads clean.mp4 with
    p = subprocess.Popen(["ffmpeg", "-v", "error", *dec, "-i", path, *vf, "-f", "rawvideo", "-pix_fmt", pix, "-"], stdout=subprocess.PIPE)
    k = 0
    while True:
        buf = p.stdout.read(w * H * ch)
        if len(buf) < w * H * ch:
            break
        yield k, np.frombuffer(buf, np.uint8).reshape(H, w, ch)
        k += 1
    p.wait()


def paint_out(rgb, al, mic, pad):
    """a mic in front of the speaker is in their matte: dragged, they would take a second mic with them. Paint it out of
    the moving speaker (the mic layer stays home, in front). Inpainted per frame: a soft patch, not their real cloth.
    rgb and al are on the speaker's canvas, whose home frame starts at x = pad"""
    if mic is None:
        return rgb
    m = np.zeros((H, rgb.shape[2]), np.uint8)
    m[:, pad:pad + W] = (mic[..., 3] > 30).astype(np.uint8)
    if not (m.astype(bool) & (al.max(axis=0) > 128)).any():
        return rgb
    hole = cv2.dilate(m, ell(15))
    out = rgb.copy()
    for k in range(len(rgb)):
        out[k] = cv2.inpaint(rgb[k], hole * (al[k] > 64), 9, cv2.INPAINT_TELEA)
    print("a mic layer overlaps the speaker: painted out of the moving speaker (check the patch on their chest)")
    return out


# ---- the room clip (cam)
def film(p, C, rgb, al, pad, room, front, out_path, n0):
    """the room, the speaker on it moved per frame through a real shutter, the desk and mic back on top. Frames where
    they are home are the live pixels themselves; every frame takes its own frame of clean.mp4, so lips stay in sync"""
    h, lift, (lox, loy) = C["h"], C["lift"], C["lift_o"]
    live = [f.copy() for _, f in fxlib.frames(p.project, n0 / FPS, (n0 + len(rgb)) / FPS)]
    fa = (front[..., 3:].astype(np.float32) / 255) if front is not None else None
    frgb = front[..., :3].astype(np.float32) if front is not None else None
    wr = fxlib.Writer(out_path, crf=13)
    G = 2.2
    for k in range(len(rgb)):
        f = n0 + k
        hp, h0, h1 = h.get(f - 1, h.get(f, 0.0)), h.get(f, 0.0), h.get(f + 1, h.get(f, 0.0))
        sp, s0, s1 = lift.get(f - 1, lift.get(f, 1.0)), lift.get(f, 1.0), lift.get(f + 1, lift.get(f, 1.0))
        if h0 == 0 and hp == 0 and h1 == 0 and s0 == 1 and sp == 1 and s1 == 1:
            wr.write(live[k])
            continue
        a = al[k].astype(np.float32)[..., None] / 255
        pm = rgb[k].astype(np.float32) * a
        n = max(1, min(16, int(math.ceil((abs(h1 - h0) + abs(h0 - hp)) * SHUTTER / 4))))
        acc = 0
        for j in range(n):
            u = ((j + 0.5) / n - 0.5) * SHUTTER                 # the shutter is centred on the frame: the box lands mid-smear
            hx = h0 + (h1 - h0) * u if u >= 0 else h0 + (h0 - hp) * u
            sl = s0 + (s1 - s0) * u if u >= 0 else s0 + (s0 - sp) * u
            M = np.float32([[sl, 0, lox * (1 - sl) - pad * sl + hx], [0, sl, loy * (1 - sl)]])     # canvas x -> frame x
            pw = cv2.warpAffine(pm, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            aw = np.clip(cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0), 0, 1)
            aw = aw[..., None] if aw.ndim == 2 else aw
            comp = room * (1 - aw) + np.clip(pw, 0, 255)
            if fa is not None:
                comp = comp * (1 - fa) + frgb * fa
            acc = acc + (np.clip(comp, 0, 255) / 255) ** G
        wr.write(np.clip((acc / n) ** (1 / G) * 255 + 0.5, 0, 255).astype(np.uint8))
    wr.close()


# ---- choreography: the table, frame by frame
def io(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (6 * u - 15) + 10)


def eo(u, p_=2.6):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** p_


def ei(u, p_=2.2):
    u = min(1.0, max(0.0, u))
    return u ** p_


def lerp(a, b, u):
    return a + (b - a) * u


def smooth(xs, k=(1, 2, 3, 2, 1)):
    xs = np.asarray(xs, np.float64)
    r = len(k) // 2
    return np.convolve(np.pad(xs, r, mode="edge"), np.asarray(k, np.float64) / sum(k), mode="valid")


def choreography(p, beats, bb):
    n0 = bb["n0"]
    raw = np.asarray(bb["boxes"], np.float64)
    bx0, bt, bx1 = smooth(raw[:, 0]), smooth(raw[:, 1]), smooth(raw[:, 2])
    tracks = p.tracks
    last = nf(p.B) - 1                      # home on this frame
    first = nf(beats[0]["at"]) - 1
    frames = list(range(first, last + 1))

    def box_at(f):
        k = max(0, min(len(bx0) - 1, f - n0))
        top = bt[k] - 3
        return (bx0[k], top, bx1[k], min(FLOOR, top + HEIGHT))
    home = box_at(nf(beats[0]["at"]))
    bw = home[2] - home[0]
    face_x = (home[0] + home[2]) / 2
    cur, down, h = {}, {}, {f: 0.0 for f in frames}
    lift_s, lift_o = {f: 1.0 for f in frames}, (W / 2, H / 2)
    clicks, guides, cards, sfx = [], [], [], []
    mq, clip = {}, {}
    pos, n_at, offset, selected = None, first, 0.0, None
    box_from = clip_from = None
    subject_box_end = None
    side = -1                               # the drag goes left (the card comes in from the right) unless dx says otherwise

    def go(nb, target):
        nonlocal pos, n_at
        start, n_start = np.array(pos), n_at
        for f in range(n_start + 1, nb + 1):
            cur[f] = tuple(start + (np.array(target, float) - start) * io((f - n_start) / max(1, nb - n_start)))
        pos, n_at = tuple(target), max(n_at, nb)

    def hover(nb, amp=1.6):
        nonlocal n_at
        q = np.array(pos)
        for f in range(n_at + 1, nb + 1):
            cur[f] = tuple(q + np.array([amp * math.sin((f - n_at) * 0.9), amp * 0.7 * math.sin((f - n_at) * 1.3)]))
        n_at = max(n_at, nb)
    for b in beats:
        act = b["act"]
        if act == "enter":
            # the ballistic part of a real pointing move covers almost all the distance fast, a short correction lands it
            na, nb = nf(b["at"]) - 1, nf(b["arrive"])
            nmid = max(na + 1, nb - 3)
            p0 = np.array(b.get("frm") or (W + 30, 1500), float)
            c = np.array(b.get("via") or (W * 0.83, 420), float)
            p1 = np.array(b.get("to") or (home[0] + 0.05 * bw, max(150.0, home[1] - 94)), float)
            d = (p1 - c) / max(1e-6, np.linalg.norm(p1 - c))
            past = p1 + d * 26 + np.array([-d[1], d[0]]) * 18
            for f in range(na, nmid + 1):
                v = eo((f - na) / max(1, nmid - na), 1.55)
                cur[f] = tuple((1 - v) ** 2 * p0 + 2 * (1 - v) * v * c + v ** 2 * past)
            for f in range(nmid + 1, nb + 1):
                cur[f] = tuple(past + (p1 - past) * io((f - nmid) / max(1, nb - nmid)))
            pos, n_at = tuple(p1), nb
            sfx += [(round((na + 3) / FPS, 3), "whoosh-soft", -24, "the cursor glides in"), (round(nb / FPS, 3), "tick", -20, "it lands")]
        elif act == "select":
            np_, nr = nf(b["at"]), nf(b["release"])
            hover(np_)
            s0 = np.array(pos, float)
            s1 = np.array(b.get("to") or (home[0] + 0.85 * bw, home[1] + 0.83 * (FLOOR - home[1])), float)
            for f in range(np_, nr + 1):
                u = (f - np_) / max(1, nr - np_)
                v = 1 - (1 - u) ** 1.7
                cur[f] = tuple(s0 + (s1 - s0) * v + np.array([26, -18]) * math.sin(v * math.pi))
                down[f] = True
                x_, y_ = cur[f]
                mq[f] = (min(s0[0], x_), min(s0[1], y_), max(s0[0], x_), max(s0[1], y_), 1.0)
                clip[f] = f"inset({min(s0[1], y_):.0f}px {W - max(s0[0], x_):.0f}px {H - max(s0[1], y_):.0f}px {min(s0[0], x_):.0f}px)"
            r_end = mq[nr][:4]
            for f, u, op in ((nr + 1, 0.62, 0.55), (nr + 2, 1.0, 0.0)):
                t_ = box_at(f)
                mq[f] = (lerp(r_end[0], t_[0], u), lerp(r_end[1], t_[1], u), lerp(r_end[2], t_[2], u), lerp(r_end[3], t_[3], u), op)
            pos, n_at = tuple(s1), nr
            clicks.append(np_)
            sfx += [(round(np_ / FPS, 3), "click", -14, "the marquee presses"), (round(nr / FPS, 3), "click", -18, "it lets go"),
                    (round((nr + 1) / FPS, 3), "tick", -16, "the box snaps to them")]
            selected, box_from, clip_from = "subject", nr + 1, nr + 1
        elif act == "drag":
            np_, ns = nf(b["at"]), nf(b["snap"])
            press = np.array(pos, float) + np.array([-6.0, 5.0])
            go(np_, press)
            dx = b.get("dx")
            if dx is None:
                dx = 0.21 * W * (-1 if face_x >= W / 2 - 40 else 1)
            dx = float(dx)
            side = -1 if dx < 0 else 1
            for f in range(np_, ns + 2):
                u = (f - np_) / (ns + 1 - np_)
                cur[f] = tuple(press + np.array([dx * io(u), 3.0 * math.sin(u * math.pi)]))
                down[f] = True
            for f in range(np_, ns):                                       # they follow a moment behind
                h[f] = offset + dx * io((f - 0.3 - np_) / (ns + 1 - np_))
            lift_o = (float(press[0]), float(press[1]))
            for f, v in ((np_ + 1, 1 + LIFT * 0.6), (ns, 1 + LIFT * 0.3)):
                lift_s[f] = v
            for f in range(np_ + 2, ns):                                   # picked up: they come forward a touch while held
                lift_s[f] = 1 + LIFT
            h[ns] = offset + dx + side * 3.0                               # the snap: the guide catches them and pulls a touch past
            h[ns + 1] = offset + dx - side * 0.8
            for f in range(ns + 2, last + 1):
                h[f] = offset + dx
            offset += dx
            fx_ = tracks[ns]["face"]["cx"] if tracks and ns < len(tracks) and tracks[ns].get("face") else face_x
            guides.append(("v", ns, fx_ + offset))                         # their face line, where it really is on the snap
            clicks.append(np_)
            for f in range(clip_from or np_, ns + 2):
                clip[f] = "inset(0px 0px 0px 0px)"
            pos, n_at = tuple(press + np.array([dx, 0.0])), ns + 1
            sfx += [(round(np_ / FPS, 3), "click", -14, "presses on them"), (round((np_ + 3) / FPS, 3), "whoosh-soft", -20, "the drag"),
                    (round(ns / FPS, 3), "tick", -12, "they snap to the guide")]
        elif act == "drop":
            nf_, ng, nl = nf(b["at"]), nf(b["grab"]), nf(b["land"])
            cw, chh = b.get("size") or CARD
            open_right = side < 0 if "side" not in b else b["side"] == "right"
            side = -1 if open_right else 1
            cx0 = (W - CARD_MARGIN - cw) if open_right else CARD_MARGIN
            cy0 = round(box_at(nl)[1]) if b.get("y") is None else b["y"]
            HOLD = 54                                                       # the cursor holds the card this far in from its edge
            edge = W - 40 if open_right else 40
            grab = np.array([edge, cy0 + chh * 0.53])
            land = np.array([cx0 + (HOLD if open_right else cw - HOLD), grab[1] + 8])
            start, n_start = np.array(pos, float), n_at
            nh = ng - 1                                                     # arrives a frame early, a little past, back onto the card
            for f in range(n_start + 1, nh + 1):
                cur[f] = tuple(start + (grab + np.array([10 * -side, -8]) - start) * eo((f - n_start) / max(1, nh - n_start), 2.0))
            cur[ng] = tuple(grab)
            for f in range(ng, nl + 1):
                u = (f - ng) / max(1, nl - ng)
                cur[f] = tuple(grab + (land - grab) * eo(u, 2.0) + np.array([0, -10 * math.sin(u * math.pi)]))
                down[f] = True
            hold_x = HOLD if open_right else cw - HOLD
            off_x = W + 40 if open_right else -cw - 40
            frames_c = {}
            for f in range(nf_, ng + 1):
                frames_c[f] = (lerp(off_x, grab[0] - hold_x, eo((f - nf_) / max(1, ng - nf_), 2.0)), 0.0, 1.03)
            for f in range(ng + 1, nl):                                     # a quarter frame behind the cursor, so the tip stays on it
                u = (f - 0.25 - ng) / max(1, nl - ng)
                frames_c[f] = (lerp(grab[0], land[0], eo(u, 2.0)) - hold_x, -8.0 * math.sin((f - ng) / max(1, nl - ng) * math.pi), 1.03)
            for i, (dxx, sc) in enumerate(((-7, 0.985), (-3, 0.992), (1, 1.004), (0, 1.0))):
                frames_c[nl + i] = (cx0 + dxx * -side, 0.0, sc)
            cards.append(dict(idx=len(cards), b=b, rect=(cx0, cy0, cw, chh), f=frames_c, nf=nf_, nl=nl, sel_from=nl, sel_to=None))
            guides.append(("h", nl, cy0))
            clicks.append(ng)
            if selected == "subject":
                subject_box_end = nl
            selected = cards[-1]
            pos, n_at = tuple(land), nl
            sfx += [(round((n_start + 1) / FPS, 3), "whoosh-soft", -22, "the cursor goes for the card"), (round(ng / FPS, 3), "click", -14, "grabs it"),
                    (round((ng + 2) / FPS, 3), "whoosh-soft", -20, "the card comes in"), (round(nl / FPS, 3), "pop", -16, "it lands"),
                    (round(nl / FPS, 3), "tick", -16, "on the guide")]
        elif act == "click":
            nc = nf(b["at"])
            if b.get("to"):
                target = np.array(b["to"], float)
            elif cards:
                cx0, cy0, cw, chh = cards[-1]["rect"]
                target = np.array([cx0 + 0.39 * cw, cy0 + 0.76 * chh])
            else:
                bx = box_at(nc)
                target = np.array([(bx[0] + bx[2]) / 2 + offset, bx[1] + 0.6 * (bx[3] - bx[1])])
            near = target + np.array([6, -7])
            go(nc - 2, near)
            for f in (nc - 1, nc):
                cur[f] = tuple(near + (target - near) * (f - (nc - 2)) / 2.0)
            down[nc] = True
            clicks.append(nc)
            if isinstance(selected, dict):
                selected["sel_to"] = nc
                selected["press"] = nc
            elif selected == "subject":
                subject_box_end = nc
            selected = None
            pos, n_at = tuple(target), nc
            sfx.append((round(nc / FPS, 3), "click", -12, "the last click"))
        elif act == "exit":
            ne = nf(b["at"])
            hover(ne - 1, amp=1.2)
            hold = np.array(cur.get(ne - 1, pos), float)
            x1 = np.array(b.get("to") or ((W + 130) if side < 0 else -130, 1700), float)
            for f in range(ne, last + 1):
                cur[f] = tuple(hold + (x1 - hold) * ei((f - ne + 1) / 4.0, 1.5))
            ret = [0.62, 0.27, 0.09, 0.02, 0.0]
            for i, f in enumerate(range(ne, last + 1)):                    # one gesture: cursor first, card next, the speaker last
                h[f] = offset * ret[min(i, len(ret) - 1)]
            h[last] = 0.0
            for cd in cards:
                for i, f in enumerate(range(ne, last + 1)):
                    cd["f"][f] = (cd["rect"][0] - side * [70, 240, 500, 900][min(i, 3)], 0.0, 1.0)
                if cd["sel_to"] is None:
                    cd["sel_to"] = ne
                for f in range(cd["nl"] + 4, ne):
                    cd["f"].setdefault(f, (cd["rect"][0], 0.0, 1.0))
                if cd.get("press"):
                    x_ = cd["rect"][0]
                    cd["f"][cd["press"]] = (x_, 0.0, 0.984)
                    cd["f"][cd["press"] + 1] = (x_, 0.0, 0.992)
            if subject_box_end is None:                                     # the selection rides them home and lets go as they land
                subject_box_end = min(last + 1, ne + len(ret))
            sfx.append((round((ne + 1) / FPS, 3), "whoosh-soft", -18, "everything clears"))
            n_at = last
    for f in frames:                        # before the first beat and any gap
        if f not in cur:
            later = [k for k in cur if k >= f]
            cur[f] = cur[min(later)] if later else cur[max(cur)]
    if subject_box_end is None:
        subject_box_end = last + 1
    box_on = set(range(box_from, subject_box_end)) if box_from is not None else set()

    def at(t):                              # the flag trails the arrow by a frame or two, on a leash
        a = max(first, min(last, int(math.floor(t))))
        b_ = max(first, min(last, a + 1))
        return np.array(cur[a]) * (1 - (t - a)) + np.array(cur[b_]) * (t - a)
    flag = {}
    for f in frames:
        q = np.array(cur[f])
        lag = at(f - 1.6) - q
        m = np.linalg.norm(lag)
        lag = lag / m * 44 if m > 44 else lag
        ox, oy = 26 + lag[0], 80 + lag[1]
        if lag[1] < -2:                     # pulled up against the arrow: it slides round the tail, so the name is never covered
            ox = max(ox, 26 + min(1.0, (-lag[1] - 2) / 26) * 28)
        flag[f] = (q[0] + ox, q[1] + oy)
    return dict(first=first, last=last, frames=frames, cur=cur, down=down, flag=flag, h=h, lift=lift_s, lift_o=lift_o, box_at=box_at,
                box_on=box_on, box_from=box_from, mq=mq, clip=clip, clicks=clicks, guides=guides, cards=cards, sfx=sfx, side=side)


def rectpath(x0, y0, x1, y1):
    return f"M{x0:.1f} {y0:.1f}H{x1:.1f}V{y1:.1f}H{x0:.1f}Z"


def handles(x0, y0, x1, y1, s):
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return "".join(rectpath(x - s / 2, y - s / 2, x + s / 2, y + s / 2) for x, y in ((x0, y0), (mx, y0), (x1, y0), (x1, my), (x1, y1), (mx, y1), (x0, y1), (x0, my)))


ARROW = "M0 0 L0 66 L15.5 51.5 L26.5 77.5 L39.5 72 L28.5 46.5 L49.5 46.5 Z"
FLASH = [1, 1, 0.8, 0.55, 0.3, 0.12]


# ---- the card's clip: the creator's own, or a labelled placeholder
def card_clip(p, b, out, start_at):
    """an all-intra 432x768 proxy, muted; its frame 0 plays at the fetch, so src_at lands on src_on"""
    src = b.get("src") or ""
    path = src if os.path.isabs(src) else os.path.join(p.project, src)
    first = float(b.get("src_at") or 0.0) - (b["src_on"] - start_at)
    if src and os.path.exists(path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, first):.4f}", "-i", path, "-an", "-t", "3.0", "-vf",
                        "scale=432:768:force_original_aspect_ratio=increase,crop=432:768,fps=30", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "16", "-g", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
        return False
    if src:
        print(f"WARNING: the card's clip {src!r} is not in the project: a placeholder card")
    from PIL import Image, ImageDraw
    C = p.S["colors"]
    im = Image.new("RGB", (432, 768), C["dark"][:3])
    d = ImageDraw.Draw(im)
    d.polygon([(186, 330), (186, 438), (276, 384)], fill=C["light"][:3])      # a play mark
    d.text((216, 520), "PLACEHOLDER", font=fxlib.font(p.project, "mono", 26), fill=C["accent"][:3], anchor="mm")
    d.text((216, 560), "your clip here", font=fxlib.font(p.project, "text", 26), fill=C["light"][:3], anchor="mm")
    tmp = out + ".png"
    im.save(tmp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", "3.0", "-i", tmp, "-c:v", "libx264", "-crf", "16",
                    "-g", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
    os.remove(tmp)
    return True


def css_rgba(c, a=None):
    r, g, b_, a0 = c
    return f"rgba({r},{g},{b_},{(a0 / 255 if a is None else a):.3f})"


def lum(c):
    ch = [x / 255 for x in c[:3]]
    ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    p = P(project, fid)
    if fxlib.size(os.path.join(project, "public", "clean.mp4")) != (W, H):
        sys.exit("live-cursor is laid out for a 1080x1920 canvas")
    ridx = f"{fid}-room"
    D, DR, WK = os.path.join(project, "fx", fid), os.path.join(project, "fx", ridx), os.path.join(project, "work", "fx", fid)
    for d in (D, WK):
        os.makedirs(d, exist_ok=True)
    beats = resolve(p, SHORT_BEATS if p.B - p.A < SHORT_UNDER else BEATS)
    mode_p = os.path.join(project, "work", "plate", "plate.json")
    mode = json.load(open(mode_p)).get("mode") if os.path.exists(mode_p) else None
    if any(b["act"] == "drag" for b in beats):
        if not p.has_room():
            print("no room_<FRAME>.npy (the plate tools): the drag is left out, everything else runs over the live picture")
            beats = [b for b in beats if b["act"] != "drag"]
        elif mode == "fallback" and not DRAG_ON_FALLBACK:
            print("WARNING: this plate is the FALLBACK (no empty room was filmed): the patch the speaker always covered is "
                  "inpainted and shows the moment they move. The drag is left out; the cursor, the box and the card run over "
                  "the live picture. Film 5 s of the empty room (edit.py EMPTY or EMPTY_CLIP), rerun the plate tools, then this")
            beats = [b for b in beats if b["act"] != "drag"]
    drags = [b for b in beats if b["act"] == "drag"]
    if not drags and any(b["act"] == "drop" for b in beats):
        beats = card_beside_face(p, beats)
    if any(p.A + 0.5 / FPS < c < p.B - 0.5 / FPS for c in p.TL.get("picture_cuts", []) + p.TL.get("reframes", [])) and drags:
        sys.exit(f"{fid}: the window spans a picture change: the room only matches one framing. Move the window or drop the drag")
    n_out = nf(beats[0]["at"]) - 1
    al = np.stack([a.copy() for _, a in fxlib.alpha(project, n_out / FPS, p.B)])
    if not len(al):
        sys.exit("public/subject.webm has no frames in the window: run pipeline/cutout.py (or matte.py) first")
    pose = p.tracks[nf(p.A)].get("pose") if p.tracks and nf(p.A) < len(p.tracks) else None
    band = BAND if BAND is not None else (max(pose["ls"][1], pose["rs"][1]) + 15 if pose else None)
    if band is None:
        top = int(np.where((al[0] > 128).sum(axis=1) >= 8)[0][0]) if (al[0] > 128).any() else 400
        band = top + 0.45 * (FLOOR - top)
    PAD, canvas = 0, W
    rgb_w = al_w = None
    al_out = al
    cam_a = cam_b = None
    C = choreography(p, beats, dict(n0=n_out, boxes=boxes_of(al, band, 0)))
    if drags:
        # the drag's frames: from the press to the first frame home
        n_press = nf(drags[0]["at"])
        moving = [f for f in C["frames"] if f >= n_press and (C["h"].get(f, 0) != 0 or C["lift"].get(f, 1) != 1)]
        n_home = (max(moving) + 1) if moving else n_press + 1
        cam_a, cam_b = n_press / FPS, min(p.B, (n_home + 1) / FPS)
        hs = list(C["h"].values())
        went_left, went_right = -min(0.0, min(hs)), max(0.0, max(hs))
        left_edge, right_edge = matte_edges(al, band)
        need_r = went_left + 60 if (went_left > 0 and right_edge) else 0      # dragged left: their right side has to exist
        need_l = went_right + 60 if (went_right > 0 and left_edge) else 0
        wide = wide_cut(p, cam_a, cam_b, need_l, need_r, WK) if WIDE and (need_l or need_r) else None
        if wide is not None:
            rgb_w, al_w, PAD = wide
        else:
            rgb_w = np.stack([f.copy() for _, f in fxlib.frames(project, cam_a, cam_b)])
            al_w = np.stack([a.copy() for _, a in fxlib.alpha(project, cam_a, cam_b)])
            if need_l or need_r:
                print("WARNING: the speaker touches the frame's edge and the source has no more picture there: the drag shows a "
                      "straight cut down their side (feathered). A smaller dx, or a drag toward that edge, reads better")
                ramp = np.ones(W, np.float32)
                if need_r:
                    ramp = np.minimum(ramp, np.clip((W - 1 - np.arange(W)) / 60.0, 0, 1))
                if need_l:
                    ramp = np.minimum(ramp, np.clip(np.arange(W) / 60.0, 0, 1))
                al_w = (al_w.astype(np.float32) * ramp[None, None, :]).astype(np.uint8)
        canvas = rgb_w.shape[2]
        if PAD or canvas != W:                     # the box and the outline follow the wide matte; before the drag the shared one
            pre = nf(cam_a) - n_out
            al_out = np.zeros((len(al), H, canvas), np.uint8)
            al_out[:, :, PAD:PAD + W] = al
            k = max(0, min(len(al_w), len(al) - pre))
            al_out[pre:pre + k] = al_w[:k]
            C = choreography(p, beats, dict(n0=n_out, boxes=boxes_of(al_out, band, PAD)))
        mic = p.plate("mic")
        rgb_w = paint_out(rgb_w, al_w, mic, PAD)
        front = None
        for layer in (p.plate("desk"), mic):
            if layer is not None:
                front = layer if front is None else _over(front, layer)
        os.makedirs(DR, exist_ok=True)
        room = p.room(empty=went_right > went_left)
        film(p, C, rgb_w, al_w, PAD, room, front, os.path.join(DR, f"{ridx}.mp4"), n_press)
        tag = fxlib.tag(f"{ridx}-film", f"fx/{ridx}/{ridx}.mp4", cam_a, cam_b, "g", "{{T0}}", "position:absolute;left:0;top:0;width:1080px;height:1920px;")
        with open(os.path.join(DR, "fx.html"), "w") as fh:
            fh.write(f"<!-- {ridx}: the room with the speaker moved on it, written by fx/{fid}/gen.py. Edit the table there, not this file. -->\n{tag}\n")
        with open(os.path.join(DR, "fx.js"), "w") as fh:
            fh.write("// filmed by gen.py (class g takes the live grade): the build shows this layer from A to B\n")
    elif os.path.isdir(DR):                        # an earlier run's room clip: no drag now, so it must not play
        import shutil
        shutil.rmtree(DR)
        print(f"removed fx/{ridx}/ from an earlier run: take its edit.FX entry out")
    write_overlay(p, fid, D, C, al_out, PAD, canvas, n_out, beats, WK)
    # the report
    mark = []
    if C["box_from"]:
        mark.append(round((C["box_from"] + 2) / FPS, 2))
    if C["guides"]:
        mark.append(round((C["guides"][0][1] + 1) / FPS, 2))
    if C["cards"]:
        mark.append(round((C["cards"][-1]["nl"] + 12) / FPS, 2))
    print(f"\nwrote fx/{fid}/" + (f" and fx/{ridx}/" if cam_a is not None else "") + ". edit.FX:")
    print(f'    dict(id="{fid}", layer="top", at={p.A:.3f}, end={p.B:.3f}, frames={mark}, note="{NOTE}"),')
    if cam_a is not None:
        print(f'    dict(id="{ridx}", layer="cam", at={cam_a:.3f}, end={cam_b:.3f}, note="live-cursor: the room with the speaker moved on it"),')
    print("SOUND sfx lines:")
    for t, name, db, what in sorted(C["sfx"]):
        print(f'    ({t:.3f}, "{name}", {db}),   # {what}')
    print("Nothing may zoom #cam in the window (the overlay tracks at scale 1); the live captions stay on (the box stops at y 1272).")


def card_beside_face(p, beats):
    """no drag, so no gap: each card goes beside the face on the side with more room, narrower if it has to be; a drop
    with less than 220 px either side is left out (and the click that lets the card go, when no card is left)"""
    out = []
    for b in beats:
        n = nf(b.get("land", b["at"]))
        f = p.tracks[n]["face"] if b["act"] == "drop" and p.tracks and n < len(p.tracks) and p.tracks[n].get("face") else None
        if f is None:
            out.append(b)
            continue
        right = W - CARD_MARGIN - (f["cx"] + 0.62 * f["w"])
        left = (f["cx"] - 0.62 * f["w"]) - CARD_MARGIN
        if max(left, right) < 220:
            print("no drag and no room beside the face for the card: that drop is left out")
            continue
        cw = int(min(CARD[0], max(left, right)))
        out.append(dict(b, side="right" if right >= left else "left", size=(cw, round(cw * CARD[1] / CARD[0]))))
    if not any(b["act"] == "drop" for b in out):
        out = [b for b in out if b["act"] != "click" or not any(x["act"] == "drop" for x in beats)]
    return out


def _over(a, b):
    """RGBA b over RGBA a (uint8)"""
    fa, fb = a[..., 3:].astype(np.float32) / 255, b[..., 3:].astype(np.float32) / 255
    out_a = fb + fa * (1 - fb)
    rgb = (b[..., :3] * fb + a[..., :3] * fa * (1 - fb)) / np.maximum(out_a, 1e-4)
    return np.dstack([np.clip(rgb, 0, 255), out_a * 255]).astype(np.uint8)


def boxes_of(al, band, pad):
    """the real bbox per frame on the home canvas: top of the head, left and right above the band"""
    out = []
    for k in range(len(al)):
        m = al[k] > 128
        rows = np.where(m.sum(axis=1) >= 8)[0]
        if not len(rows):
            out.append(out[-1] if out else [W * 0.2, 400, W * 0.8])
            continue
        top = int(rows[0])
        cols = np.where(m[top:int(max(band, top + 40))].sum(axis=0) >= 3)[0]
        out.append([int(cols[0]) - pad, top, int(cols[-1]) - pad] if len(cols) else (out[-1] if out else [W * 0.2, top, W * 0.8]))
    return out


def person(creator):
    """who the flag names: the pack's first name, else the handle, else nobody (no flag). "reel-kit" (the default pack's
    placeholder) is not a person"""
    name = str(creator.get("name") or "").strip()
    if name.lower().replace(" ", "-") in ("reel-kit", "reelkit"):
        name = ""
    return name.split()[0] if name else str(creator.get("handle") or "").strip()


def write_overlay(p, fid, D, C, al, pad, canvas, n_out, beats, WK):
    S = p.S
    col = S["colors"]
    accent = col["accent"]
    guide = (col.get("series") or [col["negative"]] * 3)[2] if len(col.get("series") or []) > 2 else col["negative"]
    pill_ink = "var(--c-ink)" if lum(accent) > 0.25 else "var(--c-light)"
    name = person(S["creator"]) if NAME is None else NAME
    frames, last = C["frames"], C["last"]
    # the outline: an accent hairline on the matte's edge, gone before the desk line
    floor_y, desk = 1720, p.plate("desk")
    if desk is not None:
        rows = np.where((desk[..., 3] > 128).mean(axis=1) > 0.5)[0]
        floor_y = int(rows[0]) + 30 if len(rows) else floor_y
    taper = np.clip((floor_y - np.arange(H, dtype=np.float32)) / 220.0, 0, 1)[:, None]
    wr = fxlib.Writer(os.path.join(D, "outline.webm"), w=canvas, h=H, alpha=True, crf=24)
    rgb = np.full((H, canvas, 3), accent[:3], np.uint8)
    for k in range(len(al)):
        v = cv2.GaussianBlur((al[k] > 128).astype(np.float32), (0, 0), 1.4)
        line = np.clip(1.0 - np.abs(v - 0.5) * 2.6, 0, 1) * taper
        wr.write(np.dstack([rgb, (line * 255).astype(np.uint8)]))
    wr.close()
    # the cards
    cards_html, cards_css = [], []
    for cd in C["cards"]:
        k = cd["idx"]
        cx0, cy0, cw, chh = cd["rect"]
        ph = card_clip(p, cd["b"], os.path.join(D, f"card{k}.mp4"), cd["b"]["at"])
        tag = fxlib.tag(f"{fid}-cv{k}", f"fx/{fid}/card{k}.mp4", cd["b"]["at"], p.B, "", "{{T%d}}" % (k + 1),
                        f"position:absolute;left:0;top:0;width:{cw}px;height:{chh}px;display:block;")
        cards_css.append(f"""#{fid}-c{k} {{ position:absolute; left:0; top:0; width:{cw}px; height:{chh}px; }}
#{fid}-f{k} {{ position:absolute; left:0; top:0; width:{cw}px; height:{chh}px; border-radius:calc(var(--radius) * 3 + 2px); overflow:hidden; background:var(--c-dark); box-shadow:0 26px 60px rgba(0,0,0,.5), 0 2px 8px rgba(0,0,0,.35); }}
#{fid}-l{k} {{ position:absolute; left:0; top:{chh + 18}px; width:{cw}px; text-align:center; color:var(--c-light); font:500 30px/1 var(--font-mono); letter-spacing:-.01em; }}
#{fid}-s{k} {{ position:absolute; left:0; top:0; width:{cw}px; height:{chh}px; overflow:visible; }}""")
        label = cd["b"].get("label", "")
        cards_html.append(f"""<div id="{fid}-c{k}">
  <div id="{fid}-f{k}">{tag}</div>
  <svg id="{fid}-s{k}" viewBox="0 0 {cw} {chh}"><path id="{fid}-sb{k}" class="{fid}-sel" d="{rectpath(0, 0, cw, chh)}"/><path id="{fid}-sh{k}" class="{fid}-hd" d="{handles(0, 0, cw, chh, 18)}"/></svg>
  <div id="{fid}-l{k}">{label}{' (placeholder)' if ph else ''}</div>
</div>""")
    otag = fxlib.tag(f"{fid}-outv", f"fx/{fid}/outline.webm", n_out / FPS, p.B, "", "{{T0}}", f"position:absolute;left:0;top:0;width:{canvas}px;height:1920px;")
    nl = "\n"
    flag_html = f'<div id="{fid}-flag">{escape(name)}</div>' if name else ""
    html = f"""<!-- live-cursor, the overlay. Generated by gen.py: edit the table there, not this file. -->
<style>
#{fid}-clip {{ position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:hidden; }}
#{fid}-out {{ position:absolute; left:{-pad}px; top:0; width:{canvas}px; height:1920px; }}
#{fid}-svg {{ position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:visible; }}
#{fid} .{fid}-sel {{ fill:none; stroke:var(--c-accent); stroke-width:3.5; }}
#{fid} .{fid}-hd {{ fill:var(--c-light); stroke:var(--c-accent); stroke-width:3; }}
#{fid}-mq {{ fill:var(--c-accent); fill-opacity:.16; stroke:var(--c-accent); stroke-width:3; }}
#{fid}-gv, #{fid}-gh {{ stroke:{css_rgba(guide)}; stroke-width:3; }}
#{fid}-pill {{ position:absolute; left:0; top:0; width:204px; height:44px; margin-left:-102px; background:var(--c-accent); border-radius:calc(var(--radius) + 1px); color:{pill_ink}; font:600 27px/44px var(--font-mono); text-align:center; letter-spacing:-.02em; white-space:nowrap; }}
{nl.join(cards_css)}
#{fid}-cur {{ position:absolute; left:0; top:0; width:52px; height:80px; overflow:visible; filter:drop-shadow(0 4px 7px rgba(0,0,0,.38)); }}
#{fid}-cur path {{ fill:var(--c-light); stroke:var(--c-dark); stroke-width:4.5; stroke-linejoin:round; paint-order:stroke; }}
#{fid}-flag {{ position:absolute; left:0; top:0; height:50px; padding:0 18px; border-radius:6px 16px 16px 16px; background:var(--c-dark); color:var(--c-light); font:600 33px/50px var(--font-text); letter-spacing:-.01em; white-space:nowrap; box-shadow:0 0 0 2px var(--c-light), 0 6px 14px rgba(0,0,0,.35); }}
#{fid}-ring {{ position:absolute; left:-30px; top:-30px; width:60px; height:60px; border-radius:50%; border:3px solid var(--c-light); box-sizing:border-box; }}
</style>
<div id="{fid}-clip"><div id="{fid}-out">{otag}</div></div>
<svg id="{fid}-svg" viewBox="0 0 1080 1920">
  <path id="{fid}-mq" d="M0 0"/>
  <path id="{fid}-box" class="{fid}-sel" d="M0 0"/>
  <path id="{fid}-hd" class="{fid}-hd" d="M0 0"/>
  <line id="{fid}-gv" x1="0" y1="0" x2="0" y2="1920"/>
  <line id="{fid}-gh" x1="0" y1="0" x2="1080" y2="0"/>
</svg>
<div id="{fid}-pill">0</div>
{nl.join(cards_html)}
<div id="{fid}-ring"></div>
{flag_html}
<svg id="{fid}-cur" viewBox="0 0 52 80"><path d="{ARROW}"/></svg>
"""
    with open(os.path.join(D, "fx.html"), "w") as fh:
        fh.write(html)
    tr = {}

    def put(sel, f, props):
        rows = tr.setdefault(sel, [])
        if not rows or rows[-1][1] != props:
            rows.append([f, props])
    for f in frames:
        x, y = C["cur"][f]
        put(f"#{fid}-cur", f, dict(x=round(x, 1), y=round(y, 1), scale=0.92 if C["down"].get(f) else 1.0))
        if name:
            fx_, fy_ = C["flag"][f]
            put(f"#{fid}-flag", f, dict(x=round(fx_, 1), y=round(fy_, 1)))
        ring = None
        for c in C["clicks"]:
            if c <= f < c + 6:
                u = (f - c) / 6.0
                x_c, y_c = C["cur"][c]
                ring = dict(x=round(x_c, 1), y=round(y_c, 1), scale=round(0.35 + 0.95 * eo(u, 2.0), 3), opacity=round(1 - u, 3))
        put(f"#{fid}-ring", f, ring or dict(opacity=0))
        if f in C["mq"]:
            x0, y0, x1, y1, op = C["mq"][f]
            put(f"#{fid}-mq", f, dict(opacity=op, attr=dict(d=rectpath(x0, y0, x1, y1))))
        else:
            put(f"#{fid}-mq", f, dict(opacity=0))
        hx, sl = C["h"].get(f, 0.0), C["lift"].get(f, 1.0)
        lox, loy = C["lift_o"]

        def sxp(v):
            return lox + (v - lox) * sl + hx

        def syp(v):
            return loy + (v - loy) * sl
        if f in C["clip"]:
            put(f"#{fid}-clip", f, dict(opacity=1, clipPath=C["clip"][f]))
            put(f"#{fid}-out", f, dict(x=round(hx, 2), scale=round(sl, 4)))
        elif C["clip"] and (f - 1 in C["clip"] or f - 2 in C["clip"]):      # the hairline lets go over two frames, still riding on them
            put(f"#{fid}-clip", f, dict(opacity=0.55 if f - 1 in C["clip"] else 0.25))
            put(f"#{fid}-out", f, dict(x=round(hx, 2), scale=round(sl, 4)))
        else:
            put(f"#{fid}-clip", f, dict(opacity=0))
        if f in C["box_on"]:
            bx0, bt, bx1, bb_ = C["box_at"](f)
            X0, X1, Y0, Y1 = sxp(bx0), sxp(bx1), syp(bt), syp(bb_)
            if f in C["mq"] and C["mq"][f][4] > 0:      # the rubber band is still closing onto them
                X0, bt_, X1, bb_d = C["mq"][f][:4]
                put(f"#{fid}-box", f, dict(opacity=1, attr=dict(d=rectpath(X0, bt_, X1, bb_d))))
                put(f"#{fid}-hd", f, dict(opacity=1, attr=dict(d=handles(X0, bt_, X1, bb_d, 11))))
            else:
                big = 26 if f == C["box_from"] + 1 else 22
                put(f"#{fid}-box", f, dict(opacity=1, attr=dict(d=rectpath(X0, Y0, X1, Y1))))
                put(f"#{fid}-hd", f, dict(opacity=1, attr=dict(d=handles(X0, Y0, X1, Y1, big))))
                put(f"#{fid}-pill", f, dict(opacity=1, x=round(min(960, max(120, (X0 + X1) / 2)), 1), y=round(max(150, Y0 - 66), 1), textContent=f"{round(X1 - X0)} × {round(Y1 - Y0)}"))
        else:
            for s_ in ("box", "hd", "pill"):
                put(f"#{fid}-{s_}", f, dict(opacity=0))
        vg = [g for g in C["guides"] if g[0] == "v" and g[1] <= f < g[1] + len(FLASH)]
        if vg:
            put(f"#{fid}-gv", f, dict(opacity=FLASH[f - vg[-1][1]], attr=dict(x1=round(vg[-1][2], 1), x2=round(vg[-1][2], 1))))
        else:
            put(f"#{fid}-gv", f, dict(opacity=0))
        hg = [g for g in C["guides"] if g[0] == "h" and g[1] <= f < g[1] + len(FLASH)]
        if hg:
            put(f"#{fid}-gh", f, dict(opacity=FLASH[f - hg[-1][1]], attr=dict(y1=hg[-1][2], y2=hg[-1][2])))
        else:
            put(f"#{fid}-gh", f, dict(opacity=0))
        for cd in C["cards"]:
            k = cd["idx"]
            if f in cd["f"]:
                cx_, dy_, sc = cd["f"][f]
                put(f"#{fid}-c{k}", f, dict(opacity=1, x=round(cx_, 1), y=round(cd["rect"][1] + dy_, 1), scale=sc))
            else:
                put(f"#{fid}-c{k}", f, dict(opacity=0))
            on_ = 1 if cd["sel_from"] <= f < (cd["sel_to"] or last + 1) else 0
            put(f"#{fid}-s{k}", f, dict(opacity=on_))
            put(f"#{fid}-l{k}", f, dict(opacity=1 if cd["nl"] + 1 <= f else 0))
    hide = [f"#{fid}-{s_}" for s_ in ("mq", "box", "hd", "gv", "gh", "pill", "ring", "clip")] + [f"#{fid}-c{c['idx']}" for c in C["cards"]]
    js = f"""// live-cursor, the overlay. Generated by gen.py: one row per frame where a value changes, so the motion is exactly what the table computed.
var T = {json.dumps(tr, separators=(",", ":"), ensure_ascii=True)};
gsap.set('{", ".join(hide)}', {{ opacity: 0 }});
gsap.set('#{fid}-cur', {{ transformOrigin: '0 0' }});
gsap.set('#{fid}-out', {{ transformOrigin: '{C["lift_o"][0] + pad:.0f}px {C["lift_o"][1]:.0f}px' }});
Object.keys(T).forEach(function (sel) {{
  T[sel].forEach(function (r) {{ tl.set(sel, r[1], q(r[0] / 30)); }});
}});
"""
    with open(os.path.join(D, "fx.js"), "w") as fh:
        fh.write(js)
    print(f"{fid}: {len(frames)} frames, {sum(len(v) for v in tr.values())} tl.set rows, " + (f"the flag says {name!r}" if name else "no flag: the pack has no name or handle (set NAME for one)"))


if __name__ == "__main__":
    main()
