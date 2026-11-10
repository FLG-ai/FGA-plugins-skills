#!/usr/bin/env python3
"""Plate: the room without the speaker, for a locked-off shot (camera on a tripod, never touched during the take).

Default, the empty room: in edit.py, EMPTY = (s0, s1) is a stretch of the take (source seconds) where nobody is in the
shot (the creator walked out at the end and let it record the room for 5 seconds), or EMPTY_CLIP = "<file>" (or
("<file>", s0, s1)) is a separate clip of the empty room from the same camera. The empty room is the median of those
frames (a flicker or a passing shadow drops out), level matched to the take. The room as the take saw it (the masked
median of the take: what it shows can't pop against the live shot) keeps every pixel the take saw; the patch the
speaker always covered, and everything outside the crops, comes from the empty room. No generated fill, nothing to
repair by hand.
Fallback, no empty room: the masked median of the take, with the patch the take never saw inpainted. It WILL show
wherever an effect moves the speaker off their spot or reveals the room. Film the empty room (the storyboard's NEEDS
line), or give plate_finish.py --fill <a photo of the empty room from the camera's spot, or a background generated
from plate_finish.py --bg-frame>.

-> work/plate/plate_src.png   the room as the take saw it, source size
   work/plate/room_pure.png   the empty room alone, level matched to the take (only with an empty room)
   work/plate/hole.png        what the take never saw well (255), source size
   work/plate/plate.json      what was done (empty room or fallback, its source, the level match, the hole)
Next: PY pipeline/plate_finish.py <project>, which turns these into the per-crop layers and room files effects read.
Run: PY pipeline/plate.py <project> [--samples N] [--find-empty] [--force]
  --find-empty  list the still stretches of the take (and of EMPTY_CLIP), with a frame from each in
                work/plate/find_empty.jpg: where the empty room is, to put in EMPTY
  --force       run even when the shot doesn't look locked off
"""
import json
import os
import subprocess
import sys
import warnings

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fxlib  # noqa: E402
from common import load_edit, project_arg, timeline  # noqa: E402

FPS = 30
K_MIN = 6                 # with an empty room, the take's own view is kept where it saw the room in this many samples
BUDGET = 1.2e9            # bytes the take's samples may hold at once (frames + masks)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def src_time(TL, t):
    k = [p for p in TL["keep"] if p["picture_out"] <= t + 1e-6][-1]
    return k["src_in"] + (t - k["out"])


_CONV = {}


def conv(path):
    """the exact decode for a source (fxlib.ACCURATE with its own range): the plate starts at the same levels as the
    footage, so the per-crop curve in plate_finish.py only has to absorb the encode"""
    if path not in _CONV:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=pix_fmt,color_range", "-of", "default=nw=1", path], capture_output=True, text=True).stdout
        full = "color_range=pc" in out or "pix_fmt=yuvj" in out
        _CONV[path] = fxlib.ACCURATE.replace("in_range=tv", "in_range=pc" if full else "in_range=tv")
    return _CONV[path]


def read_src(path, t, W, H, scale=1.0):
    """one frame of the source at t seconds, rgb uint8 (at `scale` of the source size)"""
    w, h = round(W * scale), round(H * scale)
    vf = conv(path) + (f",scale={w}:{h}:flags=area" if scale != 1.0 else "")
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.4f}", "-i", path, "-frames:v", "1", "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.uint8)[:w * h * 3].reshape(h, w, 3)


def read_span(path, a, b, n, W, H, scale=1.0):
    """n frames spread over a..b seconds of a clip, in one decode"""
    w, h = round(W * scale), round(H * scale)
    vf = f"fps={n / max(0.05, b - a):.5f}," + conv(path) + (f",scale={w}:{h}:flags=area" if scale != 1.0 else "")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.4f}", "-t", f"{b - a:.4f}", "-i", path, "-vf", vf,
                          "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    k = len(raw) // (w * h * 3)
    return np.frombuffer(raw[:k * w * h * 3], np.uint8).reshape(k, h, w, 3)


