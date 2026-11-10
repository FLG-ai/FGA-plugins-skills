#!/usr/bin/env python3
"""A phone vibrating on a wooden desk, synthesized from scratch (numpy + scipy, fixed seeds, no samples: CC0): one
two-burst ring, 5 frames on, 2 off, 5 on (0.40 s at 30 fps), so it lines up with the banner's jitter. An eccentric motor
spins up and down (the pitch rises and falls), the phone rattles against the wood (hard clipping, a knock once per
motor turn), the desk colours it. Harmonics reach 2 to 3 kHz on purpose: a phone speaker plays nothing at the 170 Hz
fundamental.

Run: PY fx/<id>/mk_buzz.py <project>   -> <project>/audio/phone-buzz.wav (stereo 48 kHz, peak -3 dBFS in the first
     30 ms). gen.py runs it for you when the file is missing.
"""
import os
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
FPS = 30
BURST, GAP = 5 / FPS, 2 / FPS      # match the banner's jitter: 5 frames on, 2 off, 5 on
F0 = 172.0                         # motor speed, Hz
SEED = 7


def band(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def burst(dur, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    spin = 1 - np.exp(-t / 0.016)                                     # the motor needs about 40 ms to come up to speed
    stop = 1 - np.exp(-(dur - t) / 0.012)                             # and coasts down
    wobble = 1 + .012 * np.sin(2 * np.pi * 31 * t + rng.uniform(0, 6)) + .006 * np.cumsum(rng.normal(0, .02, n)) / np.sqrt(n) * 40
    f = F0 * (.66 + .34 * spin) * (.8 + .2 * stop) * wobble
    ph = 2 * np.pi * np.cumsum(f) / SR + rng.uniform(0, 6)
    s = np.sin(ph)
    rattle = np.tanh(3.2 * s) + .55 * np.tanh(5 * np.sin(2 * ph + .7)) * (.5 + .5 * s)  # lifts and hits the desk: odd and even harmonics
    hit = np.clip(np.sin(ph + 1.1), 0, 1) ** 7                        # one knock per motor turn
    noise = sosfilt(butter(2, [500, 5200], "band", fs=SR, output="sos"), rng.normal(0, 1, n))
    x = rattle + 2.4 * hit * noise
    body = .9 * band(x, 120, 330) + 1.5 * band(x, 420, 1050) + 1.5 * band(x, 1200, 2600) + .4 * band(x, 3000, 5000)   # the wood: phone speakers start around 300 Hz, so the rattle carries it
    env = np.minimum(1, t / .006) * np.minimum(1, (dur - t) / .022) * (.82 + .18 * spin)
    return body * env


def make(project):
    out = os.path.join(project, "audio", "phone-buzz.wav")
    a = burst(BURST, SEED)
    b = burst(BURST, SEED + 1)
    x = np.concatenate([a, np.zeros(int(GAP * SR)), b, np.zeros(int(.03 * SR))])
    x = x / np.abs(x).max() * 10 ** (-3 / 20)
    st = np.vstack([x, np.roll(x, 12) * .97])                          # a hair wide, never phasey
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1).T * 32767).astype("<i2").tobytes())
    return out, x


if __name__ == "__main__":
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    path, x = make(os.path.abspath(os.path.expanduser(sys.argv[1])))
    rms = np.sqrt(np.mean(x[np.abs(x) > 0] ** 2))
    spec = np.abs(np.fft.rfft(x)) ** 2
    fq = np.fft.rfftfreq(len(x), 1 / SR)
    print(path, f"{len(x) / SR:.3f}s rms {20 * np.log10(rms):.1f} dBFS, centroid {np.sum(spec * fq) / np.sum(spec):.0f} Hz, "
          f"share above 400 Hz {np.sum(spec[fq > 400]) / np.sum(spec):.2f}")
