#!/usr/bin/env python3
"""head-stack: tiles fall from above the frame on the speaker's words and land on their real moving silhouette:
pymunk at 240 Hz, the top edge of the matte rebuilt every step as a chain of kinematic segments moving at the speaker's
actual velocity. The pile rides the head, slips when they lean, a tile slides off the tower onto the pile below; on the
release word the side piles lose their floor and the tower topples off past the ear, gone by the end of the line.
Crisp tiles stay DOM (one tl.set per frame per tile); shadow.webm carries what the DOM can't: the soft contact shadow,
which only falls on the speaker (clipped by the matte), and true motion blur on the fast frames, integrated over a 180
degree shutter from the 240 Hz sim. The tiles are the pack's light ground, ink, hairline and mono face.

Run: PY fx/<id>/gen.py <project> [<id>] [--search] [--n 120] [--workers 6]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, public/subject.webm, work/tracks/track.json,
          the style pack (mono face, colours, corner radius)
  writes  <project>/fx/<id>/shadow.webm, fx.html, fx.js; sim.py's TARGETS and SEED (search.py, when they are empty or
          with --search); work/<id>/stack_sim.json, stack_contacts.json
<id> defaults to this folder's name. Edit the table at the top of sim.py (labels, words, release). Needs pymunk.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True       # nothing but the effect in an fx folder
import sim  # noqa: E402

FPS, W, H = 30, 1080, 1920
LIP_H = 5                   # px at the reference head: the tile's thickness, a darker lower edge like a keycap's skirt
BLUR_FROM = 7.0             # px per frame (at the reference head): below this the crisp DOM tile shows, above it the integrated smear


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


def need_pymunk():
    try:
        import pymunk  # noqa: F401
    except ImportError:
        sys.exit("head-stack needs pymunk in the kit's Python: PY -m pip install pymunk  (a 1 MB wheel, no compiler needed)")


def out_dir(project, fid):
    d = os.path.join(project, "fx", fid)
    if os.path.realpath(d) == os.path.realpath(HERE) and os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "build.py")):
        sys.exit("that is the kit's library folder: copy it to <project>/fx/<id>/ and run the copy")
    os.makedirs(d, exist_ok=True)
    return d


def sprite(label, look, ss=3):
    """the tile as an RGBA array, premultiplied, for the smear"""
    from PIL import Image, ImageDraw
    Wt, Ht, R = look["w"], look["h"], look["r"]
    m = int(round(12 * sim.K))
    im = Image.new("RGBA", (int(round((Wt + 2 * m) * ss)), int(round((Ht + 2 * m) * ss))), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = [m * ss, m * ss, (m + Wt) * ss - 1, (m + Ht) * ss - 1]
    d.rounded_rectangle(box, R * ss, fill=look["lip"] + (255,))
    d.rounded_rectangle([box[0], box[1], box[2], (m + Ht - look["lip_h"]) * ss - 1], R * ss, fill=look["bg"] + (255,))
    d.rounded_rectangle(box, R * ss, outline=look["edge"] + (255,), width=max(1, int(round(2 * sim.K * ss))))
    a, b = sim.split(label)
    f1, f2 = look["f1"](ss), look["f2"](ss)
    wa = d.textlength(a, font=f1)
    wb = d.textlength(b, font=f2) if b else 0
    gap = 7 * sim.K * ss if b else 0
    x0 = (im.width - wa - gap - wb) / 2
    base = im.height / 2 + 13 * sim.K * ss
    d.text((x0, base), a, font=f1, fill=look["ink"] + (255,), anchor="ls")
    if b:
        d.text((x0 + wa + gap, base), b, font=f2, fill=look["ink"] + (255,), anchor="ls")
    arr = np.asarray(im, np.float32) / 255.0
    arr[:, :, :3] *= arr[:, :, 3:4]
    return arr, ss, m


def warp_into(dst, spr, ss, m, x, y, ang, look, weight=1.0):
    """composite (add) a premultiplied sprite at pose x, y, ang into dst (premultiplied, accumulation)"""
    import cv2
    hw, hh = (look["w"] + 2 * m) / 2, (look["h"] + 2 * m) / 2
    rad = math.hypot(hw, hh) + 3
    x0, y0 = int(max(0, x - rad)), int(max(0, y - rad))
    x1, y1 = int(min(dst.shape[1], x + rad + 1)), int(min(dst.shape[0], y + rad + 1))
    if x1 <= x0 or y1 <= y0:
        return
    c, s = math.cos(ang), math.sin(ang)
    M = np.array([[c / ss, -s / ss, x - x0 - c * hw + s * hh], [s / ss, c / ss, y - y0 - s * hw - c * hh]], np.float32)
    dst[y0:y1, x0:x1] += cv2.warpAffine(spr, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0) * weight


def pose_at(rec, i, kf):
    """tile i at fractional 240 Hz index kf, linear between steps; None before it exists"""
    k0 = int(math.floor(kf))
    k1 = min(k0 + 1, len(rec) - 1)
    k0 = max(0, min(k0, len(rec) - 1))
    p0, p1 = rec[k0][i], rec[k1][i]
    if p0 is None or p1 is None:
        return p0 or p1
    f = kf - math.floor(kf)
    return [p0[j] + (p1[j] - p0[j]) * f for j in range(6)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--search", action="store_true", help="search for a new pile even when sim.py has one")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "build.py")):
        sys.exit("this is the kit's library folder: copy it to <project>/fx/<id>/ and run the copy (the search writes the pile into its sim.py)")
    kit_pipeline()
    need_pymunk()
    import cv2
    import fxlib
    from PIL import Image, ImageDraw
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    sim.setup(project, fid)
    A, B = sim.A, sim.B
    print(f"{fid}: {len(sim.TILES)} tiles land at " + ", ".join(f"{t:.2f}" for t in sim.DROP_T) + f"; release {sim.RELEASE:.2f}; "
          f"face {sim.FW:.0f}px wide, so tiles {sim.TILE_W:.0f}x{sim.px(sim.TILE_H):.0f}px")
    if args.search or not sim.TARGETS or len(sim.TARGETS) != len(sim.TILES):
        import search
        search.search(project, fid, args.n, args.workers)
    y0 = sim.load_boundary()[0]
    fit = int((float(np.median(y0.min(axis=1))) - 185) / sim.px(sim.TILE_H))      # tiles that stack on the head under the top safe zone
    on_head = sum(1 for t in sim.TARGETS if t[0] == "head")
    if on_head > fit + 1:
        print(f"warning: {on_head} tiles are aimed at the head but about {fit} fit above it: the tower leaves the top of the frame. "
              f"Use fewer TILES (a selfie's head sits high and its shoulders are out of shot)")
    S = sim.main()
    rec, labels, first = S["rec"], S["labels"], S["first"]
    support = sim.load_boundary()[0]
    pk = fxlib.pack(project)
    col = pk["colors"]
    look = dict(w=sim.TILE_W, h=sim.px(sim.TILE_H), r=sim.TILE_R, lip_h=sim.px(LIP_H),
                bg=tuple(col["light"][:3]), lip=tuple(col["hair_light"][:3]), edge=tuple(col["dark"][:3]), ink=tuple(col["ink"][:3]),
                f1=lambda ss: fxlib.font(project, "mono", int(round(sim.px(42) * ss))), f2=lambda ss: fxlib.font(project, "mono", int(round(sim.px(24) * ss))))
    sprites = [sprite(l, look) for l in labels]
    m, ss = sprites[0][2], sprites[0][1]
    im = Image.new("L", (int(round((look["w"] + 2 * m) * ss)), int(round((look["h"] + 2 * m) * ss))), 0)
    ImageDraw.Draw(im).rounded_rectangle([m * ss, m * ss, (m + look["w"]) * ss - 1, (m + look["h"]) * ss - 1], look["r"] * ss, fill=255)
    sil = (np.asarray(im, np.float32) / 255.0)[:, :, None]
    sil = np.dstack([sil, sil, sil, sil])

    nf = round((B - A) * FPS)
    SUB = sim.SUB
    dom = [[] for _ in labels]
    d = out_dir(project, fid)
    wr = fxlib.Writer(os.path.join(d, "shadow.webm"), alpha=True, crf=16)
    for fi, al in fxlib.alpha(project, A, B):
        n = fi - round(A * FPS)
        if n >= nf:
            break
        matte = al.astype(np.float32) / 255.0
        shadow = np.zeros(matte.shape, np.float32)      # 1 - product(1 - s): shadows add up like real ones
        pm = np.zeros(matte.shape + (4,), np.float32)    # premultiplied smear
        kc = n * SUB - 1
        for i in range(len(labels)):
            p = pose_at(rec, i, max(kc, 0)) if kc >= 0 else None
            if p is None:
                dom[i].append(None)
                continue
            x, y, ang, vx, vy, wa = p
            if y > H + sim.px(90) or y < -sim.px(120) or x < -sim.TILE_W or x > W + sim.TILE_W:
                dom[i].append(None)
                continue
            speed = (math.hypot(vx, vy) + abs(wa) * 60.0 * sim.K) / FPS
            fast = speed > sim.px(BLUR_FROM)
            dom[i].append((x, y, math.degrees(ang), 0 if fast else 1))
            if fast:                                   # the smear: the tile accumulated over a 180 degree shutter
                samples = int(min(28, max(4, math.ceil(speed * 0.5 / 1.5))))
                spr, s_, m_ = sprites[i]
                acc = np.zeros_like(pm)
                got = 0
                for q_ in range(samples):
                    kf = kc + (q_ + 0.5) / samples * (SUB * 0.5) - SUB * 0.25
                    pp = pose_at(rec, i, kf)
                    if pp is None:
                        continue
                    warp_into(acc, spr, s_, m_, pp[0], pp[1], pp[2], look)
                    got += 1
                if got:
                    pm += acc / got * (1 - pm[:, :, 3:4])
            # the shadow, on the speaker only: tight when a tile touches, wide and soft when it flies in front
            c, s = math.cos(ang), math.sin(ang)
            bottoms = []
            for u in np.linspace(-look["w"] / 2, look["w"] / 2, 9):
                for v_ in (look["h"] / 2, -look["h"] / 2):
                    wx, wy = x + c * u - s * v_, y + s * u + c * v_
                    if 0 <= wx < W:
                        bottoms.append(support[min(n, len(support) - 1)][int(wx)] - wy)
            gap = min(bottoms) if bottoms else 999.0
            lift = 1.0 if gap < -sim.px(14) else float(np.clip(max(gap, 0.0) / sim.px(150), 0, 1))
            sig = sim.px(9.0 + 19.0 * lift)
            dx, dy = sim.px(3.0 + 16.0 * lift), sim.px(11.0 + 26.0 * lift)
            k = 0.74 - 0.38 * lift
            one = np.zeros(matte.shape + (4,), np.float32)
            warp_into(one, sil, ss, m, x + dx, y + dy, ang, look)
            shadow = 1 - (1 - shadow) * (1 - cv2.GaussianBlur(one[:, :, 3], (0, 0), sig) * k)
            if lift < 0.4:                             # the tight dark line right under the contact
                one[:] = 0
                warp_into(one, sil, ss, m, x + sim.px(1), y + sim.px(3.5), ang, look)
                shadow = 1 - (1 - shadow) * (1 - cv2.GaussianBlur(one[:, :, 3], (0, 0), sim.px(3.0)) * 0.62 * (1 - lift / 0.4))
        shadow *= matte
        a = pm[:, :, 3] + shadow * (1 - pm[:, :, 3])     # smear over shadow (black), then straight alpha for the encoder
        out = np.zeros(matte.shape + (4,), np.uint8)
        with np.errstate(divide="ignore", invalid="ignore"):
            rgb = np.where(a[:, :, None] > 1e-4, pm[:, :, :3] / a[:, :, None], 0)
        out[:, :, :3] = np.clip(rgb * 255 + 0.5, 0, 255)
        out[:, :, 3] = np.clip(a * 255 + 0.5, 0, 255)
        wr.write(out)
    wr.close()

    # ---- fx.html: the shadow clip, then the tiles in the pack's look
    Wt, Ht = look["w"], look["h"]
    html = ["<!-- head-stack: written by gen.py. Tiles fall on the words onto the speaker's real moving silhouette (pymunk, 240 Hz), then the tower topples off. -->",
            fxlib.tag("{{ID}}-sh", "fx/{{ID}}/shadow.webm", A, B, "", "{{T0}}", "position:absolute;left:0;top:0;width:1080px;height:1920px;")]
    for i, l in enumerate(labels):
        a, b = sim.split(l)
        html.append(f'<div data-layout-allow-overlap data-layout-allow-occlusion class="{{{{ID}}}}-t" id="{{{{ID}}}}-t{i}">'
                    f'<b data-layout-allow-overlap>{a}</b>' + (f'<i data-layout-allow-overlap>{b}</i>' if b else "") + "</div>")
    wt = pk["fonts"]["mono"].get("weight", 500)
    html.append(f"""<style>
