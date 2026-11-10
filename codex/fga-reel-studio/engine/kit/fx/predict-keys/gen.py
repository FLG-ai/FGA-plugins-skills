#!/usr/bin/env python3
"""predict-keys: a phone keyboard rises from the bottom of the frame and types the speaker's line as they say it,
letter by letter, key by key, the predictive bar updating on every keystroke. Then the bar offers three words, the
caret waits, a soft tap picks the one they say, it jumps into the sentence in the accent, send presses, it drops.
Solid keycaps floating on the footage, no tray, no glass, a generic keyboard (no real phone's copied); its colours and
type are the creator's (style pack).

This writes <project>/fx/<id>/fx.html + fx.js from the table below and the project:
  the words     LINE, found in words.json as the words said right before PICK (each one types on its own onset;
                words said before the window starts are already in the field when it rises)
  the bar       while a word types: what is typed so far, the word, an alternative; after it: three guesses for the
                next word, the real one first. GUESS overrides any word; otherwise both come from the video's own
                transcript. The last word's guesses are SUGGEST, the payoff
  the size      the field's top stays CHIN_GAP under the speaker's chin (work/tracks/track.json across the window):
                when the chin is low the whole keyboard scales down about its bottom centre
  the type      the pack's text face, wrapped from its real metrics (the size steps down until the line fits 2 rows)
Run: PY fx/<id>/gen.py <project> [<id>] [--check]
  reads   <project>/edit.py (the FX entry <id>: at, end), words.json, work/tracks/track.json, style/ (the pack)
  writes  <project>/fx/<id>/fx.html + fx.js and prints the sound (--check: prints the plan, writes nothing)
<id> defaults to this script's folder name. Rerun it whenever the window, the cut or the line changes.
"""
import argparse
import collections
import json
import math
import os
import re
import sys

try:
    import fxlib                     # the kit's pipeline is on the kit Python's import path (setup writes reel-kit.pth)
except ImportError:                  # any other Python: the kit is a folder above this file
    _d = os.path.dirname(os.path.realpath(__file__))
    while _d != os.path.dirname(_d) and not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        _d = os.path.dirname(_d)
    if not os.path.exists(os.path.join(_d, "pipeline", "fxlib.py")):
        sys.exit("run this with the kit's Python (PY: $REEL_KIT_HOME/.venv/bin/python), it has the kit's pipeline on its path")
    sys.path.insert(0, os.path.join(_d, "pipeline"))
    import fxlib
from common import load_edit  # noqa: E402

# ---- the table: the words, the payoff, the beats
LINE = "I typed one sentence and it was"   # the words typed, as said (in order, ending right before PICK)
PICK = "done"                              # the word the tap picks from the bar, on its first frame
SUGGEST = ("over", "done", "fine")         # the bar's three words after the line (the payoff); PICK is one of them
AFTER = None                               # what the bar guesses once the pick is in; None = (",", the next word said, ".")
GUESS = {}                                 # optional, per typed word: "word": (("alt", "alt"), ("next", "next", "next"))
SEND_AFTER = 0.33                          # s after the tap: the send arrow presses
DROP_AFTER = 0.05                          # s after send: the whole thing falls, off the frame one frame before the window ends
RISE = 0.22                                # s: up from the bottom edge, from the window's start
CHIN = None                                # or the chin's lowest y on the frame (px), instead of the track
CHIN_GAP = 48                              # px the field's top stays under the chin
MIN_FIT = 0.62                             # never scale the keyboard below this (the keys stop reading)
DB_KEY, DB_SPACE = -17.0, -18.0            # tap level per key and per space; a seeded wobble makes it human

# ---- layout (px on the 1080x1920 frame, before the fit): keyboard bottom at 1468 (Instagram's UI below), x 100..980
# (its icons from y 1155 down). The field grows a line when the sentence wraps.
KX, KW = 100, 880
KEY_H, KEY_GY, KEY_GX = 74, 10, 8
BOTTOM = 1468
BAR_H, BAR_GAP = 62, 10
FIELD_GAP = 10
FONT_PX, LINE_K = 46, 54 / 46              # the typed text; its line height as a share of the size
MIN_FONT = 34                              # the size steps down to this to fit the line on 2 rows
FIELD_PAD_Y, FIELD_PAD_X = 14, 30
SEND = 62
LS = -0.015                                # letter-spacing, em
OFF = 1010                                 # far enough below the frame that the whole stack is gone
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))


def norm(w):
    """the same match as wordAt in the composition"""
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def rnd(i):
    x = math.sin(i * 12.9898) * 43758.5453
    return x - math.floor(x)


def frame(t):
    """a time's frame, counted the way the build counts media frames (pipeline/common.py q)"""
    return round(t * FPS)


def off_frame(A, B):
    """the build times media by rounding to the nearest frame (halves to even) and shows the wrapper rounding halves up:
    a window edge between two frames lands a frame apart in the two, so say so"""
    bad = [f"{n} {t:.4f}" for n, t in (("at", A), ("end", B)) if abs(t * FPS - round(t * FPS)) > 0.01]
    if bad:
        print(f"note: the window's {' and '.join(bad)} sits between frames: put it on a frame (a multiple of 1/30 s)")


