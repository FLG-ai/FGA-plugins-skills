#!/usr/bin/env python3
"""room-doors: "the doors open", literally. On the cue word the wall behind the speaker cracks open from behind their
head and two heavy panels roll apart on inertia with a soft stop, onto a real page lit like a thing in the room (light
falls in as the gap widens, each panel throws a soft shadow on it, a lintel shadow, the speaker's own shadow, lens
blur, a slow scroll, much less parallax than the panels). The speaker, the desk, the mic and the furniture stay where
they are: everything in front is the live frame, so lips and edges are the footage. The panels are this shot's own
wall, with real inner faces drawn in perspective toward the lens centre, the lamp's side lit, the far side dark, true
motion blur. One clip; it also writes the panels' own rumble from their speed curve.

Run: PY fx/<id>/gen.py <project> [<id>] [--capture [URL]] [--stills t1 t2 ...]
  --capture        screenshots PAGE_URL (or the URL given) in a phone-sized headless browser into page.png here
  reads   <project>/edit.py (the FX entry <id>), words.json, timeline.json, public/clean.mp4, public/subject.webm,
          room_<FRAME>.npy (plate tools), public/plates/desk_<FRAME>.webm and mic_<FRAME>.webm, work/tracks/track.json,
          page.png in this folder (any tall image: a capture, a screenshot); a labelled placeholder page without it
  writes  <project>/fx/<id>/<id>.mp4, fx.html, fx.js, <project>/audio/<id>-rumble.wav; intermediates in work/fx/<id>/
<id> defaults to this folder's name. Rerun it whenever the window, the cut or the page changes.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920

# ---- the table. The beat and the look are choices; the geometry and the light are read off the footage (None = auto)
SEAM_ON = None                    # the cue word the crack starts on ("open", "send"); None = the first word in the window
OPEN_S = 0.56                     # s from the crack to the panels at rest
T_CRACK = 0.10                    # s for the crack to reach the top of the frame
SEAM_X = None                     # where the wall splits, px: None = the centre of the speaker's head on the cue word
SEAM_FROM_Y = None                # the crack starts here (behind the head) and runs up: None = just inside the top of the head
LEFT_STOP, RIGHT_STOP = 72, 1008  # where each panel's front edge stops, px. Leave some door in frame: it sells them as objects
EASE = (2.2, 2.4)                 # heavy start, long soft stop: p = 1 - (1 - u^a)^b
REBOUND = (3.2, 0.20)             # px, s: the settle against the stop
CLOSE_AT_END = True               # a window that doesn't end on a picture cut: the panels roll shut over CLOSE_S before its
CLOSE_S = 0.45                    # end, so the live shot takes over with no seam (on a cut they stay open and the cut hides it)
HEAL_GAP = 28                     # px: as the panels meet, under this gap the seam and the cut-out edges blend into the live frame
RUMBLE_PX = 0.45                  # px of judder while rolling
OPTICAL = None                    # the lens centre in px (inner faces are drawn toward it): None = the centre of the source
THICK = 0.962                     # back edge of a panel / its front edge (thickness over distance): how wide the inner faces read
ARRIS = 16                        # levels: the lit front corner of the panel facing the light, one pixel; makes the crack read
GROOVE = (0.72, 7.0)              # darkening right beside the seam on both panels (strength, px): a rebate, not a drawn line
FURNITURE_DEPTH = 0.10            # what stands this much nearer than the wall (room depth, 0..1) stays in front of the doors
KEEP_NEAR = True                  # what the matte missed at the speaker's distance (a book in their hands) stays in front too
# what's behind the doors
PAGE_URL = ""                     # the page to capture with --capture (set it per video; nothing by default)
PAGE_IMG = "page.png"             # in this folder: a capture or any tall image of what is behind the doors
PAGE_CUT = None                   # image px: everything below is blanked with the page's own background (a price, a footer)
PAGE_W = 900                      # page width on the frame at rest, px
PAGE_TOP = -112                   # top of the page on the frame at rest
PAGE_DRIFT = -18                  # px of slow scroll over the clip
PARALLAX = 1.038                  # it's further back: starts this much bigger and settles as the panels open
PAGE_BLUR = 1.5                   # px: it's on the wall plane, the lens is focused on the speaker
LIGHT_START = 0.16                # how lit the page is at the crack: light falls in as the opening widens
LIGHT_FULL_GAP = 420              # px of opening at which it's fully lit
SHADOW_NEAR = (0.88, 150.0)       # the soft shadow of the panel on the lamp's side (strength, reach px): longer
SHADOW_FAR = (0.80, 86.0)         # the other panel's
CONTACT = (0.62, 16.0)            # the tight dark line where a panel meets the opening
LINTEL = (0.62, 150.0)            # shadow from the top of the opening
HIS_SHADOW = (72, 24, 40.0, 0.34) # the speaker's shadow on the page: dx (away from the lamp), dy, blur, strength
GRAIN = 1.3                       # levels on the page, to match the footage
UNEVEN = 0.014                    # low-contrast unevenness of the surface
SHUTTER = 0.5                     # of a frame
SUB = 10                          # motion blur samples per frame
SEED = 5


def _pipeline():
    """the kit's pipeline on the import path: REEL_KIT, this folder's grandparent when it runs in the library, else
    PY's own (setup puts the pipeline on PY's import path)"""
    for c in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        p = os.path.join(c, "pipeline") if c else ""
        if p and os.path.exists(os.path.join(p, "fxlib.py")):
            sys.path.insert(0, os.path.abspath(p))
            return
    import importlib.util
    if importlib.util.find_spec("fxlib") is None:
        sys.exit("can't import the kit's fxlib: run this with the kit's PY (setup puts the pipeline on its path), or set REEL_KIT=<the kit folder>")


_pipeline()
import fxlib  # noqa: E402
from common import HF, load_edit  # noqa: E402

fr = fxlib.fr
XS = np.arange(W, dtype=np.float32)
YS = np.arange(H, dtype=np.float32)


# ---- the project
def window(project, fid):
    """the edit, the timeline and the effect's window (its edit.FX entry; "end" resolved like the build does)"""
    F = fxlib.entry(project, fid)
    return load_edit(project), json.load(open(os.path.join(project, "timeline.json"))), float(F["at"]), float(F["end"])


