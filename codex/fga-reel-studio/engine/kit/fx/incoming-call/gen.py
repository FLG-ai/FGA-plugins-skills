#!/usr/bin/env python3
"""incoming-call: the speaker's phone rings mid-sentence and they hang up on it.

A call banner drops from the top on a word and buzzes in two-burst pairs like a phone on a desk (a tiny x jitter, the
answer handset rocking), and sits there being ignored while the speaker keeps talking. On the word a soft tap lands on
decline, the banner squashes under the finger and flies off up, and a small "Call declined" pill lives for half a
second. The comedy is the speaker not reacting at all: pick a line they keep going through. The banner is a phone's
own call screen, so its colours stay a phone's (a dark banner, red decline, green accept, a grey contact glyph); the
type is the pack's. Generic, no phone's UI copied; the handset and person glyphs are drawn here.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>), words.json, and to keep the banner off the face
          work/tracks/track.json (the brow line), else the matte (public/subject.webm)
  writes  <project>/fx/<id>/fx.html, fx.js, and <project>/audio/phone-buzz.wav when it is missing (mk_buzz.py);
          prints the sounds
<id> defaults to this script's folder name. Rerun it whenever the window or the cut changes.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN_KIT = os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "fxlib.py"))   # this copy is the kit library's, not a project's
FPS = 30

# ---- the one table: who calls, and the words it lands on
CALLER = "Your Video Editor"         # who is calling: a role, never a real person's name or number
LABEL = "Incoming call"
PILL = "Call declined"
LAND_ON = ""                         # the spoken word the banner lands on (its first buzz); '' = 0.44s after A
TAP_ON = ""                          # the spoken word the tap declines it on; '' = 0.97s before B
GONE_ON = ""                         # the pill is gone by this word; '' = 0.49s before B
RING_EVERY = 0.62                    # s between buzz pairs: a real motor keeps time, it just happens to hit words

# ---- the buzz: frames at 30 fps, the same pattern as audio/phone-buzz.wav (mk_buzz.py)
ON, OFF = 5, 2                       # 5 frames on, 2 off, 5 on
AMP, ROCK = 6.0, 9                   # px of x jitter at the top of a burst (tiny); degrees the answer handset rocks

# ---- layout (frame px on the 1080x1920 canvas)
CX, CW, CH = 90, 900, 164            # x 90..990: the chat column
CY = None                            # the banner's top; None = read off the footage: 232 (under the top safe line) when
                                     # it clears the brow, else under the chin when the chest has room
SCALE = None                         # None = 1, or smaller when neither space takes it at full size
MIN_SCALE = 0.7
UNDER = 28, 1290                     # under the chin: px below it, and the line its bottom stays above (the captions band)
R, AV, DISC, PAD, DISC_GAP = 40, 108, 104, 28, 20
FONT_NAME, FONT_LABEL, FONT_PILL = 46, 32, 36
PILL_TOP = None                      # None = just under where the banner sat, the moment it starts to leave

# ---- the phone's own colours: a real object, so they stay the phone's whatever the pack
BANNER, NAME, SUB = "#1C1C1E", "#FFFFFF", "rgba(255,255,255,.62)"
RED, GREEN = "#DC3A32", "#2CA94F"
CONTACT_BG, CONTACT_FG = "#8E8E93", "#E5E5EA"

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


def rnd(i):
    x = math.sin(i * 12.9898) * 43758.5453
    return x - math.floor(x)


def chin_low(project, A, B):
    """the lowest the chin gets in the window (track.json), or None"""
    path = os.path.join(project, "work", "tracks", "track.json")
    if not os.path.exists(path):
        return None
    fr = json.load(open(path))["frames"][round(A * FPS):round(B * FPS)]
    chins = [f["face"]["chin"] for f in fr if f and f.get("face")]
    return int(max(chins)) if chins else None


def brow_line(project, A, B):
    """the highest the brow gets in the window: the eyes on the face track less a share of the face (the banner may
    cover hair or a cap crown, never the eyes); else the matte top plus a forehead"""
    path = os.path.join(project, "work", "tracks", "track.json")
    if os.path.exists(path):
        fr = json.load(open(path))["frames"][round(A * FPS):round(B * FPS)]
        ys = [min(e[1] for e in f["face"]["eyes"]) - 0.12 * f["face"]["h"] for f in fr if f and f.get("face")]
        if ys:
            return int(min(ys)), "face track"
    if os.path.exists(os.path.join(project, "public", "subject.webm")):
        tops = []
        for k, (_, al) in enumerate(fxlib.alpha(project, A, B)):
            rows = np.nonzero((al[:, CX:CX + CW] > 128).sum(axis=1) >= 6)[0] if k % 2 == 0 else []
            if len(rows):
                tops.append(int(rows[0]))
        if tops:
            return int(np.percentile(tops, 5)) + 150, "matte top + 150"
    return None, None


# a telephone handset, drawn for this: a 64 box, on the hook (arch up, both ends down). Rotated -135 for the answer glyph.
HANDSET = ("M8 40.5 C8 33.2 10.2 28.4 14.4 25.2 C19.4 21.4 25.4 19.6 32 19.6 C38.6 19.6 44.6 21.4 49.6 25.2 C53.8 28.4 56 33.2 56 40.5 "
           "Q56 44 52.5 44 L45 44 Q41.5 44 41.5 40.5 L41.5 35.8 Q41.5 33.4 39.3 32.9 C34.5 31.7 29.5 31.7 24.7 32.9 Q22.5 33.4 22.5 35.8 "
           "L22.5 40.5 Q22.5 44 19 44 L11.5 44 Q8 44 8 40.5 Z")


def disc(idv, fill, glyph_id, rot, gscale, size):
    gs = round(size * gscale)
    off = (size - gs) / 2
    return (f'<svg id="{idv}" class="@@-disc" width="{size}" height="{size}" viewBox="0 0 {size} {size}"><circle cx="{size / 2}" cy="{size / 2}" r="{size / 2}" fill="{fill}"/>'
            f'<circle id="{idv}-dim" cx="{size / 2}" cy="{size / 2}" r="{size / 2}" fill="#000" opacity="0"/>'
            f'<g transform="translate({off} {off}) scale({gs / 64})"><g id="{glyph_id}"><g transform="rotate({rot} 32 32)"><path d="{HANDSET}" fill="#fff"/></g></g></g></svg>')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    words = fxlib.words(project) if os.path.exists(os.path.join(project, "words.json")) else []
    if not words:
        print("no words.json: every beat falls back to its offset from A / B")

    def on(w, after, fallback):
        t = next((s for s, e, x in words if w and s >= after - 0.001 and norm(x) == norm(w)), None)
        if w and (t is None or t >= B):
            print(f"{w!r} is not spoken after {after:.2f} in the window: falling back to {fallback:.2f}")
        return fallback if t is None or t >= B else t

    land = on(LAND_ON, A, A + 0.44)
    land = max(land, A + 0.07)                                  # the drop takes 0.07s before it reaches its spot
    tap = on(TAP_ON, land + 0.45, B - 0.97)
    tap = max(tap, land + 0.45)
    gone = on(GONE_ON, tap + 0.3, B - 0.49)
    gone = min(max(gone, tap + 0.3), B - 0.034)
    if tap + 0.27 > B:
        print(f"the decline at {tap:.2f} leaves no room to fly off before {B:.2f}: end the window later")
    ring, t = [], land
    while t + (2 * ON + OFF) / FPS <= tap - 0.02 or not ring:   # a motor keeps time: as many pairs as fit before the tap
        ring.append(round(t, 4))
        t += RING_EVERY

    # ---- geometry: under the top safe line when the banner clears the brow, else under the chin, else the larger space
    brow, how = brow_line(project, A, B)
    chin = chin_low(project, A, B)
    cy, s, where = (232 if CY is None else CY), (1.0 if SCALE is None else SCALE), "at the top"
    if CY is None and SCALE is None and brow is not None:
        above = (brow - 8 - cy) / CH
        below = (UNDER[1] - chin - UNDER[0]) / CH if chin is not None else -1.0
        if above >= 0.97:
            s = 1.0
        elif below >= max(MIN_SCALE, min(above, 0.97)):           # the face fills the top: under the chin, over the chest
            cy, s, where = chin + UNDER[0], 1.0 if below >= 0.97 else below, "under the chin"
        else:
            s = max(MIN_SCALE, above)
            if above < MIN_SCALE:
                print(f"no room: the brow reaches y {brow} ({how}) and the chin y {chin}; the banner covers the eyes for a beat")
    print(f"brow {brow} ({how or 'not measured: no track.json or matte'}), chin {chin}: the banner sits {where}, top {cy}, "
          f"scale {s:.2f}")
    v = lambda x: round(x * s, 1)      # noqa: E731
    cw, ch = v(CW), v(CH)
    cx = round(540 - CW * s / 2, 1)
    av, dsc, pad, gap = v(AV), round(DISC * s), v(PAD), v(DISC_GAP)
    txt_x = round(pad + av + v(26), 1)
    dec_x, acc_x = round(cw - pad - dsc - gap - dsc, 1), round(cw - pad - dsc, 1)
    disc_y = round((ch - dsc) / 2, 1)
    tap_d = v(92)
    pill_top = PILL_TOP if PILL_TOP is not None else round(cy + ch + 4)
    pill_h, icon = v(68), v(44)

    html = f"""<!-- incoming-call: written by gen.py for this window (rerun it when the window or the cut changes). A phone's call
     banner, generic (no phone's UI copied, glyphs drawn by gen.py): it keeps a phone's own colours, the type is the
     pack's. It drops in on a word, buzzes in pairs while the speaker ignores it, a tap declines it, "{PILL}" for half a
     second. -->
<div id="@@-pillrow" style="top:{pill_top}px;height:{pill_h}px">
  <div id="@@-pillw" data-layout-allow-overlap style="height:{pill_h}px">
    <svg class="@@-pi" width="{icon}" height="{icon}" viewBox="0 0 44 44"><circle cx="22" cy="22" r="22" fill="{RED}"/><g transform="translate(8.36 8.36) scale({44 * .62 / 64:.4f})"><path d="{HANDSET}" fill="#fff"/></g></svg>
    <span class="@@-pt" data-layout-allow-overlap>{PILL}</span>
  </div>
</div>
<div id="@@-cardw" data-layout-allow-overflow style="left:{cx}px;top:{cy}px;width:{cw}px;height:{ch}px">
  <div id="@@-buzz">
    <div id="@@-card">
      <svg class="@@-av" width="{av}" height="{av}" viewBox="0 0 108 108"><defs><clipPath id="@@-avc"><circle cx="54" cy="54" r="54"/></clipPath></defs><circle cx="54" cy="54" r="54" fill="{CONTACT_BG}"/><g clip-path="url(#@@-avc)" fill="{CONTACT_FG}"><circle cx="54" cy="42" r="19"/><path d="M14 112 C14 80 32 68 54 68 C76 68 94 80 94 112 Z"/></g></svg>
      <div class="@@-name" data-layout-allow-overlap>{CALLER}</div>
      <div class="@@-label" data-layout-allow-overlap>{LABEL}</div>
      <div id="@@-decw" style="left:{dec_x}px;top:{disc_y}px;width:{dsc}px;height:{dsc}px">{disc("@@-dec", RED, "@@-decg", 0, .74, dsc)}</div>
      <div id="@@-accw" style="left:{acc_x}px;top:{disc_y}px;width:{dsc}px;height:{dsc}px">{disc("@@-acc", GREEN, "@@-accg", -135, .62, dsc)}</div>
      <div id="@@-tap" style="left:{round(dec_x + dsc / 2 - tap_d / 2, 1)}px;top:{round(disc_y + dsc / 2 - tap_d / 2, 1)}px;width:{tap_d}px;height:{tap_d}px"></div>
    </div>
  </div>
</div>
<style>
#@@ #@@-cardw {{ position:absolute; opacity:0; }}
#@@ #@@-buzz {{ position:absolute; left:0; top:0; width:100%; height:100%; }}
#@@ #@@-card {{ position:absolute; left:0; top:0; width:100%; height:100%; background:{BANNER}; border-radius:{v(R)}px;
  box-shadow:0 14px 34px rgba(0,0,0,.26), 0 2px 6px rgba(0,0,0,.16), inset 0 0 0 1.5px rgba(255,255,255,.08); }}
