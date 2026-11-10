#!/usr/bin/env python3
"""Plate, second pass: the room as layers and files for every crop in edit.FRAMES, colour matched to clean.mp4.
Run plate.py first. Everything here is measured off the take itself, so nothing is set per shoot.

- The static foreground: anything nearer the camera than the speaker that never moves (a desk edge, a mic, its stand),
  found with depth on frames across the take. Above the desk's top edge it is the mic layer (drawn over the speaker),
  below it the desk layer (drawn under the speaker, over the room). Nothing in front of the speaker: both layers are
  empty (transparent), never missing.
- Per crop, a curve from the plate to clean.mp4's true levels, measured on room pixels of that crop's own frames
  (pixels near the speaker are left out: their colour bleeds into the room).
Layers are video, not stills: a still takes a different path through the browser than the footage and lands levels off.

-> public/plates/plate_<FRAME>.mp4 (+ .jpg), desk_<FRAME>.webm, mic_<FRAME>.webm      stack: plate, desk, subject, mic
   work/c/room_<FRAME>.npy         float32 HxWx3 RGB at live levels: the room as the take saw it (the speaker in place)
   work/c/room_empty_<FRAME>.npy   the empty room alone (the speaker gone or moved); the same as room_<FRAME> when
                                   there was no empty room to film
   work/c/lut_<FRAME>.npy          256x3 float32: plate value -> live level
   work/c/mic_<FRAME>.npy          HxWx5 float32: the foreground's live colour (median of the take), its alpha, solid alpha
   work/c/plate_clean.png, plate_pure.png    the room and the empty room at source size (BGR)
   work/plate/near.png, fg.png, check.jpg    what depth saw, the static foreground, a sheet to look at per crop
Run: PY pipeline/plate_finish.py <project> [--fill image [--box x0,y0,x1,y1]] [--bg-frame] [--near 0.62] [--desk-y 1690] [--no-desk] [--no-mic]
  --fill     no empty room: a photo of the room from the camera's spot, or a background generated from --bg-frame's
             frame (or any picture of what the speaker hides), colour matched into the patch the take never saw.
             plate.json's mode becomes "filled", which effects treat like a filmed empty room. --box x0,y0,x1,y1
             places it on part of the source frame
  --bg-frame writes work/plate/bg_frame.png, the frame where the speaker covers the least of the room, at the source
             size, and prints the prompt for an image model to make the room without them (then --fill the result)
  --near     a fixed depth threshold (0..1): whatever stays nearer than it on every sampled frame is foreground
  --desk-y   the desk's top edge as a flat line (px on the canvas of the widest crop) instead of the fitted one
  --no-desk, --no-mic   blank a layer the finder got wrong (look at work/plate/check.jpg)
"""
import json
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import depth  # noqa: E402
import fxlib  # noqa: E402
from common import load_edit, project_arg, timeline  # noqa: E402
from plate import knot_curve, read_src, src_time  # noqa: E402

FPS = 30
MARGIN = 0.06             # depth (0..1) a thing must be nearer than most of the speaker to count as in front of them
BG_PROMPT = ("Remove the person from this photo, along with anything they hold or wear, and show the empty room behind "
             "them. Keep the camera position, framing, lens, lighting, colours and every other object exactly as they are, "
             "including anything in front of the person such as a desk or a microphone. Fill only what the person covered, "
             "continuing the wall, furniture and objects around them as they would really be. Photorealistic: the same "
             "photo with the person gone, nothing added.")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def spread(spans, n):
    """n times spread over the spans, by length"""
    total = sum(b - a for a, b in spans)
    out = []
    for a, b in spans:
        m = max(1, round(n * (b - a) / total))
        out += [a + (b - a) * (i + 0.5) / m for i in range(m)]
    return out


