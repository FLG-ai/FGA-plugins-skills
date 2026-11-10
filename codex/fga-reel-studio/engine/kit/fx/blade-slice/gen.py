#!/usr/bin/env python3
"""blade-slice: the picture is cut with a katana on one violent word.

One frame of hairline across the whole frame on the word, then two synced copies of the live shot, one each side of a
straight cut, slide apart along it with a dark gap between them while the speaker keeps talking in both halves. Just
after the word they slam home with a back ease and a punch, clean before the window ends.

This writes <project>/fx/<id>/fx.html + fx.js from the table below and the footage:
  the hairline  on the first frame of WORD (words.json, the first time it is said inside the window)
  the cut       through the speaker's mouth (or eye line) on that frame (work/tracks/track.json from track.py)
  the slam      just after the voice really stops (assets/voice.wav, else the word's end in words.json), the impact
                before the next word
Run: PY fx/<id>/gen.py <project> [<id>] [--check]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, assets/voice.wav, work/tracks/track.json
  writes  <project>/fx/<id>/fx.html + fx.js (--check: prints the plan, writes nothing)
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the word changes.
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

try:
    import fxlib                     # the kit's pipeline is on the kit Python's import path (setup writes reel-kit.pth)
except ImportError:                  # any other Python: the kit is a folder above this file
    _d = os.path.dirname(os.path.realpath(__file__))
    while _d != os.path.dirname(_d) and not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        _d = os.path.dirname(_d)
    if not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        sys.exit("run this with the kit's Python (PY: $REEL_KIT_HOME/.venv/bin/python), it has the kit's pipeline on its path")
    sys.path.insert(0, os.path.join(_d, "pipeline"))
    import fxlib
from common import load_edit  # noqa: E402

# ---- the table: the only thing that changes per video (px on the 1080x1920 frame)
WORD = "nothing"          # the violent word (hated, cut, killed): the hairline flashes on its first frame
THROUGH = "mouth"         # where the cut runs on the hairline frame: "mouth" (upper lip in one half, lower lip in the
                          # other: the most violent) or "eyes" (the eye line: cleaner)
PASS = None               # or (x, y): a point the cut passes through, used instead of THROUGH
ANGLE = -15.0             # degrees, negative = rises to the right
SLIDE = (64, 92)          # px along the cut, each half: on the frame after the hairline, and by the slam
GAP = (5, 8)              # px off the cut, each half (the dark gap between them is twice this)
HAIR_W = 4                # hairline thickness px
AFTER = 0.10              # s from where the voice stops to the impact (the halves cross); the slam starts a frame before
MIN_SLIDE = 6             # frames the halves slide apart at least, whatever the word's length
# The slam, per frame from its first frame: the fraction of the slide still left (a back ease keyed by hand: one frame
# home, past it, caught). The punch: the picture's scale per frame from the impact. SHORT is used when the window ends
# less than len(PUNCH) frames after the impact (end the window about 0.3 s after the word to get the full one).
HOME = [0.28, -0.13, -0.10, -0.03, 0.01, 0]
PUNCH = [1.035, 1.03, 1.022, 1.014, 1.007, 1.003, 1.0]
SHORT = dict(home=[0.28, -0.13, -0.08, -0.02, 0], punch=[1.035, 1.026, 1.012, 1.0], jolt=[(-7, 5), (6, -4), (-3, 2), (0, 0)])
# As approved, the slam punches but doesn't shake. SHAKE = True adds a jolt (px per frame from the impact) on the punch.
SHAKE = False
JOLT = [(-7, 5), (6, -4), (-4, 3), (3, -2), (-2, 1), (1, 0), (0, 0)]

FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))


def voice_end(project, s, e, nxt):
    """where the voice really stops after a word that runs s..e: the last 10 ms, before the next word, within 24 dB of
    the word's own peak (whisper's word ends are often a frame or two early)"""
    path = os.path.join(project, "assets", "voice.wav")
    if not os.path.exists(path):
        return e, "words.json"
    a = max(0.0, s - 0.05)
    b = min(nxt, e + 0.5) if nxt else e + 0.5
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", path, "-ac", "1",
                          "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    n = len(x) // 160
    if n < 3:
        return e, "words.json"
    rms = np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(axis=1))
    i0, i1 = int((s - a) / 0.01), max(int((e - a) / 0.01), int((s - a) / 0.01) + 1)
    peak = rms[i0:i1].max() if rms[i0:i1].size else rms.max()
    if peak < 1e-3:                                     # a silent stretch: nothing to measure
        return e, "words.json"
    floor = np.percentile(rms, 20)
    loud = np.where(rms >= max(peak * 10 ** (-24 / 20), 3 * floor))[0]
    return (a + (loud[-1] + 1) * 0.01, "assets/voice.wav") if len(loud) else (e, "words.json")


def off_frame(A, B):
    """the build times media by rounding to the nearest frame (halves to even) and shows the wrapper rounding halves up:
    a window edge between two frames lands a frame apart in the two, so say so"""
    bad = [f"{n} {t:.4f}" for n, t in (("at", A), ("end", B)) if abs(t * FPS - round(t * FPS)) > 0.01]
    if bad:
        print(f"note: the window's {' and '.join(bad)} sits between frames: put it on a frame (a multiple of 1/30 s)")


def through(project, f, how):
    """the mouth (or the middle of the eyes) from the track on frame f, or the nearest tracked frame within 3"""
    path = os.path.join(project, "work", "tracks", "track.json")
    if not os.path.exists(path):
        sys.exit(f"no {path}: run `PY KIT/pipeline/track.py {project}` first (or set PASS in the table)")
    T = fxlib.tracks(project)["frames"]
    for d in (0, 1, -1, 2, -2, 3, -3):
        i = f + d
        face = T[i].get("face") if 0 <= i < len(T) and T[i] else None
        if face:
            if how == "eyes":
                (x0, y0), (x1, y1) = face["eyes"]
                return ((x0 + x1) / 2, (y0 + y1) / 2), i
            return (face["mouth"][0], face["mouth"][1]), i
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    W, H = E.CANVAS
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    if F.get("layer", "top") != "cam":
        print(f"note: {fid} is built for layer=\"cam\" (it has layer={F.get('layer')!r})")
    f0, fB = round(A * FPS), round(B * FPS)
    off_frame(A, B)
    words = fxlib.words(project)

    # ---- times: the hairline on the word, the slam after the voice stops, the impact before the next word
    ws = fxlib.word_at(project, WORD, A)
    if ws is None or ws >= B:
        said = " ".join(t for s, e, t in words if A <= s < B)
        sys.exit(f"WORD {WORD!r} isn't said inside the window {A:.2f}-{B:.2f} (words there: {said})")
    we = next(e for s, e, t in words if abs(s - ws) < 1e-6)
    nxt = next((s for s, e, t in words if s > ws + 0.001), None)
    ve, src = voice_end(project, ws, we, nxt)
    hair = max(f0, round(ws * FPS))
    split = hair + 1
    contact = round((ve + AFTER) * FPS)
    if nxt is not None:
        contact = min(contact, round(nxt * FPS) - 1)          # the impact lands in the pause, before the next word
    contact = max(contact, split + MIN_SLIDE + 1)
    slam = contact - 1
    if slam >= fB - 1:
        sys.exit(f"the slam ({slam / FPS:.2f}) lands at or after the end of the window ({B:.2f}): end the window "
                 f"at {(contact + len(PUNCH)) / FPS:.2f} or later")
    home, punch, jolt = list(HOME), list(PUNCH), list(JOLT)
    if contact + len(punch) > fB:
        home, punch, jolt = list(SHORT["home"]), list(SHORT["punch"]), list(SHORT["jolt"])
    if contact + len(punch) > fB:                       # still no room: cut the settle short, but always end home
        room = fB - contact
        punch, jolt = punch[:room - 1] + [1.0], jolt[:room - 1] + [(0, 0)]
        home = home[:min(len(home), fB - slam) - 1] + [0]
        print(f"WARNING: the window ends {room} frames after the impact, the settle is cut short: end it at "
              f"{(contact + len(PUNCH)) / FPS:.2f} for the full one")
    shake = jolt if SHAKE else [(0, 0)] * len(punch)

    # ---- the cut: through the mouth (or eyes) on the hairline frame
    if PASS:
        pass_xy, tf = tuple(PASS), None
    else:
        pass_xy, tf = through(project, hair, THROUGH)
        if pass_xy is None:
            sys.exit(f"no face in work/tracks/track.json around frame {hair}: set PASS in the table")
    px, py = pass_xy

    print(f"{fid}: window {A:.3f}-{B:.3f}  hairline {hair / FPS:.3f} ('{WORD}' {ws:.2f}-{we:.2f}, voice stops "
          f"{ve:.2f} by {src})  slam {slam / FPS:.3f}  impact {contact / FPS:.3f}  clean {fB / FPS:.3f}")
    print(f"  the cut passes ({px:.0f}, {py:.0f}) at {ANGLE} deg: the {THROUGH if not PASS else 'PASS point'}"
          + (f" on track frame {tf}" if tf is not None else ""))
    if args.check:
        return
    d = os.path.join(project, "fx", fid)
    if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(d)), "LIBRARY.md")):
        sys.exit(f"{d} is a library folder: copy the effect into the project's own fx/{fid}/ and run it there")
    os.makedirs(d, exist_ok=True)

    # ---- geometry: two half-planes either side of the cut, run far past every frame edge
    rad = math.radians(ANGLE)
    dx, dy = math.cos(rad), math.sin(rad)
    nx, ny = math.sin(rad), -math.cos(rad)              # the normal pointing up, toward the top half
    L = float(W + H)
    a0, a1 = (px - L * dx, py - L * dy), (px + L * dx, py + L * dy)
    EPS = 1.5                                           # the lower half runs a hair past the cut: no seam when home
    b0, b1 = (a0[0] + EPS * nx, a0[1] + EPS * ny), (a1[0] + EPS * nx, a1[1] + EPS * ny)
    up, down = (L * nx, L * ny), (-L * nx, -L * ny)

    def poly(pts):
        return "polygon(" + ", ".join(f"{x:.2f}px {y:.2f}px" for x, y in pts) + ")"

    top_poly = poly([a0, a1, (a1[0] + up[0], a1[1] + up[1]), (a0[0] + up[0], a0[1] + up[1])])
    bot_poly = poly([b0, b1, (b1[0] + down[0], b1[1] + down[1]), (b0[0] + down[0], b0[1] + down[1])])
    hl = math.ceil(math.hypot(W, H))

    html = f"""<!-- blade-slice (cam). Written by gen.py (rerun it, don't edit this file). The picture is cut with a katana: one frame of
     hairline across the whole frame on the word, then two synced copies of the live shot, one each side of the cut, slide
     apart along it over a dark gap while the speaker keeps talking in both. On the end of the word they slam home with a
     back ease and a punch. Both copies are timed by the build from the window, a frame apart, in the live grade. -->
<div id="{{{{ID}}}}-root" class="{{{{ID}}}}-full">
  <div id="{{{{ID}}}}-bg" class="{{{{ID}}}}-full"></div>
  <div id="{{{{ID}}}}-shake" class="{{{{ID}}}}-full" data-layout-allow-overlap>
    <div id="{{{{ID}}}}-b" class="{{{{ID}}}}-full" data-layout-allow-overlap><video id="{{{{ID}}}}-vb" class="{{{{ID}}}}-full g" src="clean.mp4" muted playsinline data-start="{{{{START+0.0333}}}}" data-media-start="{{{{SYNC+0.0333}}}}" data-duration="{{{{DUR-0.0333}}}}" data-track-index="{{{{T1}}}}"></video></div>
    <div id="{{{{ID}}}}-a" class="{{{{ID}}}}-full" data-layout-allow-overlap><video id="{{{{ID}}}}-va" class="{{{{ID}}}}-full g" src="clean.mp4" muted playsinline data-start="{{{{START}}}}" data-media-start="{{{{SYNC}}}}" data-duration="{{{{DUR}}}}" data-track-index="{{{{T0}}}}"></video></div>
  </div>
  <div id="{{{{ID}}}}-line" data-layout-allow-overlap></div>
</div>
<style>
#{{{{ID}}}} .{{{{ID}}}}-full {{ position:absolute; left:0; top:0; width:{W}px; height:{H}px; }}
#{{{{ID}}}}-root {{ overflow:hidden; }}
#{{{{ID}}}}-bg {{ background:var(--c-dark); }}
#{{{{ID}}}} video {{ object-fit:cover; display:block; }}
#{{{{ID}}}}-line {{ position:absolute; left:{px - hl:.1f}px; top:{py - HAIR_W / 2:.1f}px; width:{2 * hl}px; height:{HAIR_W}px; background:var(--c-light); transform-origin:{hl}px {HAIR_W / 2}px; }}
</style>
"""

    def pairs(v):
        return "[" + ", ".join(f"[{a}, {b}]" for a, b in v) + "]"

    js = f"""// blade-slice: written by gen.py (rerun it, don't edit this file). Every frame is a tl.set: one frame of hairline, the
// slice, the slow slide apart, the slam, the punch. The footage copies are never re-timed. Frames count from the
// window's first frame; '{WORD}' and the voice set them (gen.py prints the plan).
var FPS = 30, F0 = {f0};                    // the window's first frame (edit.py at {A:.4f}): rerun gen.py when it moves
function T(f) {{ return q((F0 + f) / FPS); }}
var HAIR = {hair - f0}, SPLIT = {split - f0}, SLAM = {slam - f0}, CONTACT = {contact - f0}, CLEAN = {fB - f0};
var DX = {dx:.5f}, DY = {dy:.5f}, NX = {nx:.5f}, NY = {ny:.5f};
var S0 = {SLIDE[0]}, S1 = {SLIDE[1]}, G0 = {GAP[0]}, G1 = {GAP[1]};
var HOME = {json.dumps(home)}, SHAKE = {pairs(shake)}, PUNCH = {json.dumps(punch)};
function place(f, s, g) {{
  tl.set('#{{{{ID}}}}-a', {{ x: s * DX + g * NX, y: s * DY + g * NY }}, T(f));
  tl.set('#{{{{ID}}}}-b', {{ x: -(s * DX + g * NX), y: -(s * DY + g * NY) }}, T(f));
}}
gsap.set('#{{{{ID}}}}-a', {{ clipPath: '{top_poly}' }});
gsap.set('#{{{{ID}}}}-b', {{ clipPath: '{bot_poly}' }});
gsap.set('#{{{{ID}}}}-line', {{ rotation: {ANGLE} }});
gsap.set(['#{{{{ID}}}}-bg', '#{{{{ID}}}}-shake', '#{{{{ID}}}}-line'], {{ opacity: 0 }});
gsap.set('#{{{{ID}}}}-shake', {{ transformOrigin: '{W / 2:.0f}px {H / 2:.0f}px' }});
tl.set('#{{{{ID}}}}-line', {{ opacity: 1 }}, T(HAIR));
tl.set('#{{{{ID}}}}-line', {{ opacity: 0 }}, T(SPLIT));
tl.set(['#{{{{ID}}}}-bg', '#{{{{ID}}}}-shake'], {{ opacity: 1 }}, T(SPLIT));
for (var f = SPLIT; f < SLAM; f++) {{
  var p = (f - SPLIT) / Math.max(1, SLAM - 1 - SPLIT);
  place(f, S0 + (S1 - S0) * p, G0 + (G1 - G0) * p);
}}
HOME.forEach(function (h, i) {{ place(SLAM + i, S1 * h, Math.max(0, G1 * h)); }});
SHAKE.forEach(function (o, i) {{ tl.set('#{{{{ID}}}}-shake', {{ x: o[0], y: o[1], scale: PUNCH[i] }}, T(CONTACT + i)); }});
tl.set(['#{{{{ID}}}}-bg', '#{{{{ID}}}}-shake'], {{ opacity: 0 }}, T(CLEAN));
"""
    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(os.path.join(d, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write(js)
    t = lambda f: round(f / FPS, 3)                    # noqa: E731
    print(f"wrote {d}/fx.html + fx.js\nSFX for edit.SOUND['sfx'] (the hit times):\n"
          f"    ({t(hair)}, \"whoosh-soft\", -12), ({t(hair)}, \"tick\", -10),          # the hairline: the blade passes\n"
          f"    ({t(contact)}, \"impact-low\", -13), ({t(contact)}, \"tick\", -13),     # the halves slam home")


if __name__ == "__main__":
    main()
