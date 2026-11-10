"""inkscreen: the print shop press-front sets its page with (round-dot halftone, line screen, XDoG ink, paper).
impact-frame and banknote carry their own copies of the parts they use. All of it is plain numpy/cv2, deterministic,
and works on one frame at a time. Import it from this folder's gen.py: sys.path.insert(0, HERE); import inkscreen as ink
Coverage maps are float32 0..1, 1 = solid ink. Every mask comes back antialiased at output size from an ss-times-bigger threshold.
Pages are drawn by the same headless browser HyperFrames renders with: HEADLESS_BROWSER=/path/to/chrome picks another.
"""
import math
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

_BROWSER = []


def browser():
    """the headless browser: HEADLESS_BROWSER, the one setup picked, the one HyperFrames uses, else a Chrome on this computer"""
    if _BROWSER:
        return _BROWSER[0]
    for env in ("HEADLESS_BROWSER", "HYPERFRAMES_BROWSER_PATH"):
        if os.environ.get(env) and os.path.exists(os.environ[env]):
            _BROWSER.append(os.environ[env])
            return _BROWSER[0]
    npx = "npx.cmd" if os.name == "nt" else "npx"
    try:
        r = subprocess.run([npx, "-y", "hyperframes@0.8.139", "browser", "path"], capture_output=True, text=True, timeout=180)
        path = (r.stdout.strip().splitlines() or [""])[-1].strip()
    except (OSError, subprocess.TimeoutExpired):
        path = ""
    if not (path and os.path.exists(path)):
        path = next((p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                 shutil.which("google-chrome") or "", shutil.which("chromium") or "",
                                 shutil.which("chrome") or "") if p and os.path.exists(p)), "")
    if not path:
        sys.exit("no headless browser: run `npx -y hyperframes@0.8.139 browser ensure`, or set HEADLESS_BROWSER=/path/to/chrome")
    _BROWSER.append(path)
    return path


def _url(html, hash=""):
    from urllib.parse import quote
    return "file://" + quote(os.path.abspath(html)) + hash


# ---- colour -----------------------------------------------------------------------------------------------------
def for_renderer(rgb):
    """what to send to the encoder so a flat colour comes out of the real render (Writer, Chrome, hyperframes) as asked. Measured on paper and ink
    through fxclip: a clip loses about (6, 2, 6) levels at the light end and (2, 2, 5) at the dark end. Without this, newsprint goes green.
    A PNG on the page is not shifted: a still that must match a clip keeps the colour you asked for, unsent through this."""
    c = np.asarray(rgb, np.float32)
    return (c + np.array((.735, 2.43, 4.71), np.float32)) / np.array((.9773, 1.001, .9946), np.float32)


# ---- capture ----------------------------------------------------------------------------------------------------
def chrome_shot(html, png, w=1080, h=1920, scale=2, hash=""):
    """headless screenshot of a local html file at scale x. Fonts load over file://, so give them a moment."""
    subprocess.run([browser(), "--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--allow-file-access-from-files",
                    "--run-all-compositor-stages-before-draw", f"--force-device-scale-factor={scale}", f"--window-size={w},{h}",
                    "--virtual-time-budget=4000", f"--screenshot={os.path.abspath(png)}", _url(html, hash)], check=True, capture_output=True)
    return cv2.imread(png, cv2.IMREAD_COLOR)


def chrome_dom(html, w=1080, h=1920, hash=""):
    """the DOM after scripts ran: gen.py reads word rectangles out of it"""
    r = subprocess.run([browser(), "--headless", "--disable-gpu", "--no-first-run", "--allow-file-access-from-files", f"--window-size={w},{h}",
                        "--virtual-time-budget=4000", "--dump-dom", _url(html, hash)], check=True, capture_output=True, text=True)
    return r.stdout


# ---- tone -------------------------------------------------------------------------------------------------------
def pan_gray(rgb, r=.55, g=.35, b=.10):
    """a red-sensitive black and white (panchromatic stock): warm skin and red clothes stay off a dark wall. Returns float32 0..1"""
    a = rgb.astype(np.float32) / 255
    return r * a[..., 0] + g * a[..., 1] + b * a[..., 2]


def curve(x, pts):
    """piecewise-linear tone curve, smoothed by the blur that always follows it"""
    xs, ys = zip(*pts)
    return np.interp(x, xs, ys).astype(np.float32)


def local_contrast(g, s1, a1, s2=0, a2=0):
    """the retoucher's pass before screening: unsharp at the scale the dots can still carry"""
    out = g + a1 * (g - cv2.GaussianBlur(g, (0, 0), s1))
    if s2:
        out = out + a2 * (g - cv2.GaussianBlur(g, (0, 0), s2))
    return out


# ---- round-dot halftone -----------------------------------------------------------------------------------------
_dots = {}