def key_rows():
    pitch = (KW + KEY_GX) / 10
    kw = pitch - KEY_GX
    y3 = BOTTOM - KEY_H
    rows = [y3 - 3 * (KEY_H + KEY_GY), y3 - 2 * (KEY_H + KEY_GY), y3 - (KEY_H + KEY_GY), y3]
    keys = {}
    for i, c in enumerate("qwertyuiop"):
        keys[c] = (KX + i * pitch, rows[0], kw, "l")
    for i, c in enumerate("asdfghjkl"):
        keys[c] = (KX + pitch / 2 + i * pitch, rows[1], kw, "l")
    side = 1.5 * pitch - KEY_GX
    keys["shift"] = (KX, rows[2], side, "f")
    for i, c in enumerate("zxcvbnm"):
        keys[c] = (KX + 1.5 * pitch + i * pitch, rows[2], kw, "l")
    keys["back"] = (KX + KW - side, rows[2], side, "f")
    fw = 130
    keys["123"] = (KX, rows[3], fw, "f")
    keys[","] = (KX + fw + KEY_GX, rows[3], kw, "l")
    keys["ret"] = (KX + KW - fw, rows[3], fw, "f")
    keys["."] = (KX + KW - fw - KEY_GX - kw, rows[3], kw, "l")
    sx = KX + fw + KEY_GX + kw + KEY_GX
    keys[" "] = (sx, rows[3], keys["."][0] - KEY_GX - sx, "s")
    return keys, rows


def key_of(ch):
    """the key a character is typed on: its letter, the comma or full stop, the space bar; anything else on 123"""
    c = ch.lower()
    return c if c in KEYS else "123"


# real words to fall back on when the video's own transcript has no word that fits (a keyboard never offers a non-word)
COMMON = ("the and to of a in is it you that he was for on are with as I his they be at one have this from or had by "
          "but what some we can out other were all there when up use your how said an each she which do their time if "
          "will way about many then them write would like so these her long make thing see him two has look more day "
          "could go come did number sound no most people my over know water than call first who may down side been now "
          "find any new work part take get place made live where after back little only round man year came show every "
          "good me give our under name very through just form great think say help low line differ turn cause much mean "
          "before move right boy old too same tell does set three want air well also play small end put home read hand "
          "port large spell add even land here must big high such follow act why ask men change went light kind off need "
          "house picture try us again animal point mother world near build self earth father").split()


