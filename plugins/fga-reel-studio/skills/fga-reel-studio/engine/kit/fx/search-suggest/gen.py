#!/usr/bin/env python3
"""search-suggest: a search box types the question as the speaker says it, and the dropdown answers with what people
really search.

A generic search pill (a thin magnifier, no search engine's logo or colours: the pack's light ground and text face)
drops in above the head on the first word. The query types in bursts on the speaker's words, a letter a frame with the
caret leading. The suggestion rows under it swap live per prefix, the part the user hasn't typed in bold as real search
UI does, and they are real: public autocomplete for every prefix, fetched when gen.py runs and saved with the date in
suggest.json, wording untouched and in the order returned. The panel floats in the room behind the speaker: the head
cuts through it and throws a soft shadow on it. On the last word the top row highlights, a soft tap presses it, and it
all lifts away.

Run: PY fx/<id>/gen.py <project> [<id>] [--refresh]
  reads   <project>/edit.py (the FX entry <id>: layer "behind", with a CUT_WINDOWS entry over it), words.json, the
          matte (public/subject.webm) or work/tracks/track.json (to keep the pill and the top row above the head),
          style/ (the pack's text face, for the width check), and the network the first time
  writes  <project>/fx/<id>/fx.html, fx.js, suggest.json (the dated snapshot; reruns keep it while it has every prefix,
          --refresh fetches again: autocomplete moves with date and place). Prints every row it will show (read them
          before you render) and the sounds.
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the query changes.
"""
import argparse
import datetime
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN_KIT = os.path.exists(os.path.join(HERE, "..", "..", "pipeline", "fxlib.py"))   # this copy is the kit library's, not a project's
FPS = 30

# ---- the one table
QUERY = []                  # [(query word, the spoken word it types on)], e.g. [("how", "needed"), ("to", "to")];
                            # [] = the words spoken in the window, lower case, each typing on itself
OPEN_AFTER = 2              # the dropdown opens once this many query words are typed
SWAP = 2                    # frames at least between two swaps of the rows (about a real round trip)
SKIP = []                   # prefixes whose rows you'd rather not show: the rows hold the previous answer instead
N_ROWS = 4
TAP, LIFT = 2, 6            # frames after the last letter: the soft tap on the top row, then the lift
URL = "https://suggestqueries.google.com/complete/search?client=firefox&q="   # public autocomplete, no key

# ---- layout (frame px on the 1080x1920 canvas, before SCALE)
X, W = 90, 900              # the pill and the panel
PILL_Y, PILL_H = 224, 88    # the pill's top: under the top safe line
PANEL_GAP, ROW_H, PANEL_PAD, PANEL_R = 8, 66, 8, 28
TXT_X = 92                  # from the left edge: the typed text and the rows share this edge
Q_PX, ROW_PX = 46, 37
TAP_X = 700                 # where the tap lands on the top row (frame px)
SCALE = None                # None = 1, or smaller so the pill and the top row clear the head (read off the matte)
CLEAR, MIN_SCALE = 10, 0.72
SHADOW = dict(dx=30, dy=22, blur=20, opacity=.58)   # the head's shadow on the panel (nearer than a wall: tight); None = none

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
from common import load_edit  # noqa: E402  (fxlib puts the kit's pipeline on the path)


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def rnd(i):
    x = math.sin(i * 12.9898) * 43758.5453
    return x - math.floor(x)


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


