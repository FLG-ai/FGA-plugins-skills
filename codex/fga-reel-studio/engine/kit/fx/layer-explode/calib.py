#!/usr/bin/env python3
"""layer-explode, step 3 of 4 (once per video): the path from the filmed rig to the final render shifts levels by a few
(the seam jumped at the cut-in on the first take). This measures it on the flat frames, where the same picture exists
three ways: the rig's own frame, the final render of the clip written with no LUT, and a render with no effect at all.
Writes work/fx/<id>/lut.npy, which prerender.py applies.

Run: PY fx/<id>/calib.py <project> [<id>] [--workers 3]
It runs the chain itself: prerender.py --passes 1 --nolut --keep, a render of the window with the clip (fxclip.py),
one without any effect, then the comparison. Then run prerender.py again (--passes 24 to ship).
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920
PAD = 0.4                     # s of the video either side of the window in the comparison renders


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
from common import KIT, PY  # noqa: E402


def frame(path, n):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select='eq(n,{n})'", "-vsync", "0", "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(b) < W * H * 3:
        sys.exit(f"{path} has no frame {n}")
    return np.frombuffer(b[:W * H * 3], np.uint8).reshape(H, W, 3).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--workers", default="3")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    total = json.load(open(os.path.join(project, "timeline.json")))["total"]
    nA, nB = fxlib.fr(float(F["at"])), fxlib.fr(float(F["end"]))
    S0, S1 = max(0, fxlib.fr(nA / FPS - PAD)) / FPS, min(fxlib.fr(total), fxlib.fr(nB / FPS + PAD)) / FPS
    env = dict(os.environ)
    subprocess.run([PY, os.path.join(HERE, "prerender.py"), project, fid, "--passes", "1", "--nolut", "--keep"], check=True, env=env)
    clips = {}
    for name, only in ((f"{fid}-cal", fid), (f"{fid}-base", "__no_effect__")):
        subprocess.run([PY, os.path.join(KIT, "pipeline", "fxclip.py"), project, name, "--only", only, "--from", f"{S0:.4f}",
                        "--to", f"{S1:.4f}", "--sheet", "0", "--workers", args.workers, "--fresh"], check=True, env=env)
        clips[name] = os.path.join(project, "work", "sandbox", name, "clips", f"{S0:.2f}-{S1:.2f}.mp4")
    fin, base = clips[f"{fid}-cal"], clips[f"{fid}-base"]
    s0 = fxlib.fr(S0)
    passes = os.path.join(project, "work", "fx", fid, "passes", "o0")
    flat = [(1, nA), (nB - nA, nB - 1)]           # the rig's first and last frames are flat: exactly the live shot
    from PIL import Image
    V, Y, Z = [[], [], []], [[], [], []], [[], [], []]
    for k, f in flat:
        v = np.asarray(Image.open(os.path.join(passes, f"frame_{k:06d}.png")).convert("RGB")).astype(np.float32)
        y, z = frame(fin, f - s0), frame(base, f - s0)
        ok = np.abs(v - z).mean(axis=2) < 25           # where the rig and the plain render agree (not the captions sheet)
        for c in range(3):
            V[c].append(v[..., c][ok])
            Y[c].append(y[..., c][ok])
            Z[c].append(z[..., c][ok])
    lut = np.zeros((256, 3), np.float32)
    xs = np.arange(256, dtype=np.float32)
    k9 = np.ones(9) / 9
    for c in range(3):
        v, y, z = np.concatenate(V[c]).astype(np.int32), np.concatenate(Y[c]), np.concatenate(Z[c])
        cnt = np.bincount(v, minlength=256)
        have = cnt > 200
        if have.sum() < 4:
            sys.exit("too few matching pixels on the flat frames to calibrate: check the rig's first and last frames")
        gy = np.interp(xs, xs[have], (np.bincount(v, y, 256) / np.maximum(cnt, 1))[have])
        gz = np.interp(xs, xs[have], (np.bincount(v, z, 256) / np.maximum(cnt, 1))[have])
        top, bot = xs[have].max(), xs[have].min()          # outside what the flat frames hold: the same offset, not a clamp
        gy[xs > top] = xs[xs > top] + (gy[int(top)] - top)
        gz[xs > top] = xs[xs > top] + (gz[int(top)] - top)
        gy[xs < bot] = xs[xs < bot] + (gy[int(bot)] - bot)
        gz[xs < bot] = xs[xs < bot] + (gz[int(bot)] - bot)
        gy = np.convolve(np.pad(gy, 4, mode="edge"), k9, "valid")
        gz = np.convolve(np.pad(gz, 4, mode="edge"), k9, "valid")
        lut[:, c] = np.interp(gz, np.maximum.accumulate(gy + xs * 1e-4), xs)    # the value to write so the final render lands on the plain one
        print("RGB"[c], {int(a): round(float(lut[int(a), c]), 1) for a in (5, 15, 25, 40, 60, 80, 100, 130, 160, 200, 240)})
    out = os.path.join(project, "work", "fx", fid, "lut.npy")
    np.save(out, lut)
    print(f"wrote {out}: now run prerender.py (--passes 24 to ship)")


if __name__ == "__main__":
    main()
