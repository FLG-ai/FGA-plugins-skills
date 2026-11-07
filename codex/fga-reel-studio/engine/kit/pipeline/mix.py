#!/usr/bin/env python3
"""Mix: the processed voice + SFX (+ an optional music bed) -> <project>/public/master.wav

edit.SOUND = dict(
    sfx=[(time, "name", gain_db[, max_len]), ...],   # audio/sfx names (audio/SFX.md) or a .wav in <project>/audio.
                                                     # time is when the sound HITS: its loudest moment lands there.
                                                     # dict(at=, name=, db=, max_len=, align="start") places by its start.
    music=None,                                      # off by default. "audio/<track>.wav": a track the creator owns
                                                     # or made with a connected generator. Most creators add music
                                                     # in their posting app instead.
    sections=[dict(src=(15.43, 46.94), at=0.0, fade_in=0.02), ...],   # music seconds -> video time, so drops land
                                                     # on lines; default: the track from 0, faded out at the end
    tape_stop=dict(after=0, dur=0.36),               # optional: the music after section 0 winds down like a tape stop
    automation=[(31.85, 32.57, -60), ...],           # bed level changes in dB (a drop out, a lift)
    bed_db=-14.5,                                    # bed level under the voice
)
edit.CARD_SFX holds the card sounds from the card agents' beat reports (card start + beat time, same hit rule).
The voice sits on top; the bed is carved at 2.8k and side-chain ducked; master -14 LUFS, -1.5 dBTP.
Run: PY pipeline/mix.py <project>
"""
import os
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KIT, load_edit, project_arg, timeline  # noqa: E402
import style as ST  # noqa: E402

SR = 48000


def read(path):
    """any audio file ffmpeg can open (wav, mp3, m4a, 24-bit, any rate) -> float stereo at 48 kHz"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<i2").astype(np.float64).reshape(-1, 2).T / 32768


def write(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x.T * 32767).astype("<i2").tobytes())


def ramp(n, a, b):
    return np.linspace(a, b, max(n, 1))


def sfx_path(project, name):
    for d in (os.path.join(project, "audio"), os.path.join(KIT, "audio", "sfx")):
        for ext in (".wav", ".mp3", ".m4a", ".aif", ".aiff", ".flac"):
            p = os.path.join(d, name + ext)
            if os.path.exists(p):
                return p
    have = sorted(f[:-4] for f in os.listdir(os.path.join(KIT, "audio", "sfx")) if f.endswith(".wav"))
    raise SystemExit(f"sfx not found: {name}. Kit sounds: {', '.join(have)}")


def hit_offset(x):
    """seconds from a sound's start to its loudest moment (10 ms RMS envelope), so it lands on the event"""
    m = np.abs(x).mean(axis=0) ** 2
    k = max(1, int(0.010 * SR))
    env = np.convolve(m, np.ones(k) / k, mode="same")
    return int(np.argmax(env)) / SR


def sfx_items(items):
    """tuples (time, name, db[, max_len]) and dicts -> (time, name, db, max_len, align)"""
    for it in items:
        if isinstance(it, dict):
            yield it["at"], it["name"], it.get("db", -12), it.get("max_len"), it.get("align", "hit")
        else:
            yield it[0], it[1], it[2], (it[3] if len(it) > 3 else None), "hit"


