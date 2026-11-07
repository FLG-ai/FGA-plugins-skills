#!/usr/bin/env python3
"""QA a render. Nothing ships until all three pass.
  1. cuts: the last frame before and the first frame after every visual change (picture cuts, reframes, card in/out,
     end card), tiled 8 pairs per sheet into work/qa/cuts_<n>.jpg. Read them: no flash, no wrong frame, no doubled head.
  2. lip sync: for samples across every stretch where the speaker is on screen, the rendered frame is matched against
     the 4K source around the voice-synced source time. Every sample must land within 2 frames of 0 (a real slip is many frames: 0.5s is 15).
  3. loudness: -14 LUFS integrated, peak at or under -1.0 dBFS.
Plus a 720p phone copy with --phone. Run: PY pipeline/qa.py <project> renders/<file>.mp4 [--phone]
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FPS, load_edit, project_arg, q, timeline, wide  # noqa: E402
import build as B  # noqa: E402


def gray(path, t, vf, w=135, h=240):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", path, "-frames:v", "1", "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, np.uint8).reshape(h, w).astype(float)


def cut_sheets(project, render, E, TL):
    events = set(TL["picture_cuts"]) | set(TL["reframes"])
    for c in E.CARDS:
        events |= {c[2], c[3]}
    if E.END_CARD:
        events.add(E.END_IN)
    frames = sorted({round(t * FPS) for t in events if 0 < t < E.TOTAL})
    out = os.path.join(project, "work", "qa")
    os.makedirs(out, exist_ok=True)
    pngs = []
    for f in frames:
        for n in (f - 1, f):
            p = os.path.join(out, f"f{n}.png")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", render, "-vf", f"select=eq(n\\,{n}),scale={320 if wide(E) else 180}:-2",
                            "-frames:v", "1", p], check=True)
            pngs.append(p)
    sheets = []
    for r, row in enumerate([pngs[i:i + 16] for i in range(0, len(pngs), 16)]):
        ins = sum((["-i", p] for p in row), [])
        sheet = os.path.join(out, f"cuts_{r}.jpg")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *ins, "-filter_complex", f"hstack={len(row)}", sheet], check=True)
        sheets.append((sheet, frames[r * 8:(r + 1) * 8]))
    return sheets


def cam_scale(E, TL, t):
    """the #cam scale the build gives the footage at reel time t (settles, punch-ins, pushes), and whether it is moving"""
    tw = [(0.0, E.CAMERA.get("open", (1.04, 0.45))[1], E.CAMERA.get("open", (1.04, 0.45))[0], 1.0)]
    tw += [(s, 0.32, 1.045, 1.0) for s in B.settle_times(E, TL)]
    tw += [(s, 0.18, k, 1.0) for s, k in E.CAMERA.get("punch", [])]
    tw += [(a, B.T(E, b) - a, 1.0, k) for a, b, k in E.CAMERA.get("pushes", [])]
    for a, b, k in E.CAMERA.get("zooms", []):                       # lofi hard zooms: held, no motion
        tw += [(a, 1e-4, k, k), (B.T(E, b), 1e-4, 1.0, 1.0)]
    started = [w for w in tw if w[0] <= t + 1e-6]
    if not started:
        return 1.0, False
    s0, d, v0, v1 = max(started, key=lambda w: w[0])
    if t >= s0 + d:
        return v1, False
    return v0 + (v1 - v0) * ((t - s0) / d), True


def under_fx(E, t):
    """is t inside an effect that repaints the background (behind), moves the picture (cam) or covers it (over)?
    Whole-frame matching can't see the lips there; the cutout and footage copies are frame-exact anyway. Effects that
    span almost the whole video (camera-transitions) only act on the cuts, where no sample is taken."""
    for F in getattr(E, "FX", []):
        a, b = F["at"], B.T(E, F["end"])
        if F.get("layer", "top") in ("behind", "cam", "over") and b - a < 0.9 * E.TOTAL and a <= t < b:
            return True
    return False


