#!/usr/bin/env python3
"""post-wall: every day the speaker posted, as a calendar heat grid on the wall behind them.

One square per day, oldest at the bottom and newest on top like a feed, one row per calendar month. The empty calendar
draws up the wall, then the squares land in date order, faster and faster, each behind a one-frame light leading edge,
while a mono counter rolls to the total the speaker says; the last square pops in the accent on the word. The
speaker's cast shadow falls across the squares (only the squares). Flat squares in the pack's dark, light and accent.
On a tripod shot with the room plate, two optional pieces: something on the wall comes off for the beat (HOLE), and
furniture standing in front of the wall stays in front of the squares (FRONT).

Honest by construction: the days come from the creator's own dates (DATES, or a small JSON in the project). A day
before the dates reach (FROM) is a dim outline, never a zero. TOTAL and DAYS are what the speaker says on camera; what
the dates can't see (other platforms, older history) is spread evenly over the days so the counter lands on TOTAL, so
only the end value is a claim. With no dates at all it draws a seeded placeholder set and its legend says so.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>, layer "behind", a CUT_WINDOWS entry over it), words.json,
          timeline.json (picture cuts, the crop), the dates (DATES / DATA), work/tracks/track.json (where the head
          is, for the room's falloff), and only for HOLE / FRONT the room plate (room_<FRAME>.npy) and depth
  writes  <project>/fx/<id>/fx.html, fx.js (+ patch.webm for HOLE, mask.png for FRONT); prints the sounds and checks
<id> defaults to this script's folder name. Rerun it whenever the window, the cut, the dates or the numbers change.
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN_KIT = os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "fxlib.py"))   # this copy is the kit library's, not a project's
FPS = 30

# ---- the one table: the numbers, the dates, the words
TOTAL, DAYS = 0, 0          # what the speaker says on camera ("1,200 posts in 400 days"); 0 = what the dates say
END = ""                    # the last day of those DAYS, "YYYY-MM-DD"; '' = the last date in the data, else today
DATES = []                  # the creator's post dates, "YYYY-MM-DD", one entry per post (a day posted twice: twice)
DATA = "work/post_dates.json"   # or a JSON in the project: a list like DATES, {"from": day, "dates": [...]} or {day: n}
FROM = ""                   # the first day the dates cover; days before it are dim outlines ('' = the first date)
GRID_ON = ""                # the spoken word the empty calendar draws on; '' = 0.07s after A
FILL_ON = ""                # the fill starts on this word; '' = 0.12s after the calendar
SNAP_ON = ""                # the last square pops on this word; '' = the last word starting 0.35s or more before B
K = 1.65                    # acceleration of the fill: 1 = even, 2 = a slower start
LABELS = dict(day="DAY", posts="POSTS", nodata="NO DATA", placeholder="PLACEHOLDER DATA")

# ---- layout (frame px on the 1080x1920 canvas)
PITCH = None                # square pitch; None = 32, smaller when there are too many months to fit above MAX_Y
Y0 = 270                    # the top row (the newest month), under the counter
MAX_Y = 1250                # the grid and its legend stay above this (the captions band starts at 1300)
SHADOW = dict(dx=72, dy=34, blur=32, opacity=.6)    # the speaker's cast shadow on the squares; None = none
LIGHT_AT = None             # (x, y): a warm light in the room, squares near it warm a little; None = none
IN, OUT = "auto", "auto"    # "cut": in (out) with the picture cut; "wipe": wipes up the wall; auto = cut if A (B) is on one
WIPE = 0.14                 # s, the wipe in and out
# ---- tripod + room plate only (the room as room_<FRAME>.npy from the plate tools)
FRAME = ""                  # the crop over the window; '' = the one the video is in at A
HOLE = None                 # (x0, y0, x1, y1): something on the wall comes off for the beat, filled from the wall around it
FEATHER = 24
FRONT = []                  # [(x0, y0, x1, y1), ...]: furniture in front of the wall; inside each box, whatever depth says
                            # is nearer than the wall stays in front of the squares

LIB_HTML = ("<!-- LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run\n"
            "     gen.py on the project: it rewrites this file from that video's words, voice and footage. -->\n")
LIB_JS = ("// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run\n"
          '// gen.py on the project: it rewrites this file.\n')


try:
    import fxlib                      # setup puts the kit's pipeline on PY's import path
except ImportError:                   # an older setup, or the effects lab: REEL_KIT, else the kit this folder came from
    for _k in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        if _k and os.path.exists(os.path.join(_k, "pipeline", "fxlib.py")):
            sys.path.insert(0, os.path.join(os.path.abspath(_k), "pipeline"))
            break
    import fxlib
from common import load_edit  # noqa: E402  (fxlib puts the kit's pipeline on the path)


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def rnd(i):
    x = math.sin(i * 12.9898) * 43758.5453
    return x - math.floor(x)


def day(s):
    return date.fromisoformat(str(s)[:10])


def load_dates(project):
    """-> (Counter of posts per day, the first day the data covers, where they came from) or (None, None, None)"""
    dates, frm, src = list(DATES), FROM, "DATES"
    path = os.path.join(project, DATA) if DATA else ""
    if not dates and path and os.path.exists(path):
        d, src = json.load(open(path)), DATA
        if isinstance(d, dict) and ("dates" in d or "days" in d):
            frm = frm or d.get("from", "")
            dates = d.get("dates") or [k for k, n in d.get("days", {}).items() for _ in range(int(n))]
        elif isinstance(d, dict):                                    # {day: posts}
            dates = [k for k, n in d.items() for _ in range(int(n))]
        else:
            dates = d
    if not dates:
        return None, None, None
    n = Counter(day(x).isoformat() for x in dates)
    return n, day(frm) if frm else min(day(x) for x in n), src


def cut_windows(E, TLJ, A, B):
    """what the cutout needs: None when CUT_WINDOWS already cover A..B (they may skip a cut frame), else the entries to
    add, split at every picture cut inside the window (a cutout window never crosses one)"""
    t = A
    for a, b in sorted(getattr(E, "CUT_WINDOWS", [])):
        if a <= t + 1.02 / FPS and b > t:
            t = b
    if t >= B - 0.02:
        return None
    cuts = inner_cuts(TLJ, A, B)
    ends, out = [A] + cuts + [B], []
    for k, (a, b) in enumerate(zip(ends, ends[1:])):
        out.append((round(a + (1 / FPS if k else 0), 4), round(b, 4)))   # the cut frame itself gets no cutout: on that
    return out                                                           # frame the footage can still show the shot before


def inner_cuts(TLJ, A, B):
    """picture cuts (and reframes) strictly inside the window"""
    return sorted(c for c in TLJ.get("picture_cuts", []) + TLJ.get("reframes", []) if A + 0.04 < c < B - 0.04)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    F = fxlib.entry(project, fid)
    TLJ = json.load(open(os.path.join(project, "timeline.json")))
    A, B = float(F["at"]), float(F["end"])
    if F.get("layer", "top") != "behind":
        print(f"{fid} is on layer {F.get('layer', 'top')!r}: it is built for 'behind' (the speaker in front of the wall)")
    if inner_cuts(TLJ, A, B):
        print(f"picture cut(s) at {', '.join(f'{c:.2f}' for c in inner_cuts(TLJ, A, B))} inside the window: the wall sits each cut "
              "frame out" + (" and HOLE belongs to one shot: keep the window inside one" if HOLE else ""))
    need = cut_windows(E, TLJ, A, B)
    if need:
        print(f"add CUT_WINDOWS over the window or the speaker is behind the wall: {', '.join(str(w) for w in need)}")
    words = fxlib.words(project) if os.path.exists(os.path.join(project, "words.json")) else []

    def on(w, after, fallback):
        t = next((s for s, e, x in words if w and s >= after - 0.001 and norm(x) == norm(w)), None)
        if w and (t is None or t >= B):
            print(f"{w!r} is not spoken after {after:.2f} in the window: falling back to {fallback:.2f}")
        return fallback if t is None or t >= B else t

    grid = on(GRID_ON, A, A + 0.07)
    fill = on(FILL_ON, grid, grid + 0.12)
    late = [s for s, e, x in words if fill + 0.6 <= s <= B - 0.35]
    snap = on(SNAP_ON, fill + 0.3, late[-1] if late else B - 0.6)
    if snap - fill < 0.5:
        print(f"the fill only has {snap - fill:.2f}s ({fill:.2f} to {snap:.2f}): give it a longer line or move SNAP_ON")

    # ---- days and their posts
    counts, frm, src = load_dates(project)
    placeholder = counts is None
    end = day(END) if END else (max(day(x) for x in counts) if counts else date.today())
    ndays = DAYS or ((end - min(day(x) for x in counts)).days + 1 if counts else 365)
    start = end - timedelta(days=ndays - 1)
    days = [start + timedelta(days=i) for i in range(ndays)]
    if placeholder:                    # seeded and labelled: the look, never a claim
        counts = Counter({d.isoformat(): int(rnd(i) < 0.72) + int(rnd(i + 999) < 0.18) + int(rnd(i + 77) < 0.04) * 3
                          for i, d in enumerate(days)})
        frm = start
        print("NO DATES: a seeded PLACEHOLDER set is drawn and the legend says so. Put the creator's post dates in "
              f"DATES or {DATA} before this goes in a video")
    seen = sum(counts.get(d.isoformat(), 0) for d in days)
    total = TOTAL or seen
    months = []
    for d in days:
        if (d.year, d.month) not in months:
            months.append((d.year, d.month))
    rows = len(months)

    # ---- layout: 31 columns centred, pitch from how many months must fit above MAX_Y
    pitch = PITCH or max(12, min(32, int((MAX_Y - Y0 - 34) / (rows + 1))))
    if not PITCH and (MAX_Y - Y0 - 34) / (rows + 1) < 12:
        print(f"{rows} months don't fit above y {MAX_Y} at a readable size: show fewer DAYS")
    s = pitch / 32                                            # type and strokes scale with the squares
    sq = round(pitch * 27 / 32)
    x0 = round((1080 - (31 * pitch - (pitch - sq))) / 2)
    right = x0 + 31 * pitch - (pitch - sq)
    # the labels: DAY in the top row right after the newest days, the counter over the top row's empty right end.
    # When the newest month runs under them, the grid drops a row and they sit in the row it freed
    newest = days[-1].day
    day_w = (3 * 22 * 1.14 + 10 + len(str(ndays)) * 34) * 0.62 * s
    post_w = (len(f"{total:,}") * 66 + 5 * 22 * 1.14) * 0.62 * s + 12 * s
    shared = x0 + newest * pitch + 10 * s + day_w + 24 * s < right - post_w
    # the labels sit behind the speaker too: where the speaker reaches during the window, a label can't go
    occ = np.zeros((1920, 1080), bool)
    if os.path.exists(os.path.join(project, "public", "subject.webm")):
        for k, (_, al) in enumerate(fxlib.alpha(project, A, B)):
            if k % 3 == 0:
                occ |= al > 128

    def hidden(x, y, w, h):
        box = occ[max(0, int(y)):int(y + h), max(0, int(x)):int(x + w)]
        return box.size and box.mean() > 0.02
    if shared and hidden(x0 + newest * pitch + 10 * s, Y0 - 11 * s, day_w, 44 * s):
        shared = False                                        # the DAY label would sit behind the head: the far left instead
    if hidden(x0, Y0 - 11 * s, day_w, 44 * s) and not shared:
        print("the speaker covers the DAY label's spot at the top left: move the grid (Y0) or the window")
    if hidden(right - post_w, Y0 - 56 * s, post_w, 80 * s):
        print("the speaker covers the counter at the top right: move the grid (Y0) or the window")
    gy = Y0 if shared else Y0 + pitch                         # the top row's y
    day_xy = (x0 + newest * pitch + round(10 * s), gy - round(11 * s)) if shared else (x0, Y0 - round(11 * s))
    cells = []
    for i, d in enumerate(days):
        r = rows - 1 - months.index((d.year, d.month))      # the newest month on top
        n = counts.get(d.isoformat(), 0)
        cells.append(dict(i=i, x=x0 + (d.day - 1) * pitch, y=gy + r * pitch, n=n, nodata=d < frm and not n))
    bottom = gy + rows * pitch - (pitch - sq)

    # the room's light: squares dim away from the head (the track, else the frame's upper middle), warm near LIGHT_AT
    head = (540, 650)
    tpath = os.path.join(project, "work", "tracks", "track.json")
    if os.path.exists(tpath):
        fr = [f["face"] for f in json.load(open(tpath))["frames"][round(A * FPS):round(B * FPS)] if f and f.get("face")]
        if fr:
            head = (float(np.median([f["cx"] for f in fr])), float(np.median([f["cy"] for f in fr])))
    reach = 700 * s

    def light(c):
        cx, cy = c["x"] + sq / 2, c["y"] + sq / 2
        f = .80 + .20 * math.exp(-((cx - head[0]) ** 2 + (cy - head[1]) ** 2) / reach ** 2)
        w = math.exp(-((cx - LIGHT_AT[0]) ** 2 + (cy - LIGHT_AT[1]) ** 2) / (200 * s) ** 2) if LIGHT_AT else 0.0
        return round(f * 100), round(w * 100)

    def level(n):
        return 0 if n == 0 else 1 if n == 1 else 2 if n == 2 else 3 if n < 5 else 4

    # ---- timing: the frame each square lands (accelerating), the last one on the snap; the counter per frame
    f0, f1, fA = round(fill * FPS), round(snap * FPS), round(A * FPS)
    for c in cells:
        c["f"] = min(f1, f0 + int(round((f1 - f0) * (c["i"] / max(1, ndays - 1)) ** (1 / K))))
    cells[-1]["f"] = f1
    extra = total - seen
    if extra < 0:
        print(f"the dates show {seen} posts, more than TOTAL {total}: the counter still lands on {total}")
    counter, run = {}, 0.0
    for c in cells:
        run += c["n"] + extra / ndays
        counter[c["f"]] = (max(0, int(round(run))), c["i"] + 1)
    counter[f1] = (total, ndays)
    print(f"{ndays} days, {start} to {end}, {rows} months, pitch {pitch}; the dates ({src or 'placeholder'}) see {seen} "
          f"posts, the counter lands on {total}; {sum(c['nodata'] for c in cells)} days before the dates reach")

    # ---- the wall's own tone under the grid (the room, not the speaker): light type on a dark wall, ink on a light one;
    # the squares' ramp runs from the wall's tone towards the other end, so more posts always stand out more
    mid = (A + B) / 2
    rgb = next(fxlib.frames(project, mid, mid + 1 / FPS))[1].astype(np.float32)
    sub = os.path.join(project, "public", "subject.webm")
    al = next(fxlib.alpha(project, mid, mid + 1 / FPS))[1] if os.path.exists(sub) else np.zeros(rgb.shape[:2], np.uint8)
    y_a, y_b = max(0, Y0 - round(76 * s)), min(1920, bottom + round(36 * s))
    reg = rgb[y_a:y_b, x0:right]
    wall = (0.2126 * reg[..., 0] + 0.7152 * reg[..., 1] + 0.0722 * reg[..., 2])[al[y_a:y_b, x0:right] < 40]
    light_wall = bool(len(wall)) and float(np.median(wall)) > 140
    ink = "var(--c-ink)" if light_wall else "var(--c-light)"
    print(f"the wall under the grid is {'light' if light_wall else 'dark'} (median {float(np.median(wall)) if len(wall) else 0:.0f}): "
          f"{'ink' if light_wall else 'light'} type, squares {'darken' if light_wall else 'lighten'} with more posts")

    # ---- in and out: with the picture cut, or a wipe up the wall
    cuts = TLJ.get("picture_cuts", []) + TLJ.get("reframes", [])
    on_cut = lambda t: any(abs(t - c) < 1.5 / FPS for c in cuts)       # noqa: E731
    w_in = (IN if IN != "auto" else ("cut" if on_cut(A) else "wipe"))
    w_out = (OUT if OUT != "auto" else ("cut" if on_cut(B) else "wipe"))

    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)

    # ---- tripod pieces from the room plate
    patch_tag, wall_mask, hole_bottom = "", "", 0
    if HOLE or FRONT:
        frame = FRAME or fxlib.crop_at(project, A)
        if not os.path.exists(os.path.join(project, "work", "c", f"room_{frame}.npy")):
            print(f"HOLE / FRONT need the room behind the speaker in the {frame} crop (a tripod shot and the plate tools); "
                  "or set HOLE = None and FRONT = []")
        room = fxlib.room(project, frame).astype(np.float32)        # the room as the take saw it, at live levels
        import cv2
        if HOLE:
            # the thing comes off the wall: a Coons patch from the wall around the box, feathered, at live levels; a
            # clip with class g, so it takes the footage's path through the renderer and the same grade
            bx0, by0, bx1, by1 = HOLE
            w, h = bx1 - bx0, by1 - by0

            def edge(a):
                return cv2.GaussianBlur(a.reshape(-1, 1, 3), (0, 0), 14).reshape(-1, 3)
            top, bot = edge(room[by0:by0 + 6, bx0:bx1].mean(axis=0)), edge(room[by1 - 6:by1, bx0:bx1].mean(axis=0))
            lef, rig = edge(room[by0:by1, bx0:bx0 + 6].mean(axis=1)), edge(room[by0:by1, bx1 - 6:bx1].mean(axis=1))
            u = np.linspace(0, 1, w)[None, :, None]
            v = np.linspace(0, 1, h)[:, None, None]
            P = (1 - v) * top[None] + v * bot[None] + (1 - u) * lef[:, None] + u * rig[:, None] \
                - ((1 - u) * (1 - v) * top[0] + u * (1 - v) * top[-1] + (1 - u) * v * bot[0] + u * v * bot[-1])
            P = P + np.random.default_rng(7).normal(0, .5, (h, w, 1))          # the footage's own grain, roughly
            al = np.zeros((h, w), np.float32)
            al[FEATHER:-FEATHER, FEATHER:-FEATHER] = 1
            al = cv2.GaussianBlur(al, (0, 0), FEATHER / 2.2)
            rgba = np.dstack([np.clip(P, 0, 255), al * 255]).astype(np.uint8)
            wr = fxlib.Writer(os.path.join(out, "patch.webm"), w + w % 2, h + h % 2, alpha=True)
            pad = np.zeros((h + h % 2, w + w % 2, 4), np.uint8)
            pad[:h, :w] = rgba
            for _ in range(max(1, round(B * FPS) - fA)):
                wr.write(pad)
            wr.close()
            patch_tag = (f'<video id="@@-patch" class="g" src="fx/@@/patch.webm" muted playsinline data-start="{{{{START}}}}" '
                         f'data-media-start="0.0010" data-duration="{{{{DUR}}}}" data-track-index="{{{{T2}}}}" '
                         f'style="position:absolute;left:{bx0}px;top:{by0}px;width:{w + w % 2}px;height:{h + h % 2}px;"></video>')
            hole_bottom = by1
        if FRONT:
            import depth
            d = depth.infer(np.clip(room, 0, 255).astype(np.uint8))
            front = np.zeros(d.shape, np.float32)
            for fx0, fy0, fx1, fy1 in FRONT:
                # the wall is what runs round the box's edge (draw each box with plain wall all round the object). In
                # front: nearer than that wall (depth: a chair, a plant), or a different thing from it (colour: a lamp
                # on the wall is too flat for depth to see, but nothing like the paint behind it)
                box, col = d[fy0:fy1, fx0:fx1], room[fy0:fy1, fx0:fx1]
                ring = lambda a: np.concatenate([a[:6].reshape(-1, *a.shape[2:]), a[-6:].reshape(-1, *a.shape[2:]),
                                                 a[:, :6].reshape(-1, *a.shape[2:]), a[:, -6:].reshape(-1, *a.shape[2:])])
                near = np.clip((box - float(np.median(ring(box))) - 0.04) / 0.04, 0, 1)
                apart = np.clip((np.linalg.norm(col - np.median(ring(col), axis=0), axis=2) - 30) / 20, 0, 1)
                front[fy0:fy1, fx0:fx1] = np.maximum(near, apart)
                print(f"FRONT {(fx0, fy0, fx1, fy1)}: {100 * (front[fy0:fy1, fx0:fx1] > .5).mean():.0f}% of the box stays in front")
            front = (front > 0.5).astype(np.float32)                 # in front or not: a half-masked square reads as a ghost
            front = cv2.morphologyEx(front, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))     # no specks of wall texture
            front = cv2.GaussianBlur(cv2.dilate(front, np.ones((3, 3), np.uint8)), (0, 0), 1.6)
            chk = np.clip(room, 0, 255).astype(np.uint8).copy()          # check it: what stays in front, tinted
            chk[front > .5] = (0.45 * chk[front > .5] + [0, 140, 255]).clip(0, 255).astype(np.uint8)
            os.makedirs(os.path.join(project, "work", fid), exist_ok=True)
            cv2.imwrite(os.path.join(project, "work", fid, "front.jpg"), cv2.cvtColor(chk, cv2.COLOR_RGB2BGR)[::2, ::2])
            print(f"look at work/{fid}/front.jpg: the tinted parts stay in front of the squares")
            m = np.zeros(front.shape + (4,), np.uint8)
            m[..., 3] = (np.clip(1 - front, 0, 1) * 255).astype(np.uint8)
            from PIL import Image
            Image.fromarray(m).save(os.path.join(out, "mask.png"), optimize=True)
            wall_mask = ("-webkit-mask-image:url(fx/@@/mask.png); mask-image:url(fx/@@/mask.png); "
                         "-webkit-mask-size:1080px 1920px; mask-size:1080px 1920px;")
        print(f"room_{frame}.npy: " + ", ".join(
            x for x in ((f"HOLE {HOLE} -> patch.webm" if HOLE else ""), (f"FRONT {len(FRONT)} box(es) -> mask.png" if FRONT else "")) if x))

    # ---- markup
    rect = lambda c: f"M{c['x']} {c['y']}h{sq}v{sq}h-{sq}z"       # noqa: E731
    outline = "".join(f"M{c['x'] + .5} {c['y'] + .5}h{sq - 1}v{sq - 1}h-{sq - 1}z" for c in cells)
    shadow_mask = ("url(\"data:image/svg+xml," + "%3Csvg xmlns='http://www.w3.org/2000/svg' width='1080' height='1920'%3E"
                   "%3Cpath fill='white' d='" + "".join(rect(c) for c in cells if not c["nodata"]) + "'/%3E%3C/svg%3E\")")
    shadow = ""
    if SHADOW:
        shadow = (f'<div class="@@-shw">'
                  f'<video id="@@-shadow" src="subject.webm" muted playsinline data-start="{{{{START+0.0333}}}}" '
                  f'data-media-start="{{{{SYNC+0.0333}}}}" data-duration="{{{{DUR-0.0333}}}}" data-track-index="{{{{T1}}}}" '
                  f'style="position:absolute;left:{SHADOW["dx"]}px;top:{SHADOW["dy"]}px;width:1080px;height:1920px;'
                  f'filter:brightness(0) blur({SHADOW["blur"]}px);opacity:{SHADOW["opacity"]};"></video></div>')
    squares = "".join(f'<i id="@@-c{c["i"]}" class="@@-c{" @@-o" if c["nodata"] else ""}" style="left:{c["x"]}px;top:{c["y"]}px"></i>'
                      for c in cells)
    legend = LABELS["placeholder"] if placeholder else (LABELS["nodata"] if any(c["nodata"] for c in cells) else "")
    legend_y = bottom + round(8 * s)
    top_y = Y0 - round(76 * s)                                # the wipe's top: above the counter
    low_y = max(legend_y + round(28 * s), hole_bottom)        # its bottom: the lowest thing it carries
    esc = lambda x: x.replace("&", "&amp;").replace("<", "&lt;")      # noqa: E731
    html = f"""<!-- post-wall: written by gen.py (rerun it when the window, the cut, the dates or the numbers change). A square
     for every day on the wall behind the speaker, {"PLACEHOLDER data (no dates were given)" if placeholder else "from the creator's own dates"};
     the counter lands on the total the speaker says. Squares, type and lines in the pack's tokens. -->
