#!/usr/bin/env python3
"""storyboard-deck: the video's own storyboard as a deck of cards. One card template, three effects:
  <id>        (deal)  the deck slides in and the beats deal out face up into a grid, the last card slams down
  <id>-flip   (flip)  the grid gathers under the hero card, which lands big beside the head and flips to show its plan
  <id>-note   (note)  the hero turns back to its frame, a note types in as a comment, the problem gets marked, the
                      frame wipes to the fix and a check lands
This writes the three fx.html files (the cards, from the board) and the card frames. The motion and the words are
the constants at the top of each folder's fx.js.

Every card is a real beat of the board the kit made for this video (pipeline/storyboard.py writes
<project>/storyboard/index.html and frames/): front = the beat's frame, a strip with its number and time, its line;
back = the beat's plan as written on the board, its facts (sound, music, shot), typeset like an index card. The hero
(the card the flip and the note are about) shows the BEFORE frame on its front; the note wipes it to AFTER.
Without a board it falls back to the video's own lines: one card per edit.FX entry with a note (the note is the
plan, the frame is cut from public/clean.mp4 in the middle of its window).

Run: PY fx/storyboard-deck/gen.py <project> [<id>] [--board <storyboard dir or project>]
  reads   <project>/storyboard/index.html + frames/ (or --board), else <project>/edit.py, words.json, timeline.json,
          public/clean.mp4
  writes  <project>/fx/<id>/fx.html, c0.jpg..c7.jpg; <project>/fx/<id>-flip/fx.html; <project>/fx/<id>-note/fx.html,
          after.jpg; it prints the edit.FX entries the three need
<id> defaults to this script's folder name (the flip and the note are <id>-flip and <id>-note: keep those names).
Rerun it whenever the board changes (after storyboard.py) or you change the constants below.
"""
import argparse
import html
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- change only these constants
CARDS = 8            # cards in the deck (a 4 x 2 grid); fewer beats on the board = fewer cards
HERO = ""            # the beat id the flip and the note are about (e.g. "p05"); "" = the third card dealt
BEFORE = ""          # the hero's frame before the note (a 9:16 still in <project>/fx/<id>/); "" = its board frame
                     # letterboxed with black bars, which is what the default note asks to fix
AFTER = ""           # the frame after the fix (a 9:16 still in <project>/fx/<id>-note/); "" = its board frame
BARS = 0.17          # with the default BEFORE: each black bar's share of the frame height (0 = no bars, no marks)
PLAN_CHARS = 29      # the plan wraps at this many characters a line (the card fits it to its width after the
                     # pack's fonts load, and only ever shrinks it)

W, H = 396, 780      # one card, px (the deal shows it at 0.6035, the flip at 1)
FW, FH = 372, 661    # its frame
PT, LH = 146, 48     # back: the plan's top, the ruled line pitch
PLAN_LINES = 7       # plan lines that fit above the facts
FACTS = 3            # facts under the plan (Sound, Music, Shot, Length: the first three the beat has)


def e(s):
    return html.escape(str(s), quote=False)


def window(E, project, fid):
    for F in getattr(E, "FX", []):
        if F["id"] == fid:
            end = F["end"]
            if end == "end":
                end = json.load(open(os.path.join(project, "timeline.json")))["total"]
            return float(F["at"]), float(end)
    return None


def load_edit(project):
    spec = importlib.util.spec_from_file_location("edit", os.path.join(project, "edit.py"))
    E = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(E)
    return E