#{{{{ID}}}} .{{{{ID}}}}-t {{ position:absolute; left:0; top:0; width:{Wt:.1f}px; height:{Ht:.1f}px; box-sizing:border-box; border-radius:{look['r']:.1f}px;
  background:var(--c-light); border:{max(1.0, 2 * sim.K):.1f}px solid var(--c-dark); box-shadow:inset 0 -{look['lip_h']:.1f}px 0 var(--c-hair-light), 0 2px 3px rgba(0,0,0,.34);
  display:flex; align-items:baseline; justify-content:center; gap:{sim.px(7):.1f}px; padding-top:{sim.px(9):.1f}px; color:var(--c-ink);
  font-family:var(--font-mono); font-weight:{wt}; font-style:normal; white-space:nowrap; }}
#{{{{ID}}}} .{{{{ID}}}}-t b {{ font-size:{sim.px(42):.1f}px; line-height:{sim.px(42):.1f}px; font-weight:{wt}; letter-spacing:-.02em; }}
#{{{{ID}}}} .{{{{ID}}}}-t i {{ font-size:{sim.px(24):.1f}px; line-height:{sim.px(24):.1f}px; font-style:normal; font-weight:{wt}; letter-spacing:.01em; }}
</style>""")
    open(os.path.join(d, "fx.html"), "w", encoding="utf-8").write("\n".join(html) + "\n")

    # ---- fx.js: one tl.set per frame per tile, unchanged frames skipped
    rows = []
    for i, seq in enumerate(dom):
        row, prev = [], None
        for n, e in enumerate(seq):
            cur = (0, 0, 0, 0) if e is None else (round(e[0] - Wt / 2, 1), round(e[1] - Ht / 2, 1), round(e[2], 1), e[3])
            if prev is None or cur != prev:
                row.extend([n, cur[0], cur[1], cur[2], cur[3]])
                prev = cur
        rows.append(row)
    js = ["// head-stack: written by gen.py from sim.py. Per tile: frame of the window, x, y, rotation, visible (0 on frames the motion blur in shadow.webm carries).",
          "var T = " + json.dumps(rows, separators=(",", ":")) + ";",
          "T.forEach(function (r, i) {",
          "  var s = '#{{ID}}-t' + i;",
          "  gsap.set(s, { opacity: 0 });",
          "  for (var k = 0; k < r.length; k += 5) tl.set(s, { x: r[k + 1], y: r[k + 2], rotation: r[k + 3], opacity: r[k + 4] }, q(A + r[k] / 30));",
          "});"]
    open(os.path.join(d, "fx.js"), "w", encoding="utf-8").write("\n".join(js) + "\n")
    print("sets:", sum(len(r) // 5 for r in rows), "fx.js", os.path.getsize(os.path.join(d, "fx.js")), "webm", os.path.getsize(os.path.join(d, "shadow.webm")))
    json.dump([dict(t=f["t"], on=f["on"], x=f["x"], y=f["y"], v=f["v"], label=l) for f, l in zip(first, labels) if f],
              open(os.path.join(sim.WORK, "stack_contacts.json"), "w"), indent=1)
    # the sound, from the sim's real contacts: every first impact (on the head or a tile: tick; on clothes: pop), the
    # harder secondary hits, then the collapse
    sfx, last = [], -1.0
    for f, l in zip(first, labels):
        if f:
            sfx.append((round(f["t"], 3), "pop" if f["on"] == "body" and f["y"] > support[0].min() + sim.px(200) else "tick", -12, f"{l} lands"))
    for t, i, kind, rel in S.get("events", []):
        if rel > 450 and t - last > 0.05 and t < B and all(abs(t - s[0]) > 0.04 for s in sfx):
            sfx.append((round(t, 3), "tick", -15, f"{labels[i]} knocks"))
            last = t
    sfx += [(round(sim.RELEASE, 3), "impact-low", -17, "the pile gives out"), (round(sim.RELEASE + 0.12, 3), "whoosh-deep", -15, "the tower goes")]
    print("SFX (time, name, dB, what):", sorted(sfx))


if __name__ == "__main__":
    main()