def guesses(words):
    """from the video's own transcript: two alternatives for a word (same first letter, longest shared start, most
    said), and three guesses for the word after one (the real next word first, then what follows it elsewhere)"""
    count, follow, show, toks = collections.Counter(), collections.defaultdict(collections.Counter), {}, []
    for _, _, t in words:
        w = re.sub(r"^[^\w']+|[^\w']+$", "", t)
        n = norm(w).strip("'")
        if not n:
            continue
        toks.append(n)
        count[n] += 1
        if n not in show or w == w.lower():           # lower case if the video ever has it lower case; I and names keep theirs
            show[n] = w
    for a, b in zip(toks, toks[1:]):
        follow[a][b] += 1
    common = [show[w] for w, _ in count.most_common(12)]

    def shape(v, like):
        return v[:1].upper() + v[1:] if like[:1].isupper() else v

    def alts(w):
        lw = norm(w).strip("'")

        def shared(v):
            n = 0
            while n < min(len(v), len(lw)) and v[n] == lw[n]:
                n += 1
            return n
        pool = sorted((v for v in count if v != lw and v[:1] == lw[:1] and len(v) > 1),
                      key=lambda v: (-shared(v), -count[v], abs(len(v) - len(lw)), v))
        out = [show[v] for v in pool[:2]]
        for v in sorted((c for c in COMMON if c[:1].lower() == lw[:1] and c.lower() != lw), key=lambda c: -shared(c.lower())):
            if len(out) >= 2:
                break
            if v.lower() not in [o.lower() for o in out]:
                out.append(v)
        for v in COMMON:
            if len(out) >= 2:
                break
            if v.lower() != lw and v.lower() not in [o.lower() for o in out]:
                out.append(v)
        return tuple(shape(v, w) for v in out[:2])

    def nexts(w, real):
        lw = norm(w).strip("'")
        out = [real] if real else []
        for v, _ in follow[lw].most_common():
            if len(out) >= 3:
                break
            if v not in [norm(x) for x in out]:
                out.append(show[v])
        for v in [norm(c) for c in common] + [norm(c) for c in COMMON]:
            if len(out) >= 3:
                break
            if v not in [norm(x) for x in out]:
                out.append(show.get(v, v))
        return tuple(out[:3])
    return alts, nexts, common


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--check", action="store_true", help="print the plan, write nothing")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E = load_edit(project)
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    words = fxlib.words(project)
    typed = LINE.split()
    if norm(PICK) not in [norm(s) for s in SUGGEST]:
        sys.exit(f"PICK {PICK!r} has to be one of SUGGEST {SUGGEST}")

    # ---- the words: PICK said inside the window, LINE the words right before it
    at = fxlib.word_at(project, PICK, A)
    k = next((i for i, w in enumerate(words) if at is not None and at < B and abs(w[0] - at) < 1e-6), None)
    if k is None:
        sys.exit(f"PICK {PICK!r} isn't said inside the window {A:.2f}-{B:.2f}: "
                 f"{' '.join(t for s, e, t in words if A <= s < B)}")
    before = words[k - len(typed):k] if k >= len(typed) else []
    if [norm(t) for _, _, t in before] != [norm(w) for w in typed]:
        said = " ".join(t for _, _, t in words[max(0, k - len(typed) - 3):k])
        sys.exit(f"LINE has to be the words said right before {PICK!r}: the transcript there reads '... {said}'")
    pick_at = words[k][0]
    nxt = re.sub(r"^[^\w']+|[^\w']+$", "", words[k + 1][2]) if k + 1 < len(words) else "and"
    after = AFTER or (",", nxt if nxt == "I" or nxt.startswith("I'") else nxt.lower(), ".")
    alts_of, next_of, common = guesses(words)
    TYPED = []
    for i, (w, (s, e, t)) in enumerate(zip(typed, before)):
        g = GUESS.get(w) or GUESS.get(norm(w))
        alts = tuple(g[0]) if g else alts_of(w)
        nxt = tuple(SUGGEST) if i == len(typed) - 1 else (tuple(g[1]) if g else next_of(w, typed[i + 1]))
        TYPED.append((w, s, alts, nxt))
    send_at, drop_at = pick_at + SEND_AFTER, pick_at + SEND_AFTER + DROP_AFTER
    gone = (frame(B) - 1) / FPS
    if drop_at > gone - 0.12:
        sys.exit(f"the keyboard drops at {drop_at:.2f} but the window ends at {B:.2f}: end it at "
                 f"{drop_at + 0.2:.2f} or later (or shorten SEND_AFTER)")

    # ---- the type: the pack's text face, a size that fits the line on 2 rows
    global KEYS
    KEYS, ROWS_Y = key_rows()
    KEY_TOP = ROWS_Y[0]
    BAR_Y = KEY_TOP - BAR_GAP - BAR_H
    FIELD_BOTTOM = BAR_Y - FIELD_GAP
    TEXT_X = KX + FIELD_PAD_X
    TEXT_MAX = KW - FIELD_PAD_X - SEND - 26
    sentence = typed + [PICK]
    for px in range(FONT_PX, MIN_FONT - 1, -2):
        FONT = fxlib.font(project, "text", px)

        def tlen(s, F=FONT, p=px):
            return F.getlength(s) + len(s) * LS * p
        lines, cur = [], ""
        for w in sentence:
            t = (cur + " " + w).strip()
            if tlen(t) > TEXT_MAX and cur:
                lines.append(cur)
                cur = w
            else:
                cur = t
        lines.append(cur)
        if len(lines) <= 2:
            break
    else:
        sys.exit(f"the line needs {len(lines)} rows even at {MIN_FONT}px in the pack's text face: shorten LINE")
    LINEH = round(px * LINE_K)
    BOT_LINE_Y = FIELD_BOTTOM - FIELD_PAD_Y - LINEH
    TOP_LINE_Y = BOT_LINE_Y - LINEH
    field_top = (TOP_LINE_Y if len(lines) > 1 else BOT_LINE_Y) - FIELD_PAD_Y
    pick_line = len(lines) - 1
    if len(lines) > 1:
        body = [lines[0], lines[1][:-len(PICK)].rstrip()]
    else:
        body = [lines[0][:-len(PICK)].rstrip(), ""]

    # ---- the size: the field's top stays under the chin
    chin = CHIN
    if chin is None:
        path = os.path.join(project, "work", "tracks", "track.json")
        if not os.path.exists(path):
            sys.exit(f"no {path}: run `PY KIT/pipeline/track.py {project}` first (or set CHIN in the table)")
        T = fxlib.tracks(project)["frames"]
        chins = [T[i]["face"]["chin"] for i in range(frame(A), min(frame(B), len(T))) if T[i] and T[i].get("face")]
        chin = max(chins) if chins else None
        if chin is None:
            print("WARNING: no face tracked in the window: the keyboard keeps its full size; check it clears the mouth")
    fit = 1.0
    if chin is not None and chin + CHIN_GAP > field_top:
        fit = (BOTTOM - chin - CHIN_GAP) / (BOTTOM - field_top)
        if fit < MIN_FIT:
            print(f"WARNING: the chin reaches y {chin:.0f}: even at {MIN_FIT} the field covers the mouth. "
                  f"Use it on a wider shot, or set MIN_FIT lower")
            fit = MIN_FIT
    on_top = BOTTOM - (BOTTOM - field_top) * fit

    # ---- keystrokes
    n_first = len(lines[0].split()) if len(lines) > 1 else 10 ** 6
    events, line_text, wrap_t = [], "", None
    for kk, (w, t0, alts, nxt) in enumerate(TYPED):
        t1 = TYPED[kk + 1][1] if kk + 1 < len(TYPED) else t0 + 0.12
        gap = t1 - t0
        line_i = 0 if kk < n_first else 1
        if kk == n_first:
            line_text, wrap_t = "", t0
        span = gap * .80 if kk + 1 < len(TYPED) else .06                 # letters fill most of the word; the space lands just before the next
        cum, stamps = 0.0, []
        for i in range(len(w)):
            stamps.append(cum)
            cum += .7 + .6 * rnd(kk * 31 + i)                             # real thumbs: uneven
        sc = span / max(cum, 1e-6)
        for i, ch in enumerate(w):
            line_text += ch
            events.append(dict(t=t0 + stamps[i] * sc, ch=ch, line=line_i, x=tlen(line_text), word=kk, prefix=w[:i + 1]))
        line_text += " "
        events.append(dict(t=t0 + gap * .9 if kk + 1 < len(TYPED) else t0 + span + .02, ch=" ", line=line_i,
                           x=tlen(line_text), word=kk, prefix=None))
    start_f = frame(A)
    off_frame(A, B)
    pre = [e for e in events if frame(e["t"]) < start_f + 1 and e["t"] < A]     # already in the field when it rises
    live = [e for e in events if e not in pre]
    if not live:
        sys.exit("every word is said before the window starts: start the window earlier")
    for e in live:
        e["f"] = max(start_f + 1, frame(e["t"]))
    pf, sf = frame(pick_at), frame(send_at)
    if live[-1]["f"] + 3 >= pf:
        print(f"WARNING: the last keystroke ({live[-1]['f'] / FPS:.2f}) is within 3 frames of the tap ({pick_at:.2f}): "
              "the three suggestions barely land")

    print(f"{fid}: window {A:.3f}-{B:.3f}  rises {A:.2f}  {len(pre)} keystrokes already in, {len(live)} live  "
          f"tap '{PICK}' {pick_at:.2f}  send {send_at:.2f}  drops {drop_at:.2f}  gone {gone:.2f}")
    print(f"  type {px}px in the pack's text face, {len(lines)} row(s): {lines}")
    print(f"  chin {'%.0f' % chin if chin is not None else '?'}  field top {on_top:.0f}  fit {fit:.3f}")
    for w, t0, alts, nxt in TYPED:
        print(f"  {w:<14} {t0:6.2f}  while typing: {', '.join(alts):<24} next: {', '.join(nxt)}")
    if args.check:
        return
    d = os.path.join(project, "fx", fid)
    if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(d)), "LIBRARY.md")):
        sys.exit(f"{d} is a library folder: copy the effect into the project's own fx/{fid}/ and run it there")
    os.makedirs(d, exist_ok=True)

    # ---- markup
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def key_html(name, x, y, w, kind):
        label = {"shift": '<svg width="34" height="34" viewBox="0 0 24 24"><path class="ID-ico" d="M12 4 L21 13 H16 V20 H8 V13 H3 Z" '
                          'stroke-width="1.9" stroke-linejoin="round"/></svg>',
                 "back": '<svg width="40" height="30" viewBox="0 0 30 22"><path class="ID-ico" d="M9 2 H27 a2 2 0 0 1 2 2 V18 a2 2 0 0 1 '
                         '-2 2 H9 L2 11 Z" stroke-width="1.8" stroke-linejoin="round"/><path class="ID-ico" d="M14 7.5 L21 14.5 '
                         'M21 7.5 L14 14.5" stroke-width="1.8" stroke-linecap="round"/></svg>',
                 "123": "123", "ret": "return", " ": "space"}.get(name, name)
        kid = {"shift": "shift", "back": "back", "123": "n123", "ret": "ret", " ": "sp", ",": "comma", ".": "dot"}.get(name, name)
        cls = {"l": "ID-k", "f": "ID-k ID-f", "s": "ID-k ID-s"}[kind]
        return (f'<div id="ID-k-{kid}" class="{cls}" data-layout-allow-overlap style="left:{x:.1f}px;top:{y:.1f}px;'
                f'width:{w:.1f}px;height:{KEY_H}px">{label}</div>')

    keys_html = "\n".join("  " + key_html(n, *KEYS[n]) for n in KEYS)
    BALLOON_W, BALLOON_H = 112, 158
    BPATH = ("M20,0 H92 A20,20 0 0 1 112,20 V70 C112,92 96,100 96,118 V146 A12,12 0 0 1 84,158 H28 A12,12 0 0 1 16,146 "
             "V118 C16,100 0,92 0,70 V20 A20,20 0 0 1 20,0 Z")

    def pv_id(ch):
        return f"ID-pv-{ch}" if ch.islower() else f"ID-pv-U{ch}"

    used = sorted({e["ch"] for e in live if e["ch"].isalpha() and e["ch"].isascii()} |
                  {e["ch"] for e in live if e["ch"] in ",."})
    balloons = []
    for ch in used:
        kx, ky, kw, _ = KEYS[key_of(ch)]
        pid = pv_id(ch) if ch.isalpha() else {",": "ID-pv-comma", ".": "ID-pv-dot"}[ch]
        balloons.append(f'  <div id="{pid}" class="ID-pv" data-layout-allow-overlap style="left:{kx + kw / 2 - BALLOON_W / 2:.1f}px;'
                        f'top:{ky + KEY_H - BALLOON_H:.1f}px"><svg width="{BALLOON_W}" height="{BALLOON_H}" viewBox="0 0 '
                        f'{BALLOON_W} {BALLOON_H}"><path class="ID-pvp" d="{BPATH}"/></svg><b data-layout-allow-overlap>'
                        f'{esc(ch)}</b></div>')
    slot_w = (KW - 2 * KEY_GX) / 3
    slots = "\n".join(f'  <div id="ID-slot{i}" class="ID-slot" data-layout-allow-overlap style="left:{KX + i * (slot_w + KEY_GX):.1f}px;'
                      f'top:{BAR_Y}px;width:{slot_w:.1f}px;height:{BAR_H}px"><span id="ID-s{i}" data-layout-allow-overlap></span></div>'
                      for i in range(3))
    pick_slot = [norm(s) for s in SUGGEST].index(norm(PICK))
    pick_cx = KX + pick_slot * (slot_w + KEY_GX) + slot_w / 2
    pick_cy = BAR_Y + BAR_H / 2
    send_x, send_y = KX + KW - SEND - 10, FIELD_BOTTOM - SEND - 10
    pick_x = tlen(body[pick_line] + " ") if body[pick_line] else 0
    pick_w = tlen(PICK)
    html = f"""<!-- predict-keys (top). Written by gen.py (rerun it, don't edit this file): a phone keyboard with predictive text, no
     tray, floating on the footage. Generic, no real keyboard copied; colours and type are the pack's tokens. #ID-fit
     scales the whole keyboard about its bottom centre so the field clears the speaker's chin. -->
<div id="ID-fit"><div id="ID-all">
  <div id="ID-fieldw"><div id="ID-field" style="left:{KX}px;top:{field_top}px;width:{KW}px;height:{FIELD_BOTTOM - field_top}px"></div></div>
  <div id="ID-l0" class="ID-ln" data-layout-allow-overlap style="left:{TEXT_X}px;top:{BOT_LINE_Y}px">{esc(body[0])}</div>
  <div id="ID-l1" class="ID-ln" data-layout-allow-overlap style="left:{TEXT_X}px;top:{BOT_LINE_Y}px">{esc(body[1])}</div>
  <div id="ID-caret" style="left:{TEXT_X}px;top:{BOT_LINE_Y + round(5 * px / 46)}px;height:{round(44 * px / 46)}px"></div>
  <div id="ID-send" style="left:{send_x}px;top:{send_y}px"><svg width="{SEND}" height="{SEND}" viewBox="0 0 62 62"><circle id="ID-send-c" cx="31" cy="31" r="31"/><path id="ID-send-a" d="M31 45 V18 M20 29 L31 18 L42 29" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
{slots}
{keys_html}
{chr(10).join(balloons)}
  <div id="ID-pick" class="ID-ln" data-layout-allow-overlap style="left:{TEXT_X + pick_x:.1f}px;top:{BOT_LINE_Y}px">{esc(PICK)}</div>
  <div id="ID-tap"></div>
</div></div>
<style>
#ID #ID-fit, #ID #ID-all {{ position:absolute; left:0; top:0; width:1080px; height:1920px; }}
#ID #ID-fieldw {{ position:absolute; left:0; top:0; width:1080px; height:1920px;
  filter:drop-shadow(0 14px 22px color-mix(in srgb, var(--c-dark) 26%, transparent)); }}
#ID #ID-field {{ position:absolute; background:var(--c-dark); border-radius:32px;
  box-shadow:inset 0 0 0 1.5px color-mix(in srgb, var(--c-light) 16%, transparent); }}
#ID .ID-ln {{ position:absolute; font-family:var(--font-text); font-weight:var(--text-weight); font-size:{px}px; line-height:{LINEH}px;
  letter-spacing:{LS}em; color:var(--c-light); white-space:pre; }}
#ID #ID-pick {{ color:var(--c-accent); opacity:0; }}
#ID #ID-caret {{ position:absolute; width:4px; border-radius:2px; background:var(--c-accent); }}
#ID #ID-send {{ position:absolute; width:{SEND}px; height:{SEND}px; transform-origin:50% 50%; }}
#ID #ID-send-c {{ fill:var(--c-light); }}
#ID #ID-send-a {{ fill:none; stroke:var(--c-dark); }}
#ID .ID-slot {{ position:absolute; background:color-mix(in srgb, var(--c-light) 90%, var(--c-ink)); border-radius:14px; display:flex;
  align-items:center; justify-content:center; font-family:var(--font-text); font-weight:500; font-size:37px; line-height:1;
  letter-spacing:-.01em; color:var(--c-ink); white-space:nowrap;
  box-shadow:0 2px 0 color-mix(in srgb, var(--c-ink) 34%, transparent), 0 8px 16px color-mix(in srgb, var(--c-dark) 16%, transparent); }}
#ID .ID-k {{ position:absolute; background:var(--c-light); border-radius:14px; display:flex; align-items:center; justify-content:center;
  font-family:var(--font-text); font-weight:500; font-size:43px; line-height:1; color:var(--c-ink);
  box-shadow:0 2px 0 color-mix(in srgb, var(--c-ink) 42%, transparent), 0 8px 16px color-mix(in srgb, var(--c-dark) 18%, transparent); }}
#ID .ID-f {{ background:var(--c-dark); color:var(--c-light); font-size:31px;
  box-shadow:inset 0 0 0 1.5px color-mix(in srgb, var(--c-light) 14%, transparent), 0 2px 0 color-mix(in srgb, var(--c-dark) 55%, transparent),
  0 8px 16px color-mix(in srgb, var(--c-dark) 18%, transparent); }}
#ID .ID-s {{ font-size:31px; }}
#ID .ID-ico {{ fill:none; stroke:var(--c-light); }}
#ID .ID-pv {{ position:absolute; width:{BALLOON_W}px; height:{BALLOON_H}px; opacity:0; transform-origin:50% 100%;
  filter:drop-shadow(0 6px 10px color-mix(in srgb, var(--c-dark) 30%, transparent)); }}
#ID .ID-pv svg {{ position:absolute; left:0; top:0; }}
#ID .ID-pvp {{ fill:var(--c-light); }}
#ID .ID-pv b {{ position:absolute; left:0; top:6px; width:{BALLOON_W}px; text-align:center; font-family:var(--font-text); font-weight:500;
  font-size:66px; line-height:76px; color:var(--c-ink); }}
#ID #ID-tap {{ position:absolute; left:{pick_cx - 46:.1f}px; top:{pick_cy - 46:.1f}px; width:92px; height:92px; border-radius:50%;
  background:color-mix(in srgb, var(--c-ink) 26%, transparent); box-shadow:0 0 0 2px color-mix(in srgb, var(--c-light) 55%, transparent); opacity:0; }}
</style>
"""

    # ---- timeline: frames count from the window's first frame (T(f)), so the effect moves with its window
    js = []
    add = js.append
    rel = lambda f: f - start_f                                             # noqa: E731
    add(f"// {fid}: written by gen.py (rerun it, don't edit this file). Every press is a frame-exact tl.set; nothing tweened off the timeline.")
    add(f"// LINE '{LINE}', PICK '{PICK}': gen.py found their times in words.json and wrote them as frames after the window's first frame.")
    add(f"var FPS = 30, F0 = {start_f};                    // the window's first frame (edit.py at {A:.4f}): rerun gen.py when it moves")
    add("function T(f) { return q((F0 + f) / FPS); }")
    add("function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }")
    add("function rgb(c) {                                   // '#rgb', '#rrggbb' or 'rgb(a)(...)' -> [r, g, b]")
    add("  c = String(c).trim();")
    add("  if (c.charAt(0) === '#') { var h = c.slice(1); if (h.length === 3) h = h.replace(/./g, '$&$&');")
    add("    return [0, 2, 4].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }")
    add("  var m = c.match(/[\\d.]+/g) || [0, 0, 0]; return [+m[0], +m[1], +m[2]];")
    add("}")
    add("function mix(a, b, t) { var x = rgb(a), y = rgb(b); return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(x[i] + (y[i] - x[i]) * t); }).join(',') + ')'; }")
    add("var C = { light: tok('--c-light'), dark: tok('--c-dark'), ink: tok('--c-ink'), accent: tok('--c-accent') };")
    add("var KEY = mix(C.light, C.ink, 0), KEY_DOWN = mix(C.light, C.ink, 0.17), FN = mix(C.dark, C.light, 0), FN_DOWN = mix(C.dark, C.light, 0.16);")
    add("var SLOT = mix(C.light, C.ink, 0.10), SLOT_DOWN = mix(C.dark, C.light, 0);")
    wrapped = wrap_t is not None and any(e["line"] == 1 for e in pre)    # the second row started before the window
    add(f"gsap.set('#ID-fit', {{ scale: {fit:.4f}, transformOrigin: '540px {BOTTOM}px' }});")
    add(f"gsap.set('#ID-field', {{ clipPath: 'inset({LINEH if len(lines) > 1 and not wrapped else 0}px 0px 0px 0px round 32px)' }});")
    if wrapped:
        add(f"gsap.set('#ID-l0', {{ y: {TOP_LINE_Y - BOT_LINE_Y} }});")
    add(f"tl.fromTo('#ID-all', {{ y: {OFF} }}, {{ y: 0, duration: {RISE}, ease: 'expo.out', immediateRender: false }}, T(0));")
    add(f"gsap.set('#ID-all', {{ y: {OFF} }});")
    df = frame(drop_at)
    add(f"tl.to('#ID-all', {{ y: {OFF}, duration: {(frame(B) - 1 - df) / FPS:.3f}, ease: 'power3.in' }}, T({rel(df)}));")   # off the frame one frame before the window ends
    w0, w1 = tlen(body[0]), tlen(body[1])
    for ln, w in ((0, w0), (1, w1)):              # what each row shows as the keyboard rises
        on_row = [e for e in pre if e["line"] == ln]
        x = on_row[-1]["x"] if on_row else 0
        right = f"{max(0, w - x + 2):.1f}px" if on_row else "100%"
        add(f"gsap.set('#ID-l{ln}', {{ clipPath: 'inset(-14px {right} -14px -14px)' }});")
    base_x = pre[-1]["x"] if pre else 0
    add(f"gsap.set('#ID-caret', {{ x: {base_x:.1f} }});")
    sfx = [(round(A + 0.05, 3), "whoosh-soft", -17, "the keyboard rises")]
    for n, e in enumerate(live):
        fr, ch = e["f"], e["ch"]
        name = key_of(ch)
        kid = {" ": "sp", ",": "comma", ".": "dot", "123": "n123"}.get(name, name)
        down, up = ("FN_DOWN", "FN") if name == "123" else ("KEY_DOWN", "KEY")
        add(f"tl.set('#ID-k-{kid}', {{ backgroundColor: {down}, y: 2 }}, T({rel(fr)})); tl.set('#ID-k-{kid}', {{ backgroundColor: {up}, y: 0 }}, T({rel(fr + 2)}));")
        if ch in used:
            pid = pv_id(ch) if ch.isalpha() else {",": "ID-pv-comma", ".": "ID-pv-dot"}[ch]
            nxt_f = live[n + 1]["f"] if n + 1 < len(live) else fr + 9
            hold = 3 if nxt_f - fr >= 3 else 2
            add(f"tl.set('#{pid}', {{ opacity: 1, scale: .86 }}, T({rel(fr)})); tl.set('#{pid}', {{ scale: 1 }}, T({rel(fr + 1)})); "
                f"tl.set('#{pid}', {{ opacity: 0 }}, T({rel(fr + hold)}));")
        if ch.isupper():
            add(f"tl.set('#ID-k-shift', {{ backgroundColor: FN_DOWN }}, T({rel(fr - 1)})); tl.set('#ID-k-shift', {{ backgroundColor: FN }}, T({rel(fr + 1)}));")
        ln = e["line"]
        w = w0 if ln == 0 else w1
        add(f"tl.set('#ID-l{ln}', {{ clipPath: 'inset(-14px {max(0, w - e['x'] + 2):.1f}px -14px -14px)' }}, T({rel(fr)}));")
        add(f"tl.set('#ID-caret', {{ x: {e['x']:.1f} }}, T({rel(fr)}));")
        db = (DB_SPACE if ch == " " else DB_KEY) + (rnd(n * 7 + 3) - .5) * 3
        sfx.append((round(max(A, e["t"]), 3), "key" if ch == " " else "tick", round(db, 1), None))   # the real, uneven thumb time
    grow = None
    if wrap_t is not None and not wrapped:        # the field grows up one line as the second line starts
        grow = next(e["f"] for e in live if e["line"] == 1)
    elif len(lines) > 1 and not body[1]:          # only the picked word goes on the second line: it grows as it lands
        grow = pf
    if grow is not None:
        wf = grow
        add(f"tl.fromTo('#ID-field', {{ clipPath: 'inset({LINEH}px 0px 0px 0px round 32px)' }}, {{ clipPath: 'inset(0px 0px 0px 0px round 32px)', "
            f"duration: 0.12, ease: 'power3.out', immediateRender: false }}, T({rel(wf)}));")
        add(f"tl.to('#ID-l0', {{ y: {TOP_LINE_Y - BOT_LINE_Y}, duration: 0.12, ease: 'power3.out' }}, T({rel(wf)}));")
    # the bar: what it shows as the keyboard rises, then an update on every keystroke, as a real one does
    if pre:
        e = pre[-1]
        w_, _, alts_, nxt_ = TYPED[e["word"]]
        first = nxt_ if e["ch"] == " " else (e["prefix"], w_ if e["prefix"] != w_ else alts_[0], alts_[1])
    else:
        first = tuple(c[:1].upper() + c[1:] for c in (common + ["I", "The", "So"])[:3])
    for slot, text in enumerate(first):
        add(f"gsap.set('#ID-s{slot}', {{ textContent: {json.dumps(text)} }});")
    for e in live:
        w, _, alts, nxt = TYPED[e["word"]]
        if e["ch"] == " ":
            vals = nxt
        else:
            p = e["prefix"]
            vals = (p, w if p != w else alts[0], alts[1])
        for slot, v in enumerate(vals):
            add(f"tl.set('#ID-s{slot}', {{ textContent: {json.dumps(v)} }}, T({rel(e['f'])}));")
    # the payoff: three suggestions land, the caret waits
    last_space = live[-1]["f"]
    for slot in range(3):
        add(f"tl.fromTo('#ID-s{slot}', {{ scale: .82, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.12, ease: 'back.out(2)', "
            f"immediateRender: false }}, T({rel(last_space + slot)}));")
    if last_space + 5 < pf - 1:                   # one blink when there is room: it is waiting for the word
        for fr, on in [(last_space + 3, 1), (last_space + 5, 0), (pf - 1, 1)]:
            add(f"tl.set('#ID-caret', {{ opacity: {on} }}, T({rel(fr)}));")
    # the tap lands on the word
    add(f"tl.fromTo('#ID-tap', {{ opacity: 0, scale: 1.7 }}, {{ opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', "
        f"immediateRender: false }}, T({rel(pf - 3)}));")
    add(f"tl.to('#ID-tap', {{ scale: .84, duration: 0.05, ease: 'power2.out' }}, T({rel(pf)}));")
    add(f"tl.to('#ID-tap', {{ scale: 1.2, opacity: 0, duration: 0.12, ease: 'power2.out' }}, T({rel(pf + 2)}));")
    add(f"tl.set('#ID-slot{pick_slot}', {{ backgroundColor: SLOT_DOWN, y: 2 }}, T({rel(pf)})); "
        f"tl.set('#ID-slot{pick_slot}', {{ backgroundColor: SLOT, y: 0 }}, T({rel(pf + 5)}));")
    add(f"tl.set('#ID-s{pick_slot}', {{ textContent: '' }}, T({rel(pf)}));")
    for slot, v in enumerate(after):
        add(f"tl.set('#ID-s{slot}', {{ textContent: {json.dumps(v)} }}, T({rel(pf + 6)}));")
    sfx += [(round(pick_at, 3), "click", -14, "the tap on the word"), (round(pick_at + 0.1, 3), "pop", -17, "it lands in the sentence")]
    # the word flies from its slot into the sentence
    target_x, target_y = TEXT_X + pick_x, BOT_LINE_Y
    dx = pick_cx - (target_x + pick_w / 2)
    dy = pick_cy - (target_y + LINEH / 2)
    add("gsap.set('#ID-pick', { transformOrigin: '50% 50%' });")
    add(f"tl.set('#ID-pick', {{ opacity: 1 }}, T({rel(pf)}));")
    add(f"tl.fromTo('#ID-pick', {{ x: {dx:.1f}, y: {dy:.1f} }}, {{ x: 0, y: 0, duration: 0.17, ease: 'power3.out', immediateRender: false }}, T({rel(pf)}));")
    add(f"tl.fromTo('#ID-pick', {{ scale: .8 }}, {{ scale: 1, duration: 0.22, ease: 'back.out(2.4)', immediateRender: false }}, T({rel(pf)}));")
    add(f"tl.set('#ID-caret', {{ opacity: 0 }}, T({rel(pf)}));")             # the word flies in, then the caret sits after it
    add(f"tl.set('#ID-caret', {{ x: {pick_x + pick_w:.1f}, opacity: 1 }}, T({rel(pf + 5)}));")
    if pf + 14 < sf:                                                      # it keeps blinking while the word is said
        add(f"tl.set('#ID-caret', {{ opacity: 0 }}, T({rel(pf + 9)})); tl.set('#ID-caret', {{ opacity: 1 }}, T({rel(pf + 14)}));")
    # send: a second tap on the arrow when there is time for it, else the arrow just presses
    if sf - 4 > pf + 4:
        add(f"tl.set('#ID-tap', {{ x: {send_x + SEND / 2 - pick_cx:.1f}, y: {send_y + SEND / 2 - pick_cy:.1f} }}, T({rel(sf - 4)}));")
        add(f"tl.fromTo('#ID-tap', {{ opacity: 0, scale: 1.5 }}, {{ opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', "
            f"immediateRender: false }}, T({rel(sf - 3)}));")
        add(f"tl.to('#ID-tap', {{ scale: .84, opacity: 0, duration: 0.12, ease: 'power2.out' }}, T({rel(sf)}));")
    add(f"tl.fromTo('#ID-send', {{ scale: .82 }}, {{ scale: 1, duration: 0.18, ease: 'back.out(2.2)', immediateRender: false }}, T({rel(sf)}));")
    add(f"tl.set('#ID-send-c', {{ fill: C.accent }}, T({rel(sf)}));")
    add(f"tl.set('#ID-caret', {{ opacity: 0 }}, T({rel(sf)}));")
    sfx += [(round(send_at, 3), "click", -14, "send"), (round(drop_at + 0.08, 3), "whoosh", -15, "the keyboard drops")]

    def token(t):                             # ID in the templates above is the effect's id, filled in by the build
        return re.sub(r"#ID\b", "#{{ID}}", re.sub(r"(?<![A-Za-z0-9])ID-", "{{ID}}-", t))

    with open(os.path.join(d, "fx.html"), "w", encoding="utf-8") as fh:
        fh.write(token(html))
    with open(os.path.join(d, "fx.js"), "w", encoding="utf-8") as fh:
        fh.write(token("\n".join(js) + "\n"))
    print(f"wrote {d}/fx.html + fx.js\nSFX for edit.SOUND['sfx'] (the hit times; the keys keep the real thumb times):")
    for t, name, db, what in sfx:
        print(f"    ({t}, \"{name}\", {db}),{'   # ' + what if what else ''}")


if __name__ == "__main__":
    main()
