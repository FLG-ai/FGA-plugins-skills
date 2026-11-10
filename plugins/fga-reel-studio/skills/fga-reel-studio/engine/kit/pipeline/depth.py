#!/usr/bin/env python3
"""Depth: Depth Anything V2 (small, ONNX, runs locally) on any image or a window of the footage. Output is 16-bit PNG,
near = bright.
Run: PY pipeline/depth.py <project> --image in.jpg out.png
     PY pipeline/depth.py <project> --from S --to S --out work/depth/name     (one PNG per video frame: f00123.png)
In code: depth.infer(rgb[, side]) -> float32 HxW 0..1, near = 1 (relative depth, normalised per image); side is the
longer side the model sees (518 by default; more is sharper and slower).
REEL_KIT_DEPTH_CPU=1 runs it on the CPU only: on a Mac, several depth jobs at once queue on the neural engine.
Model: $REEL_KIT_HOME/models/depth_anything_v2_small.onnx (Apache-2.0, 99 MB), downloaded and checked against its
sha256 the first time anything asks for depth (pipeline/models.py).
"""
import os
import sys

import cv2
import numpy as np
import onnxruntime as ort

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402

_S = None
SIZE = 518
MEAN, STD = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)


def session():
    global _S
    if _S is None:
        # Apple's neural engine where there is one. REEL_KIT_DEPTH_CPU=1 skips it: several depth jobs at once queue on
        # it for minutes, the CPU doesn't
        want = (["CPUExecutionProvider"] if os.environ.get("REEL_KIT_DEPTH_CPU") == "1"
                else ["CoreMLExecutionProvider", "CPUExecutionProvider"])
        have = ort.get_available_providers()
        if hasattr(ort, "disable_telemetry_events"):                  # its shutdown once hung a run for minutes at exit
            ort.disable_telemetry_events()
        _S = ort.InferenceSession(models.path(models.DEPTH_MODEL), providers=[p for p in want if p in have] or have)
    return _S


def infer(rgb, side=SIZE):
    """rgb uint8 HxWx3 -> float32 HxW in 0..1, near = 1. Longer input side is about `side` (multiples of 14)."""
    H, W = rgb.shape[:2]
    k = side / max(H, W)
    h, w = max(14, round(H * k / 14) * 14), max(14, round(W * k / 14) * 14)
    x = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None]
    S = session()
    d = S.run(None, {S.get_inputs()[0].name: x})[0].squeeze()
    d = (d - d.min()) / max(1e-6, d.max() - d.min())
    return cv2.resize(d.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)


def main():
    import fxlib
    from common import project_arg
    P = project_arg()
    a = sys.argv
    if "--image" in a:
        i = a.index("--image")
        rgb = cv2.cvtColor(cv2.imread(a[i + 1]), cv2.COLOR_BGR2RGB)
        cv2.imwrite(a[i + 2], (np.clip(infer(rgb), 0, 1) * 65535).astype(np.uint16))
        print(a[i + 2])
        return
    if not all(f in a for f in ("--from", "--to", "--out")):
        sys.exit(__doc__)
    A, B = float(a[a.index("--from") + 1]), float(a[a.index("--to") + 1])
    out = os.path.join(P, a[a.index("--out") + 1])
    os.makedirs(out, exist_ok=True)
    prev = None
    for i, rgb in fxlib.frames(P, A, B):
        d = infer(rgb)
        prev = d if prev is None else 0.6 * d + 0.4 * prev          # a little temporal smoothing: the model flickers
        cv2.imwrite(os.path.join(out, f"f{i:05d}.png"), (np.clip(prev, 0, 1) * 65535).astype(np.uint16))
    print(f"depth: {B - A:.2f}s -> {out}")


if __name__ == "__main__":
    main()
