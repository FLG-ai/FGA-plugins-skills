#!/usr/bin/env python3
"""reel-cascade / playing-grid: the clips on the tiles. Your own finished videos, cut into small proxies the renderer
can seek frame by frame.

One proxy per tile: muted, 360x640 (9:16), 30 fps, all-intra (every frame a keyframe, so each seek lands exactly),
as long as the effect's window plus 0.4 s. The number of tiles comes from the effect's fx.html (t1.mp4 .. tN.mp4).

Run: PY fx/reel-cascade/mkclips.py <project> [<id>] [--from FILE[@S] ...]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/fx/<id>/fx.html (how many tiles), the files you
          pass, or <project>/public/clean.mp4 when you pass none
  writes  <project>/fx/<id>/t1.mp4 .. tN.mp4
  --from  your videos, one per tile in tile order (fewer than the tiles: they repeat). FILE@S starts that clip S
          seconds in (default 0.4: past a fade-in, onto the hook). Pick ones whose first seconds move and read small.
  without --from: PLACEHOLDERS, stretches of the project's own clean.mp4, each a different moment and framing, so
          the effect works before you have picked your videos. fx.js PLACEHOLDER labels them on the tiles: set it to
          '' once the clips are yours.
<id> defaults to this script's folder name (reel-cascade). playing-grid uses the same script:
  PY fx/reel-cascade/mkclips.py <project> playing-grid --from a.mp4 b.mp4 ...
Rerun it whenever the window gets longer.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

W, H, FPS = 360, 640, 30
LEAD = 0.4                                  # default start inside each of your videos (s)
ZOOMS = [1.0, 1.4, 1.15, 1.7, 1.25, 1.55, 1.08, 1.85]     # placeholder framings, cycling: a different crop per tile


def window(project, fid):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    for F in getattr(E, "FX", []):
        if F["id"] == fid:
            end = F["end"]
            if end == "end":
                end = json.load(open(os.path.join(project, "timeline.json")))["total"]
            return float(F["at"]), float(end)
    sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")


def tiles(project, fid):
    path = os.path.join(project, "fx", fid, "fx.html")
    if not os.path.exists(path):
        sys.exit(f"{path} is missing: copy the effect's folder into the project first")
    n = [int(x) for x in re.findall(r"fx/\{\{ID\}\}/t(\d+)\.mp4", open(path, encoding="utf-8").read())]
    if not n:
        sys.exit(f"{path} has no fx/{{{{ID}}}}/tN.mp4 clips")
    return max(n)


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def cut(src, start, length, crop, dst, crf=20):
    vf = (crop + "," if crop else "") + \
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", src, "-t", f"{length:.3f}", "-an",
                    "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-g", "1",
                    "-movflags", "+faststart", dst], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--from", dest="files", nargs="+", default=[], metavar="FILE[@S]")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    at, end = window(project, fid)
    n = tiles(project, fid)
    length = (end - at) + 0.4
    out = os.path.join(project, "fx", fid)
    if args.files:
        for k in range(n):
            spec = args.files[k % len(args.files)]
            src, _, s = spec.rpartition("@") if re.search(r"@[0-9.]+$", spec) else (spec, "", "")
            src = os.path.expanduser(src)
            if not os.path.exists(src):
                sys.exit(f"{src}: no such file")
            start = float(s) if s else LEAD
            dst = os.path.join(out, f"t{k + 1}.mp4")
            cut(src, start, length, "", dst)
            print(f"  t{k + 1}.mp4  <- {os.path.basename(src)} from {start:.2f} s")
        print(f"{n} clips in {out}: set PLACEHOLDER = '' in its fx.js")
        return
    clean = os.path.join(project, "public", "clean.mp4")
    if not os.path.exists(clean):
        sys.exit(f"{clean} is missing: run the pipeline up to the cut first, or pass your videos with --from")
    total = duration(clean)
    span = max(0.0, total - length - 0.1)
    for k in range(n):
        z = ZOOMS[k % len(ZOOMS)]
        start = span * (k + 0.5) / n                     # spread over the whole video: a different moment per tile
        crop = f"crop=iw/{z}:ih/{z}:(iw-iw/{z})/2:(ih-ih/{z})*0.3" if z != 1.0 else ""
        dst = os.path.join(out, f"t{k + 1}.mp4")
        cut(clean, start, length, crop, dst, crf=27)              # placeholders: small is fine
        print(f"  t{k + 1}.mp4  <- clean.mp4 from {start:.2f} s at {z:g}x (placeholder)")
    print(f"{n} placeholder clips in {out}: pass your own videos with --from")


if __name__ == "__main__":
    main()