def still_runs(path, min_len=1.5):
    """stretches of a clip where nothing in the frame moves (an empty room on a locked-off camera): [(s0, s1, motion)]"""
    W, H = fxlib.size(path)
    w = 96
    h = max(2, round(H * w / W / 2) * 2)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps=10,scale={w}:{h},format=gray", "-f", "rawvideo",
                          "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    if len(f) < 3:
        return []
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    still = d < max(0.35, float(np.percentile(d, 10)) * 1.8)
    runs, s = [], None
    for i, v in enumerate(list(still) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if (i - s) / 10 >= min_len:
                runs.append((round((s + 1) / 10 + 0.2, 2), round(i / 10 - 0.2, 2), round(float(d[s:i].mean()), 3)))
            s = None
    return runs


def empty_source(E):
    """(path, s0, s1, how) of the empty room from edit.EMPTY / EMPTY_CLIP, or None"""
    clip = getattr(E, "EMPTY_CLIP", None)
    if clip:
        path, rng = (clip, None) if isinstance(clip, str) else (clip[0], tuple(clip[1:3]))
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            sys.exit(f"EMPTY_CLIP not found: {path}")
        if rng is None and getattr(E, "EMPTY", None):
            rng = tuple(E.EMPTY)
        if rng is None:
            runs = still_runs(path)
            if runs:
                a, b, _ = max(runs, key=lambda r: r[1] - r[0])
                print(f"EMPTY_CLIP has no range: using its longest still stretch, {a:.2f}-{b:.2f}s "
                      f"(set EMPTY_CLIP = (\"{path}\", {a:.2f}, {b:.2f}) to pin it)")
                rng = (a, b)
            else:
                rng = (0.3, float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                                  "csv=p=0", path], capture_output=True, text=True).stdout) - 0.3)
                print("EMPTY_CLIP has no still stretch: using all of it (the median keeps the room if someone passes)")
        return path, float(rng[0]), float(rng[1]), "EMPTY_CLIP"
    if getattr(E, "EMPTY", None):
        return E.SRC, float(E.EMPTY[0]), float(E.EMPTY[1]), "EMPTY"
    return None


def find_empty(P, E):
    """print the still stretches of the take and of EMPTY_CLIP, one frame of each in work/plate/find_empty.jpg"""
    out = os.path.join(P, "work", "plate")
    os.makedirs(out, exist_ok=True)
    tiles = []
    clips = [E.SRC] + ([E.EMPTY_CLIP if isinstance(E.EMPTY_CLIP, str) else E.EMPTY_CLIP[0]] if getattr(E, "EMPTY_CLIP", None) else [])
    for path in clips:
        W, H = fxlib.size(path)
        runs = still_runs(path)
        print(f"{path}: {len(runs)} still stretch(es)" + ("" if runs else " (nobody left the shot, or the camera moves)"))
        for a, b, m in runs:
            print(f"  {a:7.2f} - {b:7.2f} s  ({b - a:.1f} s, motion {m})")
            im = read_src(path, (a + b) / 2, W, H, 320 / max(W, H)).copy()
            cv2.putText(im, f"{a:.1f}-{b:.1f}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            tiles.append(im)
    if tiles:
        h = max(t.shape[0] for t in tiles)
        row = np.hstack([np.pad(t, ((0, h - t.shape[0]), (0, 4), (0, 0))) for t in tiles])
        cv2.imwrite(os.path.join(out, "find_empty.jpg"), cv2.cvtColor(row, cv2.COLOR_RGB2BGR))
        print(f"look at {os.path.join(out, 'find_empty.jpg')}: a stretch with nobody in it goes in EMPTY = (s0, s1) "
              f"(or EMPTY_CLIP = (\"<file>\", s0, s1))")


def locked_off(P, E, TL, SW, SH):
    """how far the room moves across the take, in source px: corners in the room (never on the speaker) followed from
    the first sample to the others. A tripod shot moves a pixel or two at most; a hand-held phone loses its corners"""
    k = min(1.0, 960 / max(SW, SH))
    shots, frames = TL["shots"], []
    for t in np.linspace(0.3, TL["total"] - 0.3, 7):
        f = [s["frame"] for s in shots if s["t"] <= t + 1e-6][-1]
        cw, ch, cx, cy = E.FRAMES[f]
        g = cv2.cvtColor(read_src(E.SRC, src_time(TL, t), SW, SH, k), cv2.COLOR_RGB2GRAY)
        al = cv2.resize(next(fxlib.alpha(P, t, t + 1 / FPS))[1], (round(cw * k), round(ch * k)))
        room = np.ones(g.shape, bool)                         # False where the speaker is (or might be)
        y0, x0 = round(cy * k), round(cx * k)
        room[y0:y0 + al.shape[0], x0:x0 + al.shape[1]] = (cv2.dilate(al, np.ones((15, 15), np.uint8)) < 8)[:g.shape[0] - y0, :g.shape[1] - x0]
        frames.append((g, room))
    g0, r0 = frames[0]
    pts = cv2.goodFeaturesToTrack(g0, 400, 0.01, 8, mask=r0.astype(np.uint8))
    if pts is None or len(pts) < 20:
        return None                                            # a plain room: nothing to follow, can't tell
    worst = 0.0
    for g, r in frames[1:]:
        p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g, pts, None, winSize=(21, 21), maxLevel=4)
        q = p1.reshape(-1, 2)
        ok = (st.ravel() == 1) & (q[:, 0] >= 0) & (q[:, 1] >= 0) & (q[:, 0] < g.shape[1] - 1) & (q[:, 1] < g.shape[0] - 1)
        ok[ok] &= r[q[ok, 1].astype(int), q[ok, 0].astype(int)]
        if ok.mean() < 0.6:
            return float("inf")                                # the room's corners are gone: the camera moved a lot
        worst = max(worst, float(np.median(np.linalg.norm(q[ok] - pts.reshape(-1, 2)[ok], axis=1))) / k)
    return worst