#@@ .@@-av {{ position:absolute; left:{pad}px; top:{round((ch - av) / 2, 1)}px; }}
#@@ .@@-name {{ position:absolute; left:{txt_x}px; top:{round(ch / 2 - v(56), 1)}px; white-space:nowrap; font-family:var(--font-text); font-weight:700;
  font-size:{v(FONT_NAME)}px; line-height:{v(56)}px; letter-spacing:-.022em; color:{NAME}; }}
#@@ .@@-label {{ position:absolute; left:{txt_x}px; top:{round(ch / 2 + v(4), 1)}px; white-space:nowrap; font-family:var(--font-text); font-weight:500;
  font-size:{v(FONT_LABEL)}px; line-height:{v(42)}px; letter-spacing:-.008em; color:{SUB}; }}
#@@ #@@-decw, #@@ #@@-accw {{ position:absolute; }}
#@@ .@@-disc {{ position:absolute; left:0; top:0; display:block; }}
#@@ #@@-pillrow {{ position:absolute; left:0; width:1080px; display:flex; justify-content:center; }}
#@@ #@@-pillw {{ display:flex; align-items:center; padding:0 {v(26)}px 0 {v(12)}px; background:{BANNER}; border-radius:{round(pill_h / 2, 1)}px; opacity:0;
  box-shadow:0 8px 20px rgba(0,0,0,.24), inset 0 0 0 1.5px rgba(255,255,255,.08); }}
