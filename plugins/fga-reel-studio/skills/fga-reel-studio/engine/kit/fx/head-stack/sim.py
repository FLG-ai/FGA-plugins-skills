#!/usr/bin/env python3
"""head-stack physics: real rigid bodies on the speaker's real silhouette. Every frame the top edge of the matte
becomes a chain of kinematic segments in pymunk, moving with the speaker's actual velocity, so the pile rides the head,
slips when they lean, and gets shoved when the head swings into a tile. 240 Hz, deterministic. Each tile is timed by
shooting: re-simulate until its FIRST contact lands on its word. Every distance is in units of the face width
(track.json), so the same numbers hold on a close-up and on a wide shot.
gen.py runs this (and search.py when TARGETS is empty); run gen.py, not this.
"""
import json
import math
import os
import re
import sys

import numpy as np

# ---- the table: everything that belongs to one video. The window comes from the FX entry, times from words.json.
TILES = ["9 AM", "10 AM", "11 AM", "12 PM", "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM"]   # labels, in landing order
LANDS_ON = None             # the spoken word each tile lands on; None = the window's words, one tile per word, spread evenly
RELEASE_ON = None           # the spoken word the pile gives out on; None = the last word 0.5 to 0.9 s before the window ends
TOPPLE = None               # the side the tower goes off (+1 = image right); None = the side with more room
# ---- search.py writes the next two lines: where each tile is aimed (relative to the head or a shoulder, in face
# widths) and the seed of the run that keeps the pile on the speaker. Empty = gen.py runs the search first
# ---- search ----
TARGETS = None
SEED = 23
# ---- end search ----

FPS, SUB = 30, 8            # 240 Hz
W, H = 1080, 1920
FACE_REF = 299.0            # px: the face width the physics below was tuned at; everything in px scales from it
TILE_H, TILE_R0 = 66, 12    # px at FACE_REF; the width fits the longest label (tile_size), the corner is the pack's
G = 10500.0                 # px/s^2 at FACE_REF: a 23 cm head is about 350 px, so true gravity is 15000; this reads as weight
G_FALL = 13000.0            # from the release on: it has to clear frame by the end of the line
V_TERM = 3000.0             # terminal velocity of a light card, px/s, until the release
SOFT_BODY, SOFT_HEAD, SOFT_TILE = 0.90, 0.965, 0.985   # per 240 Hz step while touching: clothes swallow a landing, a card barely does
COLUMN = 12                 # px between chain vertices
SEG_RADIUS = 3.0
SINK = 6.0                  # px the collider sits below the matte edge: a tile presses in, and a matte's edge is soft anyway
MU_TILE, MU_HEAD, MU_BODY = 0.78, 0.95, 2.0     # chipmunk multiplies the pair: tile on head .74, tile on clothes 1.56, tile on tile .61
E_TILE, E_HEAD, E_BODY = 0.5, 0.4, 0.22         # restitution multiplies too
PLATEAU = 24                # px the crown is shaved in the collider: a round head (or a hat's peak) would never hold a tile

P = A = B = RELEASE = WORK = None     # set by setup()
K = 1.0                     # px scale: the take's face width / FACE_REF
TILE_W = 156.0
TILE_R = TILE_R0
DROP_T = []                 # when each tile lands (its word)
FW = 299.0


def px(v):
    """a distance tuned at FACE_REF, on this take"""
    return v * K