def fill_hole(P, plate, hole):
    """--fill: an image of what the speaker hides, colour matched on a ring around the hole and blended into it"""
    x0, y0, x1, y1 = (int(v) for v in arg("--box").split(",")) if arg("--box") else (0, 0, plate.shape[1], plate.shape[0])
    path = arg("--fill") if os.path.isabs(arg("--fill")) else os.path.join(P, arg("--fill"))
    g = cv2.imread(path)
    if g is None:
        sys.exit(f"--fill: can't read {path}")
    g = cv2.resize(cv2.cvtColor(g, cv2.COLOR_BGR2RGB), (x1 - x0, y1 - y0), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
    reg = plate[y0:y1, x0:x1].astype(np.float32)
    hr = (hole[y0:y1, x0:x1] > 0).astype(np.uint8)
    if not hr.any():
        print("--fill: the take saw the whole room, nothing to fill")
        return plate
    r = max(6, round(max(plate.shape[:2]) * 0.005))    # the median keeps a thin rim of the speaker just past the hole
    disc = lambda d: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))   # noqa: E731
    ring = (cv2.dilate(hr, disc(7 * r)) - cv2.dilate(hr, disc(4 * r))).astype(bool)        # level match, past the blend
    gain = (reg[ring].mean(axis=0) + 1) / (g[ring].mean(axis=0) + 1)
    print("fill gain", gain.round(3))
    g = np.clip(g * gain, 0, 255)
    g += np.random.default_rng(7).normal(0, 1.6, g.shape[:2])[..., None]   # the footage's own noise: no smoother patch
    a = cv2.GaussianBlur(cv2.dilate(hr, disc(2 * r)).astype(np.float32), (0, 0), r / 2)[..., None]  # covers that rim
    plate[y0:y1, x0:x1] = np.clip(reg * (1 - a) + g * a, 0, 255).astype(np.uint8)
    return plate


def foreground(P, E, TL, widest, spans, SW, SH):
    """the static foreground on the widest crop's canvas: (mask 0..1 float, desk line per column or None, near map,
    the take's median colour at source size inside that crop, how often the speaker covers each pixel, where they
    ever are)"""
    cw, ch, cx, cy = E.FRAMES[widest]
    times = spread(spans, 24)
    near, votes, n, colour, cover, ever = None, None, 0, [], None, None
    for t in times:
        rgb = next(fxlib.frames(P, t, t + 1 / FPS))[1]
        al = next(fxlib.alpha(P, t, t + 1 / FPS))[1]
        d = depth.infer(rgb)
        near = d if near is None else np.minimum(near, d)
        cover = (al > 128).astype(np.int16) if cover is None else cover + (al > 128)
        ever = al.copy() if ever is None else np.maximum(ever, al)
        body = d[al > 128]
        if body.size > 2000:                 # in front of the speaker = nearer than most of them, on this frame
            v = (d > np.percentile(body, 75) + MARGIN).astype(np.int16)
            votes = v if votes is None else votes + v
            n += 1
        colour.append(read_src(E.SRC, src_time(TL, t), SW, SH)[cy:cy + ch, cx:cx + cw])
    colour = np.median(np.stack(colour), axis=0).astype(np.uint8)
    if arg("--near"):
        mask = (near > float(arg("--near"))).astype(np.uint8)
    elif n:
        mask = (votes >= np.ceil(0.85 * n)).astype(np.uint8)       # in front on (nearly) every frame: it doesn't move
    else:
        mask = np.zeros(near.shape, np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    k, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    H, W = mask.shape
    for i in range(1, k):                    # specks are depth noise, not things
        if stats[i, cv2.CC_STAT_AREA] < 0.0015 * H * W:
            mask[lab == i] = 0
    # the desk: a foreground piece along the bottom edge, wider than a third of the frame. Its top edge, fitted as a
    # line (a mic stand rising out of it doesn't pull the line up), splits desk (below) from mic (above)
    line = None
    if arg("--desk-y"):
        line = np.full(W, float(arg("--desk-y")))
    else:
        k, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for i in range(1, k):
            x, y, w, h, _ = stats[i]
            if y + h >= H - 2 and w > W / 3:
                cols = np.arange(x, x + w)
                tops = np.array([np.argmax(lab[:, c] == i) for c in cols], np.float32)
                keep = tops >= np.percentile(tops, 10)
                for _ in range(3):           # drop what sticks up out of the desk (a stand, a hand), refit
                    p = np.polyfit(cols[keep], tops[keep], 1)
                    res = tops - np.polyval(p, cols)
                    keep = res > -max(6.0, 2.5 * np.std(res[keep]))
                fit = np.polyval(p, np.arange(W)) - 4
                line = fit if line is None else np.minimum(line, fit)
    return mask.astype(np.float32), line, near, colour, cover / max(1, len(times)), ever > 128


def layer_video(png, out, seconds, alpha):
    """a still as a video of `seconds` (the renderer treats stills differently from footage), levels as fxlib.Writer"""
    if alpha:
        codec = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "14", "-row-mt", "1", "-deadline",
                 "good", "-cpu-used", "3", "-auto-alt-ref", "0", "-g", "30", *fxlib.ENCODE]
    else:
        codec = ["-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", "-g", "30", *fxlib.ENCODE,
                 "-movflags", "+faststart"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.0f}", "-i", png,
                    *codec, out], check=True)