<div class="@@-cutw" data-layout-allow-overlap data-layout-allow-occlusion>
<div class="@@-sheet" data-layout-allow-overlap data-layout-allow-occlusion>
{patch_tag}
<div class="@@-wall" data-layout-allow-overlap>
<svg class="@@-tpl" width="1080" height="1920" viewBox="0 0 1080 1920"><path d="{outline}"/></svg>
{squares}
{shadow}
</div>
</div>
<div class="@@-labels" data-layout-allow-overlap data-layout-allow-occlusion>
<div class="@@-day" data-layout-allow-overlap data-layout-allow-occlusion><span class="@@-dl" data-layout-allow-overlap data-layout-allow-occlusion>{esc(LABELS["day"])}</span> <span id="@@-d" data-layout-allow-overlap data-layout-allow-occlusion>{"1".rjust(len(str(ndays)), "0")}</span></div>
<div class="@@-post" data-layout-allow-overlap data-layout-allow-occlusion><span id="@@-n" data-layout-allow-overlap data-layout-allow-occlusion>0</span><span class="@@-pl" data-layout-allow-overlap data-layout-allow-occlusion>{esc(LABELS["posts"])}</span></div>
{f'<div class="@@-key" data-layout-allow-overlap data-layout-allow-occlusion>{"" if placeholder else "<i></i>"}{esc(legend)}</div>' if legend else ""}
</div>
</div>
<style>
#@@ .@@-cutw, #@@ .@@-sheet, #@@ .@@-labels, #@@ .@@-wall, #@@ .@@-shw {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
#@@ .@@-wall {{ {wall_mask} }}
#@@ .@@-shw {{ -webkit-mask-image:{shadow_mask}; mask-image:{shadow_mask}; -webkit-mask-size:1080px 1920px; mask-size:1080px 1920px; }}
#@@ .@@-tpl {{ position:absolute; left:0; top:0; opacity:0; }}
#@@ .@@-tpl path {{ fill:none; stroke:{ink}; stroke-opacity:{'.24' if light_wall else '.17'}; stroke-width:1; }}
#@@ .@@-c {{ position:absolute; display:block; width:{sq}px; height:{sq}px; opacity:0; }}
#@@ .@@-o {{ box-shadow:inset 0 0 0 {max(1, round(2 * s * 2) / 2)}px color-mix(in srgb, {ink} 42%, transparent); }}
#@@ .@@-day, #@@ .@@-post {{ position:absolute; font-family:var(--font-mono); color:{ink}; white-space:nowrap; opacity:0;
  font-variant-numeric:tabular-nums; }}