def rnd(i):
    x = math.sin(i * 12.9898 + SEED * 78.233) * 43758.5453
    return x - math.floor(x)


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def setup(project, fid, tile_w=None, radius=None, quiet=False):
    """the take: window, words, scale. gen.py and search.py call this before anything else"""
    global P, A, B, RELEASE, WORK, K, TILE_W, TILE_R, DROP_T, FW
    import fxlib
    P = project
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    WORK = os.path.join(project, "work", fid)
    os.makedirs(WORK, exist_ok=True)
    words = [(s, t) for s, e, t in fxlib.words(project)]
    tr = fxlib.tracks(project)["frames"]
    fws = [tr[n]["face"]["w"] for n in range(round(A * FPS), min(len(tr), round(B * FPS))) if tr[n].get("face")]
    if not fws:
        sys.exit("no face in work/tracks/track.json inside this window: run pipeline/track.py")
    FW = float(np.median(fws))
    K = FW / FACE_REF
    TILE_W, TILE_R = tile_size(project) if tile_w is None else (tile_w, radius)
    TILE_R = float(min(TILE_R, px(TILE_H) / 2 - 1))
    # the release: a word near the end, else 0.64 s before the window ends
    if RELEASE_ON:
        RELEASE = next((s for s, t in words if A < s < B and norm(t) == norm(RELEASE_ON)), None)
        if RELEASE is None:
            sys.exit(f"RELEASE_ON {RELEASE_ON!r} is not spoken in the window")
    else:
        RELEASE = next((s for s, t in reversed(words) if B - 0.9 <= s <= B - 0.5), B - 0.64)
    # the landings: one word each
    n = len(TILES)
    if LANDS_ON:
        DROP_T, after = [], A
        for w in LANDS_ON:
            t = next((s for s, tx in words if after <= s < RELEASE and norm(tx) == norm(w)), None)
            if t is None:
                sys.exit(f"LANDS_ON: {w!r} is not spoken before the release, after the words before it")
            DROP_T.append(t)
            after = t + 0.01
        if len(DROP_T) != n:
            sys.exit(f"LANDS_ON has {len(DROP_T)} words for {n} tiles")
    else:
        cand = [s for s, t in words if A + 0.25 <= s <= RELEASE - 0.35]
        thin = []
        for s in cand:                                  # tiles need about 0.15 s between landings to read as separate hits
            if not thin or s - thin[-1] >= 0.15:
                thin.append(s)
        if len(thin) >= n:
            DROP_T = [thin[round(i * (len(thin) - 1) / max(1, n - 1))] for i in range(n)]
        else:
            a, b = A + 0.3, RELEASE - 0.35
            DROP_T = [a + (b - a) * i / max(1, n - 1) for i in range(n)]
            if not quiet:
                print(f"only {len(thin)} words for {n} tiles: they land evenly spaced from {a:.2f} to {b:.2f}")


def split(label):
    """the big part and the small part of a label: "9 AM" -> "9", "AM" (a number and its unit)"""
    a, _, b = label.partition(" ")
    return a, b


def tile_size(project):
    """(width, corner radius) in px: wide enough for the longest label in the pack's mono face, the pack's corner"""
    import fxlib
    pk = fxlib.pack(project)
    f1, f2 = fxlib.font(project, "mono", int(round(px(42)))), fxlib.font(project, "mono", int(round(px(24))))
    text = max(f1.getlength(a) + (px(7) + f2.getlength(b) if b else 0) for a, b in map(split, TILES))
    radius = float(pk.get("grounds", {}).get("radius", TILE_R0)) * K
    return max(px(156), text + px(70)), radius


_cache = {}