#@@ .@@-pi {{ flex:none; }}
#@@ .@@-pt {{ margin-left:{v(14)}px; white-space:nowrap; font-family:var(--font-text); font-weight:600; font-size:{v(FONT_PILL)}px; line-height:{pill_h}px;
  letter-spacing:-.01em; color:{NAME}; }}
#@@ #@@-tap {{ position:absolute; border-radius:50%; background:rgba(255,255,255,.30); box-shadow:0 0 0 2px rgba(255,255,255,.7); opacity:0; }}
</style>
"""
    # ---- the buzz: one set per frame, alternating sign with a seeded wobble (at 30 fps that reads as a motor, not a shake)
    fA = round(A * FPS)
    buzz, k = [], 0
    for t0 in ring:
        f0 = round(t0 * FPS)
        for bf in (f0, f0 + ON + OFF):
            for i in range(ON):
                env = (.62, .92, 1, .9, .55)[i]
                sign = 1 if k % 2 else -1
                x = sign * AMP * env * (.8 + .2 * rnd(k + 3)) * s
                buzz.append([bf + i - fA, round(x, 2), round(x * .035 / max(s, .01), 3), round(sign * ROCK * env, 1)])
                k += 1
            buzz.append([bf + ON - fA, 0, 0, 0])
    off = round(cy + ch + 60)
    rel = lambda t: round(t - A, 4)      # noqa: E731
    js = f"""// incoming-call: written by gen.py for this window (rerun it when the window or the cut changes). The banner drops
