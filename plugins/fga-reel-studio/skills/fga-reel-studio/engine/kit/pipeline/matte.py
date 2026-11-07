#!/usr/bin/env python3
"""Matte (optional upgrade): the speaker cut out with Robust Video Matting (temporal, soft alpha)
-> <project>/assets/subject.webm (VP9 + alpha) and public/. Smoother edges than cutout.py (which segments every frame
on its own and can shimmer at hair edges), worth it for lo-fi videos where things sit behind the speaker a lot.
Needs PyTorch: `python3 setup/setup.py --matte` installs it. The model is GPL-3.0 and is downloaded on first use,
never committed to this repo.

The alpha comes from RVM; the colour is the a-roll's own pixels, so the cutout matches the footage underneath.
Model: $REEL_KIT_HOME/models/rvm_resnet50_fp32.torchscript (github.com/PeterL1n/RobustVideoMatting, release v1.0.0).
Run: PY pipeline/matte.py <project> [--from S --to S --out work/x.webm]   (a range is for tests)
"""
import os
import subprocess
import sys
import time

import numpy as np

try:
    import torch
except ImportError:
    sys.exit("matte.py needs PyTorch: run `python3 setup/setup.py --matte`, or use pipeline/cutout.py instead")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FPS, KIT, MODELS, project_arg  # noqa: E402

MODEL = os.path.join(MODELS, "rvm_resnet50_fp32.torchscript")
MODEL_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.torchscript"


def ensure_model():
    if not os.path.exists(MODEL):
        import urllib.request
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        print("downloading the RVM model (GPL-3.0, ~100 MB) once ...", flush=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
W, H = 1080, 1920
DOWNSAMPLE = 0.4          # RVM's internal resolution for a 1080x1920 portrait: detail at the hair and cap brim


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def frames(project):
    return subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                           "stream=nb_read_frames", "-of", "csv=p=0", os.path.join(project, *project_out(project))],
                          capture_output=True, text=True).stdout.strip()


def project_out(project):
    return arg("--out", "assets/subject.webm").split("/")


def main():
    project = project_arg()
    t0 = time.time()
    src = os.path.join(project, "assets", "aroll.mp4")
    out = os.path.join(project, *project_out(project))
    a, b = arg("--from"), arg("--to")
    trim = (["-ss", a] if a else []) + (["-to", b] if b else [])
    dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    ensure_model()
    model = torch.jit.load(MODEL, map_location=dev).eval()
    dec = subprocess.Popen(["ffmpeg", "-v", "error", *trim, "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0",
                            "-crf", "18", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-auto-alt-ref", "0",
                            out], stdin=subprocess.PIPE)
    rec, n = [None] * 4, 0
    with torch.no_grad():
        while True:
            buf = dec.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break
            rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            x = torch.from_numpy(rgb).to(dev).permute(2, 0, 1)[None].float() / 255
            _, pha, *rec = model(x, *rec, DOWNSAMPLE)
            alpha = (pha[0, 0].clamp(0, 1) * 255).round().byte().cpu().numpy()
            enc.stdin.write(np.dstack([rgb, alpha]).tobytes())
            n += 1
            if n % 150 == 0:
                print(f"  {n} frames  {n / (time.time() - t0):.1f} fps", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print(f"matte: {n} frames in {time.time() - t0:.0f}s -> {out}")
    if not a and not b:
        import shutil
        shutil.copy(out, os.path.join(project, "public", "subject.webm"))
        print(f"aroll frames {n} / matte frames {frames(project)}")


if __name__ == "__main__":
    main()
