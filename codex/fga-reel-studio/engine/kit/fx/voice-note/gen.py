#!/usr/bin/env python3
"""voice-note: the speaker's line becomes a voice message.

A chat bubble with the speaker's headshot floats in the clear space above their head. Its waveform is the project's own
voice over this exact line, played through in real time behind a playhead as they say it (each bar plucks as the
playhead reaches it), with a running time and the transcript under it word by word. A tap on the send button sends it:
the bubble lifts and flies off up-right, a small Delivered label stays a moment. Two skins with the same geometry and
motion: dark (the pack's dark ground) and light (its light ground). Generic chat UI, no app imitated.

Run: PY fx/<id>/gen.py <project> [<id>] [--theme dark|light]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json (the line and its word times), assets/voice.wav
          (else public/master.wav), style/ (the pack's fonts and colours), the headshot (HEADSHOT below), and to keep
          the bubble off the face: public/subject.webm (the top of the head) and work/tracks/track.json (the chin)
  writes  <project>/fx/<id>/fx.html, fx.js (+ the headshot, copied in); prints the KARAOKE hide and the sounds
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the mix changes. Both skins in one
video: two FX entries, run it once per id (`... <project> vnote-light --theme light`).
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN_KIT = os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "fxlib.py"))   # this copy is the kit library's, not a project's
FPS = 30

# ---- the one table. Times are found on words.json inside the FX window; offsets are seconds.
THEME = "dark"            # dark: the bubble on the pack's dark ground; light: on its light ground (--theme wins)
LINE = ""                 # the transcript text; '' = the words spoken in the window, as transcribed
SEND_ON = ""              # the spoken word the tap sends it on; '' = as the playhead reaches the end of the line
POP = 0.0                 # s after A: the bubble pops (if the line started before A, the playhead is already running)
LIFT, FLY, FLY_DUR = 0.05, 0.11, 0.30    # s after the send: the bubble lifts, then flies off up-right for FLY_DUR
DELIVERED = 0.25          # s after the send: the small label, once the bubble has cleared its spot
LABEL = "Delivered"
HEADSHOT = ""             # a square photo of the speaker, project-relative; '' = the creator's (assets/headshot.*, the pack's)

# ---- layout (frame px on the 1080x1920 canvas). TOP and SCALE are read off the footage when None.
ROW_X, ROW_W = 90, 900    # the chat column: the bubble, then the headshot at its right end
TOP = None                # the bubble's top; None = read off the footage: 224 (under the top safe line) when the head
                          # leaves room, else under the chin when the chest does, else the larger of the two, scaled
SCALE = None              # None = 1, or smaller when neither space takes it at full size
CLEAR = 12                # px kept between the transcript pill and the top of the head
UNDER = 28, 1290          # under the chin: px below it, and the line its bottom stays above (the captions band)
H, AV, AVGAP = 140, 84, 12                         # bubble height, headshot size, the gap between them
BAR_W, BAR_P, BAR_MAX, BAR_MIN = 7, 12, 106, 8     # waveform bars: width, pitch, tallest, shortest
PLAY, SEND, TIME_W = 80, 72, 86                    # play button, send button, the running time's box
TR_H, TR_PX, TR_PAD, TR_LS = 52, 34, 24, -0.01     # transcript pill: height, type size, side padding, letter spacing (em)
MIN_SCALE = 0.62

LIB_HTML = ("<!-- LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run\n"
            "     gen.py on the project: it rewrites this file from that video's words, voice and footage. -->\n")
LIB_JS = ("// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run\n"
          '// gen.py on the project: it rewrites this file.\n')


try:
    import fxlib                      # setup puts the kit's pipeline on PY's import path
except ImportError:                   # an older setup, or the effects lab: REEL_KIT, else the kit this folder came from
    for _k in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        if _k and os.path.exists(os.path.join(_k, "pipeline", "fxlib.py")):
            sys.path.insert(0, os.path.join(os.path.abspath(_k), "pipeline"))
            break
    import fxlib


def norm(w):
    import re
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def head_top(project, A, B, x0, x1):
    """the highest the speaker reaches over columns x0..x1 in the window: the matte (5th percentile, so one stray frame
    doesn't move it), else the face track (its mesh top less a third of the face for hair or a cap)"""
    if os.path.exists(os.path.join(project, "public", "subject.webm")):
        tops = []
        for k, (_, al) in enumerate(fxlib.alpha(project, A, B)):
            if k % 2:
                continue
            rows = np.nonzero((al[:, x0:x1] > 128).sum(axis=1) >= 6)[0]
            if len(rows):
                tops.append(int(rows[0]))
        if tops:
            return int(np.percentile(tops, 5)), "matte"
    path = os.path.join(project, "work", "tracks", "track.json")
    if os.path.exists(path):
        fr = json.load(open(path))["frames"][round(A * FPS):round(B * FPS)]
        tops = [f["face"]["top"] - 0.35 * f["face"]["h"] for f in fr if f and f.get("face")]
        if tops:
            return int(min(tops)), "face track"
    return None, None


def chin_low(project, A, B):
    """the lowest the chin gets in the window (track.json), or None"""
    path = os.path.join(project, "work", "tracks", "track.json")
    if not os.path.exists(path):
        return None
    fr = json.load(open(path))["frames"][round(A * FPS):round(B * FPS)]
    chins = [f["face"]["chin"] for f in fr if f and f.get("face")]
    return int(max(chins)) if chins else None


def voice_env(project, t0, t1, n, line):
    """n bar heights 0..1 from the voice over t0..t1; without a voice (or a silent one) a seeded stand-in from the
    word timing, and the script says so"""
    src = next((p for p in (os.path.join(project, "assets", "voice.wav"), os.path.join(project, "public", "master.wav"))
                if os.path.exists(p)), None)
    seg = np.zeros(0)
    if src:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
        pcm = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        seg = pcm[int(t0 * 16000):int(t1 * 16000)]
    if len(seg) >= n and float(np.abs(seg).max()) > 1e-3:
        env = np.array([math.sqrt(float((x ** 2).mean())) for x in np.array_split(seg, n)])
        return (env / env.max()) ** .75, os.path.relpath(src, project)          # a lift on the quiet bars, as message waveforms do
    print("no voice under this line (or it is silent): the waveform is a stand-in from the word timing; rerun after cut.py")
    env = []
    for i in range(n):
        t = t0 + (i + 0.5) / n * (t1 - t0)
        w = next((w for w in line if w[0] <= t < w[1]), None)
        r = math.sin(i * 12.9898) * 43758.5453
        env.append((0.35 + 0.65 * abs(math.sin(math.pi * (t - w[0]) / max(0.05, w[1] - w[0])))) * (0.7 + 0.3 * (r - math.floor(r))) if w else 0.08)
    return np.array(env), "words.json (stand-in)"


def lum(c):
    ch = [v / 255 for v in c[:3]]
    ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main():
    global THEME
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--theme", choices=("dark", "light"))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    THEME = args.theme or THEME
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    if not os.path.exists(os.path.join(project, "words.json")):
        sys.exit("words.json missing: run pipeline/words.py first (the transcript and every beat come from it)")
    words = fxlib.words(project)
    line = [w for w in words if w[1] > A + 0.02 and w[0] < B - 0.05]
    if not line:
        sys.exit(f"nothing is spoken in {fid}'s window {A:.2f}-{B:.2f}: the voice note needs a line")
    T0, T1 = line[0][0], line[-1][1]
    D = T1 - T0
    toks = LINE.split() if LINE else [w[2] for w in line]
    ons = [line[min(i, len(line) - 1)][0] for i in range(len(toks))]

    # ---- the send, the flight, the label: each on its word or relative to it, all inside the window
    hit = [w for w in line if SEND_ON and norm(w[2]) == norm(SEND_ON)]
    if SEND_ON and not hit:
        print(f"SEND_ON {SEND_ON!r} is not spoken in the window: the tap lands as the playhead reaches the end")
    send = hit[0][0] if hit else T1
    fly_dur = FLY_DUR
    if send + FLY + fly_dur > B - 0.02:
        fly_dur = max(0.16, B - 0.02 - send - FLY)
        send = min(send, B - 0.02 - FLY - fly_dur)
        print(f"the window ends {B:.2f}: the send moves to {send:.2f}, the flight takes {fly_dur:.2f}s (end the window later for the full move)")
    gone = B - 0.03
    deliv = min(send + DELIVERED, gone - 0.14)
    pop = A + POP

    # ---- geometry: under the top safe line, scaled down only as far as the top of the head needs
    top = 224 if TOP is None else TOP
    need = H + 10 + TR_H
    head, how = head_top(project, A, B, ROW_X, ROW_X + ROW_W)
    chin = chin_low(project, A, B)
    scale, where = (1.0 if SCALE is None else SCALE), "above the head"
    if TOP is None and SCALE is None and head is not None:
        above = (head - CLEAR - top) / need
        below = (UNDER[1] - chin - UNDER[0]) / need if chin is not None else -1.0
        if above >= 0.97:                                            # a few px over the hair is not worth a smaller bubble
            scale = 1.0
        elif below >= max(MIN_SCALE, min(above, 0.97)):              # the head fills the top: under the chin, over the chest
            top, scale, where = chin + UNDER[0], min(1.0, below) if below < 0.97 else 1.0, "under the chin"
        else:
            scale = max(MIN_SCALE, above)
            if above < MIN_SCALE:
                print(f"no room here: the head reaches y {head} ({how}) and the chin y {chin}; the bubble covers part of "
                      "the face for the beat. Pick a line with more room, or set TOP / SCALE")
    print(f"head top {head} ({how or 'not measured: no matte or track.json'}), chin {chin}: the bubble sits {where}, "
          f"top {top}, scale {scale:.2f}")
    mid = (A + B) / 2                                                # what the bubble sits on: say when the other skin reads better
    under = next(fxlib.frames(project, mid, mid + 1 / FPS))[1][int(top):int(top + need * scale), ROW_X:ROW_X + ROW_W].astype(np.float32)
    luma = float(np.median(0.2126 * under[..., 0] + 0.7152 * under[..., 1] + 0.0722 * under[..., 2])) if under.size else 128
    if (THEME == "dark") == (luma < 75) or (THEME == "light" and luma > 175):
        print(f"the bubble sits on {'dark' if luma < 128 else 'light'} picture (median {luma:.0f}): "
              f"--theme {'light' if THEME == 'dark' else 'dark'} would stand out more")

    # ---- the chat column (from the house chat family: avatar 84 + 12, radius 32, tail 8)
    b_w = ROW_W - AV - AVGAP
    b_r = ROW_X + b_w
    wave_x = ROW_X + 24 + PLAY + 22
    send_x = b_r - 18 - SEND
    time_r = send_x - 14
    bars = max(8, int((time_r - TIME_W - 12 - wave_x + (BAR_P - BAR_W)) // BAR_P))
    wave_w = bars * BAR_P - (BAR_P - BAR_W)
    env, src = voice_env(project, T0, T1, bars, line)
    heights = [max(BAR_MIN, round(BAR_MIN + (BAR_MAX - BAR_MIN) * float(e))) for e in env]

    # ---- the transcript pill, measured in the pack's text face (it does not wrap: it shrinks to the bubble's width)
    px = TR_PX
    while True:
        f = fxlib.font(project, "text", px)
        tw = lambda s: f.getlength(s) + len(s) * TR_LS * px     # noqa: E731
        full = tw(" ".join(toks))
        if full + 2 * TR_PAD <= b_w or px <= 22:
            break
        px -= 1
    if full + 2 * TR_PAD > b_w:
        print(f"the transcript is {full:.0f}px wide at {px}px type: shorten LINE")
    tr_w = round(full + 2 * TR_PAD)
    tr_x, tr_y = b_r - tr_w, top + H + 10
    insets, prefix = [tr_w - TR_PAD - 18], ""
    for t in toks:
        prefix = (prefix + " " + t).strip()
        insets.append(round(max(0, tr_w - tw(prefix) - 2 * TR_PAD), 1))

    # ---- colours: tokens per skin; the send arrow takes whichever ground reads on the pack's accent
    S = fxlib.pack(project)
    acc, dark, light = S["colors"]["accent"], S["colors"]["dark"], S["colors"]["light"]
    on_acc = "var(--c-dark)" if contrast(acc, dark) >= contrast(acc, light) else "var(--c-light)"
    if THEME == "dark":
        C = dict(bubble="var(--c-dark)", ink="var(--c-light)", ring="color-mix(in srgb, var(--c-light) 16%, transparent)",
                 rest="color-mix(in srgb, var(--c-light) 36%, transparent)", played="var(--c-light)", head="var(--c-accent)",
                 play_bg="var(--c-light)", play_icon="var(--c-dark)", send_bg="var(--c-accent)", send_icon=on_acc,
                 check="var(--c-accent)", tap_bg="color-mix(in srgb, var(--c-light) 30%, transparent)",
                 tap_ring="color-mix(in srgb, var(--c-light) 70%, transparent)",
                 ph0="color-mix(in srgb, var(--c-light) 18%, var(--c-dark))", ph1="color-mix(in srgb, var(--c-light) 55%, var(--c-dark))")
    else:
        C = dict(bubble="var(--c-light)", ink="var(--c-ink)", ring="color-mix(in srgb, var(--c-ink) 10%, transparent)",
                 rest="color-mix(in srgb, var(--c-ink) 26%, transparent)", played="var(--c-ink)", head="var(--c-accent-light)",
                 play_bg="var(--c-ink)", play_icon="var(--c-light)", send_bg="var(--c-accent)", send_icon=on_acc,
                 check="var(--c-accent-light)", tap_bg="color-mix(in srgb, var(--c-ink) 16%, transparent)",
                 tap_ring="color-mix(in srgb, var(--c-ink) 50%, transparent)",
                 ph0="color-mix(in srgb, var(--c-ink) 13%, var(--c-light))", ph1="color-mix(in srgb, var(--c-ink) 44%, var(--c-light))")

    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)
    shot = os.path.join(project, HEADSHOT) if HEADSHOT else fxlib.headshot(project)
    if shot:
        name = "headshot" + os.path.splitext(shot)[1].lower()
        if os.path.realpath(shot) != os.path.realpath(os.path.join(out, name)):
            shutil.copy(shot, os.path.join(out, name))
        avatar = f'<img class="@@-av" src="fx/@@/{name}" alt="">'
    else:
        print("no headshot (assets/headshot.jpg, or headshot.jpg in the style pack): a placeholder glyph stands in; "
              "add the photo and rerun")
        avatar = ('<!-- PLACEHOLDER headshot: put a square photo of the speaker at assets/headshot.jpg and rerun gen.py -->'
                  '<svg class="@@-av" viewBox="0 0 48 48" data-placeholder="headshot"><circle class="@@-ph0" cx="24" cy="24" r="24"/>'
                  '<circle class="@@-ph1" cx="24" cy="19" r="8"/><path class="@@-ph1" d="M8 46 C9.5 34 16 29.5 24 29.5 C32 29.5 38.5 34 40 46 Z"/></svg>')

    def rects(cls, ids):
        return "".join(f'<rect{f" id={chr(34)}@@-p{i}{chr(34)}" if ids else ""} class="{cls}" x="{i * BAR_P}" y="{H / 2 - h / 2:.1f}" '
                       f'width="{BAR_W}" height="{h}" rx="{BAR_W / 2}"/>' for i, h in enumerate(heights))

    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")      # noqa: E731
    spans = " ".join(f'<span id="@@-w{i}" class="@@-w">{esc(t)}</span>' for i, t in enumerate(toks))
    html = f"""<!-- voice-note ({THEME}): written by gen.py for this window and this line (rerun it when the window, the cut or the
     mix changes). The line as a voice message: the bubble pops, the line's real waveform plays through behind a
     playhead, the running time, the transcript word by word, a tap sends it, Delivered. Generic chat UI; every colour
     and font is the pack's. -->
<div id="@@-all" data-layout-allow-overflow data-layout-allow-overlap>
<div id="@@-row" data-layout-allow-overflow style="left:{ROW_X}px;top:{top}px;width:{ROW_W}px;height:{H}px">
  <div id="@@-pop">
    <div class="@@-avw">{avatar}</div>
    <div class="@@-b">
      <svg class="@@-play" width="{PLAY}" height="{PLAY}" viewBox="0 0 80 80"><circle class="@@-pbg" cx="40" cy="40" r="40"/><path class="@@-pic" d="M32 24 L58 40 L32 56 Z"/></svg>
      <svg class="@@-wv" width="{wave_w}" height="{H}" viewBox="0 0 {wave_w} {H}">{rects("@@-r", False)}</svg>
      <svg id="@@-played" class="@@-wv" width="{wave_w}" height="{H}" viewBox="0 0 {wave_w} {H}">{rects("@@-pl", True)}</svg>
      <div id="@@-head"></div>
      <div id="@@-time" data-layout-allow-overlap>0:00</div>
      <svg id="@@-send" width="{SEND}" height="{SEND}" viewBox="0 0 72 72"><circle class="@@-sbg" cx="36" cy="36" r="36"/><path class="@@-sic" d="M36 53 V21 M23 34 L36 21 L49 34"/></svg>
    </div>
  </div>
</div>
<div id="@@-trw" data-layout-allow-overlap><div id="@@-tr" style="left:{tr_x}px;top:{tr_y}px;width:{tr_w}px;height:{TR_H}px"><span class="@@-trt" data-layout-allow-overlap>{spans}</span></div></div>
<div id="@@-del" data-layout-allow-overlap style="right:{1080 - b_r}px;top:{top + H - 44}px">{esc(LABEL)}<svg width="26" height="20" viewBox="0 0 26 20"><path class="@@-chk" d="M3 11 L9 17 L23 3"/></svg></div>
<div id="@@-tap" style="left:{send_x + SEND / 2 - 46:.1f}px;top:{top + H / 2 - 46:.1f}px"></div>
</div>
<style>
#@@ #@@-all {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
#@@ #@@-row {{ position:absolute; opacity:0; }}
#@@ #@@-pop {{ position:absolute; left:0; top:0; width:100%; height:100%; }}
#@@ .@@-avw {{ position:absolute; right:0; bottom:0; width:{AV}px; height:{AV}px; border-radius:50%; overflow:hidden; }}
#@@ .@@-av {{ position:absolute; left:0; top:0; width:100%; height:100%; object-fit:cover; display:block; }}
#@@ .@@-ph0 {{ fill:{C['ph0']}; }}
#@@ .@@-ph1 {{ fill:{C['ph1']}; }}
#@@ .@@-b {{ position:absolute; left:0; top:0; width:{b_w}px; height:{H}px; background:{C['bubble']}; border-radius:32px; border-bottom-right-radius:8px;
  box-shadow:0 14px 34px color-mix(in srgb, var(--c-dark) 26%, transparent), 0 2px 6px color-mix(in srgb, var(--c-dark) 16%, transparent), inset 0 0 0 1.5px {C['ring']}; }}
#@@ .@@-play {{ position:absolute; left:24px; top:{(H - PLAY) / 2}px; }}
#@@ .@@-pbg {{ fill:{C['play_bg']}; }}
#@@ .@@-pic {{ fill:{C['play_icon']}; stroke:{C['play_icon']}; stroke-width:4; stroke-linejoin:round; }}
#@@ .@@-wv {{ position:absolute; left:{wave_x - ROW_X}px; top:0; }}
#@@ .@@-r {{ fill:{C['rest']}; }}
#@@ .@@-pl {{ fill:{C['played']}; }}
#@@ #@@-head {{ position:absolute; left:{wave_x - ROW_X - 3}px; top:{(H - BAR_MAX - 12) / 2}px; width:5px; height:{BAR_MAX + 12}px; border-radius:3px; background:{C['head']}; }}
#@@ #@@-time {{ position:absolute; left:{time_r - TIME_W - ROW_X}px; top:{(H - 44) / 2}px; width:{TIME_W}px; height:44px; text-align:right;
  font-family:var(--font-mono); font-weight:500; font-size:34px; line-height:44px; letter-spacing:-.02em; font-variant-numeric:tabular-nums; color:{C['ink']}; }}
#@@ #@@-send {{ position:absolute; left:{send_x - ROW_X}px; top:{(H - SEND) / 2}px; transform-origin:50% 50%; }}
#@@ .@@-sbg {{ fill:{C['send_bg']}; }}
#@@ .@@-sic {{ fill:none; stroke:{C['send_icon']}; stroke-width:6; stroke-linecap:round; stroke-linejoin:round; }}
#@@ #@@-trw {{ position:absolute; left:0; top:0; width:1080px; height:1920px; opacity:0;
  filter:drop-shadow(0 8px 16px color-mix(in srgb, var(--c-dark) 28%, transparent)); }}
#@@ #@@-tr {{ position:absolute; background:{C['bubble']}; border-radius:{TR_H / 2}px; box-shadow:inset 0 0 0 1.5px {C['ring']}; }}
#@@ .@@-trt {{ position:absolute; left:{TR_PAD}px; top:0; white-space:pre; font-family:var(--font-text); font-weight:var(--text-weight);
  font-size:{px}px; line-height:{TR_H}px; letter-spacing:{TR_LS}em; color:{C['ink']}; }}
#@@ .@@-w {{ opacity:0; }}
#@@ #@@-del {{ position:absolute; height:44px; padding:0 18px 0 20px; display:flex; align-items:center; gap:10px; border-radius:22px; opacity:0;
  background:{C['bubble']}; box-shadow:inset 0 0 0 1.5px {C['ring']}; transform-origin:100% 50%; white-space:nowrap;
  font-family:var(--font-text); font-weight:600; font-size:27px; line-height:44px; letter-spacing:-.01em; color:{C['ink']}; }}
#@@ .@@-chk {{ fill:none; stroke:{C['check']}; stroke-width:3.4; stroke-linecap:round; stroke-linejoin:round; }}
#@@ #@@-tap {{ position:absolute; width:92px; height:92px; border-radius:50%; background:{C['tap_bg']}; box-shadow:0 0 0 2px {C['tap_ring']}; opacity:0; }}
</style>
"""

    rel = lambda t: round(t - A, 4)      # noqa: E731
    fit = (f"gsap.set(R + 'all', {{ scale: {scale:.3f}, transformOrigin: '{ROW_X + ROW_W / 2:.0f}px {top}px' }});   // smaller, so it clears the head"
           if scale < 0.999 else "// scale 1: the bubble and the transcript clear the head at full size")
    js = f"""// voice-note ({THEME}): written by gen.py for this window and this line (rerun it when the window, the cut or the mix
// changes). The bubble pops, the line's own waveform plays through in real time behind the playhead, each bar plucks
// as the playhead reaches it, the transcript pill grows word by word, a tap sends it, it flies off, Delivered.
// Times are seconds after A, read off words.json when gen.py ran.
var R = '#{{{{ID}}}}-', N = {bars}, WAVE = {wave_w}, TRR = {TR_H / 2};
var T = {{ pop: {rel(pop)}, t0: {rel(T0)}, d: {D:.4f}, tr: {rel(max(T0, pop))}, send: {rel(send)}, lift: {LIFT}, fly: {FLY}, flyDur: {fly_dur:.3f}, del: {rel(deliv)}, gone: {rel(gone)} }};
var ON = {json.dumps([rel(t) for t in ons])};   // each transcript word, on its spoken word
var INS = {json.dumps(insets)};   // the pill's right inset before the first word, then once each word is in
{fit}

// the bubble pops from its bottom-right corner (the headshot's corner)
gsap.set(R + 'pop', {{ transformOrigin: '100% 100%' }});
gsap.set(R + 'row', {{ transformOrigin: '100% 50%' }});
tl.set(R + 'row', {{ opacity: 1 }}, q(A + T.pop));
tl.fromTo(R + 'pop', {{ scale: 0.6 }}, {{ scale: 1, duration: 0.2, ease: 'back.out(1.6)', immediateRender: false }}, q(A + T.pop));

// the waveform plays through in real time behind the playhead
gsap.set(R + 'played', {{ clipPath: 'inset(0px 100% 0px 0px)' }});
tl.fromTo(R + 'played', {{ clipPath: 'inset(0px 100% 0px 0px)' }}, {{ clipPath: 'inset(0px 0% 0px 0px)', duration: T.d, ease: 'none', immediateRender: false }}, q(A + T.t0));
tl.fromTo(R + 'head', {{ x: 0 }}, {{ x: WAVE, duration: T.d, ease: 'none', immediateRender: false }}, q(A + T.t0));
for (var s = 1; s < T.d; s++) tl.set(R + 'time', {{ textContent: '0:' + (s < 10 ? '0' : '') + s }}, q(A + T.t0 + s));
for (var i = 0; i < N; i++) {{                 // each bar plucks as the playhead reaches it
  var ti = A + T.t0 + i / N * T.d, bar = R + 'p' + i;
  gsap.set(bar, {{ transformOrigin: '50% 50%' }});
  tl.fromTo(bar, {{ scaleY: 1 }}, {{ scaleY: 1.2, duration: 0.05, ease: 'power2.out', immediateRender: false }}, q(ti));
  tl.to(bar, {{ scaleY: 1, duration: 0.13, ease: 'power2.inOut' }}, q(ti + 0.05));
}}

// the transcript pill grows with the words
gsap.set(R + 'tr', {{ clipPath: 'inset(0px ' + INS[0] + 'px 0px 0px round ' + TRR + 'px)' }});
tl.set(R + 'trw', {{ opacity: 1 }}, q(A + T.tr));
ON.forEach(function (t, k) {{
  tl.set(R + 'w' + k, {{ opacity: 1 }}, q(A + t));
  tl.fromTo(R + 'tr', {{ clipPath: 'inset(0px ' + INS[k] + 'px 0px 0px round ' + TRR + 'px)' }},
    {{ clipPath: 'inset(0px ' + INS[k + 1] + 'px 0px 0px round ' + TRR + 'px)', duration: 0.08, ease: 'power3.out', immediateRender: false }}, q(A + Math.max(t, T.tr)));
}});

// the send: a soft tap, the button takes it, the bubble lifts and flies off up-right
tl.fromTo(R + 'tap', {{ opacity: 0, scale: 1.7 }}, {{ opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', immediateRender: false }}, q(A + T.send - 0.1));
tl.to(R + 'tap', {{ scale: 0.84, duration: 0.05, ease: 'power2.out' }}, q(A + T.send));
tl.to(R + 'tap', {{ scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }}, q(A + T.send + 0.07));
tl.fromTo(R + 'send', {{ scale: 0.8 }}, {{ scale: 1, duration: 0.16, ease: 'back.out(2)', immediateRender: false }}, q(A + T.send));
tl.to(R + 'row', {{ y: -16, scale: 1.02, duration: T.fly - T.lift, ease: 'power2.out' }}, q(A + T.send + T.lift));
tl.to(R + 'row', {{ x: 980, y: -420, scale: 0.52, duration: T.flyDur, ease: 'power2.in' }}, q(A + T.send + T.fly));

// Delivered, then the label and the transcript leave just before B
tl.set(R + 'del', {{ opacity: 1 }}, q(A + T.del));
tl.fromTo(R + 'del', {{ scale: 0.7 }}, {{ scale: 1, duration: 0.16, ease: 'back.out(1.8)', immediateRender: false }}, q(A + T.del));
tl.to([R + 'del', R + 'trw'], {{ opacity: 0, duration: 0.08, ease: 'power1.out' }}, q(A + T.gone - 0.08));
"""
    lib = IN_KIT and os.path.realpath(out) == os.path.realpath(HERE)   # writing into the library itself (the effects lab)
    with open(os.path.join(out, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write((LIB_HTML if lib else "") + html.replace("@@", "{{ID}}"))
    with open(os.path.join(out, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write((LIB_JS if lib else "") + js)

    nxt = next((w[0] for w in words if w[0] >= T1 - 0.01 and w not in line), None)
    hide_end = min(B, nxt - 0.02) if nxt is not None else B
    print(f"wrote {out}/fx.html + fx.js: {THEME}, {len(toks)} words, {bars} bars from {src}, send {send:.2f}, gone {gone:.2f}")
    print(f'KARAOKE["hide"] += [({A:.2f}, {hide_end:.2f})]        # the transcript carries the words')
    print("SOUND sfx (time = the visual event):")
    print(f'    ({pop + 0.05:.3f}, "pop", -17),          # the bubble pops')
    print(f'    ({send:.3f}, "click", -14),          # the send tap')
    print(f'    ({send + FLY + 0.1:.3f}, "whoosh-soft", -16),   # it flies off up-right')
    print(f'    ({deliv:.3f}, "ding", -21),          # Delivered')
    print(f"frames=[{round(T0 + D * 0.45, 2)}, {round(send, 2)}, {round(min(deliv + 0.05, gone - 0.05), 2)}]")


if __name__ == "__main__":
    main()