def bg_frame(P, E, TL, SW, SH, WD):
    """--bg-frame: the frame of the take where the speaker covers the least of the room, at the source size, for an
    image model to make the room without them; its result goes back in with --fill"""
    shots = [(s["t"], s["frame"]) for s in TL["shots"]] + [(TL["total"], None)]
    spans = {k: [(a, b) for (a, f), (b, _) in zip(shots, shots[1:]) if f == k and b - a > 2 / FPS] for k in E.FRAMES}
    widest = max((k for k in E.FRAMES if spans[k]), key=lambda k: E.FRAMES[k][0])
    best = None
    for t in spread(spans[widest], 24):
        c = float((next(fxlib.alpha(P, t, t + 1 / FPS))[1] > 128).mean())
        if best is None or c < best[0]:
            best = (c, t)
    out = os.path.join(WD, "bg_frame.png")
    cv2.imwrite(out, cv2.cvtColor(read_src(E.SRC, src_time(TL, best[1]), SW, SH), cv2.COLOR_RGB2BGR))
    g = np.gcd(SW, SH)
    print(f"wrote {out}: the take at {best[1]:.2f}s, where the speaker covers {best[0]:.0%} of the {widest} crop "
          f"({SW}x{SH}, {SW // g}:{SH // g})")
    print(f"Make one image with the connected image model: this frame as the reference, aspect ratio {SW // g}:{SH // g}, "
          f"high quality, and this prompt:\n{BG_PROMPT}")
    print(f"Save it as {os.path.join(P, 'assets', 'background.png')}, then run this again with "
          "--fill assets/background.png and look at work/plate/check.jpg")


