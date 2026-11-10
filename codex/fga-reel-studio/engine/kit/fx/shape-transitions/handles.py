#!/usr/bin/env python3
"""shape-transitions: cut the pre-roll handles and write fx.html.

A shape transition shows the INCOMING shot in the frames before its picture cut. Every join in the kit is a J-cut
(the next line's audio leads its picture by J_LEAD, 0.3 s = 9 frames), so the incoming shot's own source frames from
just before its piece are in sync with the audio already playing under them: no frozen frames, no lip-sync cost.
This cuts those frames (the handle) for every cut that gets a transition, from edit.SRC exactly like
pipeline/cut.py cuts the pieces (the piece's FRAMES crop, scaled to CANVAS with lanczos, 30 fps CFR, a third of a
frame early so it lands on the frame), checks the handle's last frame against public/clean.mp4 on the cut, and
writes fx.html: one group per cut with its handle, its shape (SHAPES in fx.js, cycling), and the synced copies of
clean.mp4 the outgoing side needs (barn doors, match push).

Which cuts: ONLY in fx.js, or by default every picture cut inside the window except one in SKIP or one a full-frame
effect covers (another cam / over FX starting on it, or running over its transition frames), as camera-transitions
decides. A join whose lead is shorter than 4 frames gets no transition.

Run: PY fx/<id>/handles.py <project> [<id>]
  reads   <project>/edit.py (SRC, FRAMES, CANVAS, FX), timeline.json (pieces, keep, picture_cuts), fx/<id>/fx.js
          (SHAPES, ONLY, SKIP, FRAMES_PER), public/clean.mp4 (the check)
  writes  <project>/fx/<id>/h<cut*100>.mp4 (one per cut) and fx/<id>/fx.html; removes stale handles
<id> defaults to this script's folder name. Rerun it whenever KEEP, SHOTS or the FX list changes.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
MIN_FRAMES = 4


def load_edit(project):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    return E


def js_const(js, name, default):
    """a constant from fx.js: var NAME = <JSON-ish literal>;"""
    m = re.search(r"^var " + name + r" = (.+?);", js, re.M)
    if not m:
        return default
    return json.loads(m.group(1).replace("'", '"'))


def frame(path, n, w, h):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select=eq(n\\,{n})", "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32) if len(raw) == w * h * 3 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    TL = json.load(open(os.path.join(project, "timeline.json")))
    F = next((F for F in getattr(E, "FX", []) if F["id"] == fid), None)
    if not F:
        sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")
    A = float(F["at"])
    B = TL["total"] if F["end"] == "end" else float(F["end"])
    d = os.path.join(project, "fx", fid)
    os.makedirs(d, exist_ok=True)
    js = open(os.path.join(d, "fx.js") if os.path.exists(os.path.join(d, "fx.js")) else os.path.join(HERE, "fx.js"),
              encoding="utf-8").read()
    SHAPES = js_const(js, "SHAPES", ["iris", "blinds", "doors", "push", "clock"])
    ONLY, SKIP = js_const(js, "ONLY", []), js_const(js, "SKIP", [])
    PER = int(js_const(js, "FRAMES_PER", 9))
    W, H = getattr(E, "CANVAS", (1080, 1920))
    others = [(G, float(G["at"]), TL["total"] if G["end"] == "end" else float(G["end"]))
              for G in getattr(E, "FX", []) if G["id"] != fid and G.get("layer", "top") in ("cam", "over")]

    cuts = []
    for c in TL["picture_cuts"]:
        if not (A < c < B):
            continue
        if ONLY and not any(abs(c - t) < 0.05 for t in ONLY):
            continue
        if any(abs(c - t) < 0.1 for t in SKIP):
            continue
        keep = next((k for k in TL["keep"] if abs(k["picture_out"] - c) < 0.002), None)
        lead = round(((keep["picture_out"] - keep["out"]) if keep else 0) * FPS)
        n = min(PER, lead)
        cover = next((G["id"] for G, a, b in others if abs(a - c) < 0.1 or (a < c and b > c - n / FPS)), None)
        if cover:
            print(f"cut {c:.3f}: {cover} covers it, no transition")
            continue
        if n < MIN_FRAMES:
            print(f"cut {c:.3f}: the J-cut lead is {lead} frames (under {MIN_FRAMES}), no transition")
            continue
        if c - n / FPS < A:
            print(f"cut {c:.3f}: its transition would start before the effect, no transition")
            continue
        cuts.append((c, n))

    groups, keepfiles = [], set()
    for k, (c, n) in enumerate(cuts):
        shape = SHAPES[k % len(SHAPES)]
        C = round(c * FPS)
        piece = next(p for p in TL["pieces"] if abs(p["out_start"] - c) < 0.002)
        w, h, x, y = E.FRAMES[piece["frame"]]
        name = f"h{round(c * 100)}.mp4"
        out = os.path.join(d, name)
        keepfiles.add(name)
        s = piece["src"] - n / FPS                       # handle frame 0 = n frames before the piece, frame n = the cut
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s - 0.3 / FPS:.4f}", "-i", E.SRC, "-an",
                        "-vf", f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1",
                        "-frames:v", str(n + 2), "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-g", "1",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
        a, b = frame(out, n, W, H), frame(os.path.join(project, "public", "clean.mp4"), C, W, H)
        diff = float(np.abs(a - b).mean()) if a is not None and b is not None else float("nan")
        print(f"cut {c:.3f}: {shape:<6} {n} frames from source {s:.3f} ({piece['frame']}) -> {name}; "
              f"its frame {n} vs clean.mp4 on the cut: mean diff {diff:.2f}{'  CHECK THIS' if not diff < 3 else ''}")

        x0 = (C - n) / FPS - A                           # the transition's first frame, s after A
        dur = n / FPS
        tag = f'data-cut="{c:.4f}" data-shape="{shape}" data-n="{n}"'
        hv = (f'<video id="{{{{ID}}}}-h{k}" class="{{{{ID}}}}-v g" src="fx/{{{{ID}}}}/{name}" muted playsinline '
              f'data-start="{{{{START+{x0:.4f}}}}}" data-media-start="0.001" data-duration="{dur:.4f}" '
              f'data-track-index="{{{{T{(3 * k) % 10}}}}}"></video>')

        def copy(j, lag=0):                              # a synced copy of the outgoing picture (lag: frames earlier)
            t = x0 - lag / FPS
            return (f'<video id="{{{{ID}}}}-o{k}{j}" class="{{{{ID}}}}-v g" src="clean.mp4" muted playsinline '
                    f'data-start="{{{{START+{t:.4f}}}}}" data-media-start="{{{{SYNC+{t:.4f}}}}}" '
                    f'data-duration="{(n + lag) / FPS:.4f}" data-track-index="{{{{T{(3 * k + 1 + j) % 10}}}}}"></video>')
        if shape == "doors":
            body = (f'{hv}<div id="{{{{ID}}}}-dl{k}" class="{{{{ID}}}}-door {{{{ID}}}}-dl">{copy(0)}'
                    f'<div class="{{{{ID}}}}-shade"></div></div>'
                    f'<div id="{{{{ID}}}}-dr{k}" class="{{{{ID}}}}-door {{{{ID}}}}-dr">{copy(1, 1 if x0 >= 1 / FPS else 0)}'
                    f'<div class="{{{{ID}}}}-shade"></div></div>')
        elif shape == "push":
            body = (f'<div id="{{{{ID}}}}-wo{k}" class="{{{{ID}}}}-wrap">{copy(0)}</div>'
                    f'<div id="{{{{ID}}}}-wi{k}" class="{{{{ID}}}}-wrap">{hv}</div>')
        else:
            body = hv
        ink = (f'<svg class="{{{{ID}}}}-ink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
               f'<circle id="{{{{ID}}}}-ring{k}" class="{{{{ID}}}}-line" cx="0" cy="0" r="0"/>'
               f'<line id="{{{{ID}}}}-hand{k}" class="{{{{ID}}}}-line" x1="0" y1="0" x2="0" y2="0"/></svg>'
               if shape in ("iris", "clock") else "")
        groups.append(f'  <!-- {c:.3f} {shape} -->\n'
                      f'  <div id="{{{{ID}}}}-g{k}" class="{{{{ID}}}}-g{" " + "{{ID}}-persp" if shape == "doors" else ""}" {tag}>'
                      f'{body}</div>{ink}')

    for f in os.listdir(d):                              # handles of cuts that moved or went away
        if re.fullmatch(r"h\d+\.mp4", f) and f not in keepfiles:
            os.remove(os.path.join(d, f))
    html = f"""<!-- shape-transitions (cam): a different shape-mask transition on each picture cut. Generated by handles.py
     (rerun it when KEEP, SHOTS or the FX list change); the motion is in fx.js. Each transition runs in the frames
     BEFORE its cut and reveals the incoming shot from its pre-roll handle (in sync with the J-cut audio already
     playing); the mask covers the frame on the last frame before the cut and the main picture carries on from the
     next frame. Outgoing pieces (doors, push) are synced copies of clean.mp4. Everything is class g: the live grade. -->
