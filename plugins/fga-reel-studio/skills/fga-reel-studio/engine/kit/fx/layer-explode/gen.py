#!/usr/bin/env python3
"""layer-explode, step 2 of 4: the live 3D rig. The frame swings round in 3D (a spring-driven pan, tilt and dolly, the
camera banking into the turn), the sheets slide apart on the words and the shot holds as a true exploded view of THIS
edit: ROOM, TYPE (the cue words in the display face), ME (the speaker, live, lips in sync), CAPTIONS (the real caption
box, word by word) and SOUND (the video's real waveform, playhead running). It folds back flat on the frame so the seam
is invisible. prerender.py then films this rig through the real renderer with a 180 degree shutter.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>, KARAOKE), words.json, assets/voice.wav, work/tracks/track.json
          (optional), the style pack; layers.py's room clips in work/fx/<id>/stage/<id>/
  writes  <project>/work/fx/<id>/stage/<id>/fx.html + fx.js (the rig prerender.py films), and prints the SOUND lines
Order: layers.py, gen.py, calib.py (once per video), prerender.py. Rerun gen.py and prerender.py when the window moves.
"""
import argparse
import json
import os
import re
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920

# ---- the table. Times come from the window and the cue words; everything else is the move
WORDS = None                 # the TYPE sheet: [(text, cue word)], each rises on its word; None = the first three words spoken
LABELS = dict(room="ROOM", type="TYPE", me="ME", cap="CAPTIONS", snd="SOUND")   # the tab on each sheet
POSE = dict(pan=-38, tilt=-9, dolly=1600, x=6, y=-128, orbit=6.0)   # the exploded pose (degrees, px) and the slow orbit while it holds
Z = dict(room=-680, type=-400, me=0, cap=290, snd=450)              # plane depths at full separation, px
TABS = dict(snd=4, cap=56, me=250, type=4, room=4)                  # label insets, px: staggered like file-folder tabs, never overlapping
TYPE_BOX = None              # (left, top, width) of the TYPE words, px; None = the top of the frame, on the side away from the face
TYPE_MAX = 300               # px: the TYPE words' size at most (each line is masked; they shrink to fit the box)
WAVE_PAD = (1.0, 1.2)        # s of the video's audio before and after the window on the SOUND sheet
BARS = 96


def _pipeline():
    """the kit's pipeline on the import path: REEL_KIT, this folder's grandparent when it runs in the library, else
    PY's own (setup puts the pipeline on PY's import path)"""
    for c in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        p = os.path.join(c, "pipeline") if c else ""
        if p and os.path.exists(os.path.join(p, "fxlib.py")):
            sys.path.insert(0, os.path.abspath(p))
            return
    import importlib.util
    if importlib.util.find_spec("fxlib") is None:
        sys.exit("can't import the kit's fxlib: run this with the kit's PY (setup puts the pipeline on its path), or set REEL_KIT=<the kit folder>")


_pipeline()
import fxlib  # noqa: E402
from common import load_edit  # noqa: E402

_ns = {}
exec(open(os.path.join(HERE, "rig_js.py"), encoding="utf-8").read(), _ns)     # read, not imported: nothing compiled into the fx folder
RIG_JS = _ns["JS"]


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def window(project, fid):
    """the edit, the timeline and the effect's window (its edit.FX entry; "end" resolved like the build does)"""
    F = fxlib.entry(project, fid)
    return load_edit(project), json.load(open(os.path.join(project, "timeline.json"))), float(F["at"]), float(F["end"])