def load_boundary():
    """per-frame top edge of the matte, cleaned: (support with the plateau, raw silhouette, per-frame track). Cached in work/"""
    if "b" in _cache:
        return _cache["b"]
    import fxlib
    from scipy.ndimage import gaussian_filter1d, median_filter
    c = os.path.join(WORK, f"tops_{round(A * FPS)}_{round(B * FPS)}.npy")
    if os.path.exists(c):
        tops = np.load(c)
    else:
        tops = []
        for _, al in fxlib.alpha(P, A, B):
            m = al > 128
            tops.append(np.where(m.any(0), m.argmax(0), H).astype(np.float32))
        tops = np.array(tops)
        np.save(c, tops)
    y = median_filter(tops, size=(1, 11))                   # hair wisps and matte crumbs out, across x
    y = gaussian_filter1d(y, 0.8, axis=1, mode="nearest")
    y = gaussian_filter1d(y, 0.7, axis=0, mode="nearest")   # a touch in time: the matte shimmers, the head does not
    tr = fxlib.tracks(P)["frames"]
    n0 = round(A * FPS)
    pose = []
    for k in range(len(y)):
        e = tr[n0 + k] if n0 + k < len(tr) else {}
        pose.append(dict(face=e.get("face"), pose=e.get("pose"), hands=e.get("hands", [])))
    fill(pose, "face")
    fill(pose, "pose")
    raw = y.copy()
    # the crown comes to a peak (or a hat's top does): shave it to a plateau that tilts with the roll, or a tile could never rest there
    roll = gaussian_filter1d(np.array([p["face"]["roll"] if p.get("face") else 0.0 for p in pose]), 1.5, mode="nearest")
    xs = np.arange(W)
    for k in range(len(y)):
        f = pose[k]["face"]
        a0, a1 = int(max(0, f["cx"] - 1.2 * f["w"])), int(min(W, f["cx"] + 1.2 * f["w"]))
        apex = y[k][a0:a1].min()
        s = np.where(y[k] < apex + px(40))[0]
        xa = s.mean()
        line = apex + px(PLATEAU) + np.tan(np.radians(roll[k])) * (xs - xa)
        span = np.abs(xs - xa) < px(170)
        y[k][span] = np.maximum(y[k][span], line[span])
    y = gaussian_filter1d(y, 2.5 * K, axis=1, mode="nearest") + px(SINK)
    raw = gaussian_filter1d(raw, 2.5 * K, axis=1, mode="nearest") + px(SINK)
    _cache["b"] = (y, raw, pose)
    return _cache["b"]


def fill(rows, key):
    """a frame without a face or a pose borrows the nearest frame's"""
    have = [i for i, r in enumerate(rows) if r.get(key)]
    if not have:
        if key == "face":
            sys.exit("no face in work/tracks/track.json inside this window: run pipeline/track.py")
        for r in rows:                                  # no pose at all: shoulders a face width either side of the head
            f = r["face"]
            r["pose"] = dict(rs=[f["cx"] - 1.6 * f["w"], f["chin"] + .3 * f["h"]], ls=[f["cx"] + 1.6 * f["w"], f["chin"] + .3 * f["h"]])
        return
    for i, r in enumerate(rows):
        if not r.get(key):
            r[key] = rows[min(have, key=lambda j: abs(j - i))][key]


def head_motion(y):
    """the lateral velocity of the head outline, frame to frame: slide one profile over the next. Column heights alone
    only move vertically, and a pile would stay put while the head slides out from under it. This is what friction
    carries it with"""
    if "m" in _cache:
        return _cache["m"]
    from scipy.ndimage import gaussian_filter1d
    n = len(y)
    xc, top = np.zeros(n), np.zeros(n)
    for k in range(n):
        ap = y[k].min()
        s = np.where(y[k] < ap + px(150))[0]
        xc[k], top[k] = s.mean(), ap
    u = np.zeros(n)
    xs = np.arange(W)
    for k in range(n - 1):
        s = np.where(y[k] < y[k].min() + px(170))[0]
        a, b = s.min(), s.max()
        best, be = 0.0, 1e18
        for dx in np.arange(-px(26), px(26) + .01, max(0.5, px(0.5))):
            yy = np.interp(xs[a:b] + dx, xs, y[k + 1])
            d = yy - y[k][a:b]
            e = np.abs(d - np.median(d)).sum()
            if e < be:
                be, best = e, dx
        u[k] = best
    if n > 1:
        u[-1] = u[-2]
    u = gaussian_filter1d(u, 1.2, mode="nearest")
    _cache["m"] = (xc, top, u * FPS, np.gradient(gaussian_filter1d(top, 1.0, mode="nearest")) * FPS)
    return _cache["m"]


