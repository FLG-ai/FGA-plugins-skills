#!/usr/bin/env python3
"""paper-tear: a full-frame page rips in two on a picture cut. Real paper, not a mask: a seeded multi-octave torn
edge, a band of raw white fibre along both torn edges (wide on one side where it is thin on the other, as a real tear
bevels), stray fibres, the sheet bends up off the page near the tear with real shading, a soft contact shadow on what
is underneath, and the two halves pull apart, turn and leave off the sides, the next shot live underneath.

The page is whatever full-frame picture is on screen before the cut: by default the shot itself (the picture rips
open onto the next shot), a press-front entry (its clip, then its last frame), or any clip or still in the project
(a card, a cover image). Everything is pre-rendered per frame: tear-a.mp4 (H.264) is the page tearing open with the
next shot's pre-roll composited into the gap, up to the cut; tear-b.webm (VP9 + alpha) is then just the two halves
and their shadow over the live picture.

This writes into <project>/fx/<id>/ from the table below and the project:
  the rip       starts on the window's first frame; the picture cut (or reframe) inside the window is where the sheet
                lets go (best 4 frames in: at = cut - 0.133, end = at + 0.367)
  the tear line through the next shot's face (work/tracks/track.json on the cut), leaning TILT px across the frame
  the sound     audio/paper-rip.wav, synthesized by mk_rip.py next to this file (no recording)
Run: PY fx/<id>/gen.py <project> [<id>] [--check]
  reads   <project>/edit.py (the FX entry <id>, SRC, FRAMES, CARDS, FX), timeline.json, public/clean.mp4, PAGE,
          work/tracks/track.json (optional)
  writes  <project>/fx/<id>/tear-a.mp4, tear-b.webm, fx.html, fx.js, <project>/audio/paper-rip.wav; the pre-roll and
          proof stills in <project>/work/<id>/ (--check: prints the plan, writes nothing)
<id> defaults to this script's folder name. Rerun it whenever the page, the window or the cut moves (about a minute).
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

try:
    import fxlib                     # the kit's pipeline is on the kit Python's import path (setup writes reel-kit.pth)
except ImportError:                  # any other Python: the kit is a folder above this file
    _d = os.path.dirname(os.path.realpath(__file__))
    while _d != os.path.dirname(_d) and not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        _d = os.path.dirname(_d)
    if not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        sys.exit("run this with the kit's Python (PY: $REEL_KIT_HOME/.venv/bin/python), it has the kit's pipeline on its path")
    sys.path.insert(0, os.path.join(_d, "pipeline"))
    import fxlib
from common import load_edit  # noqa: E402

# ---- the table (px on the 1080x1920 frame)
PAGE = ""                  # the page that tears: '' = the shot itself; an effect's id (a press-front entry: its clip,
                           # then its last frame); or a clip or still in the project ("cards/c3.mp4", "assets/cover.png")
PAGE_AT = None             # the video time the page clip's first frame is on screen; None = read it: 0 for the shot, the
                           # effect's window start, a card's start (edit.CARDS)
SEED = 11                  # another seed, another rip
LINE = None                # or (x where the tear enters at the top, x where it leaves at the bottom), instead of the face
TILT = 144                 # px the tear leans: it enters this much further right at the top than it leaves at the bottom
CUT_ROW = 4                # with no picture cut in the window (a page over the live shot): the page stops on this row
# per frame from the window's start: how far the rip has run (y, past 1920 = it keeps pulling), the angle each half has
# opened (deg), how far it has been pulled off to the side (px), the curl at the torn edge (deg), and the sheet's lift
# for the shadow. One row per frame, this table IS the animation (11 frames: the window is at least this long).
#        tip     angle  slide  curl  shadow_sigma shadow_alpha
PULL = [(190,    0.20,   0,     5,    4,   0.70),
        (660,    0.75,   0,    12,    6,   0.72),
        (1130,   1.55,   0,    20,    9,   0.72),
        (1570,   2.60,   0,    28,   12,   0.70),
        (1990,   3.90,   2,    34,   15,   0.66),
        (2400,   5.20,   8,    40,   19,   0.62),
        (2800,   6.50,  24,    44,   24,   0.58),
        (3200,   7.80,  58,    48,   30,   0.52),
        (3600,   9.00, 118,    50,   36,   0.46),
        (4000,  10.10, 214,    52,   42,   0.38),
        (4400,  11.00, 360,    54,   48,   0.30)]
LAG = 1                    # the right half runs this many frames' worth of slide behind the left (a real rip is never symmetric)
CURL_W = 230               # px of sheet that bends near the torn edge
FOCAL = 2600.0             # px, how hard a lifted edge grows toward the viewer
BAND = (4, 34)             # px, thinnest and widest fibre band
LIGHT = np.array([-0.38, -0.52, 0.76])   # upper left, in front
PAPER_FIBRE = (250, 247, 240)            # raw paper fibre: the colour of the paper itself, not the look
SS = 2                     # supersample
MARGIN = 500               # the edge tables run this far past the frame
EXTRA = 3                  # pre-roll frames past the cut, kept only to prove it lines up with clean.mp4
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))


def frame(t):
    """a time's frame, counted the way the build counts media frames (pipeline/common.py q)"""
    return round(t * FPS)


