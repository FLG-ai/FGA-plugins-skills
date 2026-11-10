#!/usr/bin/env python3
"""press-front: the speaker prints. A broadsheet front page fills the frame from the first frame (masthead, dateline,
a full-measure headline, body columns of the video's real words), and the speaker's live, lip-synced footage is the
photo: a true one-ink 45 degree round-dot halftone, redone every frame on a static screen, so only the dots over them
breathe. The deck prints word by word as it is spoken (each word lands fat and wet and draws in over three frames).
Press slam on the first frames. Newsprint and ink are the real object's colours; the type is the creator's pack.

Run: PY fx/<id>/gen.py <project> [<id>] [--stills t1 t2 ...]
  reads   <project>/edit.py (the FX entry <id>), words.json, timeline.json, public/clean.mp4, public/subject.webm,
          work/tracks/track.json (the picture-desk retouch and the crop; optional), room_<FRAME>.npy (optional: the
          room stays dead still behind them), the project's style pack (fonts and creator fields)
  writes  <project>/fx/<id>/<id>.mp4 (frame n is the frame at A + n), fx.html, fx.js;
          <project>/work/fx/<id>/last.png (the final frame as a still, for an effect that tears or turns the page)
<id> defaults to this folder's name. Rerun it whenever the window, the cut or the words change.
"""
import argparse
import datetime
import html as Hm
import json
import os
import re
import sys

sys.dont_write_bytecode = True       # no __pycache__ in an fx folder
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FPS, W, H = 30, 1080, 1920

# ---- the table: what the page says. Content is set per video (an agent writes it); identity comes from the style pack.
PAPER_NAME = "The Daily Reel"        # the masthead
HEADLINE = ""                        # full measure, complete on the first frame (the thumbnail); "" = the first sentence spoken in the window
DECK = []                            # [(text, cue word)], each prints on its spoken word; [] = the words after the headline, a few at a time
KICKER = "Top Story"                 # over the left column
BYLINE = None                        # None = "BY " + the creator's name from the pack, else their handle (left out with neither)
DATELINE = None                      # None = today's date in caps
EDITION = "PRINTED EVERY FRAME"      # right of the dateline
CAPTION = None                       # under the photo; None = "<name or handle>, on camera." ("On camera." with neither)
EARS = (("Final Edition", None), ("Late News", "More in the video"))   # (title, line); None = how long the page is on screen
PULL = None                          # the pull quote; None = a sentence they say in the video
CORRECTION = "This page is reprinted every frame. Earlier editions may differ."
AD = ("Your Ad Here", "PLACEHOLDER", "Set AD in gen.py: the offer, who it is by, the ask.")   # (title, by, line): the creator's offer
FOLLOW = None                        # None = "More like this: follow <handle>." from the pack (left out without a handle or site)
WEATHER = None                       # None = read off the room: the side the light comes from
COLOPHON = None                      # None = "Written and spoken by <name or handle>. Set, cut and printed one frame at a time, in one ink."
CONTINUED = "Continued in the comments"
HEADS = []                           # crossheads: [(the words a paragraph starts with, the crosshead)]
INDEX = None                         # "In This Video": [(name, phrase spoken)]; None = up to 8 sentence openings, with their times
# the picture
PHOTO = (243, 594, 594, 876)         # x, y, w, h of the slot on the page
CROP = None                          # x, y, w, h of the footage in the slot (px); None = head and shoulders, from the face track
CELL = 5.5 * 2 ** .5                 # 7.78 px: dot centres stay on the half-pixel grid
SHARP = .35
EYE_LIFT, EYE_CONTRAST, MOUTH_CONTRAST = .06, 1.0, 1.0      # the picture desk: open the eyes, lift the mouth so it reads through the dots
TONE = [(0, .05), (.1, .12), (.25, .3), (.42, .58), (.6, .85), (.8, .98), (1, 1)]     # the speaker's tones -> paper (0 = solid ink)
TONE_ROOM = [(0, .15), (.1, .17), (.25, .36), (.5, .66), (1, .8)]                       # the room, static: only the speaker breathes
SLAM = [1.03, 1.012, 1.003, 1.0]     # page scale on the effect's first frames (the first is already complete: the thumbnail)
SHUDDER = {3: 2, 4: -1}              # the press settling: page y offset (px) on these frames of the effect
PAPER = (240, 232, 214)              # newsprint, as it should come out of the render (a real object's colour, not the pack's)
INK = (22, 20, 19)                   # one black ink
DECK_CHARS = 34                      # a default deck stops before this many characters (one line at full size)


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
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import fxlib  # noqa: E402
import inkscreen as ink  # noqa: E402
from common import load_edit  # noqa: E402


