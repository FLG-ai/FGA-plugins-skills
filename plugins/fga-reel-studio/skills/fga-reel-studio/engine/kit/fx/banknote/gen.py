#!/usr/bin/env python3
"""banknote: the speaker is the engraved portrait on a bill, live and lip-synced, and the bill prints their number as
they say it.

The portrait is a true line engraving of every frame: parallel lines whose width follows the tone, swelling into
lozenges in the lights, cross-hatched twice in the deep shadows, bent round the head by an ellipsoid and the depth map
and locked to the head as it moves. The bill is pure math: guilloche weaves, rosettes, a lathe-work field, microtext of
the speaker's own words. Generic: no country, no government wording, no real layout. The note is a real object, so its
paper and inks are a real note's; its type is the creator's (the pack's display, text and mono faces). Hard cut in,
the number prints glyph by glyph on its words, the whole note hits once more on the last word, hard cut out.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills T ...]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json (the cue words, the microtext), public/clean.mp4,
          public/subject.webm, work/tracks/track.json (the face), style/ (the pack); depth through the kit's depth.py
  writes  <project>/fx/<id>/note.mp4 and fx.html; work/<id>/ holds the depth cache (delete it after a recut).
          --stills T writes PNGs of those output times there and nothing else
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the table changes.
"""
import argparse
import math
import os
import re
import shutil
import sys

sys.dont_write_bytecode = True       # nothing generated may land in an fx folder: everything in it gets published
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- the table: everything that changes per video ------------------------------------------------------------------
NUMBER = "12,345.67"          # the creator's real number as it prints (digits, commas, a point). A placeholder until
                              # set: the note says THE NUMBER IS REAL, so never a made-up one
TITLE = "PLACEHOLDER TITLE"   # what the number is, engraved under it in caps (a launch, a month, a product)
LANDS_ON = []                 # the spoken word each glyph of NUMBER prints on, in order (commas and the point count
                              # as glyphs), as words.json has them: "42,600" said "forty two thousand six hundred" is
                              # ["forty", "two", "thousand", "six", "hundred"], the last 0 a beat after. Glyphs past the
                              # list or on a word that isn't found print one PRINT_STEP after the one before; [] (the
                              # number isn't said) prints them all in a quick run from PRINT_AT
PUNCH_ON = ""                 # the whole note hits and the number goes wet once more on this word ('' = the last glyph)
PRINT_AT, PRINT_STEP = 0.083, 0.057   # the quick run: s after the window's start, s between glyphs
SPOKEN = ""                   # the microtext round the oval; '' = the words spoken in the window, in caps
SERIAL = ""                   # the serial in the second ink; '' = the title's initials round the number's digits
SIGNER = ""                   # the name in the rosette; '' = the pack's creator name, else their handle, else none (the
                              # kit's placeholder name "reel-kit" counts as none)
SIGNER_ROLE = ""              # one small line under the name (a title), '' = none
DISCLAIMER = ("THIS NOTE IS NOT MONEY.", "THE NUMBER IS REAL.")
FLIP = False                  # True for a mirrored front-camera take (text on their clothes reads backwards)

# ---- the speaker in the oval: read off the face track over the window; the px overrides pin it on a still
FACE_SIZE = 0.45              # the face's width as a share of the oval's width
FACE_Y = 0.05                 # the oval's centre sits this many face heights above the face's centre
FACE_CX = None                # px override: the footage x (after FLIP) that sits at the oval's centre
SRC_CY = None                 # px override: the footage y that sits at the oval's centre
SCALE = None                  # override: footage px to note px

# ---- the note (a designed object on the 1080x1920 frame, the same on every take)
OVAL = (540, 664, 342, 444)   # cx, cy, rx, ry on the note
PITCH = 6.4                   # line pitch on the face, px
PLATE = (94, 1176, 986, 1466) # the big number's plate
NUMBER_SIZE, NUMBER_BASE, TITLE_Y = 236, 1366, 1433   # the number's largest size and baseline, the title's centre
FACE_LIFT = .34               # how much the lights of the face open up
FIELD_INK = .46               # how hard the lathe-work tint prints
SS = 3
NOTE_INK = (30, 64, 46)       # a note's intaglio green
SERIAL_INK = (178, 44, 50)    # a serial's red, the only second ink
PAPER = (238, 236, 222)       # note paper, off-white
CORNERS = ((30, 30, 374, 126), (706, 30, 1050, 126), (30, 1794, 374, 1890), (706, 1794, 1050, 1890))
FPS = 30
CW, CH = 1080, 1920           # the project's frame, from public/clean.mp4
PROJECT = None


try:
    import fxlib  # noqa: E402  (setup puts the kit's pipeline on PY's import path)
except ImportError:                  # another Python, or the library folder itself: KIT/pipeline by hand
    sys.path.insert(0, os.path.join(os.environ.get("REEL_KIT_DIR") or os.path.join(HERE, "..", ".."), "pipeline"))
    try:
        import fxlib  # noqa: E402
    except ImportError:
        sys.exit("run this with the kit's Python (PY): setup puts the kit's pipeline on its import path")
sys.path.insert(0, HERE)
import inkscreen as ink  # noqa: E402


# ---- the project ----------------------------------------------------------------------------------------------------
def cue(text, after, before):
    """the start of the spoken word `text` at or after `after` (like wordAt in fx.js), None when it isn't spoken
    before `before` or the project has no words.json yet"""
    if not text or not os.path.exists(os.path.join(PROJECT, "words.json")):
        return None
    t = fxlib.word_at(PROJECT, text, after)
    return t if t is not None and t < before else None