def off_frame(A, B):
    """the build times media by rounding to the nearest frame (halves to even) and shows the wrapper rounding halves up:
    a window edge between two frames lands a frame apart in the two, so say so"""
    bad = [f"{n} {t:.4f}" for n, t in (("at", A), ("end", B)) if abs(t * FPS - round(t * FPS)) > 0.01]
    if bad:
        print(f"note: the window's {' and '.join(bad)} sits between frames: put it on a frame (a multiple of 1/30 s)")


def page_source(E, project):
    """(kind, clip, its frame 0 on screen in video seconds, still): kind "shot" (the shot itself), "clip" or "still".
    An effect's id reads its clip (fx/<id>/<id>.mp4, frame n at its window's start + n) and its last frame as a still
    (work/fx/<id>/last.png), the files press-front writes for an effect that tears its page"""
    if not PAGE:
        return "shot", os.path.join(project, "public", "clean.mp4"), 0.0, None
    F = next((F for F in getattr(E, "FX", []) if F["id"] == PAGE), None)
    if F:
        clip = os.path.join(project, "fx", PAGE, f"{PAGE}.mp4")
        last = os.path.join(project, "work", "fx", PAGE, "last.png")
        if not os.path.exists(clip) and not os.path.exists(last):
            sys.exit(f"PAGE {PAGE!r} has no page yet: run its gen.py first (it writes fx/{PAGE}/{PAGE}.mp4 and "
                     f"work/fx/{PAGE}/last.png)")
        return ("clip", clip if os.path.exists(clip) else None, float(F["at"] if PAGE_AT is None else PAGE_AT),
                last if os.path.exists(last) else None)
    path = os.path.join(project, PAGE)
    if not os.path.exists(path):
        sys.exit(f"PAGE {PAGE!r} is neither an effect in edit.FX nor a file in {project}")
    if PAGE.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        return "still", None, 0.0, path
    at = PAGE_AT
    if at is None:
        card = next((c for c in getattr(E, "CARDS", []) if os.path.normpath(c[1]) == os.path.normpath(PAGE)), None)
        parts = os.path.normpath(PAGE).split(os.sep)
        fx = next((F for F in getattr(E, "FX", []) if len(parts) > 2 and parts[0] == "fx" and F["id"] == parts[1]), None)
        at = float(card[2]) if card else float(fx["at"]) if fx else 0.0
    shot = os.path.realpath(path) == os.path.realpath(os.path.join(project, "public", "clean.mp4"))
    return ("shot" if shot else "clip"), path, at, None