def fetch(prefix):
    req = urllib.request.Request(URL + urllib.parse.quote(prefix), headers={"User-Agent": "Mozilla/5.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=15).read()
    except OSError as e:
        sys.exit(f"could not reach the autocomplete service for {prefix!r} ({e}): this effect needs the network once. "
                 "It never makes rows up.")
    for enc in ("utf-8", "latin-1"):
        try:
            return json.loads(raw.decode(enc))[1]
        except (UnicodeDecodeError, ValueError, IndexError):
            continue
    sys.exit(f"could not read the autocomplete answer for {prefix!r}")


def common(a, b):
    n = 0
    while n < min(len(a), len(b)) and a[n].lower() == b[n].lower():
        n += 1
    return n


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;")


def cut_windows(E, TLJ, A, B):
    """what the cutout needs: None when CUT_WINDOWS already cover A..B (they may skip a cut frame), else the entries to
    add, split at every picture cut inside the window (a cutout window never crosses one)"""
    t = A
    for a, b in sorted(getattr(E, "CUT_WINDOWS", [])):
        if a <= t + 1.02 / FPS and b > t:
            t = b
    if t >= B - 0.02:
        return None
    cuts = inner_cuts(TLJ, A, B)
    ends, out = [A] + cuts + [B], []
    for k, (a, b) in enumerate(zip(ends, ends[1:])):
        out.append((round(a + (1 / FPS if k else 0), 4), round(b, 4)))   # the cut frame itself gets no cutout: on that
    return out                                                           # frame the footage can still show the shot before


def inner_cuts(TLJ, A, B):
    """picture cuts (and reframes) strictly inside the window"""
    return sorted(c for c in TLJ.get("picture_cuts", []) + TLJ.get("reframes", []) if A + 0.04 < c < B - 0.04)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--refresh", action="store_true", help="fetch the suggestions again")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    if F.get("layer", "top") != "behind":
        print(f"{fid} is on layer {F.get('layer', 'top')!r}: built for 'behind' (the rows pass behind the head)")
    need = cut_windows(E, json.load(open(os.path.join(project, "timeline.json"))), A, B) if F.get("layer") == "behind" else None
    if need:
        print(f"add CUT_WINDOWS over the window or the speaker is behind the panel: {', '.join(str(w) for w in need)}")
    if not os.path.exists(os.path.join(project, "words.json")):
        sys.exit("words.json missing: run pipeline/words.py first (every letter types on a word)")
    words = fxlib.words(project)
    spoken = [w for w in words if A - 0.05 <= w[0] < B - 0.05]           # the line said in the window
    pairs = list(QUERY) or [(norm(w[2]), w[2]) for w in spoken]
    pairs = [(q, cue) for q, cue in pairs if q]
    if not pairs:
        sys.exit(f"nothing is spoken in {fid}'s window {A:.2f}-{B:.2f}: set QUERY")
    query = " ".join(q for q, _ in pairs)

    # ---- the keys: each query word types on its spoken word, a letter a frame (its space with it); never two at once
    f_land, keys, prev, t = None, {}, None, A
    for k, (q, cue) in enumerate(pairs):
        on = next((w[0] for w in words if w[0] >= t - 0.001 and norm(w[2]) == norm(cue) and w[0] < B), None)
        if on is None:
            on = (t + 0.25) if k else A + 0.15
            print(f"{cue!r} is not spoken after {t:.2f}: {q!r} types at {on:.2f}")
        t = on + 0.01
        f = round(on * FPS)
        if f_land is None:
            f_land = max(round(A * FPS) + 4, f)              # the pill drops in over 4 frames and lands on the first word
            f = f_land
        f = max(f + 1 if k == 0 else f, (prev or 0) + 1)
        n0 = len(" ".join(q for q, _ in pairs[:k])) + (1 if k else 0)
        for i in range(len(q) + (1 if k < len(pairs) - 1 else 0)):
            keys[f + i] = n0 + i + 1
        prev = f + len(q) + (1 if k < len(pairs) - 1 else 0) - 1
    f_last = max(keys)
    f_end = round(B * FPS)
    f_tap, f_lift = f_last + TAP, f_last + TAP + LIFT
    if f_lift + 6 > f_end:
        f_lift = max(f_tap + 1, f_end - 6)
        f_tap = min(f_tap, f_lift - 1)
        print(f"the window ends {B:.2f}: the tap and the lift move up to frames {f_tap} and {f_lift} (end the window later)")

    # ---- the real suggestions, every prefix, one dated snapshot
    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "suggest.json")
    if IN_KIT and os.path.realpath(out) == os.path.realpath(HERE):   # the library folder itself: keep the snapshot out of it
        path = os.path.join(project, "work", fid, "suggest.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
    prefixes = [query[:i + 1] for i in range(len(query))]
    saved = json.load(open(path)) if os.path.exists(path) else None
    if args.refresh or not saved or any(p not in saved.get("prefixes", {}) for p in prefixes):
        saved = dict(date=datetime.date.today().isoformat(), source=URL + "<prefix>",
                     note="public autocomplete, wording untouched, order as returned", prefixes={p: fetch(p) for p in prefixes})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(saved, fh, indent=1, ensure_ascii=False)
        print(f"fetched {len(prefixes)} prefixes of {query!r} ({saved['date']}) into {path}")
    SG = saved["prefixes"]

    # ---- which answer the rows show: open after OPEN_AFTER words, then a swap at most every SWAP frames, the full query last
    typed = sorted(keys.items())
    opened = len(" ".join(q for q, _ in pairs[:OPEN_AFTER])) + (1 if OPEN_AFTER < len(pairs) else 0)
    rows_at, last = [], -99
    for f, n in typed:
        p = query[:n]
        if n < min(opened, len(query)) or p in SKIP or not SG.get(p):
            continue
        if f - last >= SWAP or n == len(query):
            if rows_at and f - rows_at[-1][0] < SWAP:         # the full query lands right after a swap: it replaces it
                rows_at.pop()
            rows_at.append((f, p))
            last = f
    if not rows_at:
        sys.exit(f"autocomplete gave nothing to show for {query!r} (or every prefix is in SKIP): pick another QUERY")

    # ---- geometry: under the top safe line, scaled down only as far as the head needs
    head, how = head_top(project, A, B, X, X + W)
    need = PILL_H + PANEL_GAP + PANEL_PAD + ROW_H
    s = 1.0 if SCALE is None else SCALE
    if SCALE is None and head is not None:
        room = (head - CLEAR - PILL_Y) / need
        s = 1.0 if room >= 0.97 else max(MIN_SCALE, room)
        if room < MIN_SCALE:
            print(f"the head reaches y {head} here ({how}): even at {MIN_SCALE} the top row passes behind it. Use 'top' as "
                  "the layer with N_ROWS = 2, or a line where the head is lower")
    print(f"head top {head} ({how or 'not measured: no matte or track.json'}); scale {s:.2f}")
    v = lambda x: round(x * s, 1)      # noqa: E731
    w, x = v(W), round(540 - W * s / 2, 1)
    pill_y, pill_h = PILL_Y, v(PILL_H)
    row_h, pad, txt_x = v(ROW_H), v(PANEL_PAD), v(TXT_X)
    panel_y = round(pill_y + pill_h + v(PANEL_GAP), 1)
    panel_h = round(2 * pad + row_h * N_ROWS, 1)
    q_px, row_px = v(Q_PX), v(ROW_PX)
    tap_d = v(92)

    # rows per state, the untyped part bold; a width check in the pack's text face (the panel clips, as a real one does)
    fnt = fxlib.font(project, "text", max(8, round(row_px)))
    states, shown = [], []
    for k, (f, p) in enumerate(rows_at):
        rows = []
        for r, text in enumerate(SG[p][:N_ROWS]):
            n = common(p.rstrip(), text)
            if fnt.getlength(text) * 1.03 > w - txt_x - 8:
                print(f"  row {text!r} runs past the panel: it is clipped, as a real dropdown clips it")
            rows.append(f'<div class="@@-t" data-layout-allow-overlap data-layout-allow-occlusion style="top:{round(pad + r * row_h, 1)}px">{esc(text[:n])}<b>{esc(text[n:])}</b></div>')
            shown.append((f, p, text))
        states.append(f'<div id="@@-st{k}" class="@@-st" data-layout-allow-overlap>{"".join(rows)}</div>')

    MAG = ('<circle cx="17" cy="17" r="11.5" fill="none" class="{c}" stroke-width="{w}"/>'
           '<path d="M25.6 25.6 L34.5 34.5" fill="none" class="{c}" stroke-width="{w}" stroke-linecap="round"/>')
    glyphs = "".join(f'<svg class="@@-mg" width="{v(30)}" height="{v(30)}" viewBox="0 0 40 40" style="top:{round(pad + r * row_h + (row_h - v(30)) / 2, 1)}px">'
                     f'{MAG.format(c="@@-g2", w=3.4)}</svg>' for r in range(N_ROWS))
    letters = "".join(f'<span class="@@-c" data-layout-allow-overlap data-layout-allow-occlusion>{esc(c)}</span>' for c in query)
    shadow = ""
    if SHADOW:
        shadow = (f'<div id="@@-shw" style="left:{-x}px;top:{-panel_y}px"><video id="@@-shadow" src="subject.webm" muted playsinline '
                  f'data-start="{{{{START+0.0333}}}}" data-media-start="{{{{SYNC+0.0333}}}}" data-duration="{{{{DUR-0.0333}}}}" '
                  f'data-track-index="{{{{T0}}}}" style="position:absolute;left:{SHADOW["dx"]}px;top:{SHADOW["dy"]}px;width:1080px;'
                  f'height:1920px;filter:brightness(0) blur({SHADOW["blur"]}px);opacity:{SHADOW["opacity"]};"></video></div>')
    html = f"""<!-- search-suggest: written by gen.py for this window (rerun it when the window, the cut or the query changes). A
     search box in the room behind the speaker; the rows are real public autocomplete from fx/{{{{ID}}}}/suggest.json
     ({saved['date']}), wording untouched. Generic search UI, no engine copied; every colour and font is the pack's. -->
<div id="@@-cutw" data-layout-allow-overflow data-layout-allow-overlap>
<div id="@@-panelw" data-layout-allow-overflow style="left:{x}px;top:{panel_y}px;width:{w}px;height:{panel_h}px">
  <div id="@@-panel" data-layout-allow-overlap>
    <div id="@@-hl" style="left:{pad}px;top:{pad}px;width:{round(w - 2 * pad, 1)}px;height:{row_h}px"></div>
    <div id="@@-hl2" style="left:{pad}px;top:{pad}px;width:{round(w - 2 * pad, 1)}px;height:{row_h}px"></div>
    {glyphs}
    {"".join(states)}
    {shadow}
  </div>
</div>
</div>
<div id="@@-pillw" data-layout-allow-overflow style="left:{x}px;top:{pill_y}px;width:{w}px;height:{pill_h}px">
  <div id="@@-pill">
    <svg class="@@-pg" width="{v(42)}" height="{v(42)}" viewBox="0 0 40 40">{MAG.format(c="@@-g1", w=2.9)}</svg>
    <div class="@@-q" data-layout-allow-overlap data-layout-allow-occlusion>{letters}<span class="@@-caret"></span></div>
    <svg id="@@-x" width="{v(30)}" height="{v(30)}" viewBox="0 0 30 30"><path class="@@-g3" d="M7 7 L23 23 M23 7 L7 23" fill="none" stroke-width="2.8" stroke-linecap="round"/></svg>
  </div>
</div>
<div id="@@-tap" style="left:{round(TAP_X - tap_d / 2, 1)}px;top:{round(panel_y + pad + row_h / 2 - tap_d / 2, 1)}px;width:{tap_d}px;height:{tap_d}px"></div>
<style>
#@@ #@@-panelw, #@@ #@@-pillw {{ position:absolute; }}
#@@ #@@-cutw {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
#@@ #@@-pill {{ position:absolute; left:0; top:0; width:100%; height:100%; background:var(--c-light); border-radius:{round(pill_h / 2, 1)}px;
  box-shadow:0 14px 34px color-mix(in srgb, var(--c-dark) 26%, transparent), 0 2px 6px color-mix(in srgb, var(--c-dark) 16%, transparent); }}
#@@ .@@-pg {{ position:absolute; left:{round(txt_x / 2 - v(21) + v(2), 1)}px; top:{round((pill_h - v(42)) / 2, 1)}px; }}
#@@ .@@-g1 {{ stroke:var(--c-ink); }}
#@@ .@@-g2 {{ stroke:color-mix(in srgb, var(--c-ink) 42%, transparent); }}
#@@ .@@-g3 {{ stroke:color-mix(in srgb, var(--c-ink) 50%, transparent); }}
#@@ .@@-q {{ position:absolute; left:{txt_x}px; top:0; height:{pill_h}px; white-space:pre; font-family:var(--font-text); font-weight:500;
  font-size:{q_px}px; line-height:{pill_h}px; letter-spacing:-.015em; color:var(--c-ink); }}
#@@ .@@-c {{ display:none; }}
#@@ .@@-caret {{ display:inline-block; width:{max(2.5, v(3.5))}px; height:{v(50)}px; margin-left:{v(3)}px; vertical-align:middle;
  border-radius:2px; background:var(--c-ink); }}
#@@ #@@-x {{ position:absolute; right:{v(30)}px; top:{round((pill_h - v(30)) / 2, 1)}px; opacity:0; }}
#@@ #@@-panel {{ position:absolute; left:0; top:0; width:100%; height:100%; overflow:hidden; background:var(--c-light); border-radius:{v(PANEL_R)}px;
  box-shadow:0 14px 34px color-mix(in srgb, var(--c-dark) 26%, transparent), 0 2px 6px color-mix(in srgb, var(--c-dark) 16%, transparent); }}
#@@ #@@-hl, #@@ #@@-hl2 {{ position:absolute; border-radius:{round(v(PANEL_R) - pad, 1)}px; opacity:0; }}
#@@ #@@-hl {{ background:color-mix(in srgb, var(--c-ink) 7%, var(--c-light)); }}
#@@ #@@-hl2 {{ background:color-mix(in srgb, var(--c-ink) 14%, var(--c-light)); }}
#@@ .@@-mg {{ position:absolute; left:{round(txt_x / 2 - v(15) + v(2), 1)}px; }}
#@@ .@@-st {{ position:absolute; left:0; top:0; width:100%; height:100%; opacity:0; }}
#@@ .@@-t {{ position:absolute; left:{txt_x}px; width:{round(w - txt_x - 8, 1)}px; height:{row_h}px; overflow:hidden; white-space:pre;
  font-family:var(--font-text); font-weight:400; font-size:{row_px}px; line-height:{row_h}px; letter-spacing:-.012em; color:var(--c-ink); }}
#@@ .@@-t b {{ font-weight:700; }}
#@@ #@@-shw {{ position:absolute; width:1080px; height:1920px; }}
#@@ #@@-tap {{ position:absolute; border-radius:50%; opacity:0; background:color-mix(in srgb, var(--c-ink) 24%, transparent);
  box-shadow:0 0 0 2px color-mix(in srgb, var(--c-ink) 22%, transparent); }}
</style>
"""
    fA = round(A * FPS)
    pill_off = round(pill_y + pill_h + 40)
    lift = round(panel_y + panel_h + 60)                       # the same distance for both: they leave as one thing
    js = f"""// search-suggest: written by gen.py for this window (rerun it when the window, the cut or the query changes). The
// pill drops in and lands on the first word, the query types a letter a frame in bursts on the speaker's words, the
// real rows swap per prefix, the top row highlights and takes a soft tap, it all lifts away. The panel sits behind
// the speaker (a CUT_WINDOWS entry over the window). Frames are counted from A's frame.
var R = '#{{{{ID}}}}-', S = '#{{{{ID}}}} .{{{{ID}}}}-', FPS = 30, F0 = Math.round(A * FPS);
var LAND = {f_land - fA}, PILL_OFF = {pill_off}, LIFT = {lift};
var KEYS = {json.dumps([[f - fA, n] for f, n in typed], separators=(',', ':'))};   // [frame, letters on screen]
var ROWS = {json.dumps([[f - fA, k] for k, (f, _) in enumerate(rows_at)], separators=(',', ':'))};   // [frame, which answer]
var HILITE = {f_last - fA}, TAP = {f_tap - fA}, LIFT_F = {f_lift - fA};
var CUTF = {json.dumps([round(c * FPS) - fA for c in inner_cuts(json.load(open(os.path.join(project, "timeline.json"))), A, B)])};   // picture cuts inside the window
function at(f) {{ return q((F0 + f) / FPS); }}

// the pill drops in and lands on the first word; the panel waits for its first answer
gsap.set(R + 'pillw', {{ y: -PILL_OFF }});
gsap.set(R + 'panelw', {{ opacity: 0 }});
tl.fromTo(R + 'pillw', {{ y: -PILL_OFF }}, {{ y: 0, duration: 4 / FPS, ease: 'back.out(1.2)', immediateRender: false }}, at(LAND - 4));

// the keys: each letter on its frame, the caret follows (it sits after the letters), the clear glyph with the first one
var letters = document.querySelectorAll(S + 'c');
KEYS.forEach(function (k) {{ tl.set(letters[k[1] - 1], {{ display: 'inline' }}, at(k[0])); }});
tl.set(R + 'x', {{ opacity: 1 }}, at(KEYS[0][0]));

// the dropdown opens on the first answer, then swaps per prefix with no transition, as real search does
tl.set(R + 'panelw', {{ opacity: 1 }}, at(ROWS[0][0]));
tl.fromTo(R + 'panel', {{ clipPath: 'inset(0px 0px {panel_h}px 0px round {v(PANEL_R)}px)' }}, {{ clipPath: 'inset(-60px -60px -60px -60px round {v(PANEL_R)}px)', duration: 0.13, ease: 'power3.out', immediateRender: false }}, at(ROWS[0][0]));
ROWS.forEach(function (r, k) {{
  tl.set(R + 'st' + r[1], {{ opacity: 1 }}, at(r[0]));
  if (k) tl.set(R + 'st' + ROWS[k - 1][1], {{ opacity: 0 }}, at(r[0]));
}});

// the top row highlights on the last letter, the soft tap lands and presses it
tl.set(R + 'hl', {{ opacity: 1 }}, at(HILITE));
tl.fromTo(R + 'tap', {{ opacity: 0, scale: 1.6 }}, {{ opacity: 1, scale: 1, duration: 2 / FPS, ease: 'power2.out', immediateRender: false }}, at(TAP - 2));
tl.to(R + 'tap', {{ scale: 0.84, duration: 0.05, ease: 'power2.out' }}, at(TAP));
tl.to(R + 'tap', {{ scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }}, at(TAP + 2));
tl.set(R + 'hl2', {{ opacity: 1 }}, at(TAP));
tl.set(S + 'caret', {{ opacity: 0 }}, at(TAP));

// a picture cut inside the window: on its frame the footage can still show the shot before and no cutout plays, so
// the rows (which pass behind the head) sit that one frame out
CUTF.forEach(function (f) {{ tl.set(R + 'cutw', {{ opacity: 0 }}, at(f)); tl.set(R + 'cutw', {{ opacity: 1 }}, at(f + 1)); }});

// it all lifts away: the pill leads, the panel a frame behind; the shadow counter-moves so it stays on the head
tl.to(R + 'pillw', {{ y: -LIFT, duration: 5 / FPS, ease: 'power2.in' }}, at(LIFT_F));
tl.to(R + 'panelw', {{ y: -LIFT, duration: 5 / FPS, ease: 'power2.in' }}, at(LIFT_F + 1));
if (document.querySelector(R + 'shw')) tl.to(R + 'shw', {{ y: LIFT, duration: 5 / FPS, ease: 'power2.in' }}, at(LIFT_F + 1));
"""
    lib = IN_KIT and os.path.realpath(out) == os.path.realpath(HERE)   # writing into the library itself (the effects lab)
    with open(os.path.join(out, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write((LIB_HTML if lib else "") + html.replace("@@", "{{ID}}"))
    with open(os.path.join(out, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write((LIB_JS if lib else "") + js)

    print(f"wrote {out}/fx.html + fx.js: {query!r}, pill lands {f_land / FPS:.2f}, last letter {f_last / FPS:.2f}, "
          f"tap {f_tap / FPS:.2f}, lift {f_lift / FPS:.2f}")
    print(f"rows shown (from suggest.json, {saved['date']}): read every one before you render; put a prefix in SKIP to hold the previous rows")
    for f, p in rows_at:
        print(f"  {f / FPS:6.2f}  {p!r:24} " + " | ".join(SG[p][:N_ROWS]))
    print("SOUND sfx (time = the visual event):")
    print(f'    ({f_land / FPS:.3f}, "whoosh-soft", -17),   # the pill lands')
    print(f'    ({f_tap / FPS:.3f}, "click", -13),   # the tap on the top row')
    print(f'    ({(f_lift + 3) / FPS:.3f}, "whoosh-soft", -16),   # it lifts away')
    keys_sfx = []
    for k, (f, n) in enumerate(typed):
        name, db = ("click", -20.0) if query[n - 1] == " " else ("tick", -19.0)
        keys_sfx.append(f'({f / FPS + .004 + .006 * rnd(k):.3f}, "{name}", {db + 1.6 * rnd(k + 9):.1f})')
    print("    # a tick per letter, a softer click on each space:")
    print("    " + ", ".join(keys_sfx) + ",")
    print(f"frames=[{rows_at[0][0] / FPS + 0.1:.2f}, {f_last / FPS:.2f}, {(f_tap + 1) / FPS:.2f}]")


if __name__ == "__main__":
    main()