def shoulders(pose, k):
    """image-left and image-right shoulder x on frame k (the speaker's right shoulder is on the image left)"""
    p = pose[min(k, len(pose) - 1)]["pose"]
    return p["rs"][0], p["ls"][0]


def topple_side():
    """+1 = the tower goes off image right: the side with more room past the shoulder, unless TOPPLE says"""
    if TOPPLE:
        return TOPPLE
    y, _, pose = load_boundary()
    xc = head_motion(y)[0]
    n = int(np.clip(round((RELEASE - A) * FPS), 0, len(y) - 1))
    return 1.0 if xc[n] <= W / 2 else -1.0


def aim(target, n, pose, xc):
    """a target -> x on frame n. ("head", dx): dx face widths from the head centre; ("left" | "right", dx): dx face widths
    in from that shoulder"""
    kind, dx = target
    if kind == "head":
        return xc[n] + dx * FW
    l, r = shoulders(pose, n)
    return l + dx * FW if kind == "left" else r - dx * FW


def run(spawn, upto=None):
    """one simulation. spawn[i] = dict(x, y, t, v0). Returns (first contact per tile, poses at 240 Hz, tiles on the head at the release)"""
    import pymunk
    from scipy.ndimage import gaussian_filter1d
    y, raw, pose = load_boundary()
    xc, top, uh, vh = head_motion(y)
    ul = np.gradient(gaussian_filter1d(np.array([shoulders(pose, k)[0] for k in range(len(pose))]), 1.5, mode="nearest")) * FPS
    ur = np.gradient(gaussian_filter1d(np.array([shoulders(pose, k)[1] for k in range(len(pose))]), 1.5, mode="nearest")) * FPS
    col = max(4, int(round(px(COLUMN))))
    xs = np.clip(np.arange(0, W + 1, col), 0, W - 1)
    space = pymunk.Space()
    space.gravity = (0, px(G))
    space.iterations = 40
    space.collision_slop = 0.3 * K
    segs = []
    for j in range(len(xs) - 1):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        s = pymunk.Segment(b, (float(xs[j]), 0.0), (float(xs[j + 1]), 0.0), px(SEG_RADIUS))
        s.collision_type = 1
        s.elasticity = E_BODY
        s.friction = MU_BODY
        space.add(b, s)
        segs.append((b, s))
    n_t = len(spawn)
    tiles = [None] * n_t                    # by tile index; a tile exists from its own spawn time, whatever the order
    first = [None] * n_t
    now = [0.0]
    events = []
    th = px(TILE_H)

    def begin(arb, sp, data):
        a_, b_ = arb.shapes
        ta_, tb_ = getattr(a_, "tile", None), getattr(b_, "tile", None)
        rel = math.hypot(*(a_.body.velocity - b_.body.velocity))
        events.append((now[0], ta_ if ta_ is not None else tb_, "tile" if (ta_ is not None and tb_ is not None) else "body", rel / K))
        for sh in arb.shapes:
            t = getattr(sh, "tile", None)
            if t is not None and first[t] is None:
                other = arb.shapes[0] if arb.shapes[1] is sh else arb.shapes[1]
                first[t] = dict(t=now[0], x=float(sh.body.position.x), y=float(sh.body.position.y),
                                on="tile" if getattr(other, "tile", None) is not None else "body", v=float(abs(sh.body.velocity.y)))
    touch = {}

    def post(arb, sp, data):
        a, b = arb.shapes
        for sh, ot in ((a, b), (b, a)):
            t = getattr(sh, "tile", None)
            if t is not None:
                kind = 3 if getattr(ot, "tile", None) is not None else (1 if ot.friction == MU_BODY else 2)
                touch.setdefault(t, []).append((kind, ot))
    space.on_collision(2, 1, begin=begin, post_solve=post)
    space.on_collision(2, 2, begin=begin, post_solve=post)
    rec = []
    dt = 1.0 / (FPS * SUB)
    nf = len(y) - 1
    released = False
    cap_at_release = []
    side = topple_side()
    for n in range(nf):
        ya, yb = y[n][xs], y[n + 1][xs]
        ra, rb = raw[n][xs], raw[n + 1][xs]
        s0 = np.where(y[n] < y[n].min() + px(170))[0]
        ha, hb = s0.min(), s0.max()
        for sub in range(SUB):
            t = A + n / FPS + (sub + 1) * dt
            now[0] = t
            f = (sub + 1) / SUB
            yt = (ra + (rb - ra) * f) if released else (ya + (yb - ya) * f)
            vcol = (yb - ya) * FPS
            for j, (b, s) in enumerate(segs):
                x0, x1 = float(xs[j]), float(xs[j + 1])
                mid = 0.5 * (x0 + x1)
                steep = abs(yt[j + 1] - yt[j]) > 1.6 * (x1 - x0)
                inhead = ha <= mid <= hb
                u = uh[n] if inhead else (ul[n] if mid < ha else ur[n])
                v = vh[n] if steep else float(np.clip(0.5 * (vcol[j] + vcol[j + 1]), -px(1400), px(1400)))
                s.friction = (0.02 if released else MU_HEAD) if inhead else MU_BODY
                s.elasticity = E_HEAD if inhead else E_BODY
                if released and not (ha - px(30) <= mid <= hb + px(30)):
                    ya_, yb_ = H + 1100.0, H + 1100.0      # the shoulders are gone
                else:
                    ya_, yb_ = float(yt[j]), float(yt[j + 1])
                b.position = (-u * dt, -v * dt)    # kinematic bodies integrate first: this lands exactly on the matte at collide time
                b.velocity = (u, v)
                s.unsafe_set_endpoints((x0, ya_), (x1, yb_))
            for i in range(n_t):
                if tiles[i] is not None or spawn[i]["t"] > t:
                    continue
                body = pymunk.Body(1.0, pymunk.moment_for_box(1.0, (TILE_W, th)))
                body.position = (spawn[i]["x"], spawn[i]["y"])
                body.angle = (rnd(i * 3 + 1) - 0.5) * 0.14
                body.angular_velocity = (rnd(i * 5 + 2) - 0.5) * 1.0
                body.velocity = (0, spawn[i].get("v0", 0.0))
                shp = pymunk.Poly.create_box(body, (TILE_W - 2 * TILE_R, th - 2 * TILE_R), radius=TILE_R)
                shp.collision_type = 2
                shp.elasticity = E_TILE
                shp.friction = MU_TILE
                shp.tile = i
                space.add(body, shp)
                tiles[i] = body
            live = [(i, b) for i, b in enumerate(tiles) if b is not None]
            # the release: side piles lose their floor, the tower on the head topples off past the ear (the head stays solid: nothing crosses the face)
            if not released and t >= RELEASE and live:
                released = True
                space.gravity = (0, px(G_FALL))
                for _, body in live:
                    for shp in body.shapes:
                        shp.friction = 0.3
                xh = xc[n]
                on_cap = [(body.position.y, i) for i, body in live
                          if abs(body.position.x - xh) < px(200) and body.position.y < y[n][int(np.clip(body.position.x, 0, W - 1))] + px(5)]
                for level, (_, i) in enumerate(sorted(on_cap, reverse=True)):
                    body = tiles[i]
                    cap_at_release.append(i)
                    body.velocity = (side * px(900 + 210 * level + 90 * rnd(i * 7 + 3)), body.velocity.y - px(240 + 60 * level))
                    body.angular_velocity = side * (4.0 + 2.6 * level + 2.0 * rnd(i * 11 + 5))
                for i, body in live:
                    if i not in cap_at_release:
                        sd = 1.0 if body.position.x >= xh else -1.0
                        body.velocity = (body.velocity.x + sd * px(40 + 220 * rnd(i * 7 + 3)), body.velocity.y)
                        body.angular_velocity = body.angular_velocity + sd * (3.0 + 8.0 * rnd(i * 11 + 5))
            if not released:
                for _, body in live:               # air drag: light cards, they don't hit like bricks
                    v = body.velocity
                    sp_ = math.hypot(v.x, v.y)
                    body.velocity = v * (1.0 - min(0.5, px(G) / (px(V_TERM) ** 2) * sp_ * dt))
            touch.clear()
            space.step(dt)
            if not released:
                for i, hits in touch.items():
                    kind = min(h[0] for h in hits)
                    body = tiles[i]
                    d = {1: SOFT_BODY, 2: SOFT_HEAD, 3: SOFT_TILE}[kind]
                    body.angular_velocity = body.angular_velocity * d
                    if kind < 3:
                        ot = [h[1] for h in hits if h[0] == kind][0]
                        vs = ot.body.velocity
                        body.velocity = vs + (body.velocity - vs) * (0.5 + 0.5 * d)
            rec.append([None if b is None else (float(b.position.x), float(b.position.y), float(b.angle), float(b.velocity.x), float(b.velocity.y), float(b.angular_velocity)) for b in tiles])
            if upto is not None and first[upto] is not None:
                return first, rec, cap_at_release
    _cache["events"] = events
    return first, rec, cap_at_release