#@@ .@@-day {{ left:{day_xy[0]}px; top:{day_xy[1]}px; font-size:{round(34 * s)}px; line-height:{round(44 * s)}px; font-weight:600; letter-spacing:.02em; }}
#@@ .@@-dl {{ font-size:{round(22 * s)}px; letter-spacing:.14em; font-weight:500; }}
#@@ .@@-post {{ right:{1080 - right}px; top:{Y0 - round(56 * s)}px; font-size:{round(66 * s)}px; line-height:{round(80 * s)}px; font-weight:600;
  letter-spacing:-.01em; text-align:right; }}
#@@ .@@-pl {{ font-size:{round(22 * s)}px; letter-spacing:.14em; font-weight:500; margin-left:{round(12 * s)}px; }}
#@@ .@@-key {{ position:absolute; left:{x0}px; top:{legend_y}px; font-family:var(--font-mono); font-weight:500; font-size:{max(13, round(18 * s))}px;
  line-height:{max(18, round(24 * s))}px; letter-spacing:.14em; color:color-mix(in srgb, {ink} 62%, transparent); white-space:nowrap; opacity:0; }}
#@@ .@@-key i {{ display:inline-block; width:{max(11, round(16 * s))}px; height:{max(11, round(16 * s))}px; margin-right:{round(10 * s)}px; vertical-align:-2px;
  box-shadow:inset 0 0 0 {max(1, round(2 * s * 2) / 2)}px color-mix(in srgb, {ink} 50%, transparent); }}