def preroll(E, project, piece, n, W, H, path):
    """the next shot's n frames before its piece starts (plus EXTRA past it), cut from SRC the way cut.py cuts the
    pieces. On a source that isn't 30 fps the frame grid can land a frame off clean.mp4, so a few starts a fraction of
    a frame apart are tried and the one whose frames after the cut match clean.mp4 best is kept: (frames, mismatch)"""
    w, h, x, y = E.FRAMES[piece["frame"]]
    ref = [rgb.astype(np.float32) for _, rgb in fxlib.frames(project, piece["out_start"], piece["out_start"] + EXTRA / FPS)]
    tmp, best = path + ".try.mp4", None
    for d in (0.0, -0.008, 0.008, -0.016, 0.016, -0.024, 0.024):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{piece['src'] - n / FPS - 0.3 / FPS + d:.4f}", "-i", E.SRC, "-an",
                        "-vf", f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1",
                        "-frames:v", str(n + EXTRA), "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-g", "1",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", tmp], check=True)
        got = [rgb for _, rgb in fxlib.frames(project, 0, (n + EXTRA) / FPS, src=os.path.relpath(tmp, project))]
        diff = float(np.mean([np.abs(got[n + k].astype(np.float32) - r).mean() for k, r in enumerate(ref) if n + k < len(got)]))
        if best is None or diff < best[0]:
            best = (diff, got)
            os.replace(tmp, path)
        if diff < 1.5:
            break
    if os.path.exists(tmp):
        os.remove(tmp)
    return best[1], best[0]


