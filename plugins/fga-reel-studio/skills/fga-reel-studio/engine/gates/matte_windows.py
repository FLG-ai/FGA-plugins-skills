#!/usr/bin/env python3
"""The speaker cutout only where something sits behind the head (edit.CUT_WINDOWS), at full length.

matte.py runs about 1 frame a second on a laptop, so a whole video can take half an hour. The build only shows
subject.webm inside CUT_WINDOWS, so: matte each window (plus 4 frames either side), lay the pieces on a fully
transparent canvas at their own frames, and write one subject.webm with exactly the frames of aroll.mp4.
Run (through the lock): run/heavy.sh "$PY" matte_windows.py <project>
"""
import os
import subprocess
import sys

KIT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kit"))
sys.path.insert(0, os.path.join(KIT, "pipeline"))
from common import PY, load_edit  # noqa: E402

FPS = 30
PAD = 4


def frames(f):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip())


def main():
    project = os.path.abspath(os.path.expanduser(sys.argv[1]))
    E = load_edit(project)
    aroll = os.path.join(project, "assets", "aroll.mp4")
    N = frames(aroll)
    wins = []
    for a, b in E.CUT_WINDOWS:
        b = N / FPS if b == "end" else b
        fa, fb = max(0, round(a * FPS) - PAD), min(N, round(b * FPS) + PAD)
        wins.append((fa, fb))
    wins.sort()
    merged = []
    for fa, fb in wins:
        if merged and fa <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(fb, merged[-1][1]))
        else:
            merged.append((fa, fb))
    parts = []
    for k, (fa, fb) in enumerate(merged):
        # cached per window AND per cut (a recut that reused the old cut's mattes put the lips in the cutout
        # out of step with the voice): the name carries the window's frames and aroll.mp4's mtime
        stamp = int(os.path.getmtime(aroll))
        out = os.path.join("work", f"matte_w{k}_{fa}-{fb}_{stamp}.webm")
        if not os.path.exists(os.path.join(project, out)):
            subprocess.run([PY, os.path.join(KIT, "pipeline", "matte.py"), project, "--from", f"{fa / FPS:.4f}",
                            "--to", f"{fb / FPS:.4f}", "--out", out], check=True)
        parts.append((fa, os.path.join(project, out)))
        print(f"window {k}: frames {fa}-{fb}", flush=True)
    ins = ["-f", "lavfi", "-i", f"color=c=black@0.0:s=1080x1920:r={FPS},format=yuva420p"]
    fc, last = "", "0:v"
    for k, (fa, path) in enumerate(parts):
        ins += ["-c:v", "libvpx-vp9", "-i", path]
        fc += f"[{k + 1}:v]format=yuva420p,setpts=PTS-STARTPTS+{fa}/({FPS}*TB)[p{k}];"
        fc += f"[{last}][p{k}]overlay=eof_action=pass:format=auto[o{k}];"
        last = f"o{k}"
    fc += f"[{last}]format=yuva420p[out]"
    dst = os.path.join(project, "assets", "subject.webm")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[out]", "-frames:v", str(N),
                    "-r", str(FPS), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "18",
                    "-row-mt", "1", "-deadline", "good", "-cpu-used", "5", "-auto-alt-ref", "0", dst], check=True)
    got = frames(dst)
    print(f"aroll frames {N} / cutout frames {got}")
    if got != N:
        sys.exit("FRAME MISMATCH")
    import shutil
    shutil.copy(dst, os.path.join(project, "public", "subject.webm"))
    print("subject.webm ready")


if __name__ == "__main__":
    main()