def times(ws, A, B):
    """the rig's beats: it swings on the first word, the back sheets leave on the second TYPE word, the front ones on the
    third, it folds back over the last 29% of the window (at most 0.82 s) and lands flat one frame before the end"""
    D = B - A
    inwin = [w for w in ws if A - 0.001 <= w["start"] < B]
    if WORDS:
        after, typ = A, []
        for text, cue in WORDS:
            t = next((w["start"] for w in inwin if w["start"] >= after - 0.001 and norm(w["text"]) == norm(cue)), None)
            if t is None:
                print(f"WARNING: TYPE cue word {cue!r} is not spoken in the window after {after:.2f}")
                t = after + 0.24
            typ.append((text, t))
            after = t + 0.01
    else:
        typ = [(w["text"].strip(",.?!:;"), w["start"]) for w in inwin[:3]]
    if not typ:
        typ = [("", A)]
    land = round((B - 1 / FPS) * FPS) / FPS
    fold = land - min(0.82, 0.29 * D)
    start = min(typ[0][1], A + 0.1)
    k = min(1.0, D / 2.83)
    back = typ[1][1] if len(typ) > 1 else start + 0.26 * k
    front = typ[2][1] if len(typ) > 2 else back + 0.24 * k
    back, front = min(back, fold - 0.3), min(front, fold - 0.2)
    T = dict(start=start, back=back, front=max(front, back + 0.05), drift=start + 0.25 * D, push=fold - 0.25 * (land - fold),
             fold=fold, out=fold + 0.29 * (land - fold), land=land)
    for i, (_, t) in enumerate(typ):
        T[f"w{i}"] = t
    return T, typ


def waveform(project, a, b):
    for p in (os.path.join(project, "assets", "voice.wav"), os.path.join(project, "public", "master.wav")):
        if os.path.exists(p):
            w = wave.open(p)
            sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
            x = np.frombuffer(w.readframes(n), {2: np.int16, 4: np.int32}.get(sw, np.int16)).astype(np.float32)
            x = x.reshape(-1, ch).mean(axis=1) / float(2 ** (8 * sw - 1))
            i0, i1 = max(0, int(a * sr)), min(len(x), int(b * sr))
            edges = np.linspace(i0, i1, BARS + 1).astype(int)
            v = np.array([np.sqrt(np.mean(x[edges[i]:edges[i + 1]] ** 2)) if edges[i + 1] > edges[i] else 0 for i in range(BARS)])
            v = v / max(1e-9, v.max())
            return np.clip(v ** 0.75, 0.035, 1)
    print("no assets/voice.wav: the SOUND sheet gets a flat line")
    return np.full(BARS, 0.035)


def caption_lines(E, A, B):
    """the caption lines this window carries, exactly as the build groups and lights them (build.karaoke_lines)"""
    import build
    if not hasattr(E, "S"):
        E.S = build.project_style(E)
    L = build.karaoke_lines(E)
    total = json.load(open(os.path.join(E.PROJECT, "timeline.json")))["total"]
    out = []
    for i, ln in enumerate(L):
        t0 = ln[0]["start"]
        nxt = L[i + 1][0]["start"] if i + 1 < len(L) else total
        t1 = nxt if nxt - ln[-1]["end"] < 0.6 else min(nxt, ln[-1]["end"] + 0.3)
        if not (A - 0.001 <= t0 < B or t0 < A < t1 - 0.001):     # a line still held on screen at A comes along too:
            continue                                             # the hide ends it at A, the CAPTIONS sheet carries it on
        out.append((round(t0, 4), round(min(t1, B), 4), [(w["text"], round(w["start"], 4)) for w in ln]))
    hide = getattr(E, "KARAOKE", {}).get("hide", [])
    if out and not any(a <= A + 0.01 and b >= B - 0.05 for a, b in hide):
        print(f"WARNING: add KARAOKE hide ({A:.2f}, {B:.2f}) to edit.py: the CAPTIONS sheet carries the words in the window")
    return out