</style>
"""
    cells_js = [[c["f"] - fA, -1 if c["nodata"] else level(c["n"]), *light(c)] for c in cells]
    reach_js, hi = [], 1920                                   # [frame after A, the top of the highest landed square]
    for c in sorted(cells, key=lambda c: c["f"]):
        if c["y"] < hi:
            if reach_js and reach_js[-1][0] == c["f"] - fA:
                reach_js[-1][1] = c["y"]
            else:
                reach_js.append([c["f"] - fA, c["y"]])
            hi = c["y"]
    count_js = sorted([f - fA, n, dd] for f, (n, dd) in counter.items())
    js = f"""// post-wall: written by gen.py (rerun it when the window, the cut, the dates or the numbers change). The calendar
// draws up the wall, a square per day lands in date order, faster and faster, the counter rolls to the total, the last
// square pops in the accent on the word. Frames are counted from A's frame; colours are the pack's tokens.
var R = '#{{{{ID}}}}-', S = '#{{{{ID}}}} .{{{{ID}}}}-', FPS = 30, F0 = Math.round(A * FPS);
var T = {{ grid: {grid - A:.4f}, out: {B - A - WIPE:.4f} }};   // s after A: the calendar draws, the wipe out starts
var IN = '{w_in}', OUT = '{w_out}', WIPE = {WIPE}, CLIP = [{top_y}, {low_y}];   // the wipe runs between these two lines (y px)
var CUTF = {json.dumps([round(c * FPS) - fA for c in inner_cuts(TLJ, A, B)])};   // picture cuts inside the window
var LIGHT_WALL = {'true' if light_wall else 'false'};   // read off the footage: the squares' ramp and the leading edge run away from the wall's tone
var PAD = {len(str(ndays))};
// per day, oldest first: [frame after A it lands, level 0-4 by posts that day (-1 = before the dates reach), room light %, warm %]
var CELLS = {json.dumps(cells_js, separators=(',', ':'))};
var COUNT = {json.dumps(count_js, separators=(',', ':'))};   // [frame after A, the counter, the day]
var REACH = {json.dumps(reach_js, separators=(',', ':'))};   // [frame after A, y]: the shadow reaches no higher than the squares
var LAST = CELLS.length - 1;
function at(f) {{ return q((F0 + f) / FPS); }}
function tok(n) {{ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }}
function rgb(c) {{
  if (c[0] === '#') {{
    if (c.length === 4) c = '#' + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
    return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
  }}
  var m = c.match(/[\\d.]+/g);
  return m && m.length >= 3 ? [+m[0], +m[1], +m[2]] : [128, 128, 128];
}}
function mix(a, b, t) {{ return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }}
var DK = rgb(tok('--c-dark')), LT = rgb(tok('--c-light')), AC = tok(LIGHT_WALL ? '--c-accent-light' : '--c-accent');
var LO = LIGHT_WALL ? LT : DK, HI = LIGHT_WALL ? DK : LT, EDGE = LIGHT_WALL ? rgb(tok('--c-ink')) : LT;
var LEVEL = [LO, mix(LO, HI, 0.38), mix(LO, HI, 0.68), HI, rgb(AC)];   // none, 1, 2, 3-4, 5+ posts that day
function colour(c) {{
  var v = LEVEL[c[1]], f = c[2] / 100, w = c[3] / 100;
  var k = [f * (1 + 0.10 * w), f * (1 + 0.01 * w), f * (1 - 0.12 * w)];
  return 'rgb(' + v.map(function (x, i) {{ return Math.max(0, Math.min(255, Math.round(x * k[i]))); }}).join(',') + ')';
}}
function comma(n) {{ return String(n).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ','); }}
function pad(n) {{ var s = String(n); while (s.length < PAD) s = '0' + s; return '\\u200b' + s; }}