def main():
    project = project_arg()
    E = load_edit(project)
    S = E.SOUND
    TOTAL = timeline(project)["total"]
    N = int(TOTAL * SR)
    music = np.zeros((2, N))
    work = os.path.join(project, "work")
    os.makedirs(work, exist_ok=True)

    track = S.get("music") or S.get("score")
    if track and not os.path.exists(os.path.join(project, track)):
        raise SystemExit(f"music track not found: {track} (SOUND['music'] is project-relative; None for no music)")
    if track:
        score = read(os.path.join(project, track))
        if not S.get("sections"):
            S["sections"] = [dict(src=(0.0, min(TOTAL, score.shape[1] / SR)), at=0.0, fade_out=1.2)]

        def place(src_a, src_b, at, fade_in=0.0, fade_out=0.0):
            seg = score[:, int(src_a * SR):int(src_b * SR)].copy()
            if fade_in:
                k = int(fade_in * SR); seg[:, :k] *= ramp(k, 0, 1) ** 2
            if fade_out:
                k = int(fade_out * SR); seg[:, -k:] *= ramp(k, 1, 0) ** 2
            i = int(at * SR)
            seg = seg[:, :N - i]
            music[:, i:i + seg.shape[1]] += seg

        for sec in S["sections"]:
            place(sec["src"][0], sec["src"][1], sec["at"], sec.get("fade_in", 0.0), sec.get("fade_out", 0.0))
        if S.get("tape_stop"):
            # playback speed falls 1 -> 0 over dur, reading on from where the section ended
            ts = S["tape_stop"]
            sec = S["sections"][ts["after"]]
            T, end_at = ts["dur"], sec["at"] + (sec["src"][1] - sec["src"][0])
            n = int(T * SR)
            t = np.arange(n) / SR
            pos = sec["src"][1] + t - t * t / (2 * T)
            idx = pos * SR
            i0 = np.floor(idx).astype(int)
            fr = idx - i0
            tape = score[:, i0] * (1 - fr) + score[:, i0 + 1] * fr
            tape *= ramp(n, 1, 0) ** 0.6
            tape = np.vstack([sosfilt(butter(2, 3500, "low", fs=SR, output="sos"), c) for c in tape])
            music[:, int(end_at * SR):int(end_at * SR) + n] += tape
        auto = np.zeros(N)
        tt = np.arange(N) / SR
        for a, b, db in S.get("automation", []):
            auto[(tt >= a) & (tt < b)] = db
        music *= 10 ** (auto / 20)
        music = np.vstack([sosfilt(butter(2, 45, "high", fs=SR, output="sos"), c) for c in music])
    write(os.path.join(work, ".music_cut.wav"), music)

    sfx = np.zeros((2, N))
    cache = {}
    for t0, name, db, max_len, align in sfx_items(list(S.get("sfx", [])) + list(E.CARD_SFX)):
        if name not in cache:
            x = read(sfx_path(project, name))
            cache[name] = (x, hit_offset(x))
        x, hit = cache[name]
        s = x * 10 ** (db / 20)
        if max_len:                                # optional max length, with a short fade so runs end cleanly
            k = int(max_len * SR)
            s = s[:, :k].copy()
            f = min(int(0.08 * SR), s.shape[1])
            s[:, -f:] *= np.linspace(1, 0, f)
        if align == "hit" and not max_len:
            t0 -= hit
        i = int(round(t0 * SR))
        if i < 0:                                  # a hit near 0: drop the lead-in that would fall before the start
            s, i = s[:, -i:], 0
        s = s[:, :max(0, N - i)]
        sfx[:, i:i + s.shape[1]] += s
    write(os.path.join(work, ".sfx.wav"), sfx)

    # the pack's sound.sfx: "light" sits every effect 3 dB lower; "dense" means more effects, not louder ones
    pack = os.path.join(project, "style", "style.json")
    fx_db = -1.0 + (-3.0 if ST.load(pack if os.path.exists(pack) else None)["sound"].get("sfx") == "light" else 0.0)
    voice = os.path.join(project, "assets", "voice.wav")
    cmd = [
        "ffmpeg", "-v", "error", "-y", "-i", voice,
        "-i", os.path.join(work, ".music_cut.wav"), "-i", os.path.join(work, ".sfx.wav"),
        "-filter_complex",
        "[0:a]aformat=channel_layouts=stereo,apad=whole_dur=%.4f,asplit=2[v][sc];"
        "[1:a]volume=%.1fdB,equalizer=f=2800:t=q:w=1.4:g=-3[m];"          # carve the voice's presence band out of the bed
        "[m][sc]sidechaincompress=threshold=0.04:ratio=4:attack=20:release=320:makeup=1[md];"
        "[2:a]volume=%.1fdB[fx];"
        "[v][md][fx]amix=inputs=3:normalize=0:duration=longest,"
        "atrim=0:%.4f,loudnorm=I=-14:TP=-1.5:LRA=9[out]" % (TOTAL, S.get("bed_db", -14.5), fx_db, TOTAL),
        "-map", "[out]", "-ar", "48000", "-c:a", "pcm_s16le", os.path.join(project, "public", "master.wav"),
    ]
    subprocess.run(cmd, check=True)
    r = subprocess.run(["ffmpeg", "-nostats", "-i", os.path.join(project, "public", "master.wav"), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = r[r.rfind("Summary"):]
    print("wrote public/master.wav", " ".join(l.strip() for l in summary.splitlines() if l.strip().startswith(("I:", "Peak:"))))


if __name__ == "__main__":
    main()