def tc(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def from_board(board):
    """the beats of the kit's storyboard page: id, time range, length, kind, line, plan (its moves), facts, frame"""
    page = open(os.path.join(board, "index.html"), encoding="utf-8").read()
    out = []
    for m in re.finditer(r'<section class="beat" id="(p\d+)".*?</section>', page, re.S):
        sec, bid = m.group(0), m.group(1)
        img = re.search(r'<img src="([^"]+)"', sec)
        meta = re.findall(r"<span[^>]*>(.*?)</span>", re.search(r'<div class="meta">(.*?)</div>', sec, re.S).group(1), re.S)
        line = re.search(r'<p class="line">(.*?)</p>', sec, re.S)
        moves = [strip(x) for x in re.findall(r"<li>(.*?)</li>", sec, re.S)]
        facts = dict((strip(a), strip(b)) for a, b in re.findall(r"<dt[^>]*>(.*?)</dt><dd[^>]*>(.*?)</dd>", sec, re.S))
        if not line or not img:
            continue
        b = dict(id=bid, tc=strip(meta[1]) if len(meta) > 1 else "", dur=strip(meta[2]) if len(meta) > 2 else "",
                 kind=strip(meta[3]) if len(meta) > 3 else "", line=strip(line.group(1)).strip("“”\""),
                 plan=" ".join(x[:1].upper() + x[1:].rstrip(".") + "." for x in moves), frame=os.path.join(board, img.group(1)))
        b["facts"] = [(k, facts[k]) for k in ("Sound", "Music") if facts.get(k)] + [("Shot", b["kind"]), ("Length", b["dur"])]
        out.append(b)
    return out


def from_lines(E, project):
    """no board: one beat per edit.FX entry with a note, its frame cut from clean.mp4 in the middle of its window"""
    words = json.load(open(os.path.join(project, "words.json")))
    TL = json.load(open(os.path.join(project, "timeline.json")))
    out = []
    for k, F in enumerate(F for F in getattr(E, "FX", []) if F.get("note")):
        a, b = window(E, project, F["id"])
        line = " ".join(w["text"] for w in words if a <= (w["start"] + w["end"]) / 2 < b)
        shot = [s for s in TL["shots"] if s["t"] <= (a + b) / 2 + 1e-6][-1]["frame"]
        kind = f"Talking head, {'close' if shot == 'CLOSE' else 'wide'}"
        out.append(dict(id=f"p{k + 1:02d}", tc=f"{tc(a)}–{tc(b)}", dur=f"{b - a:.1f}s", kind=kind, line=line,
                        plan=F["note"][:1].upper() + F["note"][1:].rstrip(".") + ".", frame=("clean", (a + b) / 2),
                        facts=[("Shot", kind), ("Length", f"{b - a:.1f}s")]))
    return out


def still(src, dst, project, bars=0.0):
    """a 9:16 card frame (432x768 jpg) from a board frame or a time in clean.mp4; bars > 0 letterboxes it"""
    if isinstance(src, tuple):
        inp = ["-ss", f"{src[1]:.3f}", "-i", os.path.join(project, "public", "clean.mp4")]
    else:
        inp = ["-i", src]
    vf = "scale=432:768:force_original_aspect_ratio=increase,crop=432:768"
    if bars > 0:
        h = int(round(768 * (1 - 2 * bars) / 2)) * 2
        vf += f",crop=432:{h},pad=432:768:0:(oh-ih)/2:color=black"
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inp + ["-frames:v", "1", "-vf", vf, "-q:v", "4", dst], check=True)


def card(px, k, b, img, hero):
    plan = textwrap.wrap(b["plan"], PLAN_CHARS)
    if len(plan) > PLAN_LINES:
        plan = plan[:PLAN_LINES]
        plan[-1] = plan[-1].rstrip(" ,.;:") + "…"
    front = (f'<div class="{px}-face {px}-front"><div class="{px}-frame"><img class="{px}-img" src="{img}">'
             + ("{{FRAMEX}}" if hero else "") + '</div>'
             f'<div class="{px}-strip"><b>{e(b["id"])}</b><span>{e(b["tc"])}</span></div>'
             f'<p class="{px}-line">“{e(b["line"])}”</p></div>')
    rules = "".join(f'<i style="top:{PT + LH * i + 35}px"></i>' for i in range(PLAN_LINES + FACTS + 1))
    lines = "".join(f'<div class="{px}-pl"><span>{e(t)}' + (f'<u class="{px}-u" id="{px}-plan{i}"></u>' if hero else "")
                    + "</span></div>" for i, t in enumerate(plan))
    facts = "".join(f'<div class="{px}-fact"><em>{e(n)}</em><span>{e(v)}'
                    + (f'<u class="{px}-u" id="{px}-fact{i}"></u>' if hero else "") + "</span></div>"
                    for i, (n, v) in enumerate(b["facts"][:FACTS]))
    back = (f'<div class="{px}-face {px}-back"><div class="{px}-rules">{rules}</div>'
            f'<div class="{px}-head"><b>{e(b["id"])}</b><span>{e(b["dur"])} · {e(b["kind"])}</span></div>'
            f'<div class="{px}-red"></div><p class="{px}-bline">“{e(b["line"])}”</p>'
            f'<div class="{px}-plan">{lines}</div><div class="{px}-facts">{facts}</div>'
            f'<div class="{px}-btn">Comment on this beat</div></div>')
    inner = re.sub(r"<(div|p|span|b|em|u|i|img)([ >])", r"<\1 data-layout-allow-overlap\2", front + back)
    return f'<div class="{px}-card" id="{px}-c{k}" data-layout-allow-overlap>{inner}</div>'