<div id="{{{{ID}}}}-root">
  <svg id="{{{{ID}}}}-defs" width="0" height="0" style="position:absolute;" aria-hidden="true">
    <filter id="{{{{ID}}}}-mb" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
      <feGaussianBlur id="{{{{ID}}}}-mb-g" in="SourceGraphic" stdDeviation="0" result="b"/>
      <feComponentTransfer in="b"><feFuncA type="table" tableValues="1 1"/></feComponentTransfer>
    </filter>
  </svg>
{chr(10).join(groups)}
</div>
<style>
#{{{{ID}}}}-root {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; overflow:hidden; }}
#{{{{ID}}}} .{{{{ID}}}}-g, #{{{{ID}}}} .{{{{ID}}}}-wrap {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; overflow:hidden; }}
#{{{{ID}}}} .{{{{ID}}}}-v {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; object-fit:cover; display:block; }}
#{{{{ID}}}} .{{{{ID}}}}-persp {{ perspective:1800px; perspective-origin:{W // 2}px {H // 2}px; }}
#{{{{ID}}}} .{{{{ID}}}}-door {{ position:absolute; top:0; width:{W // 2}px; height:{H}px; overflow:hidden; backface-visibility:hidden; }}
#{{{{ID}}}} .{{{{ID}}}}-dl {{ left:0; }}
#{{{{ID}}}} .{{{{ID}}}}-dr {{ left:{W // 2}px; }}
#{{{{ID}}}} .{{{{ID}}}}-dr .{{{{ID}}}}-v {{ left:-{W // 2}px; }}
#{{{{ID}}}} .{{{{ID}}}}-shade {{ position:absolute; left:0; top:0; width:{W // 2}px; height:{H}px; background:var(--c-dark); }}
#{{{{ID}}}} .{{{{ID}}}}-ink {{ position:absolute; left:0; top:0; overflow:visible; }}
#{{{{ID}}}} .{{{{ID}}}}-line {{ fill:none; stroke:var(--c-light); stroke-width:6; stroke-linecap:round; }}
</style>
"""
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"wrote {os.path.join(d, 'fx.html')}: {len(cuts)} transitions")


if __name__ == "__main__":
    main()
