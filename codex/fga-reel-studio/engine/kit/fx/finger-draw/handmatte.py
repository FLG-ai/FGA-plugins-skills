"""finger-draw's hand matte: a clean matte of the speaker's real hand, per frame, so the line can hang behind it.
hand_matte: the landmark hull as a gate, near depth as the body of the hand (how far a pixel stands in front of the big
shapes behind it), skin colour on top, guided to the picture's own edges, feathered to the hand's softness.
depth_crop: Depth Anything V2 (the kit's pipeline/depth.py, model fetched on first use) at about 1:1 on a crop, cached.
gen.py puts KIT/pipeline on the import path before it imports this."""
import os

import cv2
import numpy as np

KEYS = ("wrist", "palm", "thumb", "index", "middle", "pinky")


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def depth_crop(path, crop, side=1036):
    """float32 depth of an rgb crop, near = 1, cached at path (about 1 s a frame on a CPU)"""
    if os.path.exists(path):
        return np.load(path).astype(np.float32)
    import depth                                    # KIT/pipeline/depth.py
    d = depth.infer(crop, side)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, d.astype(np.float16))
    return d.astype(np.float32)


def guided(I, p, r, eps):
    k = (2 * r + 1, 2 * r + 1)
    mI, mp = cv2.boxFilter(I, cv2.CV_32F, k), cv2.boxFilter(p, cv2.CV_32F, k)
    cov = cv2.boxFilter(I * p, cv2.CV_32F, k) - mI * mp
    var = cv2.boxFilter(I * I, cv2.CV_32F, k) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return cv2.boxFilter(a, cv2.CV_32F, k) * I + cv2.boxFilter(b, cv2.CV_32F, k)


def hull_gate(shape, hand, grow, y0=0, x0=0):
    pts = np.array([hand[k] for k in KEYS], np.float32) - [x0, y0]
    m = np.zeros(shape, np.uint8)
    cv2.fillConvexPoly(m, cv2.convexHull(pts.astype(np.int32)), 255)
    gk = int(grow) * 2 + 1
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gk, gk)))
    return cv2.GaussianBlur(m, (0, 0), max(2, grow * 0.1)).astype(np.float32) / 255


def prominence(d, r=300):
    """how far each pixel stands in front of the big shapes behind it (torso, desk). Hands and a mic pop, the slope of
    the clothes does not"""
    s = cv2.resize(d, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    o = cv2.morphologyEx(s, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r // 4 | 1, r // 4 | 1)))
    o = cv2.GaussianBlur(o, (0, 0), 6)
    return d - cv2.resize(o, (d.shape[1], d.shape[0]), interpolation=cv2.INTER_LINEAR)


def fill_small_holes(m, area=700):
    """shaded palm creases leave pinholes; the gaps between fingers are far bigger and stay"""
    b = (m > 0.5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(1 - b, connectivity=4)
    out = m.copy()
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < area:
            out[lab == i] = 1
    return out


def hand_matte(crop, d, hands, mic, y0=0, x0=0, grow=46, feather=1.0):
    """crop rgb uint8 at (x0, y0) of the frame, d its depth, hands landmark dicts in frame px, mic float alpha of a mic
    on the crop (or None) -> float32 0..1"""
    lab = cv2.cvtColor(crop, cv2.COLOR_RGB2LAB).astype(np.float32)
    L, a, b = lab[..., 0] * 100 / 255, lab[..., 1] - 128, lab[..., 2] - 128
    hue = np.degrees(np.arctan2(b, a))
    chroma = np.hypot(a, b)
    gate = np.zeros(L.shape, np.float32)
    for h in hands:
        gate = np.maximum(gate, hull_gate(L.shape, h, grow, y0, x0))
    prom = prominence(d)
    skin = smooth(27, 38, hue) * smooth(12, 22, L) * smooth(5, 11, chroma)
    gear = 1 - smooth(2, 6, chroma)                     # black things stand as near as a hand and are not hands
    if mic is not None:
        gear = np.maximum(mic * (1 - skin), gear)
    coarse = gate * np.clip(np.maximum(smooth(0.035, 0.075, prom) * (1 - gear), skin * smooth(0.01, 0.04, prom)), 0, 1)
    coarse = fill_small_holes(coarse.astype(np.float32))
    guide = cv2.GaussianBlur((b - a + 40) / 60, (0, 0), 0.6).astype(np.float32)
    fine = guided(guide, coarse, 5, 2e-4)
    fine = np.clip((fine - 0.2) / 0.6, 0, 1) * smooth(0.0, 0.4, gate)
    if feather:
        fine = cv2.GaussianBlur(fine.astype(np.float32), (0, 0), feather)
    return fine.astype(np.float32)
