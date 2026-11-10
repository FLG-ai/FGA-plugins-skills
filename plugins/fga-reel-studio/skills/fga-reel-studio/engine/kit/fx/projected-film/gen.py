#!/usr/bin/env python3
"""projected-film: write fx.html, the film strip around the picture, from THIS video's own voice and frame numbers.

The left rail carries a variable-area soundtrack drawn from the voice (assets/voice.wav, else public/master.wav, both
on the output timeline), laid out so the stretch of track crossing the middle of the screen is what the speaker says
on that film frame. The edge codes are the video's real frame numbers. The strip scrolls one film step every two
output frames from the effect's start (fx.js reads the strip's start offset and step from fx.html), so gen.py only
needs the window. When the voice is silent or missing (no mix yet, or a test project like the lab) the soundtrack is
drawn from words.json timing as a seeded stand-in, and the script says so: rerun it after the mix.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>: at, end), assets/voice.wav or public/master.wav, words.json,
          timeline.json (when end is "end")
  writes  <project>/fx/<id>/fx.html
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the mix changes.
"""
import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys

import numpy as np

FPS = 30
STEP = 24                       # strip advance per film frame (every 2 output frames) = 360 px/s
LW, RW = 116, 88                # left rail (perforations + soundtrack), right rail (perforations), px
PITCH, PW, PH = 65, 38, 27      # 35mm perforation pitch and size at this scale
TRACK_X, TRACK_HALF = 92, 14    # the soundtrack's centre line and its widest half width in the left rail
CODE_EVERY = 4                  # an edge code every this many perforations
EDGE_LEFT = "{n:05d}"                                   # left rail: the frame number
EDGE_RIGHT = ("SAFETY FILM", "ROLL 1  {n:05d}")         # right rail: alternating print
SR = 16000


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


def rnd(i):
    v = math.sin(i * 12.9898 + 78.233) * 43758.5453
    return v - math.floor(v)


