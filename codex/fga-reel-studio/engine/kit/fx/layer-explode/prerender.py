#!/usr/bin/env python3
"""layer-explode, step 4 of 4: film the live rig the way a camera would. N sub-frame passes through the real renderer
inside a 180 degree shutter, blended in linear light, written as one all-intra clip, through the calibration LUT
(calib.py) so it lands on the live footage's levels after the final render. Then writes fx/<id>/fx.html + fx.js.
Why not leave it live: real motion blur on the camera move, and the final render only has to play a clip. The speaker
stays in sync: the passes offset GSAP only, every <video> stays on its frame.

Run: PY fx/<id>/prerender.py <project> [<id>] [--passes 24] [--nolut] [--conc 3] [--workers 5] [--crf 11] [--keep]
A pass is about 20 s. Use --passes 8 to review, 24 to ship: at the peak of the swing the frame moves about 140 px a
frame, and fewer passes strobe. --keep leaves the pass frames in work/fx/<id>/passes (calib.py needs them).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
SHUTTER, GAMMA = 0.5, 2.2


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
from common import HF, KIT, PY  # noqa: E402
from fxclip import slice_html  # noqa: E402


def window(project, fid):
    F = fxlib.entry(project, fid)
    return fxlib.fr(float(F["at"])) / FPS, fxlib.fr(float(F["end"])) / FPS          # frame-exact


def stage_sandbox(project, fid):
    """a sandbox whose fx/ is the stage, built with only this effect: its public/index.html is the live rig"""
    stage = os.path.join(project, "work", "fx", fid, "stage")
    if not os.path.exists(os.path.join(stage, fid, "fx.js")):
        sys.exit(f"no rig in {stage}/{fid}: run layers.py and gen.py first")
    sb = os.path.join(project, "work", "sandbox", f"{fid}-stage")
    os.makedirs(sb, exist_ok=True)
    link = os.path.join(sb, "fx")
    if os.path.islink(link) and os.path.realpath(link) != os.path.realpath(stage):
        os.remove(link)
    if not os.path.lexists(link):
        os.symlink(stage, link)                 # before fxsandbox.py runs, so it keeps this fx/ instead of the project's
    subprocess.run([PY, os.path.join(KIT, "pipeline", "fxsandbox.py"), project, f"{fid}-stage", "--only", fid, "--fresh"],
                   check=True, stdout=subprocess.DEVNULL)
    return sb


def render_passes(project, fid, S, E, n, conc, workers, out_root):
    sb = stage_sandbox(project, fid)
    pub = os.path.join(sb, "public")
    sliced = slice_html(open(os.path.join(pub, "index.html"), encoding="utf-8").read(), S, E)
    sliced = re.sub(r'<video\b[^>]*data-dropped="1"[^>]*></video>', "", sliced)    # a dropped tag with no src stalls the renderer 45 s
    if not re.search(r"tl\.tweenFromTo\(\s*[-\d.]+\s*,\s*[-\d.]+", sliced) or "var PASS = 0 /*__PASS__*/;" not in sliced:
        sys.exit("the sliced page has no tl.tweenFromTo(...) or no PASS marker: fxclip.slice_html or rig_js.py changed")
    shutil.rmtree(out_root, ignore_errors=True)
    os.makedirs(out_root)
    t0, running, tries = time.time(), [], {}

    def start(k):
        d = os.path.join(out_root, f"p{k}")
        return subprocess.Popen(HF + ["render", "--format", "png-sequence", "--quiet", "-w", str(workers), "-o", os.path.join(out_root, f"o{k}")],
                                cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def reap(block):
        while running and (block or len(running) >= conc):
            for item in list(running):
                k, p = item
                if p.poll() is None:
                    continue
                running.remove(item)
                if p.returncode != 0:              # a busy machine can lose a pass's browser: run it again
                    tries[k] = tries.get(k, 0) + 1
                    if tries[k] > 2:
                        sys.exit(f"pass {k} failed three times")
                    print(f"pass {k} failed, running it again", flush=True)
                    shutil.rmtree(os.path.join(out_root, f"o{k}"), ignore_errors=True)
                    running.append((k, start(k)))
                    continue
                print(f"pass {k} {time.time() - t0:.0f}s", flush=True)
            time.sleep(0.5)
    for k in range(n):
        o = k * SHUTTER / FPS / n
        d = os.path.join(out_root, f"p{k}")
        os.makedirs(d)
        for f in os.listdir(pub):
            if f not in ("index.html", "snapshots"):
                os.symlink(os.path.realpath(os.path.join(pub, f)), os.path.join(d, f))
        h = re.sub(r"tl\.tweenFromTo\(\s*([-\d.]+)\s*,\s*([-\d.]+)", lambda m: f"tl.tweenFromTo({float(m.group(1)) + o:.5f}, {float(m.group(2)) + o:.5f}", sliced, count=1)
        h = h.replace("var PASS = 0 /*__PASS__*/;", f"var PASS = {o:.6f};")
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(h)
        reap(False)
        running.append((k, start(k)))
    reap(True)
    return sorted(f for f in os.listdir(os.path.join(out_root, "o0")) if f.endswith(".png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--passes", type=int, default=8)
    ap.add_argument("--conc", type=int, default=3)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--crf", type=int, default=11)
    ap.add_argument("--nolut", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    S, E = window(project, fid)
    work = os.path.join(project, "work", "fx", fid)
    passes = os.path.join(work, "passes")
    t0 = time.time()
    files = render_passes(project, fid, S, E, args.passes, args.conc, args.workers, passes)
    from PIL import Image
    out_dir = os.path.join(project, "fx", fid)
    os.makedirs(out_dir, exist_ok=True)
    w = fxlib.Writer(os.path.join(out_dir, f"{fid}.mp4"), crf=args.crf)
    lin = (np.arange(256, dtype=np.float32) / 255) ** GAMMA
    lutf = os.path.join(work, "lut.npy")
    LUT = np.load(lutf) if os.path.exists(lutf) and not args.nolut else None
    if LUT is None and not args.nolut:
        print("no calibration LUT yet (calib.py): the clip may land a few levels off the live footage at the cut-in")
    xs = np.arange(256, dtype=np.float32)
    for name in files:
        acc = None
        for k in range(args.passes):
            a = np.asarray(Image.open(os.path.join(passes, f"o{k}", name)).convert("RGB"))
            acc = lin[a] if acc is None else acc + lin[a]
        v = (acc / args.passes) ** (1 / GAMMA) * 255
        if LUT is not None:
            v = np.dstack([np.interp(v[..., c].ravel(), xs, LUT[:, c]).reshape(v.shape[:2]) for c in range(3)])
        w.write(np.clip(v + 0.5, 0, 255).astype(np.uint8))
    w.close()
    st = "position:absolute;left:0;top:0;width:1080px;height:1920px;"
    with open(os.path.join(out_dir, "fx.html"), "w") as fh:
        fh.write(f"<!-- {fid} [layer-explode] (cam): the rig filmed by prerender.py for {S:.3f}-{E:.3f}; it carries the live grade already. -->\n"
                 + fxlib.tag(f"{fid}-film", f"fx/{fid}/{fid}.mp4", S, E, "", "{{T0}}", st) + "\n")
    with open(os.path.join(out_dir, "fx.js"), "w") as fh:
        fh.write("// layer-explode: filmed from its live rig (gen.py + prerender.py). The build shows this layer from A to B.\n")
    if not args.keep:
        shutil.rmtree(passes, ignore_errors=True)
    print(f"wrote {out_dir}/{fid}.mp4: {len(files)} frames, {args.passes} passes, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