// in and lands on the word, buzzes in two-burst pairs while the speaker keeps talking, a soft tap declines it on the
// word, it squashes and flies off, the "{PILL}" pill is gone by the last word. Times are seconds after A.
var R = '#{{{{ID}}}}-', FPS = 30, F0 = Math.round(A * FPS);
var T = {{ land: {rel(land)}, tap: {rel(tap)}, pill: {rel(tap + 0.034)}, gone: {rel(gone)} }}, OFF = {off};
// per frame of the buzz: [frame after A, x px, rotation deg, the answer handset's rock deg]
var BUZZ = {json.dumps(buzz, separators=(',', ':'))};
function at(f) {{ return q((F0 + f) / FPS); }}

gsap.set(R + 'cardw', {{ y: -OFF, transformOrigin: '{round(dec_x + dsc / 2, 1)}px 50%' }});
gsap.set(R + 'accg', {{ transformOrigin: '50% 50%' }});
gsap.set(R + 'decw', {{ transformOrigin: '50% 50%' }});
tl.set(R + 'cardw', {{ opacity: 1 }}, q(A + T.land - 0.07));
tl.fromTo(R + 'cardw', {{ y: -OFF }}, {{ y: 0, duration: 0.17, ease: 'back.out(1.25)', immediateRender: false }}, q(A + T.land - 0.07));   // reaches its spot on the word; the overshoot settles under the first buzz

