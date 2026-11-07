#!/usr/bin/env python3
"""Cut: one 4K take -> the J-cut talking-head picture, the processed voice and timeline.json.

  - trims the dead air (edit.KEEP = audio ranges in source seconds)
  - J-cuts every join: the next line's audio leads its picture by J_LEAD
  - reframes the 4K into 9:16 shots (edit.FRAMES crops, edit.SHOTS on the output timeline), so every picture cut
    is also a framing change (a fake two-camera shoot); hide reframes under cards where you can
  - proves lip sync before it encodes anything: every picture piece must read the same source second as the
    audio playing over it (a join that rounds down to its frame once put 7s of picture 0.48s behind the voice)
Writes <project>/assets/aroll.mp4 (edit.CANVAS, 1080x1920 by default, 30fps CFR, keyframe every 10), assets/voice.wav (-16 LUFS), timeline.json.
Run: PY pipeline/cut.py <project> [--plan]   (--plan prints the pieces and the sync table only)
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FPS, load_edit, project_arg, q  # noqa: E402


def source_cuts(E):
    """hard cuts already in the source: a phone app export (Edits, CapCut) is often pre-cut in the pauses.
    Frame-difference spikes at 90x160, cached in <project>/work/source_cuts.json"""
    import numpy as np
    path = os.path.join(E.PROJECT, "work", "source_cuts.json")
    if os.path.exists(path):
        d = json.load(open(path))
        if d.get("src") == E.SRC:
            return d["cuts"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", E.SRC, "-vf", f"fps={FPS},scale=90:160,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 160, 90).astype(np.float32)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    cuts = [round((k + 1) / FPS, 4) for k in range(len(d))
            if d[k] > 18 and d[k] > 3 * np.median(d[max(0, k - 15):k + 15])]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"src": E.SRC, "cuts": cuts}, open(path, "w"))
    return cuts


def leads(E):
    """the J-cut lead of every join. J_LEAD, unless the source already has a hard cut in that pause: then the
    outgoing picture runs right up to the source cut and stops there (a frame of the next take never shows), even if
    that puts the picture change a frame or two before the voice (an L-cut). Without this, a pre-cut phone take
    double-cuts at every join (a stutter on every join). edit.J_LEADS overrides."""
    if getattr(E, "J_LEADS", None):
        return list(E.J_LEADS)
    cuts, out = source_cuts(E), []
    for (_, e), (s, _) in zip(E.KEEP, E.KEEP[1:]):
        near = [c for c in cuts if e - E.J_LEAD <= c <= e + E.J_LEAD + 1e-3]
        lead = E.J_LEAD
        if near:
            lead = min(E.J_LEAD, near[0] - e - 0.5 / FPS)
            if s + lead < near[-1] - 1e-3:
                sys.exit(f"join at source {e}: the next line's picture would start before the source cut at {near[-1]}; move KEEP")
        out.append(round(lead, 4))
    return out


def snap_shots(E, segs):
    """a framing change written next to a join belongs ON the join (leads move joins off the J_LEAD grid), and one
    written next to a hard cut already inside a kept line belongs on that cut (else: a cut, then a reframe a few
    frames later)"""
    joins = [q(g["vout"]) for g in segs[1:]]
    inside = [q(g["vout"] + (c - g["vs"]) / g["sp"]) for g in segs for c in source_cuts(E) if g["vs"] < c < g["ve"]]
    out = []
    for t, f in E.SHOTS:
        j = min(joins, key=lambda x: abs(x - t)) if joins else t
        c = min(inside, key=lambda x: abs(x - t)) if inside else t
        if abs(j - t) <= E.J_LEAD + 0.15:          # leads run about -0.15 .. J_LEAD
            t = j
        elif abs(c - t) <= 0.3:
            t = c
        out.append((t, f))
    return out


def plan(E):
    """audio follows KEEP exactly; each picture join lands its lead later (leads())"""
    segs, off = [], 0.0
    n = len(E.KEEP)
    L = leads(E) if n > 1 else []
    SP = getattr(E, "SPEED", None) or {}               # {piece index: factor}: a drawn-out word played faster (atempo + setpts)
    for i, (s, e) in enumerate(E.KEEP):
        sp = float(SP.get(i, 1.0))
        lin = L[i - 1] if i > 0 else 0.0
        lout = L[i] if i < n - 1 else E.HOLD
        segs.append(dict(s=s, e=e, sp=sp, out=off, vs=s + lin * sp, ve=e + lout * sp, vout=off + lin))
        off += (e - s) / sp
    return segs, off


def pieces(E, segs):
    """split the picture at every join and SHOTS boundary -> [(out_start, out_end, src_start, framing)]"""
    total = segs[-1]["vout"] + (segs[-1]["ve"] - segs[-1]["vs"]) / segs[-1]["sp"]
    bounds = sorted(set([q(g["vout"]) for g in segs] + [q(t) for t, _ in E.SHOTS] + [q(total)]))
    out = []
    for a, b in zip(bounds, bounds[1:]):
        g = [g for g in segs if q(g["vout"]) - 1e-6 <= a][-1]          # match on the frame-snapped join
        src = g["vs"] + (a - g["vout"]) * g["sp"]
        fr = [f for t, f in E.SHOTS if q(t) <= a + 1e-6][-1]
        out.append((a, b, src, fr, g["sp"]))
    return out, total


def sync_table(segs, pcs):
    """picture source vs audio source at the start of every piece; returns the worst offset in seconds"""
    worst = 0.0
    rows = []
    for a, b, src, fr, _sp in pcs:
        g = [g for g in segs if g["out"] - 1e-6 <= a][-1]
        gp = [g for g in segs if q(g["vout"]) - 1e-6 <= a][-1]          # the segment the picture comes from
        note = ""
        if gp is not g and gp["out"] - a <= max(gp["out"] - gp["vout"], 0) + 1.0 / FPS:
            g, note = gp, "  (L-cut: picture a frame or two ahead of its line)"   # a lead under one frame or negative
        asrc = g["s"] + (a - g["out"]) * g["sp"]
        if a < segs[-1]["out"] + (segs[-1]["e"] - segs[-1]["s"]) / segs[-1]["sp"]:      # only while someone is talking
            worst = max(worst, abs(src - asrc))
        rows.append(f"  {a:8.3f}-{b:8.3f} {fr:6s} picture {src:8.3f}  audio {asrc:8.3f}  offset {src - asrc:+.3f}{note}")
    return worst, rows


def main():
    project = project_arg()
    E = load_edit(project)
    segs, total_audio = plan(E)
    E.SHOTS = snap_shots(E, segs)
    print("leads", [round(g["vout"] - g["out"], 3) for g in segs[1:]])
    pcs, total = pieces(E, segs)
    worst, rows = sync_table(segs, pcs)
    print("\n".join(rows))
    if worst > 0.5 / FPS:
        sys.exit(f"LIP SYNC: a picture piece is {worst:.3f}s off its audio. Fix KEEP/SHOTS before cutting.")
    print("lip sync: every piece reads the same source second as its audio")
    if "--plan" in sys.argv:
        return
    assets, work = os.path.join(project, "assets"), os.path.join(project, "work")
    os.makedirs(assets, exist_ok=True)
    os.makedirs(work, exist_ok=True)

    # ---- picture: every piece cut straight from the 4K original, exact frame counts
    parts = []
    for k, (a, b, src, fr, sp) in enumerate(pcs):
        n = round((b - a) * FPS)
        w, h, x, y = E.FRAMES[fr]
        W, H = E.CANVAS
        out = os.path.join(work, f"pic_{k:02d}.mp4")
        tempo = f"setpts=(PTS-STARTPTS)/{sp:.4f}," if abs(sp - 1.0) > 1e-6 else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{src - 0.3 / FPS:.4f}", "-i", E.SRC, "-an",   # a third of a frame early: lands ON the frame, not one late
                        "-vf", f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,{tempo}fps={FPS},setsar=1",
                        "-frames:v", str(n), "-c:v", "libx264", "-crf", "12", "-preset", "medium",
                        "-pix_fmt", "yuv420p", out], check=True)
        parts.append(out)
    concat = os.path.join(work, "pic_concat.txt")
    with open(concat, "w") as fh:
        fh.write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat,
                    "-vf", f"setpts=N/{FPS}/TB", "-r", str(FPS), "-fps_mode", "cfr",
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-g", "10", "-keyint_min", "10",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(assets, "aroll.mp4")], check=True)

    # ---- voice: keep ranges with 20-30ms fades at each join, then the voice chain
    fc, n = "", len(segs)
    for i, g in enumerate(segs):
        d = (g["e"] - g["s"]) / g["sp"]
        tin = i > 0 and abs(segs[i - 1]["e"] - g["s"]) <= 1e-4          # this piece touches the one before in the source
        tout = i < n - 1 and abs(segs[i + 1]["s"] - g["e"]) <= 1e-4
        sped_in = tin and (g["sp"] != 1.0 or segs[i - 1]["sp"] != 1.0)  # a speed change inside a word: a 6 ms fade, no dip
        sped_out = tout and (g["sp"] != 1.0 or segs[i + 1]["sp"] != 1.0)
        fi = "" if (tin and not sped_in) else (",afade=t=in:d=0.006" if sped_in else ",afade=t=in:d=0.02")
        fo = "" if (tout and not sped_out) else (f",afade=t=out:st={d - 0.006:.4f}:d=0.006" if sped_out else f",afade=t=out:st={d - 0.03:.4f}:d=0.03")
        tempo = f",atempo={g['sp']:.4f}" if g["sp"] != 1.0 else ""
        fc += f"[0:a]atrim={g['s']:.4f}:{g['e']:.4f},asetpts=PTS-STARTPTS{tempo}{fi}{fo}[a{i}];"
    fc += "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ac];"
    # HPF 80, light denoise, -2 dB @250 (boxiness), +2 dB @3.2k (presence), 3:1 comp, limiter, -16 LUFS
    fc += ("[ac]highpass=f=80,afftdn=nr=8:nf=-45,equalizer=f=250:t=q:w=1.2:g=-2,"
           "equalizer=f=3200:t=q:w=1.0:g=2,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
           "alimiter=limit=0.89:level=false,loudnorm=I=-16:TP=-2:LRA=9,aresample=48000[ao]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", E.SRC, "-filter_complex", fc, "-map", "[ao]",
                    "-ac", "2", "-c:a", "pcm_s16le", os.path.join(assets, "voice.wav")], check=True)

    cuts = [q(g["vout"]) for g in segs[1:]]
    reframes = [q(t) for t, _ in E.SHOTS[1:] if all(abs(q(t) - c) > 1e-6 for c in cuts)]
    json.dump({"fps": FPS, "total_audio": round(total_audio, 4), "total": round(q(total), 4),
               "keep": [dict(src_in=g["s"], src_out=g["e"], out=round(g["out"], 4),
                             picture_out=round(g["vout"], 4), **({"speed": g["sp"]} if g["sp"] != 1.0 else {})) for g in segs],
               "picture_cuts": cuts, "reframes": reframes,
               "shots": [dict(t=q(t), frame=f) for t, f in E.SHOTS],
               "pieces": [dict(out_start=a, out_end=b, src=round(s, 4), frame=f, **({"speed": sp} if sp != 1.0 else {})) for a, b, s, f, sp in pcs]},
              open(os.path.join(project, "timeline.json"), "w"), indent=1)
    fr = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                         "stream=nb_read_frames", "-of", "csv=p=0", os.path.join(assets, "aroll.mp4")],
                        capture_output=True, text=True).stdout.strip()
    print(f"audio {total_audio:.3f}s  picture {total:.3f}s ({round(q(total) * FPS)} frames expected, aroll has {fr})")
    print("picture cuts", cuts)
    print("reframes", reframes)


if __name__ == "__main__":
    main()
