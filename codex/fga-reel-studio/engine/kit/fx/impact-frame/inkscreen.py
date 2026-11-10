"""inkscreen: the ink helpers impact-frame draws with (the XDoG part of the print shop press-front and banknote share).
Plain numpy and OpenCV, deterministic, one frame at a time. Coverage maps are float32 0..1, 1 = solid ink.
"""
import math

import cv2
import numpy as np


def for_renderer(rgb):
    """what to send to the encoder so a flat colour comes out of the real render (fxlib.Writer, Chrome, HyperFrames) as
    asked. Measured on paper and ink through fxclip: a clip loses about (6, 2, 6) levels at the light end and (2, 2, 5)
    at the dark end. Without this a light ground drifts green."""
    c = np.asarray(rgb, np.float32)
    return (c + np.array((.735, 2.43, 4.71), np.float32)) / np.array((.9773, 1.001, .9946), np.float32)


def pan_gray(rgb, r=.55, g=.35, b=.10):
    """a red-sensitive black and white (panchromatic stock): skin and warm clothes stay off a dark wall. float32 0..1"""
    a = rgb.astype(np.float32) / 255
    return r * a[..., 0] + g * a[..., 1] + b * a[..., 2]


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
    """eXtended Difference of Gaussians: sharpened image minus its blur. The raw response (positive = paper side):
    threshold it yourself."""
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