// in: with the picture cut, or one wipe up the wall that carries the squares, the patch, the shadow and the labels
tl.set([S + 'day', S + 'post', S + 'key'], {{ opacity: 1 }}, q(A + T.grid));
tl.fromTo(S + 'tpl', {{ opacity: 1, clipPath: 'inset(100% 0px 0px 0px)' }}, {{ clipPath: 'inset(0% 0px 0px 0px)', duration: 0.2, ease: 'power2.out', immediateRender: false }}, q(A + T.grid));
if (IN === 'wipe') {{
  gsap.set([S + 'sheet', S + 'labels'], {{ clipPath: 'inset(' + CLIP[1] + 'px 0px 0px 0px)' }});
  tl.fromTo([S + 'sheet', S + 'labels'], {{ clipPath: 'inset(' + CLIP[1] + 'px 0px 0px 0px)' }}, {{ clipPath: 'inset(' + CLIP[0] + 'px 0px 0px 0px)', duration: WIPE, ease: 'power2.out', immediateRender: false }}, q(A));
}}
if (OUT === 'wipe') {{          // the same wipe carries on upward and hands the wall back
  tl.fromTo([S + 'sheet', S + 'labels'], {{ clipPath: 'inset(' + CLIP[0] + 'px 0px ' + (1920 - CLIP[1]) + 'px 0px)' }}, {{ clipPath: 'inset(' + CLIP[0] + 'px 0px ' + (1920 - CLIP[0]) + 'px 0px)', duration: WIPE, ease: 'power1.in', immediateRender: false }}, q(A + T.out));
}}

