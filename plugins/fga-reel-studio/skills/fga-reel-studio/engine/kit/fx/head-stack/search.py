#!/usr/bin/env python3
"""head-stack search: the sim is chaotic (a millimetre at one drop changes the whole pile), so try many aim points and
seeds for a run that keeps the pile on the speaker until the release and clears frame by the end. Writes the winner
into this folder's sim.py (TARGETS and SEED, between the search markers) and prints the best few.
Run: PY fx/<id>/search.py <project> [<id>] [--n 120] [--workers 6]    (gen.py runs it when TARGETS is empty)
"""
import argparse
import math
import multiprocessing as mp
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import sim  # noqa: E402

HEAD_DX = 0.08              # face widths either side of the head centre a head tile is aimed at
SHOULDER_DX = (0.0, 0.25)   # face widths in from a shoulder a shoulder tile is aimed at


def shoulders_usable():
    """both shoulders in frame and above the caption band, so tiles can rest there; else every tile goes on the head"""
    y, _, pose = sim.load_boundary()
    k = len(y) // 2
    l, r = sim.shoulders(pose, k)
    ok = []
    for x in (l, r):
        xi = int(np.clip(x, 0, sim.W - 1))
        ok.append(sim.TILE_W / 2 <= x <= sim.W - sim.TILE_W / 2 and y[k][xi] < 1300)
    return all(ok)


def head_room():
    """how many tiles stack on the head before the tower reaches the top safe zone (y 185)"""
    y, _, _ = sim.load_boundary()
    return int((float(np.median(y.min(axis=1))) - 185) / sim.px(sim.TILE_H))