def type_layout(project, typ, tr, A):
    """the TYPE block: on the side of the frame away from the face, every word one masked line, the size fitted to the
    pack's display face"""
    face = tr[fxlib.fr(A)]["face"] if tr and fxlib.fr(A) < len(tr) and tr[fxlib.fr(A)].get("face") else None
    if TYPE_BOX:
        x, y, w = TYPE_BOX
    else:
        x, y, w = (462, 70, 578) if (face is None or face["cx"] <= W / 2 + 20) else (40, 70, 578)
    size = TYPE_MAX
    try:
        f = fxlib.font(project, "display", 100)
        widest = max(f.getlength(t) for t, _ in typ) / 100 if typ else 1
        size = int(min(TYPE_MAX, (w - 10) / max(widest, 1e-3)))
    except Exception as e:
        print("could not measure the display face, TYPE stays at", size, f"px ({e})")
    if face is not None and typ:                    # a close shot: the head can hide most of the words
        bh = len(typ) * size * 0.9
        hx0, hx1 = face["cx"] - 0.6 * face["w"], face["cx"] + 0.6 * face["w"]
        hy0 = face.get("top", face["cy"] - 0.5 * face["h"]) - 0.45 * face["h"]
        hy1 = face.get("chin", face["cy"] + 0.5 * face["h"])
        cover = max(0.0, min(x + w, hx1) - max(x, hx0)) * max(0.0, min(y + bh, hy1) - max(y, hy0)) / (w * bh)
        if cover > 0.3:
            print(f"WARNING: the head covers {100 * cover:.0f}% of the TYPE block on this framing (the words read as "
                  f"fragments behind it): use a wider window, fewer or shorter WORDS, or set TYPE_BOX")
    return x, y, w, size