// a picture cut inside the window: on its frame the footage can still show the shot before and no cutout plays, so
// the wall sits that one frame out (never over the head)
CUTF.forEach(function (f) {{ tl.set(S + 'cutw', {{ opacity: 0 }}, at(f)); tl.set(S + 'cutw', {{ opacity: 1 }}, at(f + 1)); }});

// the squares land behind a one-frame light leading edge
CELLS.forEach(function (c, i) {{
  if (i === LAST) return;
  var el = R + 'c' + i;
  if (c[1] < 0) {{ tl.set(el, {{ opacity: 1 }}, at(c[0])); return; }}
  tl.set(el, {{ opacity: 1, backgroundColor: 'rgb(' + EDGE.join(',') + ')' }}, at(c[0]));
  tl.set(el, {{ backgroundColor: colour(c) }}, at(c[0] + 1));
}});
// the speaker's shadow falls on the squares that have landed (its mask is the filled squares; this clip keeps it
// off the rows still to come)
if (document.querySelector(S + 'shw')) {{
  gsap.set(S + 'shw', {{ clipPath: 'inset(1920px 0px 0px 0px)' }});
  REACH.forEach(function (r) {{ tl.set(S + 'shw', {{ clipPath: 'inset(' + r[1] + 'px 0px 0px 0px)' }}, at(r[0])); }});
}}
COUNT.forEach(function (c) {{
  tl.set(R + 'n', {{ textContent: comma(c[1]) }}, at(c[0]));
  tl.set(R + 'd', {{ textContent: pad(c[2]) }}, at(c[0]));
}});