def glyph_times(A, B):
    """one time per glyph of NUMBER, each on its spoken word, searched in order; the rest in a quick run"""
    out, prev = [], A
    last = (round(B * FPS) - 1) / FPS
    for i, _ in enumerate(NUMBER):
        w = LANDS_ON[i] if i < len(LANDS_ON) else ""
        t = cue(w, prev, B)
        if t is None:
            if w:
                print(f"  glyph {i + 1} word {w!r} not spoken after {prev:.2f}: quick run")
            t = out[-1] + PRINT_STEP if out else A + PRINT_AT
        t = min(last, max(t, out[-1] if out else A))
        out.append(t)
        prev = t + 0.001
    return out


# ---- type: the pack's faces, sized to fit the note ------------------------------------------------------------------
def font(role, size):
    return fxlib.font(PROJECT, role, max(4, int(round(size * SS))))


def tracked_width(f, text, track):
    return (sum(f.getlength(c) for c in text) + track * SS * max(0, len(text) - 1)) / SS


def fit(role, text, size, width, track=0.0):
    """the largest size up to `size` at which the tracked text is no wider than `width` note px"""
    w = tracked_width(font(role, size), text, track)
    return size if w <= width or w <= 0 else max(4.0, size * width / w)


# ---- pure math: the line work ---------------------------------------------------------------------------------------
def poly(cv, pts, thick=2, closed=True):
    cv2.polylines(cv, [np.int32(np.round(pts * SS * 8))], closed, 255, thick, cv2.LINE_AA, shift=3)


def resample(pts, step=1.0):
    """a closed polyline, evenly spaced by arc length"""
    d = np.hypot(*np.diff(np.vstack([pts, pts[:1]]), axis=0).T)
    s = np.concatenate([[0], np.cumsum(d)])
    L = s[-1]
    n = int(L / step)
    u = np.linspace(0, L, n, endpoint=False)
    closed = np.vstack([pts, pts[:1]])
    return np.c_[np.interp(u, s, closed[:, 0]), np.interp(u, s, closed[:, 1])]


def normals(pts):
    t = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
    t /= np.maximum(1e-6, np.hypot(t[:, 0], t[:, 1]))[:, None]
    return np.c_[t[:, 1], -t[:, 0]]


def ellipse_path(cx, cy, rx, ry):
    th = np.linspace(0, 2 * np.pi, 6000, endpoint=False)
    return resample(np.c_[cx + rx * np.cos(th), cy + ry * np.sin(th)])


