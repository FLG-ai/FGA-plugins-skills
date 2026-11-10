"""inkscreen: the print shop banknote engraves with. Plain numpy and OpenCV, deterministic, one frame at a time.
Coverage maps are float32 0..1, 1 = solid ink.
"""
import math

import cv2
import numpy as np


# ---- colour -----------------------------------------------------------------------------------------------------
def for_renderer(rgb):
    """what to send to the encoder so a flat colour comes out of the real render (Writer, Chrome, HyperFrames) as
    asked. Measured on paper and ink through a real render: a clip loses about (6, 2, 6) levels at the light end and
    (2, 2, 5) at the dark end, so paper would go green without this. A PNG on the page is not shifted."""
    c = np.asarray(rgb, np.float32)
    return (c + np.array((.735, 2.43, 4.71), np.float32)) / np.array((.9773, 1.001, .9946), np.float32)


# ---- tone -------------------------------------------------------------------------------------------------------
def pan_gray(rgb, r=.55, g=.35, b=.10):
    """a red-sensitive black and white (panchromatic stock). Returns float32 0..1"""
    a = rgb.astype(np.float32) / 255
    return r * a[..., 0] + g * a[..., 1] + b * a[..., 2]


def curve(x, pts):
    """piecewise-linear tone curve, smoothed by the blur that always follows it"""
    xs, ys = zip(*pts)
    return np.interp(x, xs, ys).astype(np.float32)


def local_contrast(g, s1, a1, s2=0, a2=0):
    """the retoucher's pass before screening: unsharp at the scale the lines can still carry"""
    out = g + a1 * (g - cv2.GaussianBlur(g, (0, 0), s1))
    if s2:
        out = out + a2 * (g - cv2.GaussianBlur(g, (0, 0), s2))
    return out


# ---- line screen ------------------------------------------------------------------------------------------------
def phase(h, w, angle, pitch, warp=None, ss=1):
    """the phase of a family of parallel lines at `angle` degrees from horizontal, `pitch` px apart (output px). warp
    (HxW at the same size, in px) pushes the lines across themselves, so they bend round whatever warp describes. One
    cycle per line."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs, ys = (xs + .5) / ss, (ys + .5) / ss
    a = math.radians(angle)
    s = -xs * math.sin(a) + ys * math.cos(a)
    if warp is not None:
        s = s + warp
    return s / pitch * (2 * np.pi)


def lines(ph, width, soft=.02):
    """ink where the line of phase ph is wider than width (fraction of the pitch, 0..1, may vary per pixel)"""
    tri = np.abs(((ph / (2 * np.pi) + .5) % 1.0) - .5) * 2        # 0 on the line's centre, 1 midway between lines
    return np.clip((width - tri) / soft + .5, 0, 1)


# ---- paper ------------------------------------------------------------------------------------------------------
def fibre(h, w, seed=7, strength=1.0, n=None):
    """a static field of short pale and dark fibres plus a slow, faint mottle (no vignette). Returns float32 around 1.0
    to multiply paper by."""
    rng = np.random.default_rng(seed)
    f = np.zeros((h, w), np.float32)
    n = n or int(h * w / 170)
    pts = np.empty((n, 2, 2), np.int32)
    x, y = rng.uniform(0, w, n), rng.uniform(0, h, n)
    a, ln = rng.uniform(0, np.pi, n), rng.uniform(4, 22, n)
    pts[:, 0, 0], pts[:, 0, 1] = x, y
    pts[:, 1, 0], pts[:, 1, 1] = x + np.cos(a) * ln, y + np.sin(a) * ln
    light, dark = pts[rng.random(n) < .55], pts[rng.random(n) < .45]
    layer = np.zeros((h, w), np.float32)
    cv2.polylines(layer, list(light), False, 1.0, 1, cv2.LINE_AA)
    f += layer * .010
    layer = np.zeros((h, w), np.float32)
    cv2.polylines(layer, list(dark), False, 1.0, 1, cv2.LINE_AA)
    f -= layer * .013
    grain = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), .8)
    f += grain * .012
    mott = cv2.resize(rng.standard_normal((h // 24 + 2, w // 24 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    f += cv2.GaussianBlur(mott, (0, 0), 20) * .010
    return 1.0 + f * strength