def hair(fid, k):
    return "".join(f'<div class="{fid}-xh {fid}-xh-{s} {fid}-{k}-h"></div>' for s in "tblr")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E, TL, A, B = window(project, fid)
    if fxlib.size(os.path.join(project, "public", "clean.mp4")) != (W, H):
        sys.exit("layer-explode is built for a 1080x1920 canvas")
    stage = os.path.join(project, "work", "fx", fid, "stage", fid)
    if not os.path.exists(os.path.join(stage, "room.mp4")):
        sys.exit(f"no {stage}/room.mp4: run layers.py first")
    ws = json.load(open(os.path.join(project, "words.json")))
    T, typ = times(ws, A, B)
    S = fxlib.pack(project)
    tp = os.path.join(project, "work", "tracks", "track.json")
    tr = fxlib.tracks(project)["frames"] if os.path.exists(tp) else None
    D = B - A
    wav = (A - WAVE_PAD[0], B + WAVE_PAD[1])
    v = waveform(project, *wav)
    lines = caption_lines(E, A, B)
    tx, ty, tw, tsize = type_layout(project, typ, tr, A)
    line_h = round(tsize * 0.9)
    st = "position:absolute;left:0;top:0;width:1080px;height:1920px;"
    room = fxlib.tag(f"{fid}-v-room", f"fx/{fid}/room.mp4", A, B, "g", "{{T0}}", st)
    has_empty = os.path.exists(os.path.join(stage, "room_empty.mp4"))
    empty = fxlib.tag(f"{fid}-v-empty", f"fx/{fid}/room_empty.mp4", A, B, "g", "{{T1}}", st) if has_empty else ""
    me = (f'<video id="{fid}-v-me" class="g" src="subject.webm" muted playsinline data-start="{fxlib.clip_start(A):.4f}" '
          f'data-media-start="{fxlib.fr(A) / FPS + 0.001:.4f}" data-duration="{(fxlib.fr(B) - fxlib.fr(A)) / FPS:.4f}" data-track-index="{{{{T2}}}}" style="{st}"></video>')
    type_html = "".join(f'<div class="{fid}-xw"><div id="{fid}-w{i}" class="{fid}-xwi">{t}</div></div>' for i, (t, _) in enumerate(typ))
    caps = []
    for i, (a, b, wl) in enumerate(lines):
        spans = " ".join(f'<span class="k" id="{fid}-k{i}_{j}">{w}</span>' for j, (w, _) in enumerate(wl))
        caps.append(f'<div class="kw"><div id="{fid}-kc{i}" class="kc">{spans}</div></div>')
    step = 1000 / BARS
    bars = "".join(f'<div id="{fid}-b{i}" class="{fid}-xb" style="left:{40 + i * step:.1f}px;height:{max(6, 210 * x):.0f}px;margin-top:-{max(6, 210 * x) / 2:.0f}px;"></div>' for i, x in enumerate(v))
    L = LABELS

    def label(k):
        return f'<div class="{fid}-xl {fid}-{k}-l" style="left:{TABS[k]}px">{L[k]}</div>'
    html = f"""<!-- layer-explode, the live rig. Written by gen.py for {A:.3f}-{B:.3f}; prerender.py films it into fx/{fid}/{fid}.mp4. -->
<style>
#{fid} .{fid}-xf {{ position:absolute; left:0; top:0; width:1080px; height:1920px; background:var(--c-dark); }}
#{fid} .{fid}-xs {{ position:absolute; left:0; top:0; width:1080px; height:1920px; perspective:2400px; perspective-origin:540px 960px; }}
#{fid} .{fid}-x3 {{ position:absolute; left:0; top:0; width:1080px; height:1920px; transform-style:preserve-3d; transform-origin:540px 960px; }}
#{fid} .{fid}-xp {{ position:absolute; left:0; top:0; width:1080px; height:1920px; transform-origin:540px 960px; }}
#{fid} .{fid}-xh {{ position:absolute; background:var(--c-light); opacity:.86; }}
#{fid} .{fid}-xz {{ position:absolute; width:1000px; height:2.4px; background:var(--c-light); transform-origin:0 50%; }}
#{fid} .{fid}-xdim {{ position:absolute; left:0; top:0; width:1080px; height:1920px; background:var(--c-dark); opacity:0; }}
#{fid} .{fid}-xh-t {{ left:0; top:0; width:1080px; height:3px; transform-origin:0 50%; }}
#{fid} .{fid}-xh-b {{ left:0; top:1917px; width:1080px; height:3px; transform-origin:0 50%; }}
#{fid} .{fid}-xh-l {{ left:0; top:0; width:3px; height:1920px; transform-origin:50% 0; }}
#{fid} .{fid}-xh-r {{ left:1077px; top:0; width:3px; height:1920px; transform-origin:50% 0; }}
#{fid} .{fid}-xl {{ position:absolute; top:-66px; font:500 50px/1 var(--font-mono); letter-spacing:.08em; color:var(--c-light); white-space:nowrap; }}
#{fid} .{fid}-xt {{ position:absolute; left:{tx}px; top:{ty}px; width:{tw}px; text-align:left; }}
#{fid} .{fid}-xw {{ overflow:hidden; height:{line_h + round(0.2 * tsize)}px; margin-bottom:-{round(0.2 * tsize)}px; }}
#{fid} .{fid}-xwi {{ font-family:var(--font-display); font-weight:var(--display-weight); font-style:var(--display-style); font-size:{tsize}px; line-height:{line_h}px; letter-spacing:-.02em; color:var(--c-light); white-space:nowrap; }}
#{fid} .{fid}-xb {{ position:absolute; top:1600px; width:{step * 0.56:.2f}px; background:var(--c-accent); border-radius:3px; }}
#{fid} .{fid}-xph {{ position:absolute; left:0; top:1458px; width:4px; height:284px; background:var(--c-light); }}
</style>
<div class="{fid}-xf"></div>
<div class="{fid}-xs">
 <div id="{fid}-dolly" class="{fid}-x3">
  <div id="{fid}-tilt" class="{fid}-x3">
   <div id="{fid}-pan" class="{fid}-x3">
    <div class="{fid}-xz" style="left:0;top:0;"></div><div class="{fid}-xz" style="left:1080px;top:0;"></div><div class="{fid}-xz" style="left:0;top:1920px;"></div><div class="{fid}-xz" style="left:1080px;top:1920px;"></div>
    <div id="{fid}-p-room" class="{fid}-xp">
{room}
{empty}
     <div id="{fid}-dim" class="{fid}-xdim"></div>
     {hair(fid, "room")}{label("room")}
    </div>
    <div id="{fid}-p-type" class="{fid}-xp">
     <div class="{fid}-xt">{type_html}</div>
     {hair(fid, "type")}{label("type")}
    </div>
    <div id="{fid}-p-me" class="{fid}-xp">
{me}
     {hair(fid, "me")}{label("me")}
    </div>
    <div id="{fid}-p-cap" class="{fid}-xp">
     {"".join(caps)}
     {hair(fid, "cap")}{label("cap")}
    </div>
    <div id="{fid}-p-snd" class="{fid}-xp">
     {bars}
     <div id="{fid}-ph" class="{fid}-xph"></div>
     {hair(fid, "snd")}{label("snd")}
    </div>
   </div>
  </div>
 </div>
</div>
"""
    with open(os.path.join(stage, "fx.html"), "w") as fh:
        fh.write(html)
    C = S["colors"]
    hexc = lambda c: "#%02X%02X%02X" % tuple(c[:3])      # noqa: E731
    k = min(1.0, D / 2.83)
    js = (RIG_JS.replace("__ID__", fid)
          .replace("__T__", json.dumps({a: round(b, 4) for a, b in T.items()}))
          .replace("__POSE__", json.dumps(POSE)).replace("__Z__", json.dumps(Z))
          .replace("__LINES__", json.dumps(lines)).replace("__BARS__", str(BARS)).replace("__WAVE__", json.dumps([round(wav[0], 4), round(wav[1], 4)]))
          .replace("__SPEED__", f"{float(np.clip((2.83 / D) ** 0.25, 1.0, 1.4)):.3f}").replace("__DS__", f"{float(np.clip(k, 0.55, 1.0)):.3f}")
          .replace("__LIGHT__", hexc(C["light"])).replace("__LIT__", hexc(C["caption_ink"]))
          .replace("__HAS_EMPTY__", "true" if has_empty else "false").replace("__NW__", str(len(typ))))
    with open(os.path.join(stage, "fx.js"), "w") as fh:
        fh.write(js)
    f = T["land"] - T["fold"]
    print(f"wrote the rig in {stage}: swing {T['start']:.2f}, sheets leave {T['back']:.2f} / {T['front']:.2f}, fold {T['fold']:.2f}, flat {T['land']:.2f}; "
          f"TYPE {[t for t, _ in typ]} at {tsize}px; {len(lines)} caption lines")
    print("SOUND sfx lines (put them in edit.py; they follow the rig):")
    rows = [(T["start"], "impact-low", -18, "the rig lets go"), (T["start"] + 0.1, "whoosh-deep", -14, "the swing, on its fastest frame")]
    rows += [(t, "pop", -19, f"TYPE: {w}") for w, t in typ if w]
    rows += [(T["back"] + 0.04, "whoosh-soft", -19, "the room leaves"), (T["back"] + 0.31 * k, "click", -16, "ROOM hits its stop"),
             (T["back"] + 0.37 * k, "tick", -16, "TYPE"), (T["front"] + 0.3 * k, "tick", -16, "SOUND"), (T["front"] + 0.36 * k, "tick", -16, "CAPTIONS"),
             (T["push"] + 0.14 * k, "whoosh-soft", -21, "the camera drifts"), (T["fold"] + 0.46 * f, "whoosh", -14, "the fold, on its fastest frame"),
             (T["fold"] + 0.61 * f, "riser", -18, "into the landing"), (T["fold"] + 0.68 * f, "impact-low", -15, "the sheets close"),
             (T["fold"] + 0.71 * f, "shutter", -15, "and latch")]
    for t, n, db, what in sorted(rows):
        print(f'    ({t:.3f}, "{n}", {db}),   # {what}')


if __name__ == "__main__":
    main()