def lip_sync(render, E, TL, span=0.6):
    """For two quiet moments in every on-camera piece, decode the rendered frame and the source frames around the
    second you hear at that moment (frame-exact seeks, the same way cut.py extracts), crop the source the way the
    camera scale frames it, and find the best match. Offset 0 = in sync. Returns [(reel t, offset, match, note)]."""
    from concurrent.futures import ThreadPoolExecutor
    keep = TL["keep"]
    jobs = []
    for p in TL["pieces"]:
        a, b = p["out_start"], min(p["out_end"], TL["total_audio"])
        if b - a < 1.0:
            continue
        cands = [t for t in np.arange(a + 0.3, b - 0.3, 1 / FPS)
                 if B.visible(E, t) and not cam_scale(E, TL, t)[1] and not under_fx(E, t)]
        if not cands:
            continue
        for t in sorted({cands[len(cands) // 3], cands[(2 * len(cands)) // 3]}):
            jobs.append((round(float(t), 3), p))
    res = []
    with ThreadPoolExecutor(8) as ex:
        for t, p in jobs:
            g = [k for k in keep if k["out"] - 1e-6 <= t][-1]
            want = g["src_in"] + (t - g["out"])                      # the source second you hear at t
            s, _ = cam_scale(E, TL, t)
            w, h, x, y = E.FRAMES[p["frame"]]
            (W, H), (ox, oy) = E.CANVAS, E.CAM_ORIGIN
            gw, gh = (240, 135) if wide(E) else (135, 240)
            cw, ch = w / s, h / s                                    # what the scaled camera shows of the crop
            cx, cy = x + (ox - ox / s) * w / W, y + (oy - oy / s) * h / H
            vf = f"crop={cw:.0f}:{ch:.0f}:{cx:.0f}:{cy:.0f},scale={gw}:{gh}"
            r = gray(render, t, f"scale={gw}:{gh}", gw, gh)
            r = (r - r.mean()) / r.std()
            offs = np.arange(-span, span + 1e-6, 1 / FPS)
            frames = list(ex.map(lambda d: gray(E.SRC, want + d, vf, gw, gh), offs))
            cs = np.array([float((r * ((f - f.mean()) / f.std())).mean()) for f in frames])
            k = int(np.argmax(cs))
            far = [c for o, c in zip(offs, cs) if abs(o - offs[k]) > 0.1]
            note = "static (inconclusive)" if far and cs[k] - max(far) < 0.004 else ""
            res.append((t, round(float(offs[k]), 3), round(float(cs[k]), 3), note))
    return res


def loudness(render):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", render, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    s = r[r.rfind("Summary"):]
    i = float([l for l in s.splitlines() if l.strip().startswith("I:")][0].split()[1])
    pk = float([l for l in s.splitlines() if l.strip().startswith("Peak:")][0].split()[1])
    return i, pk


def main():
    project = project_arg()
    render = os.path.join(project, sys.argv[2]) if not os.path.isabs(sys.argv[2]) else sys.argv[2]
    E = load_edit(project)
    TL = timeline(project)
    B.setup(E, TL)
    ok = True
    for sheet, fr in cut_sheets(project, render, E, TL):
        print("cuts:", sheet, fr)
    worst = 0.0
    for t, d, c, note in lip_sync(render, E, TL):
        flag = note or ("" if abs(d) <= 2.5 / FPS else "   <-- OUT OF SYNC")
        if not note:
            worst = max(worst, abs(d))
        print(f"sync: reel {t:6.2f}s  offset {d:+.3f}s  match {c:.3f}  {flag}")
    if worst > 2.5 / FPS:           # +-2 frames is measurement noise (grades, overlays); a real slip is many frames
        ok = False
    i, pk = loudness(render)
    print(f"loudness: {i} LUFS, peak {pk} dBFS")
    if abs(i + 14) > 0.5 or pk > -1.0:
        ok = False
        print("loudness OUT OF SPEC")
    if "--phone" in sys.argv:
        ph = os.path.splitext(render)[0] + "-phone.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", render, "-vf", f"scale={1280 if wide(E) else 720}:-2", "-c:v", "libx264", "-crf", "24",
                        "-preset", "slow", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", ph], check=True)
        print("phone copy", ph, f"{os.path.getsize(ph) / 1e6:.1f} MB")
    print("QA PASS (now read the cut sheets)" if ok else "QA FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