# ---- the project
def window(project, fid):
    """the edit, the timeline and the effect's window (its edit.FX entry; "end" resolved like the build does)"""
    F = fxlib.entry(project, fid)
    return load_edit(project), json.load(open(os.path.join(project, "timeline.json"))), float(F["at"]), float(F["end"])


def norm(w):
    return re.sub(r"[^a-z0-9%$']", "", str(w).lower())


def frame_at(TL, E, t):
    shots = [(s["t"], s["frame"]) for s in TL.get("shots", [])] or list(E.SHOTS)
    return [f for a, f in shots if a <= t + 1e-3][-1]


def room_npy(project, frame, empty=False):
    """the room behind the speaker on this crop at live levels (plate_finish.py: work/c/room_<FRAME>.npy), or None"""
    p = os.path.join(project, "work", "c", f"room_{'empty_' if empty else ''}{frame}.npy")
    return fxlib.room(project, frame, empty=empty).astype(np.float32) if os.path.exists(p) else None


def tracks_or_none(project):
    """work/tracks/track.json's frames (track.py), or None: everything that uses it has a fallback"""
    p = os.path.join(project, "work", "tracks", "track.json")
    return fxlib.tracks(project)["frames"] if os.path.exists(p) else None


def sentences(ws):
    """[(start time, [words])] split on . ? ! and on pauses over 0.7 s"""
    out, cur, t0 = [], [], None
    for i, w in enumerate(ws):
        if not cur:
            t0 = w["start"]
        cur.append(w["text"])
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        if w["text"][-1:] in ".?!" or nxt is None or nxt["start"] - w["end"] > 0.7:
            out.append((t0, cur))
            cur = []
    return out