def align(take, room, known):
    """the similarity (scale, rotation, shift) that puts the empty room on the take: corners of the room the take saw
    clearly, followed into the empty room, RANSAC -> (M, scale, degrees, shift at the centre, corners used), or a
    string saying why there's nothing to apply"""
    gt = cv2.cvtColor(take, cv2.COLOR_RGB2GRAY)
    ge = cv2.cvtColor(room, cv2.COLOR_RGB2GRAY)
    mask = cv2.erode(known.astype(np.uint8), np.ones((15, 15), np.uint8))   # off the patch's edge
    gt = np.where(mask > 0, gt, ge)          # the never-seen patch is black in the take: no corners on its edge
    pts = cv2.goodFeaturesToTrack(gt, 3000, 0.001, 10, mask=mask)
    if pts is None or len(pts) < 40:
        return "too few corners in the room to measure"
    p1, st, _ = cv2.calcOpticalFlowPyrLK(gt, ge, pts, None, winSize=(31, 31), maxLevel=3)
    ok = st.ravel() == 1
    if ok.sum() < 40:
        return "the room's corners couldn't be followed into the empty room"
    M, inl = cv2.estimateAffinePartial2D(p1[ok], pts[ok], method=cv2.RANSAC, ransacReprojThreshold=1.0,
                                         maxIters=5000, confidence=0.999)
    if M is None or inl is None or inl.sum() < 30:
        return "no fit"
    sc = float(np.hypot(M[0, 0], M[1, 0]))
    rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    sh = M[:, 2] + (M[:, :2] - np.eye(2)) @ (np.array(gt.shape[::-1], np.float64) / 2)    # the shift at the centre
    if abs(sc - 1) > 0.03 or abs(rot) > 1 or np.hypot(*sh) > 60:
        return (f"WARNING: it only fits with a big move (scale {sc:.4f}, {rot:.2f} deg, shift {sh.round(1).tolist()}): "
                "the camera moved between them, so it was left as filmed")
    if abs(sc - 1) < 1e-4 and abs(rot) < 0.005 and np.hypot(*sh) < 0.25:
        return f"already lined up ({int(inl.sum())} corners)"
    return M, sc, rot, sh, int(inl.sum())