BUZZ.forEach(function (b) {{
  tl.set(R + 'buzz', {{ x: b[1], rotation: b[2] }}, at(b[0]));
  tl.set(R + 'accg', {{ rotation: b[3] }}, at(b[0]));
}});

// the tap, the same soft circle as the chat effects; decline takes it
tl.fromTo(R + 'tap', {{ opacity: 0, scale: 1.7 }}, {{ opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', immediateRender: false }}, q(A + T.tap - 0.1));
tl.to(R + 'tap', {{ scale: 0.84, duration: 0.05, ease: 'power2.out' }}, q(A + T.tap));
tl.to(R + 'tap', {{ scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }}, q(A + T.tap + 0.07));
tl.to(R + 'decw', {{ scale: 0.86, duration: 0.05, ease: 'power2.out' }}, q(A + T.tap));
tl.set(R + 'dec-dim', {{ opacity: 0.22 }}, q(A + T.tap));
// the banner takes the press, squashes, and goes
tl.to(R + 'cardw', {{ scaleY: 0.84, scaleX: 1.03, y: 6, duration: 0.067, ease: 'power2.out' }}, q(A + T.tap + 0.033));
tl.to(R + 'cardw', {{ y: -OFF, scaleY: 1.05, scaleX: 0.97, duration: 0.17, ease: 'power2.in' }}, q(A + T.tap + 0.1));
// "{PILL}": pops as the banner takes the press, gone by the word
tl.set(R + 'pillw', {{ opacity: 1 }}, q(A + T.pill));
tl.fromTo(R + 'pillw', {{ scale: 0.7 }}, {{ scale: 1, duration: 0.16, ease: 'back.out(1.8)', immediateRender: false }}, q(A + T.pill));
tl.to(R + 'pillw', {{ scale: 0.86, opacity: 0, duration: 0.067, ease: 'power1.in' }}, q(A + T.gone - 0.067));
"""
    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)
    lib = IN_KIT and os.path.realpath(out) == os.path.realpath(HERE)   # writing into the library itself (the effects lab)
    with open(os.path.join(out, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write((LIB_HTML if lib else "") + html.replace("@@", "{{ID}}"))
    with open(os.path.join(out, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write((LIB_JS if lib else "") + js)
    buzz_wav = os.path.join(project, "audio", "phone-buzz.wav")
    if not os.path.exists(buzz_wav):
        sys.path.insert(0, HERE)
        sys.dont_write_bytecode = True                          # no __pycache__ in the effect's folder
        import mk_buzz
        mk_buzz.make(project)
        print(f"wrote {buzz_wav} (mk_buzz.py: a synthesized phone buzz, 5 frames on, 2 off, 5 on)")
    print(f"wrote {out}/fx.html + fx.js: lands {land:.2f}, rings at {', '.join(f'{r:.2f}' for r in ring)}, declined {tap:.2f}, "
          f"pill gone {gone:.2f}")
    print("SOUND sfx (time = the visual event):")
    for r in ring:
        print(f'    ({r:.3f}, "phone-buzz", -11),   # a buzz pair (audio/phone-buzz.wav)')
    print(f'    ({tap:.3f}, "click", -13),   # the tap on decline')
    print(f'    ({tap + 0.2:.3f}, "whoosh-soft", -18),   # the banner flies off')
    print(f'    ({tap + 0.114:.3f}, "pop", -20),   # {PILL}')
    print(f"frames=[{ring[0] + 0.25:.2f}, {tap:.2f}, {tap + 0.3:.2f}]")


if __name__ == "__main__":
    main()