CSS = """
#{{ID}}-stage { position:absolute; left:0; top:0; width:1080px; height:1920px; perspective:2600px; }
#{{ID}} .{{ID}}-card { position:absolute; left:0; top:0; width:%(W)dpx; height:%(H)dpx; transform-style:preserve-3d; }
#{{ID}} .{{ID}}-face { position:absolute; left:0; top:0; width:%(W)dpx; height:%(H)dpx; border-radius:12px; overflow:hidden;
  backface-visibility:hidden; -webkit-backface-visibility:hidden; background:var(--c-light);
  box-shadow:0 16px 36px color-mix(in srgb, var(--c-ink) 30%%, transparent), 0 0 0 1px color-mix(in srgb, var(--c-dark) 16%%, transparent); }
#{{ID}} .{{ID}}-back { transform:rotateY(180deg); background:color-mix(in srgb, var(--c-light) 96%%, var(--c-ink)); }
#{{ID}} .{{ID}}-frame { position:absolute; left:12px; top:12px; width:%(FW)dpx; height:%(FH)dpx; border-radius:4px; overflow:hidden; background:var(--c-ink); }
#{{ID}} .{{ID}}-img { position:absolute; left:0; top:0; width:%(FW)dpx; height:%(FH)dpx; object-fit:cover; display:block; }
#{{ID}} .{{ID}}-strip { position:absolute; left:12px; top:681px; width:%(FW)dpx; height:30px; background:var(--c-dark); border-radius:3px;
  display:flex; align-items:center; justify-content:space-between; padding:0 12px; box-sizing:border-box;
  font-family:var(--font-mono); font-weight:500; font-size:15px; line-height:1; color:var(--c-light); letter-spacing:.02em; white-space:nowrap; }
#{{ID}} .{{ID}}-strip b { font-weight:700; color:var(--c-accent); }
#{{ID}} .{{ID}}-line { position:absolute; left:14px; top:718px; width:368px; margin:0; font-family:var(--font-display);
  font-style:var(--display-style); font-weight:var(--display-weight); font-size:20px; line-height:24px; color:var(--c-ink);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
#{{ID}} .{{ID}}-rules i { position:absolute; left:0; width:%(W)dpx; height:1px; background:var(--c-hair-light); display:block; }
#{{ID}} .{{ID}}-head { position:absolute; left:0; top:0; width:%(W)dpx; height:44px; background:var(--c-dark); display:flex; align-items:center;
  justify-content:space-between; padding:0 18px; box-sizing:border-box; font-family:var(--font-mono); font-weight:500; font-size:15px;
  line-height:1; color:var(--c-light); white-space:nowrap; }
#{{ID}} .{{ID}}-head b { font-weight:700; color:var(--c-accent); font-size:17px; }
#{{ID}} .{{ID}}-head span { overflow:hidden; text-overflow:ellipsis; max-width:300px; }
#{{ID}} .{{ID}}-head b { flex:none; }
#{{ID}} .{{ID}}-red { position:absolute; left:0; top:44px; width:%(W)dpx; height:3px; background:var(--c-neg); }
#{{ID}} .{{ID}}-bline { position:absolute; left:20px; top:62px; width:356px; margin:0; font-family:var(--font-display);
  font-style:var(--display-style); font-weight:var(--display-weight); font-size:30px; line-height:38px; color:var(--c-dark);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
#{{ID}} .{{ID}}-plan { position:absolute; left:20px; top:%(PT)dpx; width:356px; font-family:var(--font-text); font-weight:400;
  font-size:23px; line-height:%(LH)dpx; color:var(--c-ink); }
#{{ID}} .{{ID}}-pl { position:relative; height:%(LH)dpx; white-space:nowrap; }
#{{ID}} .{{ID}}-pl > span { display:inline-block; position:relative; }
#{{ID}} .{{ID}}-u { position:absolute; left:-2px; right:-2px; top:34px; height:4px; background:var(--c-accent); display:block; transform-origin:0 50%%; }
#{{ID}} .{{ID}}-facts { position:absolute; left:20px; top:%(FT)dpx; width:356px; }
#{{ID}} .{{ID}}-fact { position:relative; height:%(LH)dpx; display:flex; align-items:baseline; gap:14px; line-height:%(LH)dpx; white-space:nowrap; overflow:visible; }
#{{ID}} .{{ID}}-fact em { font-family:var(--font-mono); font-weight:700; font-size:13px; line-height:%(LH)dpx; font-style:normal;
  letter-spacing:.12em; text-transform:uppercase; color:var(--c-dark); width:70px; flex:none; }
#{{ID}} .{{ID}}-fact span { font-family:var(--font-text); font-weight:400; font-size:21px; line-height:%(LH)dpx; color:var(--c-ink);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:268px; position:relative; }
#{{ID}} .{{ID}}-btn { position:absolute; left:20px; top:708px; height:46px; padding:0 20px; border:1.5px solid var(--c-dark); border-radius:23px;
  font-family:var(--font-text); font-weight:500; font-size:18px; line-height:43px; color:var(--c-dark); box-sizing:border-box; white-space:nowrap; }
""" % dict(W=W, H=H, FW=FW, FH=FH, PT=PT, LH=LH, FT=PT + LH * (PLAN_LINES + 1))