def pcm(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def words_level(words, t, k):
    """a stand-in voice level at time t from word timing: energy inside each word, a syllable or two of shape,
    near-silence between words, a seeded flutter per row so it reads as an optical track"""
    for i, w in enumerate(words):
        if w["start"] <= t < w["end"]:
            f = (t - w["start"]) / max(0.05, w["end"] - w["start"])
            syl = 1 + int(rnd(i + 3) * 2.2)
            shape = abs(math.sin(math.pi * f * syl)) ** 0.6
            return (0.45 + 0.5 * rnd(i + 11)) * (0.35 + 0.65 * shape) * (0.7 + 0.3 * rnd(k * 7 + 1))
    return 0.04 + 0.06 * rnd(k + 7)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    A, B = window(project, fid)
    fA, fB = round(A * FPS), round(B * FPS)
    K = (fB - fA + 1) // 2 + 1                          # film frames in the window
    OY0 = -(STEP * K) - 40                              # strip y at A: it still covers the screen on the last frame
    H = 1920 - OY0 + 40

    def strip_time(s):                                  # strip row s crosses screen y 960 at this output time
        return A + 2 * (960 - OY0 - s) / (STEP * FPS)

    # ---- the soundtrack envelope: the voice, or the words.json stand-in
    voice = next((p for p in (os.path.join(project, "assets", "voice.wav"), os.path.join(project, "public", "master.wav"))
                  if os.path.exists(p)), None)
    a = pcm(voice) if voice else np.zeros(1, np.float32)
    rows = np.arange(0, H, 2)
    silent = float(np.abs(a).max()) < 1e-3
    if silent:
        wpath = os.path.join(project, "words.json")
        words = json.load(open(wpath)) if os.path.exists(wpath) else []
        print("the voice is silent or missing: the soundtrack is drawn from words.json timing (a seeded stand-in); "
              "rerun after the mix")
        env = np.array([words_level(words, strip_time(s), k) for k, s in enumerate(rows)])
    else:
        env = []
        for s in rows:
            t = strip_time(s)
            seg = a[max(0, int((t - 1 / 360) * SR)):max(0, int((t + 1 / 360) * SR))]
            env.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
        env = np.array(env)
        env = np.convolve(env, np.ones(3) / 3, mode="same")
        env = env / (np.percentile(env, 98) + 1e-6)
    env = np.clip(env, 0, 1) ** 0.6
    left = [f"{TRACK_X - 1 - TRACK_HALF * e:.1f},{s}" for s, e in zip(rows, env)]
    right = [f"{TRACK_X + 1 + TRACK_HALF * e:.1f},{s}" for s, e in reversed(list(zip(rows, env)))]
    track = f'<polygon class="{{{{ID}}}}-track" points="{" ".join(left + right)}"/>'

    def perfs(x):
        return "".join(f'<rect class="{{{{ID}}}}-perf" data-layout-allow-overflow x="{x}" y="{y}" width="{PW}" height="{PH}" rx="4.5"/>'
                       for y in range(8, H, PITCH))

    def codes(x, offset, label):
        out = []
        for i, y in enumerate(range(offset, H, CODE_EVERY * PITCH)):
            n = round(strip_time(y) * FPS)
            out.append(f'<text data-layout-allow-overflow x="{x}" y="{y}" transform="rotate(-90 {x} {y})">{label(i).format(n=max(0, n))}</text>')
        return "".join(out)

    tris = "".join(f'<polygon class="{{{{ID}}}}-tri" points="{13},{y + 5} {21},{y + 5} {17},{y - 3}"/>'
                   for y in range(120 + 2 * PITCH, H, CODE_EVERY * PITCH))
    left_svg = (f'<svg id="{{{{ID}}}}-ls" class="{{{{ID}}}}-strip" data-layout-allow-overflow width="{LW + 10}" height="{H}" viewBox="0 0 {LW + 10} {H}" '
                f'data-oy0="{OY0}" data-step="{STEP}">'
                f'<rect class="{{{{ID}}}}-base" width="{LW + 10}" height="{H}"/>'
                f'<g data-layout-allow-overflow transform="translate(10 0)">{perfs(24)}{track}'
                f'<g class="{{{{ID}}}}-ec">{codes(17, 120, lambda i: EDGE_LEFT)}</g>{tris}'
                f'<rect class="{{{{ID}}}}-seam" x="{LW - 2}" y="0" width="2" height="{H}"/></g></svg>')
    right_svg = (f'<svg id="{{{{ID}}}}-rs" class="{{{{ID}}}}-strip" data-layout-allow-overflow width="{RW + 10}" height="{H}" viewBox="0 0 {RW + 10} {H}">'
                 f'<rect class="{{{{ID}}}}-base" width="{RW + 10}" height="{H}"/>'
                 f'{perfs(26)}<g class="{{{{ID}}}}-ec">{codes(80, 250, lambda i: EDGE_RIGHT[i % len(EDGE_RIGHT)])}</g>'
                 f'<rect class="{{{{ID}}}}-seam" x="0" y="0" width="2" height="{H}"/></svg>')
    dust = "".join(f'<svg id="{{{{ID}}}}-dust{i}" class="{{{{ID}}}}-dust" width="40" height="40" viewBox="0 0 40 40">'
                   f'<path d="{d}"/></svg>' for i, d in enumerate([
                       "M18 14c4-2 9 1 8 6s-6 7-10 5-3-9 2-11z",
                       "M10 20c6-1 16-3 20-1-3 2-14 4-20 1z",
                       "M20 12c3 0 5 4 3 7l-2 9c-1 2-3 0-2-2l-1-8c-1-3 0-6 2-6z",
                       "M16 18c2-2 6-2 7 1 1 2-1 4-4 4s-5-3-3-5z"]))

    html = f"""<!-- projected-film: the shot becomes projected film. Generated by gen.py (rerun it when the window, the cut or the
     mix changes); the motion is in fx.js. On the cue word 35mm rails slide in at the left and right edges only
     (perforations, the video's own voice as the variable-area soundtrack, edge codes = this video's real frame
     numbers), all scrolling with the film at its cadence. The picture goes to a 15 fps step print (each frame held
     2, never more than one frame behind the voice), a print-film look, grain and an exposure flicker per film frame,
     a 1-2 px gate weave, a scratch and dust. On the second cue the loop slips: the frame line rolls through once.
     Gone at B, straight back to the video's own look. The footage copies are timed by the build from the effect's
     window: v0 in sync, v1 one frame behind (the step-print hold), v2 the frame above while the loop slips. -->
<svg id="{{{{ID}}}}-defs" width="0" height="0" style="position:absolute;" aria-hidden="true">
  <filter id="{{{{ID}}}}-tone" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
    <feComponentTransfer>
      <feFuncR id="{{{{ID}}}}-tr" type="table" tableValues="0 1"/>
      <feFuncG id="{{{{ID}}}}-tg" type="table" tableValues="0 1"/>
      <feFuncB id="{{{{ID}}}}-tb" type="table" tableValues="0 1"/>
    </feComponentTransfer>
  </filter>
</svg>
<div id="{{{{ID}}}}-weave">
  <div id="{{{{ID}}}}-roll">
    <div id="{{{{ID}}}}-s1" class="{{{{ID}}}}-slot">
      <video id="{{{{ID}}}}-v0" class="{{{{ID}}}}-x" src="clean.mp4" muted playsinline data-start="{{{{START}}}}" data-media-start="{{{{SYNC}}}}" data-duration="{{{{DUR}}}}" data-track-index="{{{{T0}}}}"></video>
      <video id="{{{{ID}}}}-v1" class="{{{{ID}}}}-x" src="clean.mp4" muted playsinline data-start="{{{{START+0.0333}}}}" data-media-start="{{{{SYNC}}}}" data-duration="{{{{DUR-0.0333}}}}" data-track-index="{{{{T1}}}}"></video>
    </div>
    <div id="{{{{ID}}}}-line"></div>
    <div id="{{{{ID}}}}-s2" class="{{{{ID}}}}-slot">
      <video id="{{{{ID}}}}-v2" class="{{{{ID}}}}-x" src="clean.mp4" muted playsinline data-start="{{{{START+0.0667}}}}" data-media-start="{{{{SYNC+0.0667}}}}" data-duration="{{{{DUR-0.0667}}}}" data-track-index="{{{{T2}}}}"></video>
    </div>
  </div>
  <div id="{{{{ID}}}}-vig" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion></div>
  <div id="{{{{ID}}}}-grain" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion><div id="{{{{ID}}}}-gt" data-layout-allow-overflow style="background-image:url(fx/{{{{ID}}}}/grain.png)"></div></div>
  <div id="{{{{ID}}}}-scratch"></div>
  {dust}
  <div id="{{{{ID}}}}-rl" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion>{left_svg}</div>
  <div id="{{{{ID}}}}-rr" data-layout-allow-overflow data-layout-allow-overlap data-layout-allow-occlusion>{right_svg}</div>
</div>
<style>
#{{{{ID}}}}-weave {{ position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:hidden; }}
#{{{{ID}}}}-roll {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
#{{{{ID}}}} .{{{{ID}}}}-slot {{ position:absolute; left:0; width:1080px; height:1920px; overflow:hidden; }}
#{{{{ID}}}}-s1 {{ top:0; }}
#{{{{ID}}}}-s2 {{ top:-1964px; }}
#{{{{ID}}}} .{{{{ID}}}}-x {{ position:absolute; left:0; top:0; width:1080px; height:1920px; object-fit:cover; }}
#{{{{ID}}}}-line {{ position:absolute; left:0; top:-44px; width:1080px; height:44px; background:var(--c-dark); }}
/* the vignette: an inset shadow inside an ellipse bigger than the frame, desaturated (a lens darkens, it doesn't tint) */
#{{{{ID}}}}-vig {{ position:absolute; left:-260px; top:-300px; width:1600px; height:2520px; border-radius:50%; filter:grayscale(1);
  box-shadow:inset 0 0 300px 120px color-mix(in srgb, var(--c-dark) 40%, transparent),
             0 0 0 1600px color-mix(in srgb, var(--c-dark) 40%, transparent); }}
#{{{{ID}}}}-grain {{ position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:hidden; mix-blend-mode:overlay; opacity:.3; }}
#{{{{ID}}}}-gt {{ position:absolute; left:0; top:0; width:1592px; height:2432px; background-repeat:repeat; background-size:512px 512px; }}
#{{{{ID}}}}-scratch {{ position:absolute; left:0; top:0; width:2px; height:1920px; background:var(--c-light); opacity:0; }}
#{{{{ID}}}} .{{{{ID}}}}-dust {{ position:absolute; left:0; top:0; opacity:0; }}
#{{{{ID}}}} .{{{{ID}}}}-dust path {{ fill:var(--c-dark); }}
#{{{{ID}}}}-rl {{ position:absolute; left:-10px; top:0; width:{LW + 10}px; height:1920px; overflow:hidden; }}
#{{{{ID}}}}-rr {{ position:absolute; left:{1080 - RW}px; top:0; width:{RW + 10}px; height:1920px; overflow:hidden; }}
#{{{{ID}}}} .{{{{ID}}}}-strip {{ position:absolute; left:0; top:0; display:block; }}
#{{{{ID}}}} .{{{{ID}}}}-base {{ fill:var(--c-dark); }}
#{{{{ID}}}} .{{{{ID}}}}-seam {{ fill:var(--c-dark); }}
#{{{{ID}}}} .{{{{ID}}}}-perf {{ fill:var(--c-light); }}
#{{{{ID}}}} .{{{{ID}}}}-track {{ fill:var(--c-light); opacity:.82; }}
#{{{{ID}}}} .{{{{ID}}}}-tri {{ fill:var(--c-light); opacity:.55; }}
#{{{{ID}}}} .{{{{ID}}}}-ec text {{ font-family:var(--font-mono); font-size:12.5px; font-weight:500; letter-spacing:.14em; fill:var(--c-light); opacity:.6; }}
</style>
"""
    d = os.path.join(project, "fx", fid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{os.path.join(d, 'fx.html')}: window {A:.2f}-{B:.2f}, strip {H}px, {K} film frames, "
          f"soundtrack from {'words.json (stand-in)' if silent else os.path.relpath(voice, project)}")


if __name__ == "__main__":
    main()