def _dot_lattice(h, w, cell, ss, angle=45.0):
    key = (h, w, cell, ss, angle)
    if key in _dots:
        return _dots[key]
    ys, xs = np.mgrid[0:h * ss, 0:w * ss].astype(np.float32)
    xs, ys = (xs + .5) / ss, (ys + .5) / ss
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    u, v = (xs * ca + ys * sa) / cell, (-xs * sa + ys * ca) / cell
    ru, rv = np.round(u), np.round(v)
    fu, fv = u - ru, v - rv
    d2 = fu * fu + fv * fv
    d = np.sqrt(d2)
    # the threshold is the coverage at which a round dot, growing, reaches this radius: the area of the circle clipped to its cell.
    # That makes tone reproduction exact: a 30% tone prints 30% ink, and past 78.5% the dots merge and leave pinholes of paper.
    t = np.pi * d2
    far = d > .5
    df = np.maximum(d[far], .5)
    t[far] = np.pi * df ** 2 - 4 * (df ** 2 * np.arccos(.5 / df) - .5 * np.sqrt(np.maximum(0, df ** 2 - .25)))
    cx, cy = (ru * ca - rv * sa) * cell, (ru * sa + rv * ca) * cell     # the centre of the dot this pixel belongs to
    _dots[key] = (t.astype(np.float32), cx.astype(np.float32), cy.astype(np.float32))
    return _dots[key]


def round_dots(cov, cell=7.778, ss=4, sharp=.35, angle=45.0, out=1):
    """cov: coverage map, HxW float 0..1. A static 45 degree screen of round dots, so only the radii change over time.
    sharp 0: every dot a perfect circle sized at its centre; 1: every pixel thresholded on its own (edges bite into dots, more detail).
    cell = 5.5 * sqrt(2) or 5 * sqrt(2) keeps the dot centres on the pixel grid: no beat pattern against the pixels. out: 2 returns it at 2x."""
    h, w = cov.shape
    t, cx, cy = _dot_lattice(h, w, cell, ss, angle)
    soft = cv2.GaussianBlur(cov, (0, 0), cell * .3)
    at_centre = cv2.remap(soft, cx - .5, cy - .5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    if sharp > 0:
        up = cv2.resize(cv2.GaussianBlur(cov, (0, 0), cell * .1), (w * ss, h * ss), interpolation=cv2.INTER_CUBIC)
        c = at_centre * (1 - sharp) + up * sharp
    else:
        c = at_centre
    hard = np.clip((c - t) * 40 + .5, 0, 1)                 # a hair of softness at ss, the area filter does the rest
    return cv2.resize(hard, (w * out, h * out), interpolation=cv2.INTER_AREA)


# ---- line screen ------------------------------------------------------------------------------------------------
def phase(h, w, angle, pitch, warp=None, ss=1):
    """the phase of a family of parallel lines at `angle` degrees from horizontal, `pitch` px apart (output px). warp (HxW at the same
    size, in px) pushes the lines across themselves, so they bend round whatever warp describes. One cycle per line."""
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


# ---- XDoG ink ---------------------------------------------------------------------------------------------------
def flow(gray, sigma=4.0):
    """edge tangent field from the structure tensor: (tx, ty) unit vectors along the edges"""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    a, b, c = cv2.GaussianBlur(gx * gx, (0, 0), sigma), cv2.GaussianBlur(gy * gy, (0, 0), sigma), cv2.GaussianBlur(gx * gy, (0, 0), sigma)
    theta = .5 * np.arctan2(2 * c, a - b) + np.pi / 2
    return np.cos(theta).astype(np.float32), np.sin(theta).astype(np.float32)


def along_flow(img, tx, ty, steps=5, step=1.2):
    """smooth img along the flow, a cheap line-integral convolution: broken edges join up into strokes"""
    h, w = img.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    acc, wt = img.copy(), 1.0
    for sign in (1, -1):
        px, py = xs.copy(), ys.copy()
        for k in range(1, steps + 1):
            fx = cv2.remap(tx, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            fy = cv2.remap(ty, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            px, py = px + sign * step * fx, py + sign * step * fy
            g = math.exp(-(k / (steps * .6)) ** 2)
            acc += g * cv2.remap(img, px, py, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            wt += g
    return acc / wt


def xdog(gray, sigma=1.4, k=1.6, p=24.0, eps=.0, tx=None, ty=None):
    """eXtended Difference of Gaussians: sharpened image minus its blur. Returns the raw response (positive = paper side): threshold it yourself."""
    a, b = cv2.GaussianBlur(gray, (0, 0), sigma), cv2.GaussianBlur(gray, (0, 0), sigma * k)
    d = (1 + p) * a - p * b
    if tx is not None:
        d = along_flow(d, tx, ty)
    return d - eps


def clean(mask, min_area=60):
    """drop specks from a boolean ink mask: ink lands in shapes"""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    return keep[lab]


def round_off(mask, r=1.2, ss=1):
    """ink has rounded contours: blur the mask and threshold again"""
    m = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), r * ss)
    return m > .5


# ---- paper ------------------------------------------------------------------------------------------------------
def fibre(h, w, seed=7, strength=1.0, n=None):
    """newsprint: a static field of short pale and dark fibres plus a slow, faint mottle (no vignette). Returns float32 around 1.0 to multiply paper by."""
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


def tooth(h, w, seed=11, area=.018, size=.75):
    """the paper's tooth in a solid: tiny specks where the ink missed. 1 = takes ink, 0 = a speck of paper"""
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), size)
    n /= n.std()
    thr = float(np.quantile(n[::4, ::4], 1 - area))
    return 1 - np.clip((n - thr) / .35, 0, 1)
