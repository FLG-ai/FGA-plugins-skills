#!/usr/bin/env python3
"""video-backdrop: the chapter backdrops, cut from your screen recording where it MOVES.

Every chapter shows movement (a scroll, a page opening, typing), never a near-still: the same idea as
video-card/energy.py. Energy is the mean change between consecutive frames (grayscale, downscaled) inside the part of
the screen that becomes the backdrop; a window holding a hard cut is skipped. It takes the N best non-overlapping
windows, keeps them in recording order (chapter 1 comes first in the recording too), and cuts each as a full-bleed
9:16 backdrop: a column of the screen (the webcam box left out: the speaker is in front), sped up so the movement
reads, 1080x1920, 30 fps, all-intra (every frame a keyframe, so every seek lands exactly). Each clip runs the whole
effect window and shows only during its chapter.

Run: PY fx/video-backdrop/mkclips.py <project> [<id>] <recording> [--col X] [--rate R] [--region x,y,w,h ...]
  reads   <project>/edit.py (the FX entry <id>: at, end), <project>/fx/<id>/fx.js (CUES: how many chapters)
  writes  <project>/fx/<id>/w1.mp4 .. wN.mp4, and prints the <video> tags: paste each over its chapter's
          placeholder block in fx.html (between the two comments), then set PLACEHOLDER = '' in fx.js
  --col X      the column's centre as a fraction of the recording's width (default 0.5); the column is as wide as
               9:16 of the recording's height
  --rate R     speed-up (default 1.5; 1.5-2.5 makes screen movement read)
  --region     where movement counts, x,y,w,h as fractions of the frame (default: the column); several regions:
               a window counts only as much as its stillest one
  --keep-cuts  don't skip windows with a hard cut (a page switch can look like one)
<id> defaults to this script's folder name. Rerun it when the window or the chapters change.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np

FPS = 30


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


def chapters(project, fid):
    path = os.path.join(project, "fx", fid, "fx.js")
    m = re.search(r"var CUES = \[([^\]]*)\]", open(path, encoding="utf-8").read()) if os.path.exists(path) else None
    if not m:
        sys.exit(f"{path}: no CUES constant (copy the effect's folder into the project first)")
    return min(4, len(re.findall(r"'[^']*'|\"[^\"]*\"", m.group(1))))


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    return int(s["width"]), int(s["height"])


def energy(path, regions, w0, h0):
    """per frame: the change inside each region (fractions of the frame), and over the whole frame (for cuts);
    sampled at 30 fps so indexes are frames"""
    W = 192
    H = max(2, round(W * h0 / w0 / 2) * 2)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf", f"fps={FPS},scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    boxes = [(int(x * W), int(y * H), max(1, int(w * W)), max(1, int(h * H))) for x, y, w, h in regions]
    prev, per, whole = None, [], []
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H:
            break
        f = np.frombuffer(b, np.uint8).astype(np.int16).reshape(H, W)
        if prev is None:
            per.append([0.0] * len(boxes))
            whole.append(0.0)
        else:
            d = np.abs(f - prev)
            per.append([float(d[y:y + h, x:x + w].mean()) for x, y, w, h in boxes])
            whole.append(float(d.mean()))
        prev = f
    p.wait()
    return np.array(per), np.array(whole)


def best(per, whole, n, top, keep_cuts):
    """the `top` best non-overlapping windows of n frames, most movement first (a cut = a one-frame spike)"""
    cut = np.zeros(len(whole), bool)
    if not keep_cuts:
        for i in range(1, len(whole)):
            side = [whole[max(1, i - 5):i], whole[i + 1:i + 6]]
            local = max([float(np.median(s)) for s in side if len(s)] or [0.0])
            cut[i] = whole[i] > max(4.0, 5.0 * local)
    cum = np.vstack([np.zeros(per.shape[1]), np.cumsum(per, axis=0)])
    cuts = np.concatenate([[0], np.cumsum(cut)])
    scored = [(float(((cum[s + n] - cum[s + 1]) / max(1, n - 1)).min()), s)
              for s in range(0, len(per) - n + 1) if cuts[s + n] - cuts[s + 1] == 0]
    scored.sort(reverse=True)
    picked = []
    for score, s in scored:
        if all(abs(s - t) >= n + FPS // 2 for _, t in picked):
            picked.append((score, s))
        if len(picked) == top:
            break
    return picked


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("rest", nargs="+", metavar="[id] recording")
    ap.add_argument("--col", type=float, default=0.5)
    ap.add_argument("--rate", type=float, default=1.5)
    ap.add_argument("--region", action="append", default=[])
    ap.add_argument("--keep-cuts", action="store_true")
    args = ap.parse_args()
    project = os.path.abspath(os.path.expanduser(args.project))
    fid = args.rest[0] if len(args.rest) > 1 else os.path.basename(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.expanduser(args.rest[-1])
    if not os.path.exists(src):
        sys.exit(f"{src}: no such file")
    at, end = window(project, fid)
    n_ch = chapters(project, fid)
    w0, h0 = probe(src)
    cw = min(w0, round(h0 * 9 / 16))                                   # the 9:16 column of the screen
    cx = int(min(max(0, args.col * w0 - cw / 2), w0 - cw))
    regions = [[float(v) for v in r.split(",")] for r in args.region] or [[cx / w0, 0.0, cw / w0, 1.0]]
    out_len = (end - at) + 0.2                                         # each clip runs the whole window
    n = max(2, round(out_len * args.rate * FPS))                       # source frames per clip
    per, whole = energy(src, regions, w0, h0)
    picked = best(per, whole, n, n_ch, args.keep_cuts)
    if len(picked) < n_ch:
        sys.exit(f"only {len(picked)} moving windows of {n / FPS:.2f} s without a cut: use --keep-cuts or a lower --rate")
    picked.sort(key=lambda p: p[1])                                    # chapters in recording order
    dst = os.path.join(project, "fx", fid)
    print(f"{src}: {len(per)} frames, column {cw}x{h0} at x {cx}, {n_ch} chapters of {n / FPS:.2f} s at {args.rate:g}x")
    for k, (score, s) in enumerate(picked):
        out = os.path.join(dst, f"w{k + 1}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s / FPS:.3f}", "-i", src, "-t", f"{n / FPS + 0.1:.3f}", "-an",
                        "-vf", f"crop={cw}:{h0}:{cx}:0,setpts=PTS/{args.rate},fps={FPS},scale=1080:1920:flags=lanczos,format=yuv420p",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-g", "1", "-movflags", "+faststart", out], check=True)
        print(f"  w{k + 1}.mp4  <- {s / FPS:8.2f} s  energy {score:.2f}")
    print("\n<video> tags: paste each over its chapter's placeholder block in fx.html, then set PLACEHOLDER = '':")
    for k in range(n_ch):
        print(f'  chapter {k + 1}:\n    <video id="{{{{ID}}}}-v{k + 1}" class="{{{{ID}}}}-v {{{{ID}}}}-m" src="fx/{{{{ID}}}}/w{k + 1}.mp4" '
              f'muted playsinline data-start="{{{{START}}}}" data-media-start="0" data-duration="{{{{DUR}}}}" '
              f'data-track-index="{{{{T{k}}}}}"></video>')


if __name__ == "__main__":
    main()