def solve(targets, verbose=True):
    """shooting: for each tile in order, move its release until its first contact lands on its word"""
    y, _, pose = load_boundary()
    xc, _, _, _ = head_motion(y)
    spawn = []
    for i, tgt in enumerate(targets):
        tw = DROP_T[i]
        n = int(np.clip(round((tw - A) * FPS), 0, len(y) - 1))
        x = float(np.clip(aim(tgt, n, pose, xc), TILE_W / 2, W - TILE_W / 2))
        ys = -px(TILE_H) - px(40) * rnd(i * 13 + 6)
        fall = math.sqrt(2 * max(px(100), y[n][int(np.clip(x, 0, W - 1))] - ys) / px(G))     # a first guess at the fall
        v0 = px(900.0) if tw - fall < A else 0.0           # it has to be on its way already when the window opens
        spawn.append(dict(x=x, y=float(ys), t=max(A, tw - fall), v0=v0))
    for i in range(len(targets)):
        for it in range(6):
            future = [dict(x=0, y=0, t=99)] * (len(targets) - i - 1)
            first, _, _ = run(spawn[:i + 1] + future, upto=i)
            f = first[i]
            if f is None:
                raise SystemExit(f"tile {i} never lands")
            e = f["t"] - DROP_T[i]
            if verbose:
                print(f"  tile {i} {TILES[i]:>12} iter {it}: lands {f['t']:.3f} on {f['on']} at x{f['x']:.0f} y{f['y']:.0f}  err {e * 1000:+.1f} ms")
            if abs(e) < 0.0045:
                break
            if spawn[i]["t"] - e < A:            # it can't leave before the window opens: it was already falling, faster
                spawn[i]["v0"] = spawn[i].get("v0", 0.0) + px(1800) * min(1.0, (A - (spawn[i]["t"] - e)) / 0.1)
            spawn[i]["t"] = max(A, spawn[i]["t"] - e)
    return spawn


def main(targets=None):
    targets = targets or TARGETS
    if not targets:
        sys.exit("no TARGETS yet: run search.py (gen.py does it for you)")
    spawn = solve(targets)
    first, rec, capt = run(spawn)
    out = dict(spawn=spawn, first=first, cap=capt, events=_cache.get("events", []), rec=rec, labels=list(TILES),
               tile=[TILE_W, px(TILE_H), TILE_R], drop_t=DROP_T, release=RELEASE)
    json.dump(out, open(os.path.join(WORK, "stack_sim.json"), "w"))
    print("on the head at the release:", capt)
    return out