def knot_curve(src, dst, clamp):
    """a per-channel curve src -> dst (offsets measured at a few levels, medians, interpolated): robust to the odd
    pixel that changed between the two"""
    knots = [8, 14, 20, 28, 40, 60, 90, 130, 180, 235, 250]
    lut = np.zeros((256, 3), np.float32)
    for c in range(3):
        pv, lv = src[:, c].astype(np.int32), dst[:, c].astype(np.float32)
        ofs = []
        for kk in knots:
            m = np.abs(pv - kk) <= max(2, kk // 8)
            ofs.append(float(np.median(lv[m] - pv[m])) if m.sum() > 1000 else np.nan)
        ofs = np.array(ofs)
        good = ~np.isnan(ofs)
        ofs = np.interp(knots, np.array(knots)[good], ofs[good]) if good.any() else np.zeros(len(knots))
        lut[:, c] = np.arange(256) + np.interp(np.arange(256), knots, np.clip(ofs, -clamp, clamp))
    return lut


def main():
    P = project_arg()
    E = load_edit(P)
    TL = timeline(P)
    out = os.path.join(P, "work", "plate")
    os.makedirs(out, exist_ok=True)
    if "--find-empty" in sys.argv:
        return find_empty(P, E)
    if not os.path.exists(os.path.join(P, "public", "subject.webm")):
        sys.exit("plate.py needs the speaker's matte first: PY pipeline/matte.py (or cutout.py) <project>")
    SW, SH = fxlib.size(E.SRC)
    moved = locked_off(P, E, TL, SW, SH)
    if moved is None:
        moved = 0.0
        print("camera: the room is too plain to follow; treating the shot as locked off")
    else:
        moved *= max(E.CANVAS[0] / v[0] for v in E.FRAMES.values())          # in px of the video
        if moved < 1e6:
            print(f"camera: the room drifts up to {moved:.1f}px of the video across the take")
    if 3 < moved < 1e6:
        print("  the camera drifts a little (a tripod settling): the room sits at its average position, so edges can be "
              "off by half that at the start and end of the take")
    if moved > 12 and "--force" not in sys.argv:
        how = f"the room moves {moved:.0f}px" if moved < 1e6 else "the room can't be followed from frame to frame"
        sys.exit(f"This shot isn't locked off ({how}): the room and its layers need a camera on a "
                 "tripod that nobody touches. Pick effects that don't need the room (fx/LIBRARY.md, the supply column), "
                 "or run with --force to try anyway.")
    emp = empty_source(E)
    # work at the resolution the crops need (plus headroom for a push-in), not more: memory scales with it
    scale = min(1.0, max(E.CANVAS[0] / v[0] for v in E.FRAMES.values()) * 1.25)
    WW, WH = round(SW * scale), round(SH * scale)
    X0 = max(0, round((min(v[2] for v in E.FRAMES.values()) - 300) * scale))
    X1 = min(WW, round((max(v[2] + v[0] for v in E.FRAMES.values()) + 300) * scale))
    per = WH * (X1 - X0) * 4
    n = int(arg("--samples", 64 if emp else 140))
    if n * per > BUDGET:
        n = max(24, int(BUDGET // per))
        print(f"  {n} samples (memory)")
    # every shot counts, but a frame only knows about the pixels inside its own crop (the matte stops at the crop edge)
    shots = [(s["t"], s["frame"]) for s in TL["shots"]] + [(TL["total"], None)]
    spans = [(a, b, f) for (a, f), (b, _) in zip(shots, shots[1:]) if b > a]
    total = sum(b - a for a, b, _ in spans)
    times = []
    for a, b, f in spans:
        m = max(2, round(n * (b - a) / total))
        times += [(a + (b - a) * (i + 0.5) / m, f) for i in range(m)]
    stack, masks = [], []
    kern = np.ones((17, 17), np.uint8)
    for j, (t, f) in enumerate(times):
        cw, ch, cx, cy = (round(v * scale) for v in E.FRAMES[f])
        rgb = read_src(E.SRC, src_time(TL, t), SW, SH, scale)
        al = next(fxlib.alpha(P, t, t + 1 / FPS))[1]
        big = cv2.resize(al, (cw, ch), interpolation=cv2.INTER_LINEAR)
        m = np.ones((WH, WW), np.uint8)                 # 1 = unknown or the speaker
        m[cy:cy + ch, cx:cx + cw] = cv2.dilate((big > 8).astype(np.uint8), kern)[:WH - cy, :WW - cx]
        stack.append(rgb[:, X0:X1])
        masks.append(m[:, X0:X1].astype(bool))
        print(f"\r  take sample {j + 1}/{len(times)}", end="", flush=True)
    print()
    S = np.stack(stack)
    M = np.stack(masks)
    del stack, masks
    take = np.zeros((WH, X1 - X0, 3), np.uint8)
    for y in range(WH):                      # masked median, a row at a time
        r = S[:, y].astype(np.float32)
        r[M[:, y]] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            take[y] = np.nan_to_num(np.nanmedian(r, axis=0)).astype(np.uint8)
    count = (~M).sum(axis=0)
    info = dict(mode="fallback", samples=len(times), scale=round(scale, 4), camera_moves_px=round(moved, 2) if moved < 1e6 else "moves")

    if emp:
        path, a, b, how = emp
        EW, EH = fxlib.size(path)
        if (EW, EH) != (SW, SH):
            sys.exit(f"{how} is {EW}x{EH} and the take is {SW}x{SH}: the empty room has to come from the same camera")
        k = 16 if WW * WH > 4e6 else 24
        F = read_span(path, a, b, k, EW, EH, scale)
        if len(F) < 3:
            sys.exit(f"{how} {a:.2f}-{b:.2f}s gave {len(F)} frames: check the seconds")
        room = np.zeros((WH, WW, 3), np.uint8)
        for y in range(0, WH, 256):          # median in bands: a 4K stack sorted at once is a lot of memory
            room[y:y + 256] = np.median(F[:, y:y + 256], axis=0).astype(np.uint8)
        del F
        rg = room[:, X0:X1]
        known = count >= K_MIN
        hole = ~known
        # nobody may still be in the "empty" frames: where the speaker always sat, the take shows them, the room doesn't
        if hole.mean() > 0.002:
            idx = np.flatnonzero(hole)[::7]                  # a sample of the patch is plenty, and small
            them = np.median(S.reshape(len(S), -1, 3)[:, idx], axis=0)
            same = (np.abs(them.astype(np.float32) - rg.reshape(-1, 3)[idx].astype(np.float32)).mean(axis=1) < 10).mean()
            if same > 0.6:
                sys.exit(f"{how} {a:.2f}-{b:.2f}s still shows the speaker ({same * 100:.0f}% of where they sit looks the "
                         f"same as the take): pick seconds after they've left (plate.py --find-empty)")
        # line the empty room up with the take before anything else: a nudged tripod shifts it, focus breathing scales
        # it (a few hundredths of a percent show at the frame's edges). Corners of the room the take saw, followed into
        # the empty room, fitted as scale + rotation + shift
        fit = align(take, rg, known)
        if not isinstance(fit, str):
            M, sc, rot, sh, used = fit
            M = M.copy()
            M[:, 2] += np.array([X0, 0.0]) - M[:, :2] @ np.array([X0, 0.0])      # the crop region -> the whole frame
            room = cv2.warpAffine(room, M, (WW, WH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            rg = room[:, X0:X1]
            sh = [round(float(v) / scale, 2) for v in sh]
            print(f"  empty room fitted to the take ({used} corners): scale {(sc - 1) * 100:+.3f}%, rotation {rot:+.3f} "
                  f"deg, shift {sh[0]:+.2f},{sh[1]:+.2f} px")
            info_fit = dict(scale=round(sc, 6), rotate_deg=round(rot, 4), shift_px=sh, corners=used)
        else:
            print(f"  empty room fitted to the take: {fit}")
            info_fit = dict(scale=1.0, rotate_deg=0.0, shift_px=[0.0, 0.0], note=fit)
        # level match (exposure, light that changed between the take and the empty stretch): a curve, on the pixels
        # the take saw that agree with the room once a plain offset is taken out
        tf, rf = take[known].astype(np.float32), rg[known].astype(np.float32)
        off = np.median(tf - rf, axis=0)
        ok = np.abs(tf - (rf + off)).mean(axis=1) < 14
        lut = knot_curve(rf[ok], tf[ok], 40)
        pure = np.dstack([lut[room[..., c], c] for c in range(3)])
        agree = float(ok.mean())
        print(f"  {how} {a:.2f}-{b:.2f}s: {agree * 100:.0f}% of what the take saw agrees with the empty room, "
              f"level offset RGB {np.round(off, 1).tolist()}")
        if agree < 0.4:
            print("  WARNING: the empty room and the take disagree a lot: did the light change, or the camera move?")
        alpha = np.clip(cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 6 * scale + 1) * 1.6, 0, 1)[..., None]
        plate = pure.copy()
        plate[:, X0:X1] = take * (1 - alpha) + pure[:, X0:X1] * alpha
        cv2.imwrite(os.path.join(out, "room_pure.png"), cv2.cvtColor(
            cv2.resize(np.clip(np.round(pure), 0, 255).astype(np.uint8), (SW, SH), interpolation=cv2.INTER_CUBIC), cv2.COLOR_RGB2BGR))
        info.update(mode="empty", empty=dict(source=path, how=how, start=a, end=b, frames=k, fit=info_fit), agree=round(agree, 3),
                    offset=[round(float(v), 2) for v in off])
    else:
        hole = count < 2
        if os.path.exists(os.path.join(out, "room_pure.png")):
            os.remove(os.path.join(out, "room_pure.png"))
        full = read_src(E.SRC, src_time(TL, times[0][0]), SW, SH, scale).copy()   # outside the crops: a frame of the take
        full[:, X0:X1] = take
        h = np.zeros((WH, WW), np.uint8)
        h[:, X0:X1] = hole.astype(np.uint8) * 255
        small = cv2.resize(full, (WW // 4, WH // 4), interpolation=cv2.INTER_AREA)
        hs = cv2.resize(h, (WW // 4, WH // 4), interpolation=cv2.INTER_NEAREST)
        fill = cv2.inpaint(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), hs, 8, cv2.INPAINT_TELEA)
        fill = cv2.cvtColor(cv2.resize(fill, (WW, WH), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
        fill = cv2.GaussianBlur(fill, (0, 0), 6)
        a_ = cv2.GaussianBlur((h > 0).astype(np.float32), (0, 0), 5)[..., None]
        plate = full * (1 - a_) + fill * a_
        print("  WARNING: no empty room (edit.py EMPTY or EMPTY_CLIP): the patch the speaker always covered is inpainted "
              "and WILL show when an effect moves them or reveals the room. Film 5 s of the empty room, or run "
              "plate_finish.py --fill <photo of the empty room, or a generated background: --bg-frame>.")
    hole_full = np.zeros((WH, WW), np.uint8)
    hole_full[:, X0:X1] = hole.astype(np.uint8) * 255
    cv2.imwrite(os.path.join(out, "hole.png"), cv2.resize(hole_full, (SW, SH), interpolation=cv2.INTER_NEAREST))
    plate = cv2.resize(np.clip(np.round(plate), 0, 255).astype(np.uint8), (SW, SH), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(os.path.join(out, "plate_src.png"), cv2.cvtColor(plate, cv2.COLOR_RGB2BGR))
    seen = np.zeros(hole.shape, bool)               # what the video shows: the crops (the margin around them is spare)
    for w, h, x, y in E.FRAMES.values():
        seen[round(y * scale):round((y + h) * scale), max(0, round(x * scale) - X0):round((x + w) * scale) - X0] = True
    info.update(hole_pct=round(float(hole[seen].mean()) * 100, 2), source=E.SRC, size=[SW, SH])
    json.dump(info, open(os.path.join(out, "plate.json"), "w"), indent=1)
    print(f"plate ({info['mode']}): the take never saw {info['hole_pct']:.1f}% of what the crops show "
          f"({'from the empty room' if emp else 'inpainted'}), {len(times)} samples -> {out}")
    print(f"next: PY {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plate_finish.py')} {P}")


if __name__ == "__main__":
    main()