def words(project):
    p = os.path.join(project, "words.json")
    return [(w["start"], w["end"], w["text"]) for w in json.load(open(p))] if os.path.exists(p) else []


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def word_at(ws, text, after, before=1e9):
    for s, _, t in ws:
        if after - 0.001 <= s < before and norm(t) == norm(text):
            return s
    return None


def frame_at(TL, E, t):
    shots = [(s["t"], s["frame"]) for s in TL.get("shots", [])] or list(E.SHOTS)
    return [f for a, f in shots if a <= t + 1e-3][-1]


def room_npy(project, frame, empty=False):
    """the room behind the speaker on this crop at live levels (plate_finish.py: work/c/room_<FRAME>.npy), or None"""
    p = os.path.join(project, "work", "c", f"room_{'empty_' if empty else ''}{frame}.npy")
    return fxlib.room(project, frame, empty=empty).astype(np.float32) if os.path.exists(p) else None


def tracks_or_none(project):
    """work/tracks/track.json's frames (track.py), or None: everything that uses it has a fallback"""
    p = os.path.join(project, "work", "tracks", "track.json")
    return fxlib.tracks(project)["frames"] if os.path.exists(p) else None


def plate_alpha(project, name, frame):
    p = os.path.join(project, "public", "plates", f"{name}_{frame}.webm")
    if not os.path.exists(p):
        return np.zeros((H, W), np.float32)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", p, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                         capture_output=True).stdout
    if len(raw) < W * H * 4:
        return np.zeros((H, W), np.float32)
    return np.frombuffer(raw[:W * H * 4], np.uint8).reshape(H, W, 4)[..., 3].astype(np.float32) / 255


def plate_mode(project):
    """'empty' (the plate came from a real empty room), 'fallback' (the patch the speaker always covered is inpainted and
    shows once they move) or None (no plate tools run)"""
    p = os.path.join(project, "work", "plate", "plate.json")
    return json.load(open(p)).get("mode") if os.path.exists(p) else None


def same_frame_spans(TL, frame, A, B, reach=8.0):
    """the stretches of the video on this framing near the window: a locked-off camera sees the same wall in all of them"""
    shots = [(s["t"], s["frame"]) for s in TL.get("shots", [])] + [(TL["total"], None)]
    out = []
    for (a, f), (b, _) in zip(shots, shots[1:]):
        if f == frame:
            a, b = max(a, A - reach), min(b, B + reach)
            if b - a > 0.2:
                out.append((a, b))
    return out or [(A, B)]