def cover(rgb, W, H):
    """fill W x H, cropping the overflow from the middle"""
    h, w = rgb.shape[:2]
    s = max(W / w, H / h)
    im = cv2.resize(rgb, (max(W, round(w * s)), max(H, round(h * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    y, x = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
    return im[y:y + H, x:x + W]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    W, H = E.CANVAS
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    f0, fB = frame(A), frame(B)
    off_frame(A, B)
    rows_n = len(PULL)
    if fB - f0 < rows_n:
        sys.exit(f"the rip runs {rows_n} frames: end the window at {(f0 + rows_n) / FPS:.3f} or later")
    TL = json.load(open(os.path.join(project, "timeline.json")))
    cut = next((c for c in sorted(TL["picture_cuts"] + TL.get("reframes", [])) if f0 < frame(c) < f0 + rows_n), None)
    kind, page_clip, page_at, page_still = page_source(E, project)
    live = kind == "shot"
    if cut is None and live:
        sys.exit("no picture cut inside the window: the shot can only tear open onto another shot. Put the window "
                 "4 frames before a cut, or set PAGE to a clip or still that is on screen over the live shot")
    f_cut = frame(cut) if cut is not None else f0 + CUT_ROW
    if cut is not None and f_cut - f0 != CUT_ROW:
        print(f"note: the cut is {f_cut - f0} frames into the rip (it reads best at {CUT_ROW}: at={(f_cut - CUT_ROW) / FPS:.3f})")

    # the tear line: through the next shot's face on the cut
    line, how = LINE, "LINE"
    if line is None:
        how = "the middle"
        cx, cy = W / 2, H / 2
        tp = os.path.join(project, "work", "tracks", "track.json")
        if os.path.exists(tp):
            T = fxlib.tracks(project)["frames"]
            face = next((T[i]["face"] for i in range(f_cut, min(f_cut + 4, len(T))) if T[i] and T[i].get("face")), None)
            if face:
                cx, cy, how = face["cx"], face["cy"], "the face under the page"
        top = cx + TILT * cy / H
        line = (round(top), round(top - TILT))
    print(f"{fid}: window {A:.3f}-{B:.3f}  rip {f0 / FPS:.3f}-{(f0 + rows_n) / FPS:.3f}  "
          + (f"cut {cut:.3f} (row {f_cut - f0}): the next shot's pre-roll under it" if cut is not None else
             f"no cut: the page stops on row {CUT_ROW}, the live shot is underneath"))
    shown = [os.path.relpath(x, project) for x in (page_clip, page_still) if x]
    print(f"  page: {' then '.join(shown)}" + (" (the shot itself, in the live grade)" if live else
          f" (its frame 0 on screen at {page_at:.3f})" if page_clip else "") + f"  tear line {line} ({how})")
    if args.check:
        return
    d = os.path.join(project, "fx", fid)
    if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(d)), "LIBRARY.md")):
        sys.exit(f"{d} is a library folder: copy the effect into the project's own fx/{fid}/ and run it there")
    os.makedirs(d, exist_ok=True)
    work = os.path.join(project, "work", fid)
    os.makedirs(work, exist_ok=True)

    # ---- the sound: synthesized, not recorded
    sys.path.insert(0, HERE)
    import mk_rip  # noqa: E402
    os.makedirs(os.path.join(project, "audio"), exist_ok=True)
    mk_rip.write(os.path.join(project, "audio", "paper-rip.wav"))

    rng = np.random.RandomState(SEED)

    def vnoise(n, wavelength, r=rng):
        """1D value noise, 0-mean, -1..1, cubic between random knots"""
        k = int(n / wavelength) + 4
        knots = r.uniform(-1, 1, k)
        x = np.arange(n) / wavelength
        i = np.floor(x).astype(int)
        t = x - i
        a, b, c, e = knots[i], knots[i + 1], knots[i + 2], knots[i + 3]
        return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - e) * t ** 2 + (-a + 3 * b - 3 * c + e) * t ** 3)

    def octaves(n, table, r=rng):
        return sum(a * vnoise(n, w, r) for a, w in table)

    N = (H + 2 * MARGIN) * SS                  # rows of the edge tables, at SS
    rows_px = (np.arange(N) / SS) - MARGIN
    base = line[0] + (line[1] - line[0]) * (rows_px / H)
    smooth_part = octaves(N, [(46 * SS, 1000 * SS), (26 * SS, 380 * SS)])
    detail_part = octaves(N, [(11 * SS, 120 * SS), (6 * SS, 52 * SS), (3.2 * SS, 21 * SS), (1.7 * SS, 9 * SS), (0.9 * SS, 4 * SS)])
    EDGE_S = base + smooth_part / SS           # the smooth tear line (px): the sheet bends around this
    EDGE = EDGE_S + detail_part / SS           # the real jagged edge (px)
    n1 = octaves(N, [(1, 170 * SS), (0.5, 60 * SS), (0.3, 24 * SS)])
    n1 = np.clip(0.5 + 0.55 * n1, 0, 1)
    WIDE_L = BAND[0] + (BAND[1] - BAND[0]) * n1 ** 1.5
    WIDE_R = BAND[0] + (BAND[1] - BAND[0]) * ((1 - n1) ** 1.5) * np.clip(0.75 + 0.5 * vnoise(N, 90 * SS), 0.4, 1.0)
    ROUGH_L = octaves(N, [(2.4, 14 * SS), (1.4, 6 * SS), (0.7, 2.5 * SS)])
    ROUGH_R = octaves(N, [(2.4, 14 * SS), (1.4, 6 * SS), (0.7, 2.5 * SS)])
    CURL_VAR = np.clip(1 + 0.42 * octaves(N, [(1, 420 * SS), (0.45, 170 * SS)]), 0.45, 1.5)    # the bend is never even along a tear

    # ---- fine 2D textures for the raw fibre, in texture space
    TW, TH = W * SS, H * SS
    r2 = np.random.RandomState(SEED + 1)
    fuzz = cv2.GaussianBlur(r2.normal(0, 1, (TH, TW)).astype(np.float32), (0, 0), 0.9)
    fuzz /= fuzz.std()
    fibre = cv2.GaussianBlur(r2.normal(0, 1, (TH, TW)).astype(np.float32), (0, 0), sigmaX=5.0, sigmaY=0.7)   # long across the tear, short along it
    fibre /= fibre.std()
    speck = cv2.GaussianBlur(r2.normal(0, 1, (TH, TW)).astype(np.float32), (0, 0), 0.8)
    speck /= speck.std()
    UU, VV = np.meshgrid((np.arange(TW) + .5) / SS, (np.arange(TH) + .5) / SS)
    UU = UU.astype(np.float32)
    row_idx = ((VV + MARGIN) * SS).astype(np.int32).clip(0, N - 1)
    edge2d = EDGE[row_idx].astype(np.float32)

    def stray(side, r):
        """a few loose fibres standing off the torn edge, a stroke layer in texture space"""
        lay = np.zeros((TH, TW), np.uint8)
        for y in r.randint(0, TH, 95):
            x0 = EDGE[int(y + MARGIN * SS)] * SS
            L = r.uniform(4, 14) * SS
            a = r.uniform(-1.0, 1.0)
            pts = np.array([[x0 - side * 2 * SS, y], [x0 + side * L * .55, y + L * a * .35], [x0 + side * L, y + L * a * r.uniform(.5, 1.1)]]).astype(np.int32)
            cv2.polylines(lay, [pts], False, int(r.uniform(90, 230)), 1, cv2.LINE_AA)
        return lay.astype(np.float32) / 255

    STRAY_L, STRAY_R = stray(+1, np.random.RandomState(SEED + 2)), stray(-1, np.random.RandomState(SEED + 3))

    def half_texture(page2x, side, tip):
        """premultiplied RGBA (float32 0..1) of one half at SS: the printed page up to a rough inner line, raw fibre from
        there to the torn edge. Below the tip the sheet is whole."""
        torn = (VV < tip + 3 * fuzz).astype(np.float32)
        torn = cv2.GaussianBlur(torn, (0, 0), 0.6)
        dd = (edge2d - UU) if side < 0 else (UU - edge2d)            # px inside the half, measured from the torn edge
        wide = (WIDE_L if side < 0 else WIDE_R)[row_idx].astype(np.float32) + (ROUGH_L if side < 0 else ROUGH_R)[row_idx].astype(np.float32)
        wide = np.maximum(wide, 1.0)
        alpha_torn = np.clip((dd + 0.5 * fuzz) * SS * 0.8 + 0.5, 0, 1)
        if side < 0:                                                # the left half lies under the right, and runs past the line where the sheet is whole, so no seam shows
            alpha = alpha_torn * torn + np.clip((dd + 4) * SS * 0.8 + 0.5, 0, 1) * (1 - torn)
        else:
            alpha = alpha_torn * torn + np.clip(dd * SS * 0.8 + 0.5, 0, 1) * (1 - torn)
        band = np.clip((wide + 0.9 * fuzz - dd) * SS * 0.7 + 0.5, 0, 1) * torn
        tone = 1 + 0.018 * fibre + 0.012 * speck
        fib = np.stack([np.full_like(UU, c / 255) for c in PAPER_FIBRE], -1) * tone[..., None]
        lip = np.clip(1 - np.abs(wide + 0.9 * fuzz - dd) / 1.6, 0, 1) * torn * 0.16      # the printed layer's broken lip throws a hair of shadow on the fibre
        rgb = page2x * (1 - band[..., None]) + fib * band[..., None]
        rgb = rgb * (1 - lip[..., None])
        st = (STRAY_L if side < 0 else STRAY_R) * torn
        a = np.maximum(alpha, st * 0.7)
        rgb = rgb * alpha[..., None] + fib * (a - alpha)[..., None]    # premultiplied
        return np.concatenate([rgb, a[..., None]], -1).astype(np.float32)

    # ---- the sheet's shape. Forward: page (u, v) -> bend near the torn edge -> turn about the running tip + slide off ->
    # perspective. warp_half solves it backwards for every screen pixel (fixed point, the bend from a lookup table), so
    # there is no mesh to show: no triangles, no stair steps, whatever the foreshortening.
    AMAX = np.radians(79.0)
    NA, NX = 96, 257
    AMT = np.linspace(0, AMAX, NA)
    XI = np.linspace(0, 1, NX)
    _c = np.cos(AMT[:, None] * XI[None, :] ** 2)
    _s = np.sin(AMT[:, None] * XI[None, :] ** 2)
    C_T = np.zeros((NA, NX), np.float32)
    S_T = np.zeros((NA, NX), np.float32)
    C_T[:, 1:] = np.cumsum((_c[:, 1:] + _c[:, :-1]) / 2 * (XI[1] - XI[0]), axis=1)      # how far along the flat you have got at xi (in curve widths)
    S_T[:, 1:] = np.cumsum((_s[:, 1:] + _s[:, :-1]) / 2 * (XI[1] - XI[0]), axis=1)      # how high you are at xi (in curve widths)
    TOT = C_T[:, -1].copy()
    _N = np.linspace(0, 1, NX)
    XI_OF = np.stack([np.interp(_N, C_T[i] / TOT[i], XI) for i in range(NA)]).astype(np.float32)
    GX, GY = np.meshgrid(np.arange(W // 2, dtype=np.float32) * 2 + 1, np.arange(H // 2, dtype=np.float32) * 2 + 1)   # 2px cells

    def smoothstep(x):
        x = np.clip(x, 0, 1)
        return x * x * (3 - 2 * x)

    def table(tab, n, amt):
        return cv2.remap(tab, (n * (NX - 1)).astype(np.float32), (amt / AMAX * (NA - 1)).astype(np.float32), cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)

    def solve(side, row, fr):
        """for every screen point on a 2px grid: the page point (u, v) that lands there, and its shade"""
        tip, ang, slide, curl, _, _ = row
        z0 = slide * 0.25                                             # the half comes up off the page as it leaves
        drift = slide * (0.12 if side < 0 else -0.06)                 # the two never travel the same way
        v_tip = min(tip, H)
        px, py = float(np.interp(v_tip, rows_px, EDGE_S)), float(tip)
        k = np.ones_like(GX)
        v = GY.copy()
        for _ in range(7):
            X = W / 2 + (GX - W / 2) / k - side * slide
            Y = H / 2 + (GY - H / 2) / k - drift
            h = np.maximum(tip - v, 0.0)
            a = np.radians(ang) * smoothstep(h / 520.0) * side
            ca, sa = np.cos(a), np.sin(a)
            rx, ry = X - px, Y - py
            bent = px + ca * rx + sa * ry
            v = py - sa * rx + ca * ry
            e = np.interp(v, rows_px, EDGE_S).astype(np.float32)
            h = np.maximum(tip - v, 0.0)
            amt = np.radians(curl) * np.interp(v, rows_px, CURL_VAR) * smoothstep(h / 700.0) * (1 + 0.2 * np.sin(2 * np.pi * (v / 820.0 + fr * 0.31) + side))   # it flutters
            amt = np.clip(amt, 0, AMAX).astype(np.float32)
            travelled = (bent - (e - CURL_W)) if side < 0 else ((e + CURL_W) - bent)   # how far past the start of the curve this point is, on the flat
            tot = np.interp(amt, AMT, TOT) * CURL_W
            n = np.clip(travelled / tot, 0, 1)
            xi = table(XI_OF, n, amt)
            over = np.maximum(travelled - tot, 0.0) / np.cos(amt)
            z = table(S_T, xi, amt) * CURL_W + over * np.sin(amt)
            k = FOCAL / (FOCAL - z - z0)
        dd = (1 - xi) * CURL_W - over
        u = np.where(travelled <= 0, bent, (e - dd) if side < 0 else (e + dd))
        alpha = amt * xi ** 2 * (travelled > 0)
        nx = np.sin(alpha) * (-1 if side < 0 else 1)
        nz = np.cos(alpha)
        lit = np.clip(0.3 + 0.7 * (nx * LIGHT[0] + nz * LIGHT[2]) / LIGHT[2], 0.42, 1.1)
        return u.astype(np.float32), v.astype(np.float32), lit.astype(np.float32)

    def warp_half(tex, side, row, fr):
        u, v, lit = solve(side, row, fr)
        big = cv2.resize(np.stack([u, v, lit], -1), (W * SS, H * SS), interpolation=cv2.INTER_LINEAR)
        mx, my, sh = big[..., 0] * SS - 0.5, big[..., 1] * SS - 0.5, big[..., 2]
        res = cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        res[..., :3] *= sh[..., None]
        return res

    # ---- the next shot's pre-roll (cut like pipeline/cut.py), under the page until the cut
    n = f_cut - f0
    handle = None
    if cut is not None:
        piece = next(p for p in TL["pieces"] if abs(p["out_start"] - cut) < 0.02)
        join = next((k for k in TL["keep"] if abs(k["picture_out"] - cut) < 0.002), None)
        lead = round((join["picture_out"] - join["out"]) * FPS) if join else n
        if n > lead:
            print(f"WARNING: the J-cut lead here is {lead} frames: the pre-roll's first {n - lead} frames run ahead of "
                  f"the next line's audio. Start the window at {(f_cut - lead) / FPS:.3f}")
        handle, diff = preroll(E, project, piece, n, W, H, os.path.join(work, "h.mp4"))
        print(f"  pre-roll: {n} frames before the cut, its frames after the cut against clean.mp4: mean diff {diff:.2f}"
              + ("  CHECK THIS" if diff > 3 else ""))
    for f in ("h.mp4", "tear.mp4", "tear.webm"):              # files an older version of this effect published
        if os.path.exists(os.path.join(d, f)):
            os.remove(os.path.join(d, f))
    live_frames = {i: rgb for i, rgb in fxlib.frames(project, f0 / FPS, (f0 + rows_n) / FPS)}     # proof stills only

    # ---- the page's frames: alive up to the cut, then the sheet holds its last frame
    pages, last = {}, None
    if page_clip:                                     # the clip while it lasts, then its own last frame (a still drawn
        off = frame(page_at)                          # for print, like press-front's last.png, can land levels off it)
        rel = os.path.relpath(page_clip, project)
        nclip = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                            page_clip], capture_output=True, text=True).stdout.strip() or 0) * FPS)
        a, b = max(f0 - off, 0), max(min(f_cut - off, nclip), 1)
        for j, rgb in fxlib.frames(project, min(a, b - 1) / FPS, b / FPS, src=rel):
            pages[j + off] = rgb if rgb.shape[:2] == (H, W) else cover(rgb, W, H)
        if pages:
            held = pages[max(pages)]
            for i in range(f0, f_cut):
                pages.setdefault(i, held)
    if page_still and not pages:                      # a still page, or an effect's last frame when its clip is gone
        im = cv2.imread(page_still, cv2.IMREAD_COLOR)
        if im is None:
            sys.exit(f"can't read the still {page_still}")
        last = cover(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), W, H)
        for i in range(f0, f_cut):
            pages.setdefault(i, last)
    if not pages:
        sys.exit(f"no frames of {os.path.relpath(page_clip, project)} at {f0 / FPS:.2f}-{f_cut / FPS:.2f} (its frame 0 at "
                 f"{page_at:.2f}): check PAGE_AT")
    last = pages[max(pages)]

    # until the cut the page fills the frame: one opaque H.264 clip with the next shot composited into the opening tear
    # (a takeover lands at the picture's own levels only in H.264); from the cut, VP9 with alpha carries just the halves
    # and their shadow over the live picture, so everything on screen shows through the gap again
    wa = fxlib.Writer(os.path.join(d, "tear-a.mp4"), w=W, h=H)
    wb = fxlib.Writer(os.path.join(d, "tear-b.webm"), w=W, h=H, alpha=True, crf=8)
    YY = (np.arange(H, dtype=np.float32) + .5)[:, None]

    def shift(img, dx, dy):
        return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), flags=cv2.INTER_LINEAR)

    for k, row in enumerate(PULL):
        i = f0 + k
        page = pages.get(i, last).astype(np.float32) / 255
        page2x = cv2.resize(page, (W * SS, H * SS), interpolation=cv2.INTER_CUBIC)
        tip = row[0]
        L = warp_half(half_texture(page2x, -1, tip), -1, row, i)
        rowR = PULL[max(0, k - LAG)]
        rowR = (row[0], row[1] * 0.92, rowR[2], row[3], row[4], row[5])
        R = warp_half(half_texture(page2x, +1, tip), +1, rowR, i)
        L = cv2.resize(L, (W, H), interpolation=cv2.INTER_AREA)
        R = cv2.resize(R, (W, H), interpolation=cv2.INTER_AREA)
        comp = R + L * (1 - R[..., 3:])                                # the right half lies on top
        keep = smoothstep((YY - (tip + 40)) / 40.0)                    # where the sheet is still whole and flat it is the page itself
        if keep.max() > 0:
            rgba_page = np.concatenate([page, np.ones((H, W, 1), np.float32)], -1)
            comp = comp * (1 - keep[..., None]) + rgba_page * keep[..., None]
        a = comp[..., 3]
        sig, sa = row[4], row[5]
        aL, aR = L[..., 3], R[..., 3]
        sh = np.maximum(cv2.GaussianBlur(shift(aL, sig * 0.8, sig * 0.5), (0, 0), sig),            # the light is upper left: the left half throws its shadow out across the gap
                        cv2.GaussianBlur(shift(aR, sig * 0.25, sig * 0.5), (0, 0), sig * 0.8))
        sh = np.maximum(sh, cv2.GaussianBlur(a, (0, 0), max(1.5, sig * 0.28)) * 0.8) * sa           # and a tight contact line on both
        out_a = a + sh * (1 - a)
        rgb = comp[..., :3] / np.maximum(out_a, 1e-4)[..., None]       # the shadow is black: premultiplied it adds no colour
        under = (handle[k] if handle is not None and k < n else live_frames.get(i, last)).astype(np.float32)
        prev = under * (1 - out_a[..., None]) + np.clip(rgb, 0, 1) * 255 * out_a[..., None]
        if k < n:                                     # under it: the next shot's pre-roll (or the live shot, with no cut)
            wa.write(np.clip(prev, 0, 255).round().astype(np.uint8))
        else:
            wb.write(np.concatenate([np.clip(rgb, 0, 1) * 255, out_a[..., None] * 255], -1).round().astype(np.uint8))
        cv2.imwrite(os.path.join(work, f"f{i}.jpg"), prev[..., ::-1].astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"  frame {i} t={i / FPS:.3f} tip {tip} covers {a.mean() * 100:.1f}%", flush=True)
    wa.close()
    wb.close()

    tag = 'style="position:absolute;left:0;top:0;width:{w}px;height:{h}px;"'.format(w=W, h=H)
    cls = "g" if live else ""                         # the shot itself takes the live grade; another page keeps its own look
    html = (f"<!-- paper-tear (over). Written by gen.py (rerun it, don't edit this file): tear-a.mp4 is the page tearing open "
            f"with the {'next shot' if cut is not None else 'live shot'} composited into the gap, until the "
            f"{'cut' if cut is not None else 'halves pull away'}; tear-b.webm is then the two halves and their contact shadow "
            f"over the live picture{', both in the live grade' if live else ''}. -->\n"
            f'<video id="{{{{ID}}}}-a" class="{cls}" src="fx/{{{{ID}}}}/tear-a.mp4" muted playsinline data-start="{{{{START}}}}" '
            f'data-media-start="0.001" data-duration="{n / FPS:.4f}" data-track-index="{{{{T0}}}}" {tag}></video>\n'
            f'<video id="{{{{ID}}}}-b" class="{cls}" src="fx/{{{{ID}}}}/tear-b.webm" muted playsinline '
            f'data-start="{{{{START+{n / FPS:.4f}}}}}" data-media-start="0.001" data-duration="{(rows_n - n) / FPS:.4f}" '
            f'data-track-index="{{{{T1}}}}" {tag}></video>\n')
    js = "// paper-tear: written by gen.py (rerun it, don't edit this file). Both clips are pre-rendered, nothing to time here.\n"
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(os.path.join(d, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write(js)
    print(f"wrote {d}: tear-a.mp4, tear-b.webm, fx.html, fx.js; proof stills in {work}\n"
          f"SFX for edit.SOUND['sfx']:\n"
          f"    dict(at={f0 / FPS:.3f}, name=\"paper-rip\", db=-5, align=\"start\"),   # audio/paper-rip.wav, starts with the rip\n"
          f"    ({(f_cut + 3) / FPS:.3f}, \"whoosh\", -14),   # the halves pull away"
          + (f"\nthe tear is the transition on the cut at {cut:.3f}: keep CAMERA settles off it" if cut is not None else ""))


if __name__ == "__main__":
    main()