def rrect_path(x0, y0, x1, y1, r):
    pts = []
    for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for a in np.linspace(a0, a0 + 90, 60):
            pts.append((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
    return resample(np.array(pts))


def weave(cv, path, amp, waves, strands, thick=2, swell=None):
    """the bank-note border: strands of one sine wave, each a phase along, running round a closed path. The crossings
    make the lace"""
    n = normals(path)
    s = np.arange(len(path)) / len(path)
    for k in range(strands):
        off = amp * np.sin(2 * np.pi * waves * s + 2 * np.pi * k / strands)
        if swell:
            off = off * (1 - swell[0] + swell[0] * np.cos(2 * np.pi * swell[1] * s + 2 * np.pi * k / strands * swell[2]))
        poly(cv, path + n * off[:, None], thick)


def rosette(cv, cx, cy, r0, a1, n1, a2, n2, strands, thick=2, squash=1.0):
    """spirograph lace: strands of a radius that beats at two frequencies, each strand a phase along"""
    th = np.linspace(0, 2 * np.pi, 3000, endpoint=False)
    for k in range(strands):
        p = 2 * np.pi * k / strands
        r = r0 + a1 * np.sin(n1 * th + p) + a2 * np.sin(n2 * th - 2 * p)
        poly(cv, np.c_[cx + r * np.cos(th), cy + r * np.sin(th) * squash], thick)


def lathe_field(cv, x0, y0, x1, y1):
    """the tint behind everything: a dense family of waves, each line a touch out of phase with the last, so they beat
    into slow moire bands"""
    xs = np.arange(x0, x1, 1.0)
    for dy, a1, l1, a2, l2, psi, th in ((4.2, 9, 148, 3.5, 61, .055, 2), (6.3, 13, 233, 2, 47, -.041, 2)):
        for k in range(int((y1 - y0) / dy) + 40):
            y = y0 - 80 + k * dy + a1 * np.sin(2 * np.pi * xs / l1 + k * psi) + a2 * np.sin(2 * np.pi * xs / l2 - k * psi * 1.7)
            poly(cv, np.c_[xs, y], th, closed=False)


def text_mask(shape, text, x, y, f, anchor="mm", track=0.0):
    """text at note px (x, y) on an SS canvas, tracked by hand so letter spacing is real. A uint8 mask the size of the
    canvas"""
    im = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(im)
    if track == 0:
        d.text((x * SS, y * SS), text, font=f, fill=255, anchor=anchor)
    else:
        total = sum(f.getlength(c) for c in text) + track * SS * (len(text) - 1)
        px = x * SS - total / 2
        for c in text:
            d.text((px, y * SS), c, font=f, fill=255, anchor="l" + anchor[1])
            px += f.getlength(c) + track * SS
    return np.asarray(im, np.uint8)


def ring_text(cv, text, cx, cy, rx, ry, f):
    """microtext on an ellipse, every glyph turned to the tangent; the phrase repeats to go round once and the tracking
    closes the ring exactly"""
    path = ellipse_path(cx * SS, cy * SS, rx * SS, ry * SS)
    L = len(path)
    unit = sum(f.getlength(c) for c in text)
    if unit > L:                                  # a long window: as much of it as goes round once
        while text and sum(f.getlength(c) for c in text) > L * 0.98:
            text = text[:-1]
    else:
        text = text * max(1, int(L * 0.98 // max(unit, 1)))
    adv = [f.getlength(c) for c in text]
    extra = max(0.0, (L - sum(adv)) / max(1, len(text)))
    s = L * .75                                   # start at the top of the oval
    size = int(f.size * 2.2)
    for c, a in zip(text, adv):
        mid = int(s + a / 2) % L
        p, q = path[mid], path[(mid + 6) % L]
        ang = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
        g = Image.new("L", (size, size), 0)
        ImageDraw.Draw(g).text((size / 2, size / 2), c, font=f, fill=255, anchor="mm")
        g = np.asarray(g.rotate(-ang, resample=Image.BICUBIC), np.uint8)
        x0, y0 = int(p[0] - size / 2), int(p[1] - size / 2)
        region = cv[y0:y0 + size, x0:x0 + size]
        np.maximum(region, g[:region.shape[0], :region.shape[1]], out=region)
        s = (s + a + extra) % L


def erode(m, r):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    return cv2.erode(m, k)


def engrave_text(mask, y_top, y_bot, pitch=3.0, lit=.62, shade=(0, 0), outline=2):
    """a letter as an engraver cuts it: solid ink crossed by paper-white hairlines that are widest at the top of the
    letter and pinch out toward the foot, so it is lit from above with no gradient, only line. shade: a hatched cast
    shadow to the lower right. mask: uint8 at SS"""
    h, w = mask.shape
    m = mask.astype(np.float32) / 255
    ys = (np.arange(h, dtype=np.float32) + .5)[:, None]
    ph = ys / (pitch * SS) * (2 * np.pi)
    t = np.clip((ys / SS - y_top) / max(1, y_bot - y_top), 0, 1)
    white = ink.lines(ph, lit * (1 - t) ** 1.2, .05)
    fill = m * (1 - white)
    edge = np.clip(m - erode(m, outline), 0, 1)
    out = np.maximum(fill, edge)
    if shade[0] or shade[1]:
        M = np.float32([[1, 0, shade[0] * SS], [0, 1, shade[1] * SS]])
        sh = cv2.warpAffine(m, M, (w, h))
        hatch_ph = ink.phase(h, w, -45, 3.2 * SS)
        hatch = ink.lines(hatch_ph, np.full((h, w), .34, np.float32), .08)
        out = np.maximum(out, np.clip(sh - m, 0, 1) * hatch)
    return out


# ---- the static note --------------------------------------------------------------------------------------------------
def build_note(spoken_text, serial, signer, role):
    """everything that does not move, as ink coverage at SS. Returns the ink mask, the clear oval mask, the serial ink"""
    H, W = 1920 * SS, 1080 * SS
    ox, oy, rx, ry = OVAL
    field = np.zeros((H, W), np.uint8)
    lathe_field(field, 93, 93, 987, 1827)
    keep = np.zeros((H, W), np.uint8)
    cv2.rectangle(keep, (94 * SS, 94 * SS), (986 * SS, 1826 * SS), 255, -1)
    field[keep == 0] = 0
    # knock the tint out of what must read clean
    clear = np.zeros((H, W), np.uint8)
    cv2.ellipse(clear, (ox * SS, oy * SS), ((rx + 60) * SS, (ry + 60) * SS), 0, 0, 360, 255, -1, cv2.LINE_AA)
    cv2.rectangle(clear, (PLATE[0] * SS, PLATE[1] * SS), (PLATE[2] * SS, PLATE[3] * SS), 255, -1)
    field = (field.astype(np.float32) * (1 - clear.astype(np.float32) / 255) * FIELD_INK).astype(np.uint8)
    lace = np.zeros((H, W), np.uint8)
    # the border: two rails and a double weave between them
    border = rrect_path(58, 58, 1022, 1862, 42)
    weave(lace, border, 25, 128, 10, thick=2)
    weave(lace, border, 25, 32, 6, thick=2, swell=(.5, 16, 2))
    for inset, th in ((24, 4), (30, 2), (88, 2), (93, 4)):
        poly(lace, rrect_path(inset, inset, 1080 - inset, 1920 - inset, max(6, 72 - inset)), th)
    # the oval: microtext, rope, scalloped lace, rays
    rim = 14
    poly(lace, ellipse_path(ox, oy, rx + 2, ry + 2), 4)
    ring_text(lace, spoken_text + "  *  " + TITLE + "  *  ", ox, oy, rx + rim, ry + rim, font("text", 12.5))
    poly(lace, ellipse_path(ox, oy, rx + 2 * rim, ry + 2 * rim), 2)
    weave(lace, ellipse_path(ox, oy, rx + 2 * rim + 13, ry + 2 * rim + 13), 11, 110, 6, thick=2)
    poly(lace, ellipse_path(ox, oy, rx + 2 * rim + 26, ry + 2 * rim + 26), 2)
    outer = ellipse_path(ox, oy, rx + 2 * rim + 28, ry + 2 * rim + 28)
    nn = normals(outer)
    s = np.arange(len(outer)) / len(outer)
    for k in range(14):                       # the scallop: lace that blooms off the rope and fades into the tint
        p = 2 * np.pi * k / 14
        off = 12 + 11 * np.sin(2 * np.pi * 48 * s + p) + 5 * np.sin(2 * np.pi * 144 * s - 2 * p)
        poly(lace, outer + nn * off[:, None], 2)
    # big plate for the number: double rule
    px0, py0, px1, py1 = PLATE
    for inset, th in ((0, 4), (6, 2)):
        poly(lace, rrect_path(px0 + inset, py0 + inset, px1 - inset, py1 - inset, 24), th)
    # lower field: a ribbon across the note, a rosette on it, the signature in its heart
    rc = (540, 1650)
    rib = np.zeros((H, W), np.uint8)
    xs = np.arange(94.0, 986.0, 1.0)
    for k in range(16):
        p = 2 * np.pi * k / 16
        env = .55 + .45 * np.abs(xs - 540) / 446
        y = rc[1] + 64 * env * np.sin(2 * np.pi * xs / 44 + p) + 9 * np.sin(2 * np.pi * xs / 14.67 - 2 * p)
        poly(rib, np.c_[xs, y], 1, closed=False)
    for dy in (-82, -88, 82, 88):
        poly(rib, np.c_[xs, np.full_like(xs, rc[1] + dy)], 2 if abs(dy) == 88 else 3, closed=False)
    fieldmask = np.zeros((H, W), np.uint8)
    cv2.rectangle(fieldmask, (94 * SS, (rc[1] - 88) * SS), (986 * SS, (rc[1] + 88) * SS), 255, -1)
    field[fieldmask > 0] = 0
    lace = np.maximum(lace, rib)
    disc = np.zeros((H, W), np.uint8)
    cv2.circle(disc, (rc[0] * SS, rc[1] * SS), 186 * SS, 255, -1, cv2.LINE_AA)
    lace[disc > 0] = 0
    field[disc > 0] = 0
    rosette(lace, rc[0], rc[1], 150, 28, 30, 7, 90, 20, thick=1)
    rosette(lace, rc[0], rc[1], 110, 16, 24, 5, 72, 16, thick=1)
    disc = np.zeros((H, W), np.uint8)
    cv2.circle(disc, (rc[0] * SS, rc[1] * SS), 88 * SS, 255, -1, cv2.LINE_AA)
    lace[disc > 0] = 0
    poly(lace, ellipse_path(rc[0], rc[1], 88, 88), 3)
    poly(lace, ellipse_path(rc[0], rc[1], 82, 82), 2)
    # four corner plates for the denomination, breaking the border the way a value panel does, and two centre plates
    plates = list(CORNERS) + [(402, 40, 678, 116), (392, 1804, 688, 1880)]
    for (x0, y0, x1, y1) in plates:
        c = np.zeros((H, W), np.uint8)
        cv2.rectangle(c, ((x0 + 20) * SS, y0 * SS), ((x1 - 20) * SS, y1 * SS), 255, -1)
        cv2.rectangle(c, (x0 * SS, (y0 + 20) * SS), (x1 * SS, (y1 - 20) * SS), 255, -1)
        for cc in ((x0 + 20, y0 + 20), (x1 - 20, y0 + 20), (x0 + 20, y1 - 20), (x1 - 20, y1 - 20)):
            cv2.circle(c, (cc[0] * SS, cc[1] * SS), 20 * SS, 255, -1, cv2.LINE_AA)
        lace[c > 0] = 0
        field[c > 0] = 0
        poly(lace, rrect_path(x0, y0, x1, y1, 20), 4)
        poly(lace, rrect_path(x0 + 8, y0 + 8, x1 - 8, y1 - 8, 13), 2)
        weave(lace, rrect_path(x0 + 4, y0 + 4, x1 - 4, y1 - 4, 16), 3, 90, 3, thick=1)
    type_ink = np.zeros((H, W), np.float32)
    # the title in engraved caps, in the display face
    size = fit("display", TITLE, 53, PLATE[2] - PLATE[0] - 80, track=2.2)
    t = text_mask((H, W), TITLE, 540, TITLE_Y, font("display", size), "mm", track=2.2)
    type_ink = np.maximum(type_ink, engrave_text(t, TITLE_Y - 19, TITLE_Y + 19, pitch=2.6, lit=.34, outline=1))
    # the heart of the rosette: the signer, one or two lines, and a role under it
    if signer:
        parts = signer.split(" ", 1)
        rows = [(parts[0], rc[1] - 16), (parts[1], rc[1] + 18)] if len(parts) == 2 else [(signer, rc[1])]
        size = min(fit("display", r[0], 34, 148) for r in rows)
        for txt, y in rows:
            type_ink = np.maximum(type_ink, text_mask((H, W), txt, rc[0], y, font("display", size)).astype(np.float32) / 255)
        if role:
            size = fit("text", role, 13, 140, track=1.4)
            type_ink = np.maximum(type_ink, text_mask((H, W), role, rc[0], rc[1] + 52, font("text", size), track=1.4).astype(np.float32) / 255)
    size = min(fit("text", line, 18, 252, track=1.5) for line in DISCLAIMER)
    for line, y in zip(DISCLAIMER, (1829, 1855)):
        type_ink = np.maximum(type_ink, text_mask((H, W), line, 540, y, font("text", size), track=1.5).astype(np.float32) / 255)
    # the serial, the only second ink
    serial_ink = np.zeros((H, W), np.float32)
    size = fit("mono", serial, 27, 236, track=1.4)
    serial_ink = np.maximum(serial_ink, text_mask((H, W), serial, 540, 78, font("mono", size), track=1.4).astype(np.float32) / 255)
    all_ink = np.maximum(np.maximum(field, lace).astype(np.float32) / 255, type_ink)
    ov = np.zeros((H, W), np.uint8)
    cv2.ellipse(ov, (ox * SS, oy * SS), (rx * SS, ry * SS), 0, 0, 360, 255, -1, cv2.LINE_AA)
    return all_ink, ov.astype(np.float32) / 255, serial_ink


def number_layers():
    """each glyph of the number, in the big plate and in the corner plates, as ink at SS cropped to its own box. Printed
    one by one on the words"""
    H, W = 1920 * SS, 1080 * SS
    out = [[] for _ in NUMBER]
    # the big number: as large as the plate takes, its width and its cap height both
    size = fit("display", NUMBER, NUMBER_SIZE, PLATE[2] - PLATE[0] - 80)
    l_, t_, r_, b_ = font("display", size).getbbox("0123456789", anchor="ls")
    cap = -t_ / SS
    room = NUMBER_BASE - PLATE[1] - 18
    if cap > room:
        size *= room / cap
    big = font("display", size)
    widths = [big.getlength(c) / SS for c in NUMBER]
    x = 540 - sum(widths) / 2
    # cap height of the digits: measured, so the engraved light runs top to foot of the glyph
    l_, t_, r_, b_ = big.getbbox("1", anchor="ls")
    ytop, yfoot = NUMBER_BASE + t_ / SS, NUMBER_BASE + b_ / SS
    for i, c in enumerate(NUMBER):
        im = Image.new("L", (W, H), 0)
        ImageDraw.Draw(im).text((x * SS, NUMBER_BASE * SS), c, font=big, fill=255, anchor="ls")
        layer = engrave_text(np.asarray(im, np.uint8), ytop, yfoot, pitch=3.6, lit=.46, shade=(5, 5), outline=2)
        out[i].append(crop_layer(layer))
        x += widths[i]
    small = font("display", fit("display", NUMBER, 62, CORNERS[0][2] - CORNERS[0][0] - 56))
    swidths = [small.getlength(c) / SS for c in NUMBER]
    l_, t_, r_, b_ = small.getbbox("1", anchor="ls")
    for (px0, py0, px1, py1) in CORNERS:
        x = (px0 + px1) / 2 - sum(swidths) / 2
        sbase = (py0 + py1) / 2 + (-t_ / SS) / 2 - 2
        for i, c in enumerate(NUMBER):
            im = Image.new("L", (W, H), 0)
            ImageDraw.Draw(im).text((x * SS, sbase * SS), c, font=small, fill=255, anchor="ls")
            layer = engrave_text(np.asarray(im, np.uint8), sbase + t_ / SS, sbase + b_ / SS, pitch=2.8, lit=.38, outline=1)
            out[i].append(crop_layer(layer))
            x += swidths[i]
    return out


def crop_layer(a):
    ys, xs = np.where(a > 0)
    if len(ys) == 0:
        return (0, 0, np.zeros((SS, SS), np.float32))
    pad = 12
    y0, y1, x0, x1 = max(0, ys.min() - pad), ys.max() + pad, max(0, xs.min() - pad), xs.max() + pad
    x0, y0 = x0 - x0 % SS, y0 - y0 % SS                # on the note's own grid, so it lands where it was set
    return (x0, y0, a[y0:y1, x0:x1].copy())


# ---- the live portrait ----------------------------------------------------------------------------------------------
class Portrait:
    def __init__(self, faces, framing):
        ox, oy, rx, ry = OVAL
        self.faces, self.have = faces, sorted(faces)
        self.src_cx, self.src_cy, self.scale = framing
        self.box = (ox - rx, oy - ry, 2 * rx, 2 * ry)
        self.H, self.W = 2 * ry * SS, 2 * rx * SS
        ys, xs = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        self.xs, self.ys = (xs + .5) / SS, (ys + .5) / SS       # oval box px
        # the field round them: a turned lattice of rings and rays, heavier toward the rim, so the head sits in a pool
        # of light made of line
        u, v = (self.xs - rx) / rx, (self.ys - ry) / ry
        rr = np.sqrt(u * u + v * v)
        ang = np.arctan2(v, u)
        rings = rr * ry / 4.6 * 2 * np.pi
        rays = ang * 300
        w_ring = np.clip(.26 + .44 * rr ** 2.2, 0, .82)
        w_ray = np.clip(.04 + .44 * rr ** 3, 0, .56)
        self.bg = np.maximum(ink.lines(rings, w_ring, .10), ink.lines(rays, w_ray, .14))
        self.base = None

    def face(self, n):
        """the face on frame n, or on the nearest frame of the window that has one"""
        if n in self.faces:
            return self.faces[n]
        return self.faces[min(self.have, key=lambda k: abs(k - n))]

    def to_box(self, x, y):
        rx, ry = OVAL[2], OVAL[3]
        if FLIP:
            x = CW - x
        return (x - self.src_cx) * self.scale + rx, (y - self.src_cy) * self.scale + ry

    def engrave(self, rgb, al, dep, n):
        """one frame of the speaker, cut in line. rgb, al, dep are full frames, already flipped. Returns ink coverage at
        SS in the oval box"""
        rx, ry = OVAL[2], OVAL[3]
        sw, sh = int(2 * rx / self.scale), int(2 * ry / self.scale)
        x0, y0 = int(self.src_cx - sw / 2), int(self.src_cy - sh / 2)

        def crop(a):
            c = a[max(0, y0):max(0, y0 + sh), max(0, x0):max(0, x0 + sw)]
            if c.shape[0] < sh or c.shape[1] < sw:
                c = cv2.copyMakeBorder(np.ascontiguousarray(c), max(0, -y0), max(0, sh - c.shape[0] - max(0, -y0)),
                                       max(0, -x0), max(0, sw - c.shape[1] - max(0, -x0)), cv2.BORDER_REPLICATE)
            return np.ascontiguousarray(c)
        e = self.face(n)
        fx, fy = self.to_box(e["cx"], e["cy"])
        fw, fh = e["w"] * self.scale, e["h"] * self.scale
        roll = -e["roll"] if FLIP else e["roll"]
        if self.base is None:
            self.base = (fx, fy, roll)
        g = ink.pan_gray(crop(rgb), .35, .50, .15)
        # the picture desk: open the eyes, lift the mouth, calm busy clothes below the chin
        gh, gw = g.shape
        yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
        lift = np.zeros_like(g)
        k = 1 / self.scale
        for ex, ey in e["eyes"]:
            bx, by = self.to_box(ex, ey)
            lift += np.exp(-(((xx - bx * k) / (fw * k * .20)) ** 2 + ((yy - by * k) / (fw * k * .13)) ** 2))
        mx, my = self.to_box(*e["mouth"])
        mouth = np.exp(-(((xx - mx * k) / (fw * k * .30)) ** 2 + ((yy - my * k) / (fw * k * .20)) ** 2))
        g = g + .03 * lift + 1.1 * mouth * (g - cv2.GaussianBlur(g, (0, 0), 8))
        _, cy_chin = self.to_box(e["cx"], e["chin"])
        below = np.clip((yy - (cy_chin * k + 24)) / 50, 0, 1)
        g = g * (1 - below) + (cv2.GaussianBlur(g, (0, 0), 3.2) * .9 + .03) * below
        g = ink.local_contrast(g, 6, .8, 26, .55)
        tone = cv2.resize(g, (self.W, self.H), interpolation=cv2.INTER_CUBIC)
        aa = cv2.resize(crop(al).astype(np.float32) / 255, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        D = cv2.resize(crop(dep), (self.W, self.H), interpolation=cv2.INTER_CUBIC)
        # the warp: a head-shaped bulge plus the fine relief of the depth map, plus a shift that rides with the head so
        # the lines stay on it
        c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        dx, dy = self.xs - fx, self.ys - fy
        u = (dx * c + dy * s) / (fw * .78)
        v = (-dx * s + dy * c) / (fh * .80)
        q = np.clip(1 - u * u - v * v, 0, 1)
        bulge = np.sqrt(q)
        head = np.clip(q * 6, 0, 1)
        head = head * head * (3 - 2 * head)
        fall = np.clip((self.ys - (cy_chin - .02 * fh)) / (.10 * fh), 0, 1)   # nothing bends below the chin: a mic
        head = head * (1 - fall * fall * (3 - 2 * fall))                       # under it would whirl the lines
        dk = 1 - ink.curve(tone, [(0, 0), (.08, .03), (.28, .28), (.5, .58), (.72, .85), (.88, .98), (1, 1)])
        dk = dk * (1 - FACE_LIFT * head * (1 - dk))           # a lit face: the lights and mids open up, the deep darks stay
        relief = np.clip(D - cv2.GaussianBlur(D, (0, 0), 70 * SS / 3), -.045, .045)
        fdx, fdy = fx - self.base[0], fy - self.base[1]
        drot = math.radians(roll - self.base[2])
        rx_, ry_ = -dy * drot, dx * drot

        def warp(angle, bulge_amp, relief_amp):
            a = math.radians(angle)
            nx, ny = -math.sin(a), math.cos(a)
            ride = -((fdx + rx_) * nx + (fdy + ry_) * ny) * head
            return (ride + bulge_amp * bulge * head + relief_amp * relief * (.16 + .84 * head)) * SS
        P1 = PITCH * SS
        ph1 = ink.phase(self.H, self.W, -4, P1, warp(-4, 92, 200), ss=1)
        ph2 = ink.phase(self.H, self.W, 58, P1, warp(58, -40, -100), ss=1)
        ph3 = ink.phase(self.H, self.W, -62, P1, warp(-62, 14, 60), ss=1)
        w1 = np.clip(dk / .62, 0, 1) ** .85 * .86
        loz = np.clip(1 - dk / .55, 0, 1) * .65              # in the lights the line pinches into lozenges where the
        w1 = w1 * (1 - loz + loz * (.5 + .5 * np.cos(ph2)))  # crossing family passes
        w2 = np.clip((dk - .42) / .48, 0, 1) * .72
        w3 = np.clip((dk - .72) / .28, 0, 1) * .62
        m = np.maximum.reduce([ink.lines(ph1, w1, .06), ink.lines(ph2, w2, .06), ink.lines(ph3, w3, .06)])
        return m * aa + self.bg * (1 - aa)


# ---- frames in, frames out ------------------------------------------------------------------------------------------
def depth_cache(work, A, B):
    """Depth Anything on every frame of the window (the kit's depth.py), smoothed in time: the model flickers and these
    lines would show it"""
    p = os.path.join(work, f"depth_{A:.2f}_{B:.2f}.npy")
    if os.path.exists(p):
        return np.load(p, mmap_mode="r")
    import depth                                     # KIT/pipeline/depth.py: the model is fetched on first use
    out = []
    for _, rgb in fxlib.frames(PROJECT, A, B):
        d = depth.infer(rgb)
        out.append(cv2.resize(cv2.GaussianBlur(d, (0, 0), 3), (CW // 2, CH // 2), interpolation=cv2.INTER_AREA))
    a = np.array(out, np.float32)
    kernel = np.array([1, 4, 6, 4, 1], np.float32) / 16
    b = a.copy()
    for i in range(len(a)):
        idx = np.clip(np.arange(i - 2, i + 3), 0, len(a) - 1)
        b[i] = (a[idx] * kernel[:, None, None]).sum(0)
    os.makedirs(work, exist_ok=True)
    np.save(p, b.astype(np.float16))
    return b


class Bill:
    def __init__(self, faces, framing, lands, punch, spoken_text, serial, signer, role):
        self.note3, self.ov3, self.serial3 = build_note(spoken_text, serial, signer, role)
        self.note1 = cv2.resize(self.note3, (1080, 1920), interpolation=cv2.INTER_AREA)
        self.ov1 = cv2.resize(self.ov3, (1080, 1920), interpolation=cv2.INTER_AREA)
        self.serial1 = cv2.resize(self.serial3, (1080, 1920), interpolation=cv2.INTER_AREA)
        del self.note3, self.ov3, self.serial3
        self.glyphs = number_layers()
        self.glyph_frames = [fxlib.fr(t) for t in lands]
        self.punch = fxlib.fr(punch)
        self.portrait = Portrait(faces, framing)
        pap = np.array(PAPER, np.float32)[None, None] * ink.fibre(1920, 1080, seed=21)[..., None]
        # a few security threads, one per ink, the way a note's paper has them
        rng = np.random.default_rng(5)
        for col, n in ((NOTE_INK, 220), (SERIAL_INK, 170)):
            lay = np.zeros((1920, 1080), np.float32)
            for _ in range(n):
                x, y, a, ln = rng.uniform(0, 1080), rng.uniform(0, 1920), rng.uniform(0, np.pi), rng.uniform(8, 26)
                bend = rng.uniform(-.5, .5)
                t = np.linspace(0, 1, 12)
                pts = np.c_[x + np.cos(a + bend * t) * ln * t, y + np.sin(a + bend * t) * ln * t]
                cv2.polylines(lay, [np.int32(pts * 8)], False, 1.0, 1, cv2.LINE_AA, shift=3)
            pap = pap * (1 - lay[..., None] * .10) + np.array(col, np.float32) * lay[..., None] * .10
        self.paper1 = pap

    def glyph_ink(self, n):
        """the glyphs printed so far: a new one lands fat and wet and draws in over three frames. On the punch the whole
        number goes wet once more"""
        return [(i, n - self.punch if 0 <= n - self.punch < 3 else n - f) for i, f in enumerate(self.glyph_frames) if n >= f]

    def compose(self, n, rgb, al, dep):
        px, py, pw, ph = self.portrait.box
        cut = self.portrait.engrave(rgb, al, dep, n)
        oval = cv2.resize(cut, (pw, ph), interpolation=cv2.INTER_AREA)
        m = self.note1.copy()
        e = self.ov1[py:py + ph, px:px + pw]
        m[py:py + ph, px:px + pw] = m[py:py + ph, px:px + pw] * (1 - e) + oval * e
        # the digits, at SS, one window each
        for i, age in self.glyph_ink(n):
            for (x0, y0, g) in self.glyphs[i]:
                if age < 3:
                    r, thr = ((3.6, .20), (2.6, .30), (1.6, .40))[age]
                    g2 = np.clip((cv2.GaussianBlur(g, (0, 0), r) - thr) / .12 + .5, 0, 1)
                else:
                    g2 = g
                X0, Y0 = x0 // SS, y0 // SS                           # to output size, on the note's own grid
                small = cv2.resize(g2, (max(1, g2.shape[1] // SS), max(1, g2.shape[0] // SS)), interpolation=cv2.INTER_AREA)
                h, w = small.shape[:2]
                h, w = min(h, 1920 - Y0), min(w, 1080 - X0)
                m[Y0:Y0 + h, X0:X0 + w] = np.maximum(m[Y0:Y0 + h, X0:X0 + w], small[:h, :w])
        a = m[..., None] * .975
        b = self.serial1[..., None] * .95
        img = self.paper1 * (1 - a) + np.array(NOTE_INK, np.float32) * a
        return img * (1 - b) + np.array(SERIAL_INK, np.float32) * b


def flipped(a):
    return np.ascontiguousarray(a[:, ::-1]) if FLIP else a


def scaled(img, s):
    if s == 1.0:
        return img
    M = cv2.getRotationMatrix2D((540, OVAL[1]), 0, s)
    return cv2.warpAffine(img, M, (1080, 1920), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def punch_scale(n, n_in, n_punch):
    a, p = n - n_in, n - n_punch
    if 0 <= a < 4:
        return (1.035, 1.014, 1.004, 1.0)[a]
    if 0 <= p < 5:
        return (1.024, 1.012, 1.005, 1.002, 1.0)[p]
    return 1.0


def to_frame(img, ground):
    """the 9:16 note on the project's frame: as is on 1080x1920, else as tall as the frame, centred on the pack's dark"""
    if (CW, CH) == (1080, 1920):
        return img
    k = min(CW / 1080, CH / 1920)
    w, h = max(2, round(1080 * k)), max(2, round(1920 * k))
    out = np.empty((CH, CW, 3), np.float32)
    out[:] = ground
    x0, y0 = (CW - w) // 2, (CH - h) // 2
    out[y0:y0 + h, x0:x0 + w] = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    return out


def keep_js(out_dir):
    """run from the library folder on a project that has no copy yet: its fx.js comes along with the clip"""
    if not os.path.exists(os.path.join(out_dir, "fx.js")) and os.path.realpath(out_dir) != os.path.realpath(HERE):
        shutil.copy(os.path.join(HERE, "fx.js"), os.path.join(out_dir, "fx.js"))


def main():
    global CW, CH, PROJECT
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="+", type=float, metavar="T", help="output times to write as PNGs, nothing else")
    args = ap.parse_args()
    PROJECT, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(PROJECT, fid)
    A, B = float(F["at"]), float(F["end"])
    CW, CH = fxlib.size(os.path.join(PROJECT, "public", "clean.mp4"))
    S = fxlib.pack(PROJECT)
    words = fxlib.words(PROJECT) if os.path.exists(os.path.join(PROJECT, "words.json")) else []
    work = os.path.join(PROJECT, "work", fid)
    out_dir = os.path.join(PROJECT, "fx", fid)
    os.makedirs(work, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    if NUMBER == "12,345.67" or TITLE == "PLACEHOLDER TITLE":
        print("  WARNING NUMBER and TITLE are still the placeholders: set the creator's real number and what it is")

    # ---- the face over the window, and where it sits in the oval
    frames = fxlib.tracks(PROJECT)["frames"]
    n0, n1 = fxlib.fr(A), max(fxlib.fr(B), fxlib.fr(A) + 1)
    faces = {n: frames[n]["face"] for n in range(n0, min(n1, len(frames))) if frames[n] and frames[n].get("face")}
    if not faces:
        sys.exit(f"no face in work/tracks/track.json between {A:.2f} and {B:.2f}: the portrait follows the face")
    med = lambda k: float(np.median([f[k] for f in faces.values()]))   # noqa: E731
    cx = CW - med("cx") if FLIP else med("cx")
    framing = (FACE_CX if FACE_CX is not None else cx,
               SRC_CY if SRC_CY is not None else med("cy") - FACE_Y * med("h"),
               SCALE if SCALE is not None else FACE_SIZE * 2 * OVAL[2] / med("w"))
    print(f"banknote {fid}: {A:.2f}-{B:.2f}, frame {CW}x{CH}; footage ({framing[0]:.0f}, {framing[1]:.0f}) at the oval's "
          f"centre, scale {framing[2]:.3f}")

    # ---- the words: when each glyph prints, the punch, the microtext
    lands = glyph_times(A, B)
    punch = cue(PUNCH_ON, lands[-1], B)
    if punch is None:
        punch = lands[-1]
    said = ""
    for s, _, t in words:                    # transcription splits "$12,000." into "$12" ",000.": no space before those
        if A - 0.001 <= s < B:
            said += ("" if not said or t[:1] in ",.;:!?)%" else " ") + t
    said = said.upper()
    spoken_text = SPOKEN or said or TITLE
    digits = re.sub(r"\D", "", NUMBER)[-8:].zfill(8)
    initials = [w[0] for w in TITLE.split() if w[:1].isalpha()] or ["A"]
    serial = SERIAL or f"{''.join(initials[:2]).ljust(2, initials[0])} {digits} {initials[-1]}"
    creator = S.get("creator") or {}
    name = creator.get("name") or ""
    if name.strip().lower().replace(" ", "-") == "reel-kit":     # the kit's own placeholder name, not a creator
        name = ""
    signer = SIGNER or name or creator.get("handle") or ""
    print("  glyphs at " + " ".join(f"{t:.2f}" for t in lands) + f"; punch {punch:.2f}; serial {serial}")

    bill = Bill(faces, framing, lands, punch, spoken_text, serial, signer, SIGNER_ROLE)
    dep_all = depth_cache(work, A, B)
    ground = np.array(S["colors"]["dark"][:3], np.float32)
    n_punch = fxlib.fr(punch)

    def frame(n, rgb, al):
        d = cv2.resize(np.asarray(dep_all[min(n - n0, len(dep_all) - 1)], np.float32), (CW, CH), interpolation=cv2.INTER_CUBIC)
        im = scaled(bill.compose(n, flipped(rgb), flipped(al), flipped(d)), punch_scale(n, n0, n_punch))
        return to_frame(im, ground)

    if args.stills:
        want = {fxlib.fr(t) for t in args.stills}
        for (n, rgb), (_, al) in zip(fxlib.frames(PROJECT, A, B), fxlib.alpha(PROJECT, A, B)):
            if n in want:
                out = os.path.join(work, f"still_{n / FPS:.2f}.png")
                cv2.imwrite(out, cv2.cvtColor(np.clip(frame(n, rgb, al), 0, 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
                print(out)
        return
    # the clip goes through the video's renderer, which shifts paper toward green, so it is sent compensated. Written
    # to a temp name first: a half-written clip must never sit where something can read it
    tmp = os.path.join(work, "note.tmp.mp4")
    w = fxlib.Writer(tmp, w=CW, h=CH, crf=17)
    count = 0
    for (n, rgb), (_, al) in zip(fxlib.frames(PROJECT, A, B), fxlib.alpha(PROJECT, A, B)):
        w.write(np.clip(ink.for_renderer(frame(n, rgb, al)), 0, 255).astype(np.uint8))
        count += 1
    w.close()
    if count < n1 - n0:
        sys.exit(f"only {count} of {n1 - n0} frames could be read: is the window inside the video?")
    os.replace(tmp, os.path.join(out_dir, "note.mp4"))
    tag = (f'<video id="{{{{ID}}}}-clip" src="fx/{{{{ID}}}}/note.mp4" muted playsinline data-start="{{{{START}}}}" '
           f'data-media-start="0.0010" data-duration="{(n1 - n0) / FPS:.4f}" data-track-index="{{{{T0}}}}" '
           f'style="position:absolute;left:0;top:0;width:{CW}px;height:{CH}px;"></video>')
    with open(os.path.join(out_dir, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write("<!-- banknote (over): written by gen.py. note.mp4 is the whole note for this window, pre-rendered "
                 "(frame 0 is the window's\n     first frame, the speaker's lips are the live frames). -->\n" + tag + "\n")
    keep_js(out_dir)
    print(f"wrote {out_dir}/note.mp4 ({n1 - n0} frames) and fx.html")
    print(f"edit.py: KARAOKE hide over the window, e.g. ({A:.2f}, {B:.2f}); SOUND sfx to start from:")
    print(f"    ({A:.3f}, \"impact-low\", -12),   # the note slams in")
    last = -1.0
    for t in lands:
        if t - last >= 0.1:
            print(f"    ({t:.3f}, \"tick\", -14),   # a glyph prints")
            last = t
    print(f"    ({punch:.3f}, \"shutter\", -12),   # the whole note hits, the number goes wet")


if __name__ == "__main__":
    main()