# ---- the light and the geometry, read off the room
def measure(project, E, TL, frame, room, ws, A, B):
    """everything that was measured by hand on the first take: the seam, the lens centre, which side the lamp is on,
    the colour of the light, how bright a lit page would be in this room"""
    m = {}
    t_seam = word_at(ws, SEAM_ON, A, B) if SEAM_ON else next((s for s, _, _ in ws if A - 0.001 <= s < B), None)
    if SEAM_ON and t_seam is None:
        print(f"WARNING: cue word {SEAM_ON!r} is not spoken in the window: the crack starts 0.04s in")
    m["t_seam"] = max(A + 1 / FPS, t_seam if t_seam is not None else A + 0.04)      # one frame of the whole wall first
    m["t_open"] = min(m["t_seam"] + OPEN_S, B - 0.1)
    on_cut = any(abs(c - B) < 2.5 / FPS for c in TL.get("picture_cuts", []) + TL.get("reframes", []) + [TL["total"]])
    m["t_close"], m["close_s"] = None, CLOSE_S
    if CLOSE_AT_END and not on_cut:
        last = (fr(B) - 1) / FPS                         # the window's last frame
        if last - m["t_open"] - CLOSE_S < 0.25:          # no time to hold open: a quicker close, and the agent hears about it
            m["close_s"] = float(np.clip(last - m["t_open"] - 0.12, 0.24, CLOSE_S))
            print(f"WARNING: {last - m['t_seam']:.2f}s from the cue word to the end of the window is short for the doors to open, "
                  f"hold and roll shut ({OPEN_S + 0.25 + CLOSE_S + 1 / FPS:.2f}s): they roll shut in {m['close_s']:.2f}s. Give the "
                  f"window more time, or end it on a picture cut")
        m["t_close"] = last - m["close_s"]
    n = fr(m["t_seam"])
    al = next(fxlib.alpha(project, n / FPS, (n + 1) / FPS))[1].astype(np.float32) / 255
    tr = tracks_or_none(project)
    face = tr[n]["face"] if tr and n < len(tr) and tr[n].get("face") else None
    if SEAM_X is not None:
        m["seam_x"] = float(SEAM_X)
    elif face:
        m["seam_x"] = float(face["cx"])
    else:                                                       # the head: the top of the matte
        rows = np.where((al > 0.5).sum(axis=1) > 8)[0]
        top = rows[0] if len(rows) else int(0.3 * H)
        cols = np.where(al[top:top + int(0.08 * H)] > 0.5)[1]
        m["seam_x"] = float(np.mean(cols)) if len(cols) else W / 2
    sx = int(round(m["seam_x"]))
    col = al[:, max(0, sx - 30):sx + 30].max(axis=1)
    rows = np.where(col > 0.5)[0]
    head_top = float(rows[0]) if len(rows) else 0.3 * H
    fh = face["h"] if face else 0.2 * W
    m["seam_from_y"] = float(SEAM_FROM_Y) if SEAM_FROM_Y is not None else head_top + max(40.0, 0.15 * fh)
    if OPTICAL is not None:
        m["optical"] = tuple(OPTICAL)
    else:
        cw, ch, cx, cy = E.FRAMES[frame]
        try:
            sw, sh = fxlib.size(E.SRC)
        except Exception:
            sw, sh = cw + 2 * cx, ch + 2 * cy
        m["optical"] = ((sw / 2 - cx) * W / cw, (sh / 2 - cy) * H / ch)
    # the light: which side is brighter, how high the brightest light sits, its colour
    L = room.mean(axis=2)
    up = slice(0, int(0.7 * H))
    left, right = L[up, :int(0.4 * W)].mean(), L[up, int(0.6 * W):].mean()
    m["lamp"] = "left" if left >= right else "right"
    top = L[:int(0.75 * H)]
    thr = np.percentile(top, 99)
    ys = np.where(top >= thr)[0]
    m["lamp_y"] = float(np.clip(np.mean(ys) if len(ys) else 400, 200, 1300))
    bright = room[L >= np.percentile(L, 97)]
    bright = bright[bright.max(axis=1) < 250] if (bright.max(axis=1) < 250).sum() > 200 else bright
    tint = bright.mean(axis=0) / max(1.0, bright.mean(axis=0).max())
    m["tint"] = tuple(float(0.5 + 0.5 * v) for v in tint)
    m["page_white"] = float(np.clip(1.35 * np.percentile(L, 97), 70, 215))
    m["page_black"] = float(np.clip(np.percentile(L, 2), 6, 40))
    wall = np.median(room[:int(0.6 * H)].reshape(-1, 3), axis=0)
    lit = wall * 1.25 * np.array(m["tint"])
    m["face_lit"] = tuple(float(v) for v in np.clip(lit + (255 - lit) * 0.12, 0, 255))                 # the wall's own colour, catching the lamp
    m["face_dark"] = tuple(float(v) for v in np.clip(wall * 0.42, 0, 255))                              # turned away from it
    print(f"seam x {m['seam_x']:.0f} from y {m['seam_from_y']:.0f}, crack {m['t_seam']:.3f}, at rest {m['t_open']:.3f}, lens centre "
          f"({m['optical'][0]:.0f}, {m['optical'][1]:.0f}), lamp on the {m['lamp']} at y {m['lamp_y']:.0f}, page white {m['page_white']:.0f}")
    return m


# ---- motion
def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def travel(t):
    """0..1 of the way open; when the window doesn't end on a picture cut the panels roll shut again before its end"""
    u = np.clip((t - G["t_seam"]) / (G["t_open"] - G["t_seam"]), 0, 1)
    p = 1 - (1 - u ** EASE[0]) ** EASE[1]
    if G.get("t_close") is not None:
        v = np.clip((t - G["t_close"]) / G["close_s"], 0, 1)
        p = p * (1 - v * v * v * (v * (v * 6 - 15) + 10))
    return p


def offsets(t):
    """(left, right) panel offset in px at time t, plus the settle against the stop"""
    p = travel(t)
    sx = G["seam_x"]
    dl, dr = (sx - LEFT_STOP) * p, (RIGHT_STOP - sx) * p
    if G["t_open"] < t < G["t_open"] + REBOUND[1] and (G.get("t_close") is None or t < G["t_close"]):
        b = REBOUND[0] * np.sin(np.pi * min(1.0, (t - G["t_open"]) / REBOUND[1]))
        dl, dr = dl - b, dr - b
    return dl, dr


def speed(t):
    return abs(travel(t + 0.5 / FPS) - travel(t - 0.5 / FPS)) * FPS


def judder(t):
    """seeded roller judder, scaled by how fast they roll (x, y)"""
    a = RUMBLE_PX * min(1.0, speed(t) * 1.2)
    return a * np.sin(t * 2 * np.pi * 37.0), a * 0.8 * np.sin(t * 2 * np.pi * 23.0 + 1.1)


# ---- the page
def browser():
    if os.environ.get("HEADLESS_BROWSER"):
        return os.environ["HEADLESS_BROWSER"]
    r = subprocess.run(HF + ["browser", "path"], capture_output=True, text=True)
    path = (r.stdout.strip().splitlines() or [""])[-1].strip()
    if not path or not os.path.exists(path):
        sys.exit("no headless browser: run `npx -y hyperframes@0.8.139 browser ensure`, or set HEADLESS_BROWSER=/path/to/chrome")
    return path