def main():
    P = project_arg()
    E = load_edit(P)
    TL = timeline(P)
    WD = os.path.join(P, "work", "plate")
    if not os.path.exists(os.path.join(WD, "plate_src.png")):
        sys.exit("run plate.py first: PY pipeline/plate.py <project>")
    info = json.load(open(os.path.join(WD, "plate.json"))) if os.path.exists(os.path.join(WD, "plate.json")) else {}
    plate = cv2.cvtColor(cv2.imread(os.path.join(WD, "plate_src.png")), cv2.COLOR_BGR2RGB)
    hole = cv2.imread(os.path.join(WD, "hole.png"), 0)
    pure_path = os.path.join(WD, "room_pure.png")
    pure = cv2.cvtColor(cv2.imread(pure_path), cv2.COLOR_BGR2RGB) if info.get("mode") == "empty" and os.path.exists(pure_path) else None
    SH, SW = plate.shape[:2]
    if "--bg-frame" in sys.argv:
        return bg_frame(P, E, TL, SW, SH, WD)
    if arg("--fill"):
        if pure is not None:
            print("--fill: there is an empty room already, the fill is not needed and was skipped")
        else:
            plate = fill_hole(P, plate, hole)
            cv2.imwrite(os.path.join(WD, "plate_src.png"), cv2.cvtColor(plate, cv2.COLOR_RGB2BGR))
            info.update(fill=arg("--fill"), mode="filled")       # the patch is a real picture now: effects treat it as the room
            json.dump(info, open(os.path.join(WD, "plate.json"), "w"), indent=1)
    shots = [(s["t"], s["frame"]) for s in TL["shots"]] + [(TL["total"], None)]

    def spans_of(name):
        return [(a, b) for (a, f), (b, _) in zip(shots, shots[1:]) if f == name and b - a > 2 / FPS]
    used = [k for k in E.FRAMES if spans_of(k)]
    widest = max(used, key=lambda k: E.FRAMES[k][0])
    cw, ch, cx, cy = E.FRAMES[widest]
    CW, CH = E.CANVAS

    # ---- the static foreground, on the widest crop the video uses, then on the source frame so every crop can use it
    mask, line, near, colour, frac, ever = foreground(P, E, TL, widest, spans_of(widest), SW, SH)
    cv2.imwrite(os.path.join(WD, "near.png"), (near * 255).astype(np.uint8))
    rows = np.arange(mask.shape[0])[:, None]
    below = rows >= line[None, :] if line is not None else np.zeros(mask.shape, bool)
    desk_m = mask * below * (0 if "--no-desk" in sys.argv else 1)
    # the mic layer is drawn over the speaker, so only what is really in front of them: nothing they ever pass in
    # front of (a hand over a lamp says the lamp is behind), nothing that lies wholly where they always are (their
    # own knee, the chair arm the matte took with them), and only pieces that touch where they are (a thing off to
    # the side is in the plate already; over the speaker it could only go wrong)
    passes = (frac > 0.03) & (frac < 0.9)
    mic = ((mask > 0) & ~below).astype(np.uint8)
    near_them = cv2.dilate(ever.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
    k, lab, _, _ = cv2.connectedComponentsWithStats(mic, 8)
    for i in range(1, k):
        piece = lab == i
        if ((passes & piece).sum() > 0.05 * piece.sum() or not (near_them & piece).any()
                or (frac[piece] > 0.5).mean() > 0.85):
            mic[piece] = 0
    mic_m = mic.astype(np.float32) * (0 if "--no-mic" in sys.argv else 1)
    cv2.imwrite(os.path.join(WD, "fg.png"), np.dstack([np.zeros_like(mask), desk_m * 255, mic_m * 255]).astype(np.uint8))
    print(f"foreground: desk {desk_m.mean() * 100:.1f}% of the frame, mic {mic_m.mean() * 100:.1f}%"
          + ("" if (desk_m.any() or mic_m.any()) else " (nothing in front of the speaker: empty desk and mic layers)"))

    def to_src(m):                           # widest-crop canvas -> source frame
        big = cv2.GaussianBlur(cv2.resize(m.astype(np.float32), (cw, ch), interpolation=cv2.INTER_LINEAR), (0, 0), 1.6)
        out = np.zeros((SH, SW), np.float32)
        out[cy:cy + ch, cx:cx + cw] = np.clip(big * 1.5 - 0.25, 0, 1)[:SH - cy, :SW - cx]
        return out
    desk_s, mic_s = to_src(desk_m), to_src(mic_m)
    colour_s = plate.copy()
    colour_s[cy:cy + ch, cx:cx + cw] = colour[:SH - cy, :SW - cx]

    # ---- per crop: the curve to live levels, the room files, the layers
    pub = os.path.join(P, "public", "plates")
    work = os.path.join(P, "work", "c")
    os.makedirs(pub, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    cv2.imwrite(os.path.join(work, "plate_clean.png"), cv2.cvtColor(plate, cv2.COLOR_RGB2BGR))
    if pure is not None:
        cv2.imwrite(os.path.join(work, "plate_pure.png"), cv2.cvtColor(pure, cv2.COLOR_RGB2BGR))
    elif os.path.exists(os.path.join(work, "plate_pure.png")):
        os.remove(os.path.join(work, "plate_pure.png"))
    seconds = max(20, TL["total"] + 1)

    def cut(img, w, h, x, y, interp=cv2.INTER_LANCZOS4):
        if img.ndim == 2:
            return cv2.resize(img[y:y + h, x:x + w], (CW, CH), interpolation=cv2.INTER_LINEAR)
        return cv2.resize(img[y:y + h, x:x + w], (CW, CH), interpolation=interp if w < 1.3 * CW else cv2.INTER_AREA)
    luts, checks, measured = {}, [], {}
    for name in sorted(E.FRAMES, key=lambda k: (k != widest, k not in used)):   # the widest first: others may borrow its curve
        w, h, x, y = E.FRAMES[name]
        room = cut(plate, w, h, x, y)
        empty = cut(pure, w, h, x, y) if pure is not None else room
        fg = np.maximum(cut(desk_s, w, h, x, y), cut(mic_s, w, h, x, y))
        fg_out = cv2.dilate((fg > 0.03).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
        fg_out |= cut((hole > 0).astype(np.float32), w, h, x, y) > 0.01     # the curve is measured where the take saw the room
        stack, oks = [], []
        for t in spread(spans_of(name), 30) if name in used else []:
            n = round(t * FPS)
            stack.append(next(fxlib.frames(P, n / FPS, (n + 1) / FPS))[1])
            al = next(fxlib.alpha(P, n / FPS, (n + 1) / FPS))[1]
            oks.append((cv2.dilate((al > 8).astype(np.uint8), np.ones((61, 61), np.uint8)) == 0) & ~fg_out)
        ident = np.tile(np.arange(256, dtype=np.float32)[:, None], (1, 3))
        if name == widest and stack:
            # one curve, measured on the crop that shows the most room: it is the encode, the same for every crop, and
            # a tight crop the speaker fills measures it badly
            pv = np.concatenate([room[o] for o in oks])
            lv = np.concatenate([s[o] for s, o in zip(stack, oks)])
            luts[name] = knot_curve(pv, lv, 8) if len(pv) > 5000 else ident
        lut = luts.get(widest, ident)
        med = np.median(np.stack(stack), axis=0).astype(np.float32) if stack else None
        grade = lambda im: np.dstack([lut[im[..., c], c] for c in range(3)])      # noqa: E731
        room_l, empty_l = grade(room), grade(empty)
        if stack:
            always = np.all(np.stack(oks), axis=0)
            err = float(np.abs(room_l - med)[always].mean()) if always.any() else float("nan")
            measured[name] = round(err, 2)
            print(f"{name}: room vs live where the room shows: mean error {err:.2f} levels; "
                  f"curve offsets R,G,B at 20/60/130/235: {[[round(float(lut[k, c] - k), 1) for k in (20, 60, 130, 235)] for c in range(3)]}")
        np.save(os.path.join(work, f"lut_{name}.npy"), lut)
        np.save(os.path.join(work, f"room_{name}.npy"), room_l.astype(np.float32))
        np.save(os.path.join(work, f"room_empty_{name}.npy"), empty_l.astype(np.float32))
        mic_a = cut(mic_s, w, h, x, y)
        desk_a = cut(desk_s, w, h, x, y)
        mic_col = med if med is not None else grade(cut(colour_s, w, h, x, y))
        np.save(os.path.join(work, f"mic_{name}.npy"), np.dstack([mic_col, mic_a, mic_a]).astype(np.float32))
        room8 = np.clip(np.round(room_l), 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(pub, f"plate_{name}.jpg"), cv2.cvtColor(room8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 97])
        tmp = os.path.join(WD, "_layer.png")
        cv2.imwrite(tmp, cv2.cvtColor(room8, cv2.COLOR_RGB2BGR))
        layer_video(tmp, os.path.join(pub, f"plate_{name}.mp4"), seconds, False)
        mic8 = np.clip(np.round(mic_col), 0, 255).astype(np.uint8)
        for label, col, a in (("desk", room8, desk_a), ("mic", mic8, mic_a)):
            cv2.imwrite(tmp, cv2.cvtColor(np.dstack([col, (a * 255).round().astype(np.uint8)]), cv2.COLOR_RGBA2BGRA))
            layer_video(tmp, os.path.join(pub, f"{label}_{name}.webm"), seconds, True)
        os.remove(tmp)
        live = stack[len(stack) // 2] if stack else room8
        fgv = np.dstack([np.zeros_like(desk_a), desk_a, mic_a]) * 255
        checks.append(np.hstack([cv2.resize(im, (270, 480), interpolation=cv2.INTER_AREA) for im in
                                 (live, room8, np.clip(empty_l, 0, 255).astype(np.uint8), fgv.astype(np.uint8))]))
    sheet = np.vstack(checks)
    cv2.imwrite(os.path.join(WD, "check.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
    info.update(crops=list(E.FRAMES), error_levels=measured, desk_pct=round(float(desk_m.mean()) * 100, 2),
                mic_pct=round(float(mic_m.mean()) * 100, 2))
    json.dump(info, open(os.path.join(WD, "plate.json"), "w"), indent=1)
    print(f"plates, room files and layers written for {list(E.FRAMES)} ({info.get('mode', '?')}); "
          f"look at {os.path.join(WD, 'check.jpg')} (live | room | empty room | desk green, mic blue)")
    if info.get("mode") not in ("empty", "filled"):
        print("WARNING: no empty room: the patch the speaker always covered is inpainted. It shows wherever an effect "
              "moves them or reveals the room. Film 5 s of the empty room, or --fill a photo from the camera's spot or "
              "a generated background (--bg-frame).")


if __name__ == "__main__":
    main()
