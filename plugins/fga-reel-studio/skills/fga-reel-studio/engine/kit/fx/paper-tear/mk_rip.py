#!/usr/bin/env python3
"""paper-rip.wav: a paper rip built from what paper does, no recording (CC0, like everything in audio/sfx). A tear is
thousands of tiny fractures: each one a click a millisecond long, ringing in the fibres at some frequency between 1.5
and 9 kHz. Their rate climbs as the rip speeds up, then the sheet lets go with a soft low flap. Seeded.

Run: PY fx/<id>/mk_rip.py <project>   -> <project>/audio/paper-rip.wav (gen.py runs it for you; mix.py looks there first)
"""
import os
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
DUR_RIP, DUR_TAIL = 0.27, 0.14
SEED = 7


def channel(r, N):
    x = np.zeros(N)
    t = 0.0
    while t < DUR_RIP:
        p = t / DUR_RIP
        rate = 500 + 2600 * p ** 1.4                                # fractures per second: the rip accelerates
        rate *= 0.7 + 0.6 * (np.sin(2 * np.pi * (31 * t + 0.13)) > 0)  # stick and slip
        t += r.exponential(1 / rate)
        i = int(t * SR)
        if i >= N - 200:
            break
        L = int(r.uniform(0.0006, 0.0028) * SR)
        f = np.exp(r.uniform(np.log(1500), np.log(9500)))
        tt = np.arange(L) / SR
        amp = r.lognormal(-0.3, 0.75) * min(1, p * 9 + 0.25) * (1 - 0.35 * p)
        x[i:i + L] += amp * np.exp(-tt * r.uniform(1800, 5000)) * np.sin(2 * np.pi * f * tt + r.uniform(0, 6.28))
    # the noise of the fibres between the clicks, following how busy the tear is
    env = np.convolve(np.abs(x), np.ones(240) / 240, "same")
    return x + sosfilt(butter(2, [1800, 11000], "band", fs=SR, output="sos"), r.normal(0, 1, N)) * env * 2.2


def write(out):
    rng = np.random.RandomState(SEED)
    N = int((DUR_RIP + DUR_TAIL) * SR)
    L, R = channel(np.random.RandomState(SEED), N), channel(np.random.RandomState(SEED + 1), N)
    mix = 0.5 * (L + R)
    L, R = 0.75 * mix + 0.25 * L, 0.75 * mix + 0.25 * R
    # the sheet's body: a low papery rustle under the rip, then the flap as the halves let go
    body = sosfilt(butter(2, [180, 1400], "band", fs=SR, output="sos"), rng.normal(0, 1, N))
    tt = np.arange(N) / SR
    body = body * np.clip(tt / 0.03, 0, 1) * np.exp(-np.maximum(tt - DUR_RIP, 0) / 0.05) * (0.25 + 0.75 * np.clip(tt / DUR_RIP, 0, 1))
    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk, R / pk
    body = body / np.abs(body).max() * 0.32
    L, R = L + body, R + body
    sos = butter(2, 120, "high", fs=SR, output="sos")
    L, R = sosfilt(sos, L), sosfilt(sos, R)
    fade = np.ones(N)
    k = int(0.02 * SR)
    fade[-k:] = np.linspace(1, 0, k)
    L, R = L * fade, R * fade
    pk = max(np.abs(L).max(), np.abs(R).max())
    pcm = (np.stack([L, R], 1) * (10 ** (-2 / 20) / pk) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    w = wave.open(out, "wb")
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
    w.close()
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    print(write(os.path.join(os.path.abspath(os.path.expanduser(sys.argv[1])), "audio", "paper-rip.wav")))