def plan(n, rng, sides, room):
    """where each tile goes: the shipped order (head, left, right, head, left, head, right, head, either, head...),
    a side swapped now and then; no more on the head than fit under the top of the frame (at least one), the rest on
    the shoulders; all on the head when the shoulders can't hold a tile"""
    if not sides:
        return "C" * n
    base = ("C" + "LRCLCRCXC" * (n // 9 + 1))[:n]
    out, on_head = [], 0
    for ch in base:
        if ch == "C" and on_head >= max(1, room):
            ch = "X"
        if ch == "X" or (ch in "LR" and rng.random() < 0.3):
            ch = rng.choice("LR")
        on_head += ch == "C"
        out.append(ch)
    return "".join(out)


def make(rng, sides, room):
    targets = []
    for ch in plan(len(sim.TILES), rng, sides, room):
        if ch == "C":
            targets.append(("head", round(rng.uniform(-HEAD_DX, HEAD_DX), 4)))
        else:
            targets.append(("left" if ch == "L" else "right", round(rng.uniform(*SHOULDER_DX), 4)))
    return targets


def score(cfg):
    targets, seed = cfg
    sim.SEED = seed
    try:
        spawn = sim.solve(targets, verbose=False)
    except SystemExit:
        return -999, cfg, {}
    first, rec, capt = sim.run(spawn)
    y, _, pose = sim.load_boundary()
    xc, top, _, _ = sim.head_motion(y)
    px, Wt = sim.px, sim.TILE_W
    tp = sim.RELEASE - 0.21                                  # the pile just before it goes
    k = int(np.clip((tp - sim.A) * 240, 0, len(rec) - 1))
    st = [p for p in rec[k] if p]
    n = int(np.clip((tp - sim.A) * 30, 0, len(y) - 1))
    xh, apex = xc[n], top[n]
    f = pose[n]["face"]
    inframe = [p for p in st if Wt / 2 - px(30) < p[0] < sim.W and p[1] < 1500]
    cap = [p for p in st if abs(p[0] - xh) < px(200) and p[1] < apex + px(160)]
    left = [p for p in st if p[0] < xh - px(200) and apex + px(240) < p[1] < 1500 and p[0] > 0]
    right = [p for p in st if p[0] > xh + px(200) and apex + px(240) < p[1] < 1500 and p[0] < sim.W]
    moving = sum(1 for p in st if math.hypot(p[3], p[4]) > px(500))
    st0 = [p for p in rec[int(np.clip((tp - 0.22 - sim.A) * 240, 0, len(rec) - 1))] if p]
    moving0 = sum(1 for p in st0 if math.hypot(p[3], p[4]) > px(500))          # readable for the whole hold, not only at its end
    ytop = min((p[1] for p in st), default=999)
    late_spawn = [i for i, s in enumerate(spawn) if s["t"] <= sim.A + 1e-6]
    miss = sum(1 for i, fc in enumerate(first) if fc is None or (i not in late_spawn and abs(fc["t"] - sim.DROP_T[i]) > 0.02))
    k2 = int(np.clip((sim.B - 0.03 - sim.A) * 240, 0, len(rec) - 1))
    late = sum(1 for p in rec[k2] if p and p[1] < sim.H + px(85) and -px(80) < p[0] < sim.W + px(80))
    ang = [abs(math.degrees(p[2]) % 180 - (180 if math.degrees(p[2]) % 180 > 90 else 0)) for p in inframe]
    tilted = sum(1 for a in ang if a > 38)
    flipped = sum(1 for p in st if math.cos(p[2]) < 0)                          # upside-down labels read badly at this speed
    onface = sum(1 for p in st if abs(p[0] - xh) < px(90) + Wt / 2 and f["top"] < p[1] < f["chin"])
    capx = np.std([p[0] for p in cap]) if len(cap) > 1 else 0
    capa = np.std([p[2] for p in cap]) if len(cap) > 1 else 0
    # a tile that first touched up high but finished on a shoulder: the slide-off moment
    at = rec[k]
    slid = sum(1 for i, fc in enumerate(first) if fc and at[i] and fc["y"] < apex + px(40) and at[i][1] > apex + px(240) and 0 < at[i][0] < sim.W)
    sides = any(t[0] != "head" for t in targets)
    s = 3.0 * len(inframe) + min(len(cap), 5) + 1.5 * min(len(left), 3) + 1.5 * min(len(right), 3) \
        - (4 * max(0, 1 - len(left)) + 4 * max(0, 1 - len(right)) if sides else 0) - 4 * miss - 5 * late - moving - moving0 - tilted \
        - 3 * flipped - 3 * onface + min(capx / px(6.0), 2.0) + min(capa * 18, 1.5) + 2.5 * min(slid, 1) - max(0, 185 - ytop) * 0.08
    return s, cfg, dict(n=len(inframe), cap=len(cap), left=len(left), right=len(right), miss=miss, late=late, slid=slid,
                        ytop=round(ytop), tilted=tilted, flipped=flipped, onface=onface, moving=moving)


def init(project, fid, tile_w, radius):
    sim.setup(project, fid, tile_w, radius, quiet=True)


def write_winner(targets, seed):
    """the winner into this folder's sim.py, between the search markers (never into the kit's library copy)"""
    if os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "build.py")):
        sys.exit("this is the kit's library folder: copy it to <project>/fx/<id>/ and run the copy")
    path = os.path.join(HERE, "sim.py")
    src = open(path, encoding="utf-8").read()
    a, b = "# ---- search ----\n", "# ---- end search ----\n"
    i, j = src.index(a) + len(a), src.index(b)
    body = "TARGETS = [" + ",\n           ".join(repr(t) for t in targets) + "]\n" + f"SEED = {seed}\n"
    open(path, "w", encoding="utf-8").write(src[:i] + body + src[j:])
    sim.TARGETS, sim.SEED = targets, seed


def search(project, fid, n=120, workers=6):
    sim.load_boundary()
    sim.head_motion(sim.load_boundary()[0])
    sides = shoulders_usable()
    room = head_room()
    rng = random.Random(4242)
    cfgs = [(make(rng, sides, room), rng.randint(1, 99)) for _ in range(n)]
    if sides and room < 3:
        print(f"the head sits high: room for {max(0, room)} tile(s) above it, so at most {max(1, room)} goes there and the rest on the shoulders")
    print(f"searching {n} piles on {workers} workers" + ("" if sides else " (the shoulders can't hold a tile: all on the head)"), flush=True)
    with mp.get_context("spawn").Pool(workers, initializer=init, initargs=(project, fid, sim.TILE_W, sim.TILE_R)) as pool:
        res = []
        for i, r in enumerate(pool.imap_unordered(score, cfgs)):
            res.append(r)
            if (i + 1) % 20 == 0:
                print(i + 1, "best", round(max(x[0] for x in res), 2), flush=True)
    res.sort(key=lambda r: -r[0])
    for r in res[:5]:
        print(round(r[0], 2), r[1][1], r[2])
    best = res[0]
    write_winner(best[1][0], best[1][1])
    print("winner written to", os.path.join(HERE, "sim.py"))
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    import gen
    gen.kit_pipeline()
    project = os.path.abspath(os.path.expanduser(args.project))
    sim.setup(project, args.id)
    search(project, args.id, args.n, args.workers)


if __name__ == "__main__":
    main()
