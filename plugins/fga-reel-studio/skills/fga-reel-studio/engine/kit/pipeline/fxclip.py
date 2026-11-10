#!/usr/bin/env python3
"""FX clip: render just a slice of the video with only the FX you name, in real motion and through the real renderer,
with sound. A full render is minutes; this is seconds, so an effect can be judged moving, not from stills. Several
can run at once.

Run: PY pipeline/fxclip.py <project> <name> --only id1,id2 --from S --to S [--workers 3] [--sheet 12] [--fresh]
  <name> is the fxsandbox name: edit <project>/work/sandbox/<name>/edit.py to try camera or cutout changes (--fresh
  recopies it from the project).
-> <project>/work/sandbox/<name>/clips/<S>-<E>.mp4 and .jpg (a contact sheet of --sheet frames, each labelled with its
   time). The sound is public/master.wav (else assets/voice.wav).
Colour in these clips is the final colour. Snapshots show live footage about 8 levels darker than a render does, so
judge seams here.
"""
import math
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KIT, PY, hf  # noqa: E402

FPS = 30


def arg(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


def slice_html(html, S, E):
    """cut the composition to S..E: media tags are re-timed or dropped, the master timeline is scrubbed from S to E"""
    def one(m):
        tag = m.group(0)
        st = re.search(r'data-start="([-\d.]+)"', tag)
        du = re.search(r'data-duration="([-\d.]+)"', tag)
        if not st or not du:
            return tag
        ms = re.search(r'data-media-start="([-\d.]+)"', tag)
        a, d = float(st.group(1)), float(du.group(1))
        b = a + d
        if b <= S or a >= E:
            return ""                       # a media tag with no src stalls the render 45s waiting on it
        new_a = max(a, S)
        new_ms = (float(ms.group(1)) if ms else 0.0) + (new_a - a)
        new_d = min(b, E) - new_a
        tag = re.sub(r'data-start="[^"]*"', f'data-start="{max(0.0, new_a - S):.4f}"', tag)
        tag = re.sub(r'data-duration="[^"]*"', f'data-duration="{new_d:.4f}"', tag)
        if ms:
            tag = re.sub(r'data-media-start="[^"]*"', f'data-media-start="{new_ms:.4f}"', tag)
        else:
            tag = tag.replace("data-start=", f'data-media-start="{new_ms:.4f}" data-start=', 1)
        return tag
    html = re.sub(r"<(?:video|audio)\b[^>]*>(?:</(?:video|audio)>)?", one, html)
    html = re.sub(r'(<div id="root"[^>]*data-duration=")[^"]*"', lambda m: f'{m.group(1)}{E - S:.4f}"', html)
    html = html.replace("window.__timelines['main'] = tl;",
                        f"var __sub = gsap.timeline({{ paused: true }}); tl.pause(0); __sub.add(tl.tweenFromTo({S:.4f}, {E:.4f}, {{ ease: 'none', duration: {E - S:.4f} }}), 0); "
                        f"window.__timelines = window.__timelines || {{}}; window.__timelines['main'] = __sub;")
    return html


def contact(mp4, out, S, E, sheet):
    from PIL import Image, ImageDraw
    n = round((E - S) * FPS)
    pick = sorted({min(n - 1, round(i * (n - 1) / max(1, sheet - 1))) for i in range(sheet)})
    W, H, cols = 300, 533, min(6, len(pick))
    rows = math.ceil(len(pick) / cols)
    im = Image.new("RGB", (cols * W, rows * H), (12, 12, 12))
    d = ImageDraw.Draw(im)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    for k, f in enumerate(pick):
        fr = raw[f * W * H * 3:(f + 1) * W * H * 3]
        if len(fr) < W * H * 3:
            continue
        x, y = (k % cols) * W, (k // cols) * H
        im.paste(Image.frombytes("RGB", (W, H), fr), (x, y))
        d.rectangle([x, y, x + 66, y + 16], fill=(0, 0, 0))
        d.text((x + 4, y + 2), f"{S + f / FPS:.2f}", fill=(255, 255, 255))
    im.save(out, quality=88)


def main():
    a = sys.argv[1:]
    if len(a) < 2 or "--from" not in a or "--to" not in a:
        sys.exit(__doc__)
    project, name = os.path.abspath(os.path.expanduser(a[0])), a[1]
    only = arg(a, "--only", "")
    S, E = round(float(arg(a, "--from")) * FPS) / FPS, round(float(arg(a, "--to")) * FPS) / FPS
    workers = arg(a, "--workers", "3")
    sheet = int(arg(a, "--sheet", "12"))
    cmd = [PY, os.path.join(KIT, "pipeline", "fxsandbox.py"), project, name, "--only", only] + (["--fresh"] if "--fresh" in a else [])
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    sb = os.path.join(project, "work", "sandbox", name)
    pub = os.path.join(sb, "public")
    clip = os.path.join(sb, "clip")
    shutil.rmtree(clip, ignore_errors=True)
    os.makedirs(clip)
    for f in os.listdir(pub):
        if f in ("index.html", "snapshots"):
            continue
        os.symlink(os.path.realpath(os.path.join(pub, f)), os.path.join(clip, f))
    html = open(os.path.join(pub, "index.html"), encoding="utf-8").read()
    open(os.path.join(clip, "index.html"), "w", encoding="utf-8").write(slice_html(html, S, E))
    outdir = os.path.join(sb, "clips")
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, f"{S:.2f}-{E:.2f}")
    silent = base + ".silent.mp4"
    hf(["render", "-q", "looks", "--quiet", "-w", str(workers), "-o", silent], clip)
    if not os.path.exists(silent):
        sys.exit("render failed: no clip came out")
    mp4 = base + ".mp4"
    sound = next((p for p in (os.path.join(project, "public", "master.wav"), os.path.join(project, "assets", "voice.wav"))
                  if os.path.exists(p)), None)
    if sound:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-ss", f"{S:.4f}", "-t", f"{E - S:.4f}", "-i", sound,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", mp4], check=True)
        os.remove(silent)
    else:
        os.replace(silent, mp4)
    if sheet:
        contact(mp4, base + ".jpg", S, E, sheet)
    print(mp4)
    if sheet:
        print(base + ".jpg")


if __name__ == "__main__":
    main()