NOTE_HTML = """<div id="{{ID}}-after"><img class="{{ID}}-img" src="fx/{{ID}}/after.jpg"></div>%(bars)s<i id="{{ID}}-edge"></i>"""
NOTE_TAIL = """
<div id="{{ID}}-chip" data-layout-allow-overlap><div class="{{ID}}-ch" data-layout-allow-overlap><b class="{{ID}}-av" data-layout-allow-overlap></b>
<span class="{{ID}}-name" data-layout-allow-overlap></span><span class="{{ID}}-on" data-layout-allow-overlap></span></div>
<p class="{{ID}}-text" id="{{ID}}-typed" data-layout-allow-overlap></p></div>
<div id="{{ID}}-check"><svg width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" class="{{ID}}-ck"/>
<path id="{{ID}}-tick" d="M19 33 L28 42 L46 23" fill="none" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"
 stroke-dasharray="40" stroke-dashoffset="40"/></svg></div>"""
NOTE_CSS = """
#{{ID}}-after { position:absolute; left:0; top:0; width:%(FW)dpx; height:%(FH)dpx; clip-path:inset(0 100%% 0 0); }
#{{ID}} .{{ID}}-bar { position:absolute; left:3px; width:%(BW)dpx; border:3px solid var(--c-neg); border-radius:3px; box-sizing:border-box; display:block; }
#{{ID}}-edge { position:absolute; left:0; top:0; width:4px; height:%(FH)dpx; background:var(--c-accent); display:block; }
#{{ID}}-chip { position:absolute; left:40px; top:240px; width:580px; background:var(--c-light); border-radius:18px; padding:20px 26px 22px;
  box-sizing:border-box; box-shadow:0 16px 36px color-mix(in srgb, var(--c-ink) 30%%, transparent), 0 0 0 1px color-mix(in srgb, var(--c-ink) 10%%, transparent); }
#{{ID}} .{{ID}}-ch { display:flex; align-items:center; gap:14px; height:52px; }
#{{ID}} .{{ID}}-av { width:52px; height:52px; border-radius:50%%; flex:none; display:flex; align-items:center; justify-content:center; overflow:hidden;
  background:var(--c-accent); color:var(--c-light); font-family:var(--font-text); font-weight:700; font-size:20px; letter-spacing:.02em; }
#{{ID}} .{{ID}}-av img { width:52px; height:52px; object-fit:cover; display:block; }
#{{ID}} .{{ID}}-name { font-family:var(--font-text); font-weight:600; font-size:28px; line-height:1; color:var(--c-ink); white-space:nowrap; }
#{{ID}} .{{ID}}-on { font-family:var(--font-mono); font-weight:500; font-size:19px; line-height:1; color:var(--c-muted-light); white-space:nowrap; }
#{{ID}} .{{ID}}-text { margin:12px 0 0; height:126px; font-family:var(--font-text); font-weight:400; font-size:31px; line-height:42px; color:var(--c-ink); }
#{{ID}}-typed i { font-style:normal; display:none; }
#{{ID}}-typed .{{ID}}-caret { display:inline-block; width:3px; height:36px; background:var(--c-dark); vertical-align:-6px; margin-left:1px; }
#{{ID}}-check { position:absolute; left:0; top:0; width:64px; height:64px; }
#{{ID}} .{{ID}}-ck { fill:var(--c-accent); }
#{{ID}}-tick { stroke:var(--c-dark); }
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    ap.add_argument("--board", help="the storyboard to deal (a storyboard folder, or a project that has one)")
    a = ap.parse_args()
    project = os.path.abspath(os.path.expanduser(a.project))
    ids = {"deal": a.id, "flip": a.id + "-flip", "note": a.id + "-note"}
    E = load_edit(project)
    for fid in ids.values():
        if not window(E, project, fid):
            print(f"note: no FX entry {fid!r} in {project}/edit.py yet (the entries to add are printed below)")
    board = os.path.abspath(os.path.expanduser(a.board)) if a.board else os.path.join(project, "storyboard")
    if os.path.isdir(os.path.join(board, "storyboard")) and not os.path.exists(os.path.join(board, "index.html")):
        board = os.path.join(board, "storyboard")
    if os.path.exists(os.path.join(board, "index.html")):
        beats, src = from_board(board), "the storyboard"
    else:
        beats, src = from_lines(E, project), "the video's own lines (no storyboard yet)"
    if not beats:
        sys.exit("no beats with a line to deal")
    n = min(CARDS, len(beats))
    pick = [beats[round(i * (len(beats) - 1) / max(1, n - 1))] for i in range(n)]
    hk = min(2, n - 1)
    if HERO:
        hb = next((b for b in beats if b["id"] == HERO), None)
        if not hb:
            sys.exit(f"HERO {HERO!r} is not a beat of {src}")
        if hb not in pick:
            pick[hk] = hb
        hk = pick.index(hb)
    hero = pick[hk]

    dirs = {k: os.path.join(project, "fx", v) for k, v in ids.items()}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    imgs = []
    for k, b in enumerate(pick):                           # the card frames, into the deal's folder
        name = f"c{k}.jpg"
        if k == hk and BEFORE:
            still(os.path.join(dirs["deal"], BEFORE), os.path.join(dirs["deal"], name), project)
        else:
            still(b["frame"], os.path.join(dirs["deal"], name), project, bars=BARS if k == hk else 0.0)
        imgs.append(f"fx/{ids['deal']}/{name}")
    after = os.path.join(dirs["note"], "after.jpg")
    still(os.path.join(dirs["note"], AFTER) if AFTER else hero["frame"], after, project)

    bars = ""
    if not BEFORE and BARS > 0:                            # the marks land on the default BEFORE's bars
        bh = round(FH * BARS)
        bars = (f'<i class="{{{{ID}}}}-bar" id="{{{{ID}}}}-bt" style="top:3px; height:{bh - 3}px;"></i>'
                f'<i class="{{{{ID}}}}-bar" id="{{{{ID}}}}-bb" style="top:{FH - bh}px; height:{bh - 3}px;"></i>')
    for kind, fid in ids.items():
        cards = "".join(card("{{ID}}", k, b, imgs[k], k == hk) for k, b in enumerate(pick))
        extra_css = tail = ""
        if kind == "note":
            cards = cards.replace("{{FRAMEX}}", NOTE_HTML % dict(bars=bars))
            tail, extra_css = NOTE_TAIL, NOTE_CSS % dict(FW=FW, FH=FH, BW=FW - 6)
        cards = cards.replace("{{FRAMEX}}", "")
        what = {"deal": "the beats deal out of a deck into a grid", "flip": "the grid gathers under the hero, which flips to its plan",
                "note": "the hero turns back, a note types in, the frame wipes to the fix"}[kind]
        out = (f"<!-- {kind}: {what}. Written by fx/{ids['deal']}/gen.py from {e(src)}: don't edit by hand, rerun it.\n"
               f"     {n} cards, the hero (the card the flip and the note are about) is card {hk} ({hero['id']}). -->\n"
               f'<div id="{{{{ID}}}}-stage" data-hero="{hk}" data-cards="{n}">{cards}{tail}</div>\n<style>{CSS}{extra_css}</style>\n')
        with open(os.path.join(dirs[kind], "fx.html"), "w", encoding="utf-8") as f:
            f.write(out)
    print(f"dealt {n} cards from {src}: " + ", ".join(b["id"] for b in pick) + f"; hero card {hk} = {hero['id']} “{hero['line']}”")
    print("wrote " + ", ".join(f"fx/{v}/" for v in ids.values()) + f" in {project}\nedit.FX entries (set at/end on the lines):")
    for kind, fid in ids.items():
        w = window(E, project, fid)
        at, end = (f"{w[0]:.2f}", f"{w[1]:.2f}") if w else ("<at>", "<end>")
        print(f'    dict(id="{fid}", layer="top", at={at}, end={end}, note="storyboard deck: {kind}"),')


if __name__ == "__main__":
    main()
