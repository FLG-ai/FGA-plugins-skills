#!/usr/bin/env python3
"""clone-row: six more of the speaker, all talking, slide out from behind them in pairs on three words and snap back
into them on a fourth. Each row is the cutout scaled about the head (the vanishing point), a touch darker and softer
with distance, one frame later in media time per generation so they are not robotically identical, each falling off
into the dark from the collar down so its own mic and hands never show. Horizontal motion blur on the slides through
one SVG filter per row. Stack (layer cam): the clones furthest first, then the speaker's cutout on top, over the live
footage. No plate: the room stays the real pixels, so it can start and end anywhere without a seam.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, public/subject.webm, work/tracks/track.json
  writes  <project>/fx/<id>/fx.html, fx.js (seven <video> tracks, T0..T6)
<id> defaults to this folder's name. Rerun it whenever the window, the cut or the words change.
"""
import argparse
import json
import os
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920

# ---- the table. Distances are in head half-widths (measured on the matte at the eye line), so they fit any framing.
# row: scale, |dx| from the head, dy, brightness, lens softness px. Scale is about the head: the vanishing point.
ROWS = [(0.56, 1.56, -0.12, 0.90, 0.5),
        (0.38, 2.27, -0.20, 0.75, 0.8),
        (0.26, 2.74, -0.25, 0.60, 1.1)]
OUT_ON = None               # the spoken word each row slides out on, nearest row first; None = the first three words of the window
BACK_ON = None              # the spoken word they all snap back on; None = the word after the third row's
SLIDE = 0.28                # s a row takes to slide out (power3.out)
BACK = 0.32                 # s the snap back takes (expo.in), the rows landing together
FADE = None                 # (y0, y1) px on the cutout: each clone falls off into the dark between them; None = from the chin
FADE_FACE = (0.12, 1.20)    # ...this many face heights under the chin: gone above its own mic and hands
HIDDEN = 0.80               # scale at which a copy sits completely behind the speaker: where a row leaves from and lands back
BLUR = 0.5                  # motion blur strength, a fraction of the frame-to-frame move (a 180 degree shutter)


# ---- the kit and the project
def kit_pipeline():
    """fxlib and the rest of the kit's pipeline: PY has them on its path (setup puts them there). Run from the kit's
    library folder itself, they are two folders up"""
    try:
        import fxlib  # noqa: F401
    except ImportError:
        up = os.path.abspath(os.path.join(HERE, "..", "..", "pipeline"))
        if not os.path.exists(os.path.join(up, "fxlib.py")):
            sys.exit("can't import fxlib: run this with the kit's Python (PY), which has the kit's pipeline on its path")
        sys.path.insert(0, up)


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def spoken(words, w, after, before=1e9):
    """start of the first spoken word w in [after, before) (as wordAt in fx.js), or None"""
    for s, e, text in words:
        if after - 0.001 <= s < before and norm(text) == norm(w):
            return s
    return None


def out_dir(project, fid):
    d = os.path.join(project, "fx", fid)
    if os.path.realpath(d) == os.path.realpath(HERE) and os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "build.py")):
        sys.exit("that is the kit's library folder: copy it to <project>/fx/<id>/ and run the copy")
    os.makedirs(d, exist_ok=True)
    return d


def fr(t):
    return round(t * FPS)


def measure(project, A, B):
    """the vanishing point (head centre at the eye line), the head half-width on the matte there, and the chin, averaged
    over the window"""
    import fxlib
    tr = fxlib.tracks(project)["frames"]
    xs, ys, hws, chins, fhs = [], [], [], [], []
    for i, al in fxlib.alpha(project, A, B):
        f = tr[i].get("face") if i < len(tr) else None
        if i % 3 or not f:
            continue
        ey = int(np.clip((f["eyes"][0][1] + f["eyes"][1][1]) / 2, 0, H - 1))
        row = al[ey] > 128
        c = int(np.clip(f["cx"], 0, W - 1))
        if row[c]:
            l = c - int(np.argmin(row[c::-1])) if not row[:c + 1].all() else 0
            r = c + int(np.argmin(row[c:])) if not row[c:].all() else W
            hws.append((r - l) / 2)
        xs.append(f["cx"])
        ys.append(ey)
        chins.append(f["chin"])
        fhs.append(f["chin"] - f["top"])
    if not xs:
        sys.exit("no face in work/tracks/track.json inside this window: run pipeline/track.py")
    hw = float(np.median(hws)) if hws else 0.59 * float(np.median([tr[i]["face"]["w"] for i in range(fr(A), fr(B)) if tr[i].get("face")]))
    return float(np.mean(xs)), float(np.mean(ys)), hw, float(np.mean(chins)), float(np.mean(fhs))