def capture(url, dest):
    """the page in a phone-sized window (430 px wide, 3x, a phone's user agent), tall enough for a few screens"""
    ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
          "Version/17.0 Mobile/15E148 Safari/604.1")
    r = subprocess.run([browser(), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000", f"--user-agent={ua}",
                        "--force-device-scale-factor=3", "--window-size=430,2400", f"--screenshot={dest}", url],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(dest):
        sys.exit(f"the capture failed ({url}): put any tall image of the page in {dest} by hand")
    print("captured", url, "->", dest)


def placeholder_page(project, path):
    """no page yet: a plain page in the creator's own colours and type, labelled as a placeholder"""
    from PIL import Image, ImageDraw
    S = fxlib.pack(project)
    C = S["colors"]
    w, h = 1290, 2600
    im = Image.new("RGB", (w, h), C["light"][:3])
    d = ImageDraw.Draw(im)
    ink, muted, hair, acc = C["ink"][:3], C["muted_light"][:3], C["hair_light"][:3], C["accent_on_light"][:3]
    d.rectangle((0, 0, w, 220), fill=C["dark"][:3])                 # the top ~160 px sit above the frame (PAGE_TOP)
    d.text((70, 330), "Your page", font=fxlib.font(project, "display", 150), fill=ink)
    d.text((70, 510), "goes here.", font=fxlib.font(project, "display", 150), fill=ink)
    d.rectangle((70, 730, 470, 746), fill=acc)
    d.text((70, 800), "PLACEHOLDER", font=fxlib.font(project, "mono", 44), fill=acc)
    tf = fxlib.font(project, "text", 46)
    for i, line in enumerate(("Put a capture of the real page in", f"fx/<id>/{PAGE_IMG}, or run gen.py --capture <url>.")):
        d.text((70, 890 + 70 * i), line, font=tf, fill=muted)
    for k in range(8):
        y = 1150 + 150 * k
        d.rounded_rectangle((70, y, w - 70 - (k % 3) * 160, y + 40), radius=10, fill=hair)
    d.rounded_rectangle((70, 2380, w - 70, 2520), radius=24, outline=ink, width=6)
    im.save(path)
    print(f"no {PAGE_IMG}: a placeholder page ({path})")


def page_plate(project, src_path, white, black, tint):
    """the page on a canvas wider than the frame, in the room's light. Returns it as float and its x padding"""
    src = cv2.imread(src_path)[..., ::-1].astype(np.float32)
    if PAGE_CUT:
        bg = np.median(src[-8:].reshape(-1, 3), axis=0)
        src[int(PAGE_CUT):] = bg
    s = PAGE_W / src.shape[1]
    small = cv2.resize(src, (PAGE_W, max(2, round(src.shape[0] * s))), interpolation=cv2.INTER_AREA)
    pad_x = 420
    canvas = cv2.copyMakeBorder(small, 0, 0, pad_x, pad_x, cv2.BORDER_REPLICATE)
    canvas = cv2.copyMakeBorder(canvas, 0, H, 0, 0, cv2.BORDER_REPLICATE)
    canvas = cv2.GaussianBlur(canvas, (0, 0), PAGE_BLUR)
    lit = black + canvas / 255.0 * (white - black) * np.array(tint, np.float32)
    return lit, pad_x


def surface(seed=3):
    """very low contrast 2D unevenness of a lit surface, so the 1D shadow ramps don't band into stripes"""
    rng = np.random.default_rng(seed)
    a = cv2.resize(rng.standard_normal((H // 40 + 2, W // 40 + 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    b = cv2.resize(rng.standard_normal((H // 9 + 2, W // 9 + 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    return (1 + UNEVEN * (a + 0.5 * b))[..., None]


def page_at(lit, pad, t, A, B):
    """the page on the frame at time t: a slow scroll and a much smaller parallax than the panels"""
    p = travel(t)
    u = (t - A) / max(1e-3, B - A)
    zoom = PARALLAX + (1 - PARALLAX) * p
    cx, cy = W / 2, 330.0
    y0 = PAGE_TOP + PAGE_DRIFT * u
    x0 = (W - PAGE_W) / 2 - pad
    Mt = np.float32([[zoom, 0, cx + (x0 - cx) * zoom], [0, zoom, cy + (y0 - cy) * zoom]])
    return cv2.warpAffine(lit, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ---- what stands in the room, and the wall without it
def furniture_mask(room, desk, work, frame, cnt=None):
    """anything that stands clearly nearer than the wall (a chair, a shelf, a lamp, the floor) stays in front of the
    doors. Read from the room's depth, so no colour test per room"""
    cache = os.path.join(work, f"standing_{frame}.npy")
    if os.path.exists(cache):
        return np.load(cache)
    import depth
    d = cv2.GaussianBlur(depth.infer(np.clip(room, 0, 255).astype(np.uint8)), (0, 0), 2)
    wall = float(np.percentile(d[:int(0.5 * H)], 25))
    m = (d > wall + FURNITURE_DEPTH).astype(np.uint8)
    m[desk > 0.5] = 0
    if cnt is not None:                              # where the speaker always sat nothing was seen: wall, whatever depth says
        m[cnt < 2] = 0
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    for i in range(1, n):                            # furniture stands on the floor: a near patch up high is ceiling or wall
        if st[i, cv2.CC_STAT_AREA] < 1500 or st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT] < 0.5 * H:
            m[lab == i] = 0
    m = cv2.GaussianBlur(cv2.dilate(m, np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 2.0)
    np.save(cache, m)
    cv2.imwrite(os.path.join(work, f"standing_{frame}.jpg"), cv2.cvtColor(np.clip(room * (0.35 + 0.65 * m[..., None]), 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
    print(f"standing in front of the wall: {100 * (m > 0.5).mean():.1f}% of the frame (lit in work/fx/<id>/standing_{frame}.jpg)")
    return m


def row_fill(tex, mask):
    """every run of `mask` in a row bridged from the wall on either side of it: the furniture out of the door texture"""
    out = tex.copy()
    m = mask > 0.5
    for y in np.where(m.any(axis=1))[0]:
        row = m[y]
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            la, lb = max(0, a - 34), max(0, a - 4)
            ra, rb = min(W, b + 4), min(W, b + 34)
            left = np.median(tex[y, la:lb], axis=0) if lb - la > 3 else None
            right = np.median(tex[y, ra:rb], axis=0) if rb - ra > 3 else None
            if left is None and right is None:
                continue
            left = right if left is None else left
            right = left if right is None else right
            u = np.linspace(0, 1, b - a, dtype=np.float32)[:, None]
            out[y, a:b] = left * (1 - u) + right * u
    return out


def shot_mean(project, spans, work, frame):
    """the room as this framing sees it: the mean of the live pixels wherever the speaker isn't, and how often each
    pixel was seen (every third frame of the spans)"""
    cache = os.path.join(work, f"seen_{frame}_{fr(spans[0][0])}_{fr(spans[-1][1])}.npz")
    if os.path.exists(cache):
        z = np.load(cache)
        return z["mean"], z["cnt"]
    acc, cnt = np.zeros((H, W, 3), np.float64), np.zeros((H, W), np.float64)
    k = np.ones((31, 31), np.uint8)
    for a, b in spans:
        a, b = a + 2 / FPS, b - 2 / FPS
        for j, ((_, rgb), (_, al)) in enumerate(zip(fxlib.frames(project, a, b), fxlib.alpha(project, a, b))):
            if j % 3:
                continue
            vis = cv2.dilate((al > 8).astype(np.uint8), k) == 0
            acc[vis] += rgb[vis]
            cnt += vis
    mean = (acc / np.maximum(cnt, 1)[..., None]).astype(np.float32)
    np.savez(cache, mean=mean, cnt=cnt.astype(np.float32))
    return mean, cnt.astype(np.float32)


def room_from_shot(mean, cnt):
    """no plate: the seen room, the patch the speaker always covered inpainted (it only shows once the doors move)"""
    hole = (cnt < 2).astype(np.uint8) * 255
    small = cv2.resize(np.clip(mean, 0, 255).astype(np.uint8), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    fill = cv2.inpaint(small, cv2.resize(hole, (W // 4, H // 4), interpolation=cv2.INTER_NEAREST), 8, cv2.INPAINT_TELEA)
    fill = cv2.GaussianBlur(cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32), (0, 0), 6)
    a = cv2.GaussianBlur((hole > 0).astype(np.float32), (0, 0), 5)[..., None]
    return mean * (1 - a) + fill * a


def seen_room(room, mean, cnt):
    """the room as this shot's own live pixels show it wherever the speaker doesn't cover them (same sharpness and level
    as the footage, and true even when the plate is a fallback's guess), the plate only behind them"""
    wgt = cv2.GaussianBlur((cnt >= 6).astype(np.float32), (0, 0), 6)[..., None]
    wgt = np.clip((wgt - 0.5) * 2, 0, 1)
    return (room * (1 - wgt) + mean.astype(np.float32) * wgt).astype(np.float32)


def wall_texture(tex, front_static, work, key):
    """the wall with nothing in front of it: the seen room, the furniture bridged over from the wall around it"""
    cache = os.path.join(work, f"wall_{key}.npy")
    if os.path.exists(cache):
        return np.load(cache)
    fill = row_fill(tex, front_static)
    fill = cv2.GaussianBlur(fill, (0, 0), sigmaX=1.0, sigmaY=2.0)
    fill += np.random.default_rng(SEED).normal(0, 0.7, (H, W, 1)).astype(np.float32)
    a = cv2.GaussianBlur((front_static > 0.3).astype(np.float32), (0, 0), 3)[..., None]
    tex = (tex * (1 - a) + fill * a).astype(np.float32)
    np.save(cache, tex)
    return tex


def near_extra(rgb, spk, desk, face, state):
    """pixels the matte missed that are as near as the speaker (a held book, the chair they sit in), from this frame's
    depth smoothed over frames; thin bands round their outline are dropped. They stay in front of the doors"""
    import depth
    d = depth.infer(rgb, side=518)
    state["d"] = d if state.get("d") is None else 0.6 * d + 0.4 * state["d"]
    d = state["d"]
    solid = spk > 0.95
    if face:
        band = np.zeros_like(solid)
        band[int(max(0, face["top"])):int(min(H, face["chin"] + 0.3 * face["h"]))] = True
        if (solid & band).sum() > 500:
            solid &= band
    if solid.sum() < 500:
        return 0.0
    focus, far, near = float(np.median(d[solid])), float(np.percentile(d, 5)), float(np.percentile(d, 99.5))
    fg = (d > focus - 0.35 * max(0.02, focus - far)) & (d < focus + 0.6 * max(0.02, near - focus)) & (spk < 0.95) & (desk < 0.3)
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] < 1500:
            fg[lab == k] = 0
    return cv2.GaussianBlur(fg.astype(np.float32), (0, 0), 2.0) if fg.any() else 0.0


def guided(I, p, r, eps):
    k = (2 * r + 1, 2 * r + 1)
    box = lambda x: cv2.boxFilter(x, cv2.CV_32F, k)   # noqa: E731
    mI, mp = box(I), box(p)
    a = (box(I * p) - mI * mp) / (box(I * I) - mI * mI + eps)
    b = mp - a * mI
    return box(a) * I + box(b)


def shifted(tex, d, dy=0.0):
    Mt = np.float32([[1, 0, d], [0, 1, dy]])
    return cv2.warpAffine(tex, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def backdrop(tex_now, page, cast, t):
    """page + panels at one instant of the shutter. Lamp on the left: the right panel's inner face catches the light,
    the left panel throws the longer shadow; mirrored when the lamp is on the right"""
    dl, dr = offsets(t)
    jx, jy = judder(t)
    sx = G["seam_x"]
    xl, xr = sx - dl + jx, sx + dr + jx
    gap = max(0.0, xr - xl)
    ox = G["optical"][0]
    lamp_left = G["lamp"] == "left"
    light = LIGHT_START + (1 - LIGHT_START) * sstep(0, LIGHT_FULL_GAP, gap)
    fall = 1.0 - 0.2 * (XS / W if lamp_left else 1 - XS / W)
    bl = ox + (xl - ox) * THICK                       # back edge of the left panel's inner face
    br = ox + (xr - ox) * THICK
    sl, sr = (SHADOW_NEAR, SHADOW_FAR) if lamp_left else (SHADOW_FAR, SHADOW_NEAR)
    s_l = 1 - sl[0] * np.exp(-np.maximum(XS - bl, 0) / sl[1])
    s_r = 1 - sr[0] * np.exp(-np.maximum(br - XS, 0) / sr[1])
    c_l = 1 - CONTACT[0] * np.exp(-np.maximum(XS - bl, 0) / CONTACT[1])
    c_r = 1 - CONTACT[0] * np.exp(-np.maximum(br - XS, 0) / CONTACT[1])
    shade = (fall * s_l * s_r * c_l * c_r * light)[None, :]
    lintel = (1 - LINTEL[0] * np.exp(-YS / LINTEL[1]))[:, None]
    pb = G["page_black"]
    bg = pb * 0.5 + (page * cast - pb * 0.5) * (shade * lintel)[..., None]
    fall_y = (0.55 + 0.45 * np.exp(-((YS - G["lamp_y"]) / 520.0) ** 2)).astype(np.float32)[:, None, None]
    face_lt, face_dk = np.array(G["face_lit"], np.float32), np.array(G["face_dark"], np.float32)
    face_l = face_dk if lamp_left else face_lt * fall_y          # a face turned toward the lamp catches it
    face_r = face_lt * fall_y if lamp_left else face_dk
    if bl > xl:
        cov = (np.clip(XS + 1 - xl, 0, 1) * np.clip(bl - XS, 0, 1))[None, :, None]
        bg = bg * (1 - cov) + face_l * cov
    if br < xr:
        cov = (np.clip(XS + 1 - br, 0, 1) * np.clip(xr - XS, 0, 1))[None, :, None]
        bg = bg * (1 - cov) + face_r * cov
    cl = np.clip(xl - XS, 0, 1)[None, :, None]
    cr = np.clip(XS + 1 - xr, 0, 1)[None, :, None]
    left = shifted(tex_now, -dl + jx, jy)
    right = shifted(tex_now, dr + jx, jy)
    groove_l = 1 - GROOVE[0] * np.exp(-np.maximum(xl - XS, 0) / GROOVE[1]) * min(1.0, gap / 1.5)
    groove_r = 1 - GROOVE[0] * np.exp(-np.maximum(XS - xr, 0) / GROOVE[1]) * min(1.0, gap / 1.5)
    bg = bg * (1 - cl) + left * groove_l[None, :, None] * cl
    bg = bg * (1 - cr) + right * groove_r[None, :, None] * cr
    edge = xr if lamp_left else xl                   # the lit front corner of the panel facing the light
    ar = np.clip(1 - np.abs(XS + 0.5 - edge - (0.8 if lamp_left else -0.8)), 0, 1)[None, :, None] * ARRIS * min(1.0, gap / 2.0)
    return bg + ar


def rumble(path):
    """the sound of these panels, synthesized from their own speed curve (CC0, numpy only): sub rollers and grit that
    follow how fast they roll, a soft bump at the stop. Place it by its start at the crack, minus 0.04 s"""
    from scipy.io import wavfile
    from scipy.signal import butter, sosfilt
    sr, lead, tail = 48000, 0.04, 0.40
    t0, t1 = G["t_seam"], G["t_open"]
    t_end = (G["t_close"] + G["close_s"] + tail) if G.get("t_close") is not None else t1 + tail
    n = int((t_end - t0 + lead) * sr)
    tt = t0 - lead + np.arange(n) / sr
    rng = np.random.default_rng(SEED + 1)
    spd = np.array([speed(x) for x in tt[::240]])
    spd = np.interp(np.arange(n), np.arange(len(spd)) * 240, spd)
    spd = spd / max(1e-6, spd.max())
    env = np.maximum(spd ** 0.7, 0.22 * sstep(0, 0.06, tt - t0 + lead) * (1 - sstep(t1 - 0.05, t1 + 0.05, tt)))
    if G.get("t_close") is not None:                 # rolling shut: the same rumble on the way back
        tc = G["t_close"]
        tz = tc + G["close_s"]
        env = np.maximum(env, 0.22 * sstep(tc - 0.02, tc + 0.04, tt) * (1 - sstep(tz - 0.05, tz + 0.05, tt)))
    out = np.zeros((2, n))
    for c in range(2):
        low = sosfilt(butter(2, [28, 150], "bandpass", fs=sr, output="sos"), rng.standard_normal(n))
        low /= np.abs(low).max()
        grit = sosfilt(butter(2, [260, 1500], "bandpass", fs=sr, output="sos"), rng.standard_normal(n))
        grit /= np.abs(grit).max()
        rollers = 0.65 + 0.35 * np.sin(2 * np.pi * (19 + 7 * spd) * tt + c)
        sub = np.sin(2 * np.pi * np.cumsum(46 + 18 * spd) / sr + c * 0.4)
        out[c] = 0.75 * low * env * rollers + 0.30 * sub * env + 0.13 * grit * spd ** 1.6 * rollers
    stops = [t1] if G.get("t_close") is None or G["t_close"] >= t1 else []
    for stop in stops + ([G["t_close"] + G["close_s"]] if G.get("t_close") is not None else []):   # a low, soft bump at each stop
        tb = tt - stop
        out += 0.9 * np.where(tb > 0, np.sin(2 * np.pi * (58 - 60 * np.minimum(tb, 0.2)) * tb) * np.exp(-tb / 0.075), 0.0)
    out *= np.minimum(1.0, (tt[-1] - tt) / 0.08) * np.minimum(1.0, (tt - tt[0]) / 0.01)
    out = out / np.abs(out).max() * 0.71
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavfile.write(path, sr, (out.T * 32767).astype(np.int16))


G = {}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--capture", nargs="?", const="", default=None, help="screenshot PAGE_URL (or this URL) into page.png")
    ap.add_argument("--stills", nargs="*", type=float, help="seconds on the output timeline: write these frames as PNGs only")
    ap.add_argument("--fresh", action="store_true", help="forget the cached room measurements (after new plates)")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E, TL, A, B = window(project, fid)
    if fxlib.size(os.path.join(project, "public", "clean.mp4")) != (W, H):
        sys.exit("room-doors is built for a 1080x1920 canvas")
    out_dir, work = os.path.join(project, "fx", fid), os.path.join(project, "work", "fx", fid)
    if args.fresh:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    page_path = os.path.join(out_dir, PAGE_IMG)
    if args.capture is not None:
        url = args.capture or PAGE_URL
        if not url:
            sys.exit("--capture needs a URL: set PAGE_URL at the top of gen.py or pass it (--capture https://...)")
        capture(url, page_path)
    frame = frame_at(TL, E, A)
    if any(A + 0.5 / FPS < c < B - 0.5 / FPS for c in TL.get("picture_cuts", []) + TL.get("reframes", [])):
        sys.exit(f"{fid}: the window {A:.2f}-{B:.2f} spans a picture change: end it on the cut")
    ws = words(project)
    spans = same_frame_spans(TL, frame, A, B)
    mean, cnt = shot_mean(project, spans, work, frame)
    room = room_npy(project, frame)
    if plate_mode(project) == "fallback":
        print("WARNING: this plate is the FALLBACK (no empty room was filmed): where the speaker always sat the wall is "
              "inpainted, and the panels carry that patch as they roll away (a smeared shape on the wall beside them). "
              "Film 5 s of the empty room (edit.py EMPTY or EMPTY_CLIP) and rerun the plate tools for a clean wall")
    if room is None:
        print("no room_<FRAME>.npy from the plate tools: the room comes from this framing's own frames (locked-off shots only)")
        room = room_from_shot(mean, cnt)
    room = seen_room(room, mean, cnt)              # depth, light and the panels all read what the take really shows
    G.update(measure(project, E, TL, frame, room, ws, A, B))
    mic, desk = plate_alpha(project, "mic", frame), plate_alpha(project, "desk", frame)
    fallback = plate_mode(project) == "fallback"
    # a real empty room: depth on the plate is true everywhere, a chair hidden behind the speaker included. A fallback's
    # patch where they always sat is a guess: not furniture, and bridged over from the wall either side like furniture is
    standing = furniture_mask(room, desk, work, frame, cnt if fallback else None)
    bridge = np.maximum(standing, cv2.GaussianBlur((cnt < 2).astype(np.float32), (0, 0), 2)) if fallback else standing
    tex = wall_texture(room, bridge, work, f"{frame}_{fr(spans[0][0])}_{fr(spans[-1][1])}_{int(fallback)}")
    if not os.path.exists(page_path):
        placeholder_page(project, os.path.join(work, "placeholder.png"))
        page_src = os.path.join(work, "placeholder.png")
    else:
        page_src = page_path
    lit, pad = page_plate(project, page_src, G["page_white"], G["page_black"], G["tint"])
    surf = surface()
    want = None if args.stills is None else {fr(t) for t in args.stills}
    wr = None if want is not None else fxlib.Writer(os.path.join(out_dir, f"{fid}.mp4"), crf=14)
    f_seam = fr(G["t_seam"])
    tr_all, near_state = tracks_or_none(project), {}
    dx, dy, blur, st = HIS_SHADOW
    dx = dx if G["lamp"] == "left" else -dx
    for (i, rgb), (_, al) in zip(fxlib.frames(project, A, B), fxlib.alpha(project, A, B)):
        if want is not None and i not in want:
            continue
        t = i / FPS
        if i < f_seam or (G.get("t_close") is not None and t >= G["t_close"] + G["close_s"]):   # before the crack, and shut again
            if wr:
                wr.write(rgb)
            continue
        rng = np.random.default_rng([SEED, i])
        # the speaker, off the live frame: the matte snapped to the footage's edges, colour pulled in from inside
        I = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        a_soft = cv2.GaussianBlur(al.astype(np.float32) / 255, (0, 0), 0.7)
        spk = np.clip((guided(I, a_soft, 4, 2e-4) - 0.5) * 1.5 + 0.5, 0, 1)
        face = tr_all[i]["face"] if tr_all and i < len(tr_all) and tr_all[i].get("face") else None
        held = near_extra(rgb, spk, desk, face, near_state) if KEEP_NEAR else 0.0
        front = 1 - (1 - spk) * (1 - mic) * (1 - desk) * (1 - standing) * (1 - held)
        solid = (spk > 0.97) | (mic > 0.9) | (desk > 0.9) | (standing > 0.9) | (np.asarray(held) > 0.9)
        m = solid.astype(np.float32)
        mb = cv2.GaussianBlur(m, (0, 0), 2.2)
        ext = cv2.GaussianBlur(rgb.astype(np.float32) * m[..., None], (0, 0), 2.2) / np.maximum(mb, 1e-3)[..., None]
        F = np.where(solid[..., None], rgb.astype(np.float32), np.where(mb[..., None] > 0.02, ext, rgb.astype(np.float32)))
        # the door surface this frame: the live wall where it can be seen, so there is no pop on the first move
        vis = cv2.GaussianBlur((cv2.dilate((front > 0.02).astype(np.uint8), np.ones((29, 29), np.uint8)) == 0).astype(np.float32), (0, 0), 4)[..., None]
        tex_now = tex * (1 - vis) + rgb.astype(np.float32) * vis
        sh = cv2.warpAffine(cv2.GaussianBlur(al.astype(np.float32) / 255, (0, 0), blur), np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
        cast = (1 - st * sh)[..., None]
        page = page_at(lit, pad, t, A, B) * surf
        crack_y = G["seam_from_y"] * (1 - sstep(0, T_CRACK, t - G["t_seam"]))
        acc = np.zeros((H, W, 3), np.float32)
        for k in range(SUB):
            tk = t + ((k + 0.5) / SUB - 0.5) * SHUTTER / FPS
            acc += backdrop(tex_now, page, cast, max(tk, G["t_seam"]))
        bg = acc / SUB
        rows = sstep(crack_y - 3, crack_y + 3, YS)[:, None, None]     # rows the crack hasn't reached are still solid wall
        bg = tex_now * (1 - rows) + bg * rows
        bg = bg + cv2.GaussianBlur(rng.standard_normal((H, W, 1)).astype(np.float32), (0, 0), 0.6)[..., None] * GRAIN * 1.6 * (1 - vis)
        A_ = front[..., None]
        out = bg * (1 - A_) + F * A_
        if G.get("t_close") is not None and t > G["t_close"]:     # rolling shut: as they meet, the seam and the cut-out edges heal
            heal = 1 - sstep(0, HEAL_GAP, travel(t) * (RIGHT_STOP - LEFT_STOP))
            out = out * (1 - heal) + rgb.astype(np.float32) * heal
        u8 = np.clip(out + rng.uniform(0, 1, (H, W, 1)).astype(np.float32), 0, 255).astype(np.uint8)
        if wr:
            wr.write(u8)
        else:
            path = os.path.join(work, f"still_{t:.2f}.png")
            cv2.imwrite(path, u8[..., ::-1])
            print(path)
    if not wr:
        return
    wr.close()
    snd = f"{fid}-rumble"
    rumble(os.path.join(project, "audio", f"{snd}.wav"))
    tag = fxlib.tag(f"{fid}-v", f"fx/{fid}/{fid}.mp4", A, B, "g", "{{T0}}", "position:absolute;left:0;top:0;width:1080px;height:1920px;")
    with open(os.path.join(out_dir, "fx.html"), "w") as fh:
        fh.write(f"<!-- {fid} [room-doors] (cam). Written by gen.py for the window {A:.3f}-{B:.3f}: a full-frame clip of the live shot with the wall opening. -->\n{tag}\n")
    with open(os.path.join(out_dir, "fx.js"), "w") as fh:
        fh.write("// room-doors: everything is in the clip (class g takes the live grade); its frame 0 is the frame at A. Nothing to tween.\n")
    ts, to = G["t_seam"], G["t_open"]
    print(f"wrote {out_dir}/{fid}.mp4, fx.html, fx.js and audio/{snd}.wav. SOUND sfx lines:")
    if G.get("t_close") is not None:
        print(f"the window doesn't end on a picture cut: the panels roll shut from {G['t_close']:.3f} and the live frame is back "
              f"at {G['t_close'] + G['close_s']:.3f}")
    stop = f'\n    ({to:.3f}, "impact-low", -20),   # the stop' if G.get("t_close") is None or G["t_close"] >= to else ""
    print(f'    dict(at={ts - 0.04:.3f}, name="{snd}", db=-12, align="start"),   # the panels rolling (open, and shut again), from their own speed\n'
          f'    ({ts:.3f}, "click", -16),   # the latch as the crack starts{stop}')
    print(f"frames that sell it: [{ts + 0.13:.2f}, {ts + 0.33:.2f}, {to + 0.15:.2f}]")


if __name__ == "__main__":
    main()