def mmss(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def opening(words):
    """an index entry: the first two words of a sentence, or just the first when a comma ends it (a list)"""
    out = []
    for x in words[:2]:
        out.append(x)
        if x[-1:] in ",.?!:;":
            break
    return " ".join(out).strip(",.?!:;")


# ---- what the page says, from the table, the pack and words.json
def person(C):
    """the creator as a person on the page: the pack's name, else their handle, else nobody. "reel-kit" (the default
    pack's placeholder) is not a person"""
    name = str(C.get("name") or "").strip()
    if name.lower().replace(" ", "-") in ("reel-kit", "reelkit"):
        name = ""
    return name or str(C.get("handle") or "").strip()


def content(project, S, ws, A, B, room):
    C = S["creator"]
    name, handle, site = person(C), C.get("handle", ""), C.get("site", "")
    defaults = []
    inwin = [w for w in ws if A - 0.001 <= w["start"] < B]
    head = HEADLINE
    rest = inwin
    if head:                                                             # a headline that is what they say first: the deck runs on from it
        hw = [norm(x) for x in head.split() if norm(x)]
        if [norm(w["text"]) for w in inwin[:len(hw)]] == hw:
            rest = inwin[len(hw):]
    else:
        defaults.append("HEADLINE")
        sent = sentences(inwin)
        first = sent[0][1] if sent else []
        if len(first) > 7:                                               # a long first sentence: its first clause, else its opening words
            cut = next((i + 1 for i, x in enumerate(first) if x[-1:] in ",;:" and 2 <= i + 1 <= 7), 5)
            first = first[:cut]
        head = " ".join(first).upper().rstrip(",;:") if first else PAPER_NAME.upper()
        rest = inwin[len(first):]
    deck = []
    if DECK:
        after = A
        for text, cue in DECK:
            t = next((w["start"] for w in ws if w["start"] >= after - 0.001 and norm(w["text"]) == norm(cue) and w["start"] < B), None)
            if t is None:
                print(f"WARNING: deck cue {cue!r} is not spoken in the window after {after:.2f}: it prints on the frame before")
                t = after
            deck.append((text, t))
            after = t + 0.01
    elif rest:
        defaults.append("DECK")
        chunk, n = [], 0
        for w in rest:
            if n + len(w["text"]) + 1 > DECK_CHARS:
                break
            chunk.append(w)
            n += len(w["text"]) + 1
        for k in range(0, len(chunk), 2):                        # two spoken words per print
            deck.append((" ".join(w["text"] for w in chunk[k:k + 2]), chunk[k]["start"]))
    dur = B - A
    ears = [(t, line if line is not None else f"On sale for {dur:.1f} seconds") for t, line in EARS]
    allsent = sentences(ws)
    pull = PULL
    if pull is None:
        defaults.append("PULL")
        pick = [s for s in allsent if 6 <= len(s[1]) <= 16 and s[0] >= B] or [s for s in allsent if 6 <= len(s[1]) <= 16] or allsent
        pull = " ".join(pick[0][1]) if pick else ""
    index = INDEX
    if index is None:
        rows = [(opening(s[1]), s[0]) for s in allsent if len(s[1]) >= 3]
        step = max(1, len(rows) // 8 + (1 if len(rows) % 8 else 0))
        index = [(r[0][:1].upper() + r[0][1:], r[1]) for r in rows[::step]][:8]
    else:
        idx = []
        for label, phrase in index:
            toks = [norm(x) for x in phrase.split()]
            clean = [norm(w["text"]) for w in ws]
            t = next((ws[i]["start"] for i in range(len(clean) - len(toks) + 1) if clean[i:i + len(toks)] == toks), None)
            if t is None:
                sys.exit(f"INDEX phrase not spoken: {phrase!r}")
            idx.append((label, t))
        index = idx
    if WEATHER is None and room is not None:
        L = room.mean(axis=2)
        side = "left" if L[:, :W // 3].mean() > L[:, -W // 3:].mean() else "right"
        weather = f"Steady light from the {side}."
    else:
        weather = WEATHER or "Steady, one light."
    follow = FOLLOW if FOLLOW is not None else (f"More like this: follow {handle or site}." if (handle or site) else "")
    colophon = COLOPHON or (f"Written and spoken by {name}. " if name else "Spoken on camera. ") + "Set, cut and printed one frame at a time, in one ink."
    caption = CAPTION or (f"{name}, on camera." if name else "On camera.")
    byline = BYLINE if BYLINE is not None else (f"BY {name.upper()}" if name else "")
    today = datetime.date.today()
    date = DATELINE or f"{today.strftime('%A, %B').upper()} {today.day}, {today.year}"
    if AD[1] == "PLACEHOLDER":
        defaults.append("AD (placeholder)")
    if defaults:
        print("press-front: defaults in use for " + ", ".join(defaults) + ": set them at the top of gen.py for this video")
    used = {norm(" ".join(x.split())) for x in (head, pull)}
    quotes = [" ".join(s_[1]) for s_ in allsent if 4 <= len(s_[1]) <= 14 and norm(" ".join(s_[1])) not in used]
    return dict(head=head, deck=deck, ears=ears, pull=pull, index=index, weather=weather, follow=follow, colophon=colophon,
                caption=caption, byline=byline, date=date, site=(site or handle).upper(), quotes=quotes)


def body(ws):
    """the video's words as paragraphs of three sentences, flowing from the left column into the right one the way a
    story does: the break falls at the sentence end nearest 46% of the text (else between two words). Crossheads: HEADS"""
    sent = sentences(ws)
    paras = [" ".join(" ".join(s[1]) for s in sent[k:k + 3]) for k in range(0, len(sent), 3)]
    total = sum(len(p) + 1 for p in paras)
    want, n, cut = 0.46 * total, 0, None
    for i, p in enumerate(paras):                       # where the flow crosses `want`: a sentence end near it, else a word gap
        if n + len(p) + 1 >= want:
            ends = [m.end() for m in re.finditer(r"[.?!]\s", p + " ")]
            gaps = [m.start() for m in re.finditer(r" ", p)]
            at = want - n
            near = [e for e in ends if abs(e - at) < 0.15 * total]
            k = min(near, key=lambda e: abs(e - at)) if near else (min(gaps, key=lambda g: abs(g - at)) if gaps else len(p))
            cut = (i, k)
            break
        n += len(p) + 1
    left, right = [], []
    for i, p in enumerate(paras):
        parts = [(p, left if cut is None or i < cut[0] else right)]
        if cut and i == cut[0]:
            parts = [(p[:cut[1]].strip(), left), (p[cut[1]:].strip(), right)]
        for text, out in parts:
            if not text:
                continue
            for key, hd in HEADS:
                if text.startswith(key):
                    out.append(f'<h4 class="dsp">{Hm.escape(hd)}</h4>')
            cls = ' class="run"' if out is right and not right and cut and i == cut[0] else ""
            out.append(f"<p{cls}>{Hm.escape(text)}</p>")
    return "".join(left), "".join(right)


def brand_css(project, S, work):
    """the pack's fonts and tokens for the page: the project's brand.css (its fonts/ beside it)"""
    for p in (os.path.join(project, "style", "brand.css"), os.path.join(project, "public", "brand.css")):
        if os.path.exists(p):
            return p
    import style as ST
    return ST.write(ST.load(os.path.join(project, "style", "style.json")), work)


def page_html(project, S, ws, c, work):
    left, right = body(ws)
    e = Hm.escape
    idx = "".join(f'<div class="row"><span>{e(n)}</span><i></i><span class="t">{mmss(t)}</span></div>' for n, t in c["index"])
    deck = " ".join(f'<span class="w">{e(t)}</span>' for t, _ in c["deck"])
    px, py, pw, ph = PHOTO                      # no deck (a short window): the headline sits centred in the band
    gut = 16
    col = (1000 - 4 * gut) / 5
    lcol = (40, col)
    sy = py + ph + 58
    rcol = (40 + 4 * (col + gut), col)
    css = ink._url(brand_css(project, S, work))
    by = f'<div class="by">{e(c["byline"])}</div>' if c["byline"] else ""
    ad = f'<div class="ad"><div class="a">{e(AD[0])}</div><div class="b">{e(AD[1])}</div><div class="c">{e(AD[2])}</div></div>'
    follow = (f'<h5 class="dsp">Follow</h5><p>{e(c["follow"])}</p><h5 class="sub dsp">Colophon</h5>' if c["follow"]
              else '<h5 class="dsp">Colophon</h5>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="{css}"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ width:1080px; height:1920px; background:#fff; color:#000; overflow:hidden; font-kerning:normal; text-rendering:geometricPrecision; -webkit-font-smoothing:antialiased; }}
.abs {{ position:absolute; }}
.dsp {{ font-family:var(--font-display); font-weight:var(--display-weight); font-style:var(--display-style); }}
.rule {{ position:absolute; left:40px; width:1000px; background:#000; height:1px; }}
.vr {{ position:absolute; width:1px; background:#000; }}
#mast {{ left:214px; width:652px; top:124px; height:132px; text-align:center; font-size:126px; line-height:132px; white-space:nowrap; letter-spacing:-.005em; }}
.ear {{ top:156px; width:158px; height:88px; border:1px solid #000; text-align:center; font:400 15.5px/19px var(--font-text); letter-spacing:.03em; padding:9px 6px 0; overflow:hidden; }}
.ear b {{ display:block; font-size:22px; line-height:25px; letter-spacing:0; }}
#date {{ left:40px; width:1000px; top:266px; height:34px; display:flex; justify-content:space-between; align-items:center; font:500 16px/1 var(--font-mono); letter-spacing:.12em; white-space:nowrap; }}
#head {{ left:40px; width:1000px; top:{307 if c["deck"] else 358}px; height:168px; text-align:center; font-size:178px; line-height:168px; white-space:nowrap; letter-spacing:0; }}
#deck {{ left:40px; width:1000px; top:476px; text-align:center; font-family:var(--font-display); font-weight:400; font-size:80px; line-height:1.1; white-space:nowrap; }}
.col {{ top:{py}px; height:{ph + 40}px; font:400 21px/1.15 var(--font-text); text-align:justify; hyphens:auto; overflow:hidden; }}
.col p {{ text-indent:1em; }} .col p.run {{ text-indent:0; }}
.col h4 {{ font-size:29px; line-height:1; text-align:center; hyphens:none; margin:11px 0 7px; padding-top:9px; border-top:1px solid #000; }}
.col h4:first-child {{ margin-top:0; }}
.col h4.kick {{ border-top:0; padding-top:0; font-size:31px; margin-bottom:7px; }}
.cont {{ font:italic 400 19px/22px var(--font-text); text-align:center; hyphens:none; margin-top:9px; padding-top:7px; border-top:1px solid #000; }}
.pq {{ font-size:27px; line-height:1.12; text-align:center; hyphens:none; margin:12px 0 10px; padding:10px 0; border-top:2px solid #000; border-bottom:1px solid #000; }}
.by {{ text-align:center; font:500 14.5px/18px var(--font-text); letter-spacing:.12em; padding:0 0 7px; hyphens:none; }}
#cap {{ left:{px}px; width:{pw}px; top:{py + ph + 6}px; text-align:center; font:italic 400 23px/28px var(--font-text); white-space:nowrap; overflow:hidden; }}
#slot {{ left:{px}px; top:{py}px; width:{pw}px; height:{ph}px; border:1px solid #000; }}
.strip {{ top:{sy}px; width:{col}px; height:{1896 - sy}px; font:400 19px/22px var(--font-text); text-align:justify; hyphens:auto; overflow:hidden; }}
.strip h5 {{ font-size:25px; line-height:1; text-align:center; hyphens:none; padding-bottom:5px; margin-bottom:6px; border-bottom:1px solid #000; }}
.strip h5.sub {{ margin-top:13px; padding-top:10px; border-top:1px solid #000; border-bottom:0; padding-bottom:0; margin-bottom:4px; }}
.pull {{ font-size:44px; line-height:1.1; text-align:center; hyphens:none; padding:2px 0 0; }}
.row {{ display:flex; font:400 17.5px/27px var(--font-text); hyphens:none; white-space:nowrap; }} .row i {{ flex:1 1 0; min-width:12px; border-bottom:1px dotted #000; margin:0 4px 8px; }}
.row span:first-child {{ flex:0 1 auto; min-width:0; overflow:hidden; }} .row .t {{ flex:none; font-family:var(--font-mono); }}
.ad {{ border:1px solid #000; outline:3px double #000; outline-offset:2px; padding:15px 7px 14px; text-align:center; hyphens:none; margin:6px 5px 0; }}
.ad .a {{ font-size:23px; line-height:1.05; }} .ad .b {{ font:600 14px/18px var(--font-mono); letter-spacing:.13em; margin:8px 0; }} .ad .c {{ font:italic 400 18px/21px var(--font-text); }}
</style></head><body>
<div id="furn">
  <div class="abs ear" style="left:40px;"><b class="dsp">{e(c["ears"][0][0])}</b>{e(c["ears"][0][1])}</div>
  <div class="abs ear" style="right:40px;"><b class="dsp">{e(c["ears"][1][0])}</b>{e(c["ears"][1][1])}</div>
  <div class="abs dsp" id="mast">{e(PAPER_NAME)}</div>
  <div class="rule" style="top:262px;"></div><div class="rule" style="top:265px;"></div>
  <div class="abs" id="date"><span>{e(c["site"])}</span><span>{e(c["date"])}</span><span>{e(EDITION)}</span></div>
  <div class="rule" style="top:300px;"></div><div class="rule" style="top:303px;"></div>
  <div class="abs dsp" id="head">{e(c["head"])}</div>
  <div class="rule" style="top:{py - 14}px;height:2px;"></div>
  <div class="abs col" style="left:{lcol[0]}px;width:{lcol[1]}px;"><h4 class="kick dsp">{e(KICKER)}</h4>{by}{left}</div>
  <div class="abs col" style="left:{rcol[0]}px;width:{rcol[1]}px;">{right}<div class="cont">{e(CONTINUED)}</div></div>
  <div class="vr" style="left:{lcol[0] + lcol[1] + gut / 2 - .5}px;top:{py}px;height:{ph + 40}px;"></div>
  <div class="vr" style="left:{rcol[0] - gut / 2 - .5}px;top:{py}px;height:{ph + 40}px;"></div>
  <div class="abs" id="slot"></div>
  <div class="abs" id="cap">{e(c["caption"])}</div>
  <div class="rule" style="top:{sy - 12}px;height:2px;"></div>
  <div class="abs strip" style="left:40px;"><h5 class="dsp">In This Video</h5>{idx}</div>
  <div class="abs strip" style="left:{40 + col + gut}px;width:{2 * col + gut}px;"><div class="pull dsp">&ldquo;{e(c["pull"])}&rdquo;</div><h5 class="sub dsp">Correction</h5><p>{e(CORRECTION)}</p></div>
  <div class="abs strip" style="left:{40 + 3 * (col + gut)}px;">{ad}<h5 class="sub dsp">Weather</h5><p>{e(c["weather"])}</p></div>
  <div class="abs strip" style="left:{40 + 4 * (col + gut)}px;">{follow}<p>{e(c["colophon"])}</p></div>
  <div class="vr" style="left:{40 + col + gut / 2 - .5}px;top:{sy}px;height:{1896 - sy}px;"></div>
  <div class="vr" style="left:{40 + 3 * col + 2.5 * gut - .5}px;top:{sy}px;height:{1896 - sy}px;"></div>
  <div class="vr" style="left:{40 + 4 * col + 3.5 * gut - .5}px;top:{sy}px;height:{1896 - sy}px;"></div>
</div>
<div class="abs" id="deck">{deck}</div>
<div id="pool" style="display:none">{"".join(f'<div class="pq dsp">&ldquo;{e(q)}&rdquo;</div>' for q in c["quotes"])}</div>
<pre id="rects" style="display:none"></pre>
<script>
var layer = location.hash.slice(1);
if (layer === 'only-furn') document.getElementById('deck').style.visibility = 'hidden';
if (layer === 'only-deck') document.getElementById('furn').style.display = 'none';
function fitW(el, min) {{                       // one line that fits its box: the pack's face sets how big it can be
  var s = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollWidth > el.clientWidth + 1 && s > min) {{ s -= 1; el.style.fontSize = s + 'px'; }}
}}
function fitH(el, min) {{                      // a box that holds its lines: shrink until they all show
  var s = parseFloat(getComputedStyle(el).fontSize);
  while (el.scrollHeight > el.clientHeight + 1 && s > min) {{ s -= 0.5; el.style.fontSize = s + 'px'; }}
}}
function fillH(els, from, to) {{                // body copy set as large as the columns allow: a short video still fills them
  var best = from;
  for (var s = from; s <= to; s += 0.5) {{
    els.forEach(function (el) {{ el.style.fontSize = s + 'px'; }});
    if (els.some(function (el) {{ return el.scrollHeight > el.clientHeight + 1; }})) break;
    best = s;
  }}
  els.forEach(function (el) {{ el.style.fontSize = best + 'px'; }});
}}
document.fonts.ready.then(function () {{
  fitW(document.getElementById('mast'), 40);
  fitW(document.getElementById('head'), 60);
  fitW(document.getElementById('deck'), 36);
  fitW(document.getElementById('cap'), 14);
  document.querySelectorAll('.ear').forEach(function (el) {{ fitH(el, 10); }});
  var cols = [].slice.call(document.querySelectorAll('.col'));
  fillH(cols, 19, 24);
  // a short video leaves the columns short: fill them with lines the speaker says, set as quotes, while they fit
  var pool = [].slice.call(document.querySelectorAll('#pool .pq'));
  function room(col) {{ return col.clientHeight - col.scrollHeight; }}
  function fits(col) {{ return col.scrollHeight <= col.clientHeight + 1; }}
  pool.forEach(function (q) {{                     // each quote into the column with the most room that can take it
    var order = cols.slice().sort(function (a, b) {{
      var ea = a.lastElementChild.getBoundingClientRect().bottom, eb = b.lastElementChild.getBoundingClientRect().bottom;
      return ea - eb;
    }});
    for (var i = 0; i < order.length; i++) {{
      var col = order[i], cont = col.querySelector('.cont');
      col.insertBefore(q, cont);
      if (fits(col)) return;
      col.removeChild(q);
    }}
  }});
  var out = [].map.call(document.querySelectorAll('#deck .w'), function (w) {{ var r = w.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }});
  document.getElementById('rects').textContent = JSON.stringify(out);
}});
</script></body></html>'''


def render_page(project, S, ws, c, work):
    path = os.path.join(work, "page.html")
    open(path, "w", encoding="utf-8").write(page_html(project, S, ws, c, work))
    furn = ink.chrome_shot(path, os.path.join(work, "furn.png"), scale=2, hash="#only-furn")
    deck = ink.chrome_shot(path, os.path.join(work, "deck.png"), scale=2, hash="#only-deck")
    dom = ink.chrome_dom(path, hash="#only-deck")
    m = re.search(r'<pre id="rects"[^>]*>(.*?)</pre>', dom, re.S)
    rects = json.loads(m.group(1)) if m and m.group(1).strip() else []
    if len(rects) != len(c["deck"]):
        sys.exit("the deck's word rectangles did not come back from the page (fonts not loaded?)")
    return furn, deck, rects


def to_mask(bgr):
    return 1 - cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255


def press_ink(mask2, seed=3, gain=.46, rough=.10):
    """type on paper at 2x: the ink spreads a little and the fibres worry its edge, so nothing has a screen font's clean edge"""
    h, w = mask2.shape
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), 1.1)
    n /= n.std()
    m = cv2.GaussianBlur(mask2, (0, 0), .9)
    return np.clip((m + n * rough - gain) / .16 + .5, 0, 1)


def auto_crop(project, A, B, tr):
    """head and shoulders in the slot's shape: as wide as the shoulders (1.69 face widths at least), the top of the head
    (the matte's highest point over the window: hair, a cap) a little under the slot's top edge"""
    px, py, pw, ph = PHOTO
    n0, n1 = fxlib.fr(A), fxlib.fr(B)
    fs = [tr[n]["face"] for n in range(n0, min(n1, len(tr))) if tr[n].get("face")] if tr else []
    ps = [tr[n]["pose"] for n in range(n0, min(n1, len(tr))) if tr[n].get("pose")] if tr else []
    tops = []
    for k, (_, al) in enumerate(fxlib.alpha(project, A, B)):
        if k % 3 == 0:
            rows = np.where((al > 128).sum(axis=1) >= 8)[0]
            if len(rows):
                tops.append(rows[0])
    head_top = float(np.percentile(tops, 10)) if tops else None
    if fs:
        cx, fw = (float(np.median([f[k] for f in fs])) for k in ("cx", "w"))
        head_top = head_top if head_top is not None else float(np.median([f["top"] for f in fs])) - 0.4 * fw
    else:
        al = next(fxlib.alpha(project, A, A + 1 / FPS))[1]
        top = head_top if head_top is not None else 0.25 * H
        band = al[int(top):int(top) + 260] > 128
        xs = np.where(band)[1]
        cx = float(xs.mean()) if len(xs) else W / 2
        fw = float(np.median(band.sum(axis=1))) * 0.95 if band.any() else 0.28 * W
        head_top = top
    span = float(np.median([abs(q["ls"][0] - q["rs"][0]) for q in ps])) if ps else 0.0
    w = min(W, max(1.69 * fw, 1.1 * span))
    h = w * ph / pw
    if h > H:
        h, w = H, H * pw / ph
    x = float(np.clip(cx - w / 2, 0, W - w))
    y = float(np.clip(head_top - 0.07 * h, 0, H - h))
    return (round(x), round(y), round(w), round(h))


class Page:
    def __init__(self, project, fid, A, B, frame, work):
        self.project, self.A = project, A
        S = fxlib.pack(project)
        ws = json.load(open(os.path.join(project, "words.json")))
        self.room_rgb = room_npy(project, frame)
        self.c = content(project, S, ws, A, B, self.room_rgb)
        furn, deck, rects = render_page(project, S, ws, self.c, work)
        h2, w2 = 2 * H, 2 * W
        self.furn2 = press_ink(to_mask(furn))
        self.deck2 = press_ink(to_mask(deck), seed=5)
        self.paper2 = (np.array(PAPER, np.float32)[None, None] * ink.fibre(h2, w2, seed=7, n=h2 * w2 // 300)[..., None]).astype(np.float32)
        self.tooth2 = ink.tooth(h2, w2, seed=11, area=.012, size=.9)
        self.deck_words = []                       # each word of the deck its own mask, printed on its time
        for (text, t), (x, y, w, h) in zip(self.c["deck"], rects):
            pad = 6
            self.deck_words.append((t, (int((x - pad) * 2), int((y - pad) * 2), int((x + w + pad) * 2), int((y + h + pad) * 2))))
        self.room = ink.pan_gray(np.clip(self.room_rgb, 0, 255), .45, .40, .15) if self.room_rgb is not None else None
        self.track = tracks_or_none(project)
        self.crop = tuple(CROP) if CROP else auto_crop(project, A, B, self.track)
        print(f"photo: the footage at {self.crop} (x, y, w, h) fills the slot" + ("" if self.room is not None else "; no room plate, the live room is screened too"))

    def retouch(self, g, n):
        """what a picture desk did with a brush: open the eyes, lift the mouth so it reads through the dots, calm what is below
        the chin (a knit or a pattern only beats against the screen). Tracked to the face; nothing without a track"""
        f = self.track[n]["face"] if self.track and n < len(self.track) else None
        if not f:
            return g
        h, w = g.shape
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        fw = f["w"]
        lift = np.zeros_like(g)
        for ex, ey in f["eyes"]:
            lift += np.exp(-(((xs - ex) / (fw * .19)) ** 2 + ((ys - ey) / (fw * .13)) ** 2))
        g = g + EYE_LIFT * lift + EYE_CONTRAST * np.clip(lift, 0, 1) * (g - cv2.GaussianBlur(g, (0, 0), 6))
        mx, my = f["mouth"]
        m = np.exp(-(((xs - mx) / (fw * .30)) ** 2 + ((ys - my) / (fw * .20)) ** 2))
        g = g + MOUTH_CONTRAST * m * (g - cv2.GaussianBlur(g, (0, 0), 9))
        below = np.clip((ys - f["chin"] - 30) / 60, 0, 1)
        return g * (1 - below) + cv2.GaussianBlur(g, (0, 0), 4.5) * below

    def photo(self, rgb, al, n, out=1):
        """this frame of the speaker, screened. With a room plate only they move: the room's dots never change"""
        a = al.astype(np.float32) / 255
        g = self.retouch(ink.pan_gray(rgb, .45, .40, .15), n)
        g = ink.local_contrast(g, 5, .9, 18, .5)
        room = self.room if self.room is not None else ink.pan_gray(rgb, .45, .40, .15)
        tone = ink.curve(g, TONE) * a + ink.curve(room, TONE_ROOM) * (1 - a)
        cx, cy, cw, ch = self.crop
        px, py, pw, ph = PHOTO
        crop = cv2.resize(tone[cy:cy + ch, cx:cx + cw], (pw, ph), interpolation=cv2.INTER_CUBIC if pw >= cw else cv2.INTER_AREA)
        return ink.round_dots(1 - crop, cell=CELL, sharp=SHARP, out=out)

    def compose(self, n, rgb, al, scale=1.0, dy=0, still=False):
        """frame n of the page. still=True: colours for a PNG, not for the video encoder"""
        m = self.furn2.copy()
        for tw, (x0, y0, x1, y1) in self.deck_words:
            age = n - fxlib.fr(tw)
            if age < 0:
                continue
            word = self.deck2[y0:y1, x0:x1]
            if age < 3:                                                 # wet: the word lands fat and draws in over three frames
                r, thr = ((3.2, .22), (2.2, .32), (1.4, .42))[age]
                word = np.clip((cv2.GaussianBlur(word, (0, 0), r) - thr) / .10 + .5, 0, 1)
            m[y0:y1, x0:x1] = np.maximum(m[y0:y1, x0:x1], word)
        px, py, pw, ph = PHOTO
        dots = self.photo(rgb, al, n, out=2)
        m[py * 2 + 2:(py + ph) * 2 - 2, px * 2 + 2:(px + pw) * 2 - 2] = dots[2:-2, 2:-2]
        m = m * self.tooth2                                             # the paper's tooth in the solids
        a = (m * .965)[..., None]
        img = self.paper2 * (1 - a) + np.array(INK, np.float32)[None, None] * a
        if not still:
            img = ink.for_renderer(img)
        if scale != 1.0 or dy:
            Wb, Hb = round(W * scale), round(H * scale)
            big = cv2.resize(img, (Wb, Hb), interpolation=cv2.INTER_AREA)
            x0, y0 = (Wb - W) // 2, (Hb - H) // 2 - dy
            if dy:
                big = cv2.copyMakeBorder(big, 8, 8, 0, 0, cv2.BORDER_REPLICATE)
                y0 += 8
            return np.clip(big[y0:y0 + H, x0:x0 + W], 0, 255).astype(np.uint8)
        return np.clip(cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--stills", nargs="*", type=float, help="seconds on the output timeline: write these frames as PNGs only")
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    E, TL, A, B = window(project, fid)
    if fxlib.size(os.path.join(project, "public", "clean.mp4")) != (W, H):
        sys.exit("press-front is a 1080x1920 page: it needs a 9:16 canvas")
    out_dir, work = os.path.join(project, "fx", fid), os.path.join(project, "work", "fx", fid)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work, exist_ok=True)
    pg = Page(project, fid, A, B, frame_at(TL, E, A), work)
    n0 = fxlib.fr(A)

    def page(n, rgb, al, still=False):
        k = n - n0                                                       # frames into the effect: the slam is the effect's, not the video's
        return pg.compose(n, rgb, al, SLAM[k] if 0 <= k < len(SLAM) else 1.0, SHUDDER.get(k, 0), still=still)
    if args.stills is not None:
        for t in args.stills:
            n = fxlib.fr(t)
            _, rgb = next(fxlib.frames(project, n / FPS, (n + 1) / FPS))
            _, al = next(fxlib.alpha(project, n / FPS, (n + 1) / FPS))
            path = os.path.join(work, f"still_{t:.2f}.png")
            cv2.imwrite(path, cv2.cvtColor(page(n, rgb, al, still=True), cv2.COLOR_RGB2BGR))
            print(path)
        return
    w = fxlib.Writer(os.path.join(out_dir, f"{fid}.mp4"), crf=16)
    last = None
    for (n, rgb), (_, al) in zip(fxlib.frames(project, A, B), fxlib.alpha(project, A, B)):
        w.write(page(n, rgb, al))
        last = (n, rgb, al)
    w.close()
    if last:
        cv2.imwrite(os.path.join(work, "last.png"), cv2.cvtColor(pg.compose(*last, still=True), cv2.COLOR_RGB2BGR))
    tag = fxlib.tag(f"{fid}-clip", f"fx/{fid}/{fid}.mp4", A, B, "", "{{T0}}", "position:absolute;left:0;top:0;width:1080px;height:1920px;")
    with open(os.path.join(out_dir, "fx.html"), "w") as fh:
        fh.write(f"<!-- {fid} [press-front]: written by gen.py for the window {A:.3f}-{B:.3f}. A full-frame pre-render: the page with the live halftone. -->\n{tag}\n")
    with open(os.path.join(out_dir, "fx.js"), "w") as fh:
        fh.write("// press-front: everything is in the clip (paper, so no live grade); its frame 0 is the frame at A. Nothing to tween.\n")
    print(f"wrote {out_dir}/{fid}.mp4 ({fxlib.fr(B) - n0} frames), fx.html, fx.js; the last frame as a still in {work}/last.png")
    print("SOUND sfx lines (the slam, then one print per deck chunk):")
    lines = [f"    ({A + 0.067:.3f}, \"impact-low\", -12),   # the press slams"]
    for k, (text, t) in enumerate(pg.c["deck"]):
        lines.append(f"    ({t:.3f}, \"shutter\", {-14 if k == len(pg.c['deck']) - 1 else -16}),   # prints: {text}")
    print("\n".join(lines))
    print(f"KARAOKE hide: ({A:.2f}, {B:.2f}) (the page carries the words)")


if __name__ == "__main__":
    main()