def out3(u):
    return 1 - (1 - u) ** 3


def expo_in(u):
    return 0.0 if u <= 0 else 2 ** (10 * (u - 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    kit_pipeline()
    import fxlib
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    words = fxlib.words(project)
    # the words: three rows out, one word back
    if OUT_ON:
        outs, after = [], A
        for w in OUT_ON:
            t = spoken(words, w, after, B)
            if t is None:
                sys.exit(f"OUT_ON: {w!r} is not spoken in {A:.2f}-{B:.2f} after the words before it")
            outs.append(t)
            after = t + 0.01
    else:
        outs = [s for s, e, t in words if A + 0.05 <= s < B][:len(ROWS)]
    if len(outs) < len(ROWS):
        sys.exit(f"the window has {len(outs)} words for {len(ROWS)} rows: set OUT_ON, or widen the window")
    back0 = spoken(words, BACK_ON, outs[-1] + 0.01, B) if BACK_ON else next((s for s, e, t in words if outs[-1] + 0.15 <= s < B), None)
    if back0 is None:
        back0 = outs[-1] + SLIDE + 0.35
        print(f"no word to snap back on after the last row: back at {back0:.2f}")
    back = (back0, back0 + BACK)
    if back[1] > B - 1 / FPS:
        print(f"warning: the snap back lands at {back[1]:.2f}, after the window ends ({B:.2f}): end the window later")
    ax, ay, hw, chin, fh = measure(project, A, B)
    fade = FADE or (chin + FADE_FACE[0] * fh, chin + FADE_FACE[1] * fh)
    print(f"{fid}: vanishing point {ax:.0f},{ay:.0f}; head half-width {hw:.0f}px on the matte; fade {fade[0]:.0f}-{fade[1]:.0f}; "
          f"rows out {', '.join(f'{t:.2f}' for t in outs)}, back {back[0]:.2f}-{back[1]:.2f}")
    n0, n1 = fr(A), fr(B)
    rows = []
    for k, (s, d, dy, br, soft) in enumerate(ROWS):
        ps, pd, pdy = (HIDDEN, 0.0, 0.0) if k == 0 else (ROWS[k - 1][0], ROWS[k - 1][1] * hw, ROWS[k - 1][2] * hw)   # out from behind the row in front
        rows.append(dict(t0=outs[k], s=s, d=d * hw, dy=dy * hw, br=br, soft=soft, ps=ps, pd=pd, pdy=pdy, gen=k + 1))
    edge = max(r["d"] + r["s"] * hw for r in rows)
    if ax - edge < -hw or ax + edge > W + hw:
        print("note: the outer row runs off the frame edge (fine: the line carries on out of shot)")

    def pose(r, t):
        """scale, dx, dy of a row at t (dx positive = outward)"""
        if t < fr(r["t0"]) / FPS - 0.001:
            return r["ps"], r["pd"], r["pdy"], False
        b0 = back[0] + 0.02 * (len(rows) - r["gen"])    # the furthest row leaves first, they land together
        if t >= back[1]:
            return HIDDEN, 0.0, 0.0, False
        if t >= b0:
            e = expo_in((t - b0) / (back[1] - b0))
            return r["s"] + (HIDDEN - r["s"]) * e, r["d"] * (1 - e), r["dy"] * (1 - e), True
        e = out3(min(1.0, (t - r["t0"] + 1 / FPS) / SLIDE))   # the first frame on the word has already moved
        return r["ps"] + (r["s"] - r["ps"]) * e, r["pd"] + (r["d"] - r["pd"]) * e, r["pdy"] + (r["dy"] - r["pdy"]) * e, True

    # the fall-off: a smoothstep written as stops, so there is no line where it starts or ends
    stops = []
    for j in range(9):
        u = j / 8
        stops.append(f"rgba(0,0,0,{1 - u * u * (3 - 2 * u):.3f}) {fade[0] + (fade[1] - fade[0]) * u:.0f}px")
    mask = "linear-gradient(to bottom, " + ", ".join(stops) + ")"
    style = "position:absolute;left:0;top:0;width:1080px;height:1920px;"
    start = fxlib.clip_start(A)
    html = ["<!-- clone-row: written by gen.py. Six copies of the speaker furthest first, then the speaker on top. -->",
            '<svg width="0" height="0" style="position:absolute"><defs>' + "".join(
                f'<filter id="{{{{ID}}}}-mb{k}" x="-20%" y="0%" width="140%" height="100%" color-interpolation-filters="sRGB">'
                f'<feGaussianBlur id="{{{{ID}}}}-mbg{k}" stdDeviation="0 0"/></filter>' for k in range(len(rows))) + "</defs></svg>"]
    track = 0
    for k in reversed(range(len(rows))):
        r = rows[k]
        for side in ("L", "R"):
            # each copy ends a frame apart after the snap back, when it is already hidden: identical media windows trip
            # the duplicate-media lint. The speaker on top plays the window's exact length, so skip that one
            end_frames = fr(back[1]) - n0 + track
            if end_frames >= n1 - n0:
                end_frames += 1
            ms = fr(A) / FPS - r["gen"] / FPS + 0.001
            html.append(f'<div class="{{{{ID}}}}-w" id="{{{{ID}}}}-w{k}{side}" data-layout-allow-overlap style="filter:url(#{{{{ID}}}}-mb{k}) brightness({r["br"]}) blur({r["soft"]}px);">'
                        f'<video id="{{{{ID}}}}-v{k}{side}" class="g" src="subject.webm" muted playsinline data-start="{start:.4f}" data-media-start="{max(0.0, ms):.4f}" '
                        f'data-duration="{end_frames / FPS:.4f}" data-track-index="{{{{T{track}}}}}" style="{style}"></video></div>')
            track += 1
    html.append(f'<video id="{{{{ID}}}}-subject" class="g" src="subject.webm" muted playsinline data-start="{start:.4f}" '
                f'data-media-start="{fr(A) / FPS + 0.001:.4f}" data-duration="{(n1 - n0) / FPS:.4f}" data-track-index="{{{{T{track}}}}}" style="{style}"></video>')
    html.append(f"""<style>
#{{{{ID}}}} .{{{{ID}}}}-w {{ position:absolute; left:0; top:0; width:1080px; height:1920px; transform-origin:{ax:.1f}px {ay:.1f}px;
  -webkit-mask-image:{mask}; mask-image:{mask}; }}
</style>""")
    d = out_dir(project, fid)
    open(os.path.join(d, "fx.html"), "w", encoding="utf-8").write("\n".join(html) + "\n")

    data = []
    for r in rows:
        row, was = [], None
        for n in range(n0, n1 + 1):
            t = n / FPS
            s, dd, dy, vis = pose(r, t)
            speed = abs(pose(r, t + 0.5 / FPS)[1] - pose(r, t - 0.5 / FPS)[1])
            cur = (round(s, 4), round(dd, 1), round(dy, 1), 1 if vis else 0, round(speed * BLUR * 0.42, 1))    # 0.42: sigma of a box that long
            if cur != was:
                row.extend([n, *cur])
                was = cur
        data.append(row)
    js = ["// clone-row: written by gen.py. Per row: video frame, scale, dx, dy, visible, horizontal motion blur sigma.",
          "var R = " + json.dumps(data, separators=(",", ":")) + ";",
          "gsap.set('#{{ID}} .{{ID}}-w', { opacity: 0 });",
          "R.forEach(function (r, k) {",
          "  for (var i = 0; i < r.length; i += 6) {",
          "    var t = q(r[i] / 30);",
          "    tl.set('#{{ID}}-w' + k + 'L', { scale: r[i + 1], x: -r[i + 2], y: r[i + 3], opacity: r[i + 4] }, t);",
          "    tl.set('#{{ID}}-w' + k + 'R', { scale: r[i + 1], x: r[i + 2], y: r[i + 3], opacity: r[i + 4] }, t);",
          "    tl.set('#{{ID}}-mbg' + k, { attr: { stdDeviation: r[i + 5] + ' 0' } }, t);",
          "  }",
          "});"]
    open(os.path.join(d, "fx.js"), "w", encoding="utf-8").write("\n".join(js) + "\n")
    print("sets", sum(len(r) // 6 for r in data), "->", d)
    sfx = [(t + 0.04, "whoosh-soft", -18 - k, "a pair slides out") for k, t in enumerate(outs)]
    sfx += [(back[1] - 0.06, "whoosh-deep", -15, "the snap back"), (back[1], "pop", -19, "they land in the speaker"), (back[1], "impact-low", -17, "the landing")]
    print("SFX (time, name, dB, what):", [(round(t, 3), n, db, x) for t, n, db, x in sfx])


if __name__ == "__main__":
    main()