// the last square pops in the accent on the word, the counter lands with it
var L = R + 'c' + LAST, SNAP = CELLS[LAST][0];
gsap.set(L, {{ backgroundColor: AC, transformOrigin: '50% 50%' }});
tl.set(L, {{ opacity: 1 }}, at(SNAP));
tl.fromTo(L, {{ scale: 3.6 }}, {{ scale: 1, duration: 0.2, ease: 'back.out(1.7)', immediateRender: false }}, at(SNAP));
tl.set([R + 'n', R + 'd'], {{ color: AC }}, at(SNAP));
gsap.set(R + 'n', {{ display: 'inline-block', transformOrigin: '100% 100%' }});
tl.fromTo(R + 'n', {{ scale: 1.14 }}, {{ scale: 1, duration: 0.2, ease: 'back.out(1.8)', immediateRender: false }}, at(SNAP));
"""
    lib = IN_KIT and os.path.realpath(out) == os.path.realpath(HERE)   # writing into the library itself (the effects lab)
    with open(os.path.join(out, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write((LIB_HTML if lib else "") + html.replace("@@", "{{ID}}"))
    with open(os.path.join(out, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write((LIB_JS if lib else "") + js)
    for stale, need in (("patch.webm", HOLE), ("mask.png", FRONT), ("tpl.png", False), ("room.png", False)):
        p = os.path.join(out, stale)
        if not need and os.path.exists(p) and not (IN_KIT and os.path.realpath(out) == os.path.realpath(HERE)):
            os.remove(p)

    # ---- sound: a tick per frame the fill moves, rising into the snap
    ticks = sorted({c["f"] for c in cells[:-1]})
    print(f"wrote {out}/fx.html + fx.js: in {w_in}, out {w_out}; grid {grid:.2f}, fill {fill:.2f} to {snap:.2f}, "
          f"{len(ticks)} frames of fill")
    print("SOUND sfx (time = the visual event):")
    print(f'    ({grid + 0.05:.3f}, "whoosh-soft", -17),   # the calendar draws up the wall')
    print(f'    ({snap:.3f}, "pop", -14),   # the last square pops')
    print(f'    ({snap:.3f}, "ding", -19),   # the counter lands')
    print(f'    ({snap:.3f}, "impact-low", -17),')
    tick = [(round(f / FPS, 3), "tick", round(-22 + 6 * (f - ticks[0]) / max(1, ticks[-1] - ticks[0]), 1)) for f in ticks]
    print(f"    # and a tick per frame the fill moves ({len(tick)}), rising into the snap:")
    print("    " + ", ".join(repr(t) for t in tick) + ",")
    print(f"frames=[{(fill + snap) / 2:.2f}, {snap + 0.1:.2f}, {min(B - 0.1, snap + 0.45):.2f}]")


if __name__ == "__main__":
    main()
