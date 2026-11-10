#!/usr/bin/env python3
"""New effect: rebuild an effect the creator saw in someone else's video as their own, in their style, and add it to
their library. The steps are KIT/effect/EFFECT.md; this script is the mechanical part of each one. Everything lives in
HOME/effects/<name>/ (the reference, the frames, the test, the review) and a kept effect lands in HOME/fx/<folder>/.

Run: PY KIT/pipeline/effect.py <step> <name> ...
  fetch   <name> <link or file>              -> ref.mp4 (+ ref.json): downloads a link (yt-dlp), copies a file
  look    <name> <start> <end> [--fps N]     -> look/sheet-NN.jpg: every frame of that window, labelled with its time
  measure <name> <start> <end> [x0,y0,x1,y1] -> per frame: the light text box (size and weight changes) and the
                                                frame's three bands (hard cuts, layout switches); prints the changes
  testbed <name> [project]                   -> testbed/: the newest edited video (or the one named) with no effects,
                                                in the creator's current style. Put the new effect in its FX.
  try     <name> <id> --at t1 t2 ...         -> stills of the effect on the testbed (fxsandbox), read every one
  compare <name> <ref start> <ref end> <test start> <test end> [--no-render]
                                             -> renders the testbed, compare.mp4: the reference left, theirs right
  review  <name>                             -> review/: the Keep / Fix / Drop page, from review.json
  keep    <name>                             -> HOME/fx/<folder>/ + its LIBRARY.md row + LOG.md + the effects page
  library [--open]                           -> HOME/effects/index.html: every effect, theirs first
"""
import datetime
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HOME, KIT, PY, hf  # noqa: E402
import style as ST  # noqa: E402

EFFECTS = os.path.join(HOME, "effects")
MINE = os.path.join(HOME, "fx")
CMD = "/reel-kit:"                       # how the commands read in Claude Code (the page says so for other hosts)
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
       "-movflags", "+faststart"]
MEDIA = (".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a")          # linked into the testbed, never copied


def work(name):
    d = os.path.join(EFFECTS, name)
    os.makedirs(d, exist_ok=True)
    return d


def state(name, **update):
    p = os.path.join(work(name), "state.json")
    s = json.load(open(p)) if os.path.exists(p) else {}
    if update:
        s.update(update)
        json.dump(s, open(p, "w"), indent=1)
    return s


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st, num_den = j["streams"][0], j["streams"][0]["r_frame_rate"].split("/")
    return dict(width=st["width"], height=st["height"], fps=round(float(num_den[0]) / float(num_den[1]), 3),
                duration=round(float(j["format"]["duration"]), 3))


def esc(s):
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ fetch
def fetch(name, src):
    d, ref = work(name), os.path.join(work(name), "ref.mp4")
    if re.match(r"https?://", src):
        r = subprocess.run([PY, "-m", "yt_dlp", "-q", "--no-warnings", "--no-playlist", "-f",
                            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b", "--merge-output-format", "mp4",
                            "-o", os.path.join(d, "ref.%(ext)s"), src], capture_output=True, text=True)
        if r.returncode or not os.path.exists(ref):
            print(r.stderr[-1500:], file=sys.stderr)
            sys.exit("Couldn't download that link (private, removed, or the site wants a login). Ask the creator to "
                     "save the video to their computer (any downloader for that site works) and send the file instead.")
    else:
        src = os.path.abspath(os.path.expanduser(src))
        if not os.path.exists(src):
            sys.exit(f"no file at {src}")
        if src.lower().endswith(".mp4"):
            shutil.copy(src, ref)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src] + ENC + [ref], check=True)
    info = dict(probe(ref), source=src)
    json.dump(info, open(os.path.join(d, "ref.json"), "w"), indent=1)
    state(name, source=src)
    print(f"{ref}  {info['width']}x{info['height']}  {info['fps']} fps  {info['duration']}s")


# ------------------------------------------------------------------ look + measure
def frames(name, start, end, fps=None):
    """[(time, PIL image)] for every frame of the reference in [start, end)"""
    from PIL import Image
    ref = os.path.join(work(name), "ref.mp4")
    info = probe(ref)
    fps = fps or info["fps"]
    w, h = info["width"], info["height"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-i", ref, "-t", f"{end - start:.3f}",
                          "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True,
                         check=True).stdout
    n = len(raw) // (w * h * 3)
    return [(start + i / fps, Image.frombytes("RGB", (w, h), raw[i * w * h * 3:(i + 1) * w * h * 3])) for i in range(n)]


def look(name, start, end, fps=None, cols=6, rows=4, tw=240):
    from PIL import Image, ImageDraw
    out = os.path.join(work(name), "look")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    fr = frames(name, start, end, fps)
    th = round(tw * fr[0][1].height / fr[0][1].width)
    per = cols * rows
    for s in range(0, len(fr), per):
        chunk = fr[s:s + per]
        sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (20, 20, 20))
        for i, (t, im) in enumerate(chunk):
            x, y = (i % cols) * tw, (i // cols) * (th + 22)
            sheet.paste(im.resize((tw, th)), (x, y + 22))
            ImageDraw.Draw(sheet).text((x + 6, y + 5), f"{t:.3f}s", fill=(240, 240, 240))
        p = os.path.join(out, f"sheet-{s // per + 1:02d}.jpg")
        sheet.save(p, quality=86)
        print(f"{p}  {chunk[0][0]:.3f}-{chunk[-1][0]:.3f}s")


def measure(name, start, end, box=None):
    import numpy as np
    fr = frames(name, start, end)
    prev = None
    print("time      text box (x0,y0,x1,y1 / w x h of the light pixels)   bands top/mid/bottom luma")
    for t, im in fr:
        a = np.asarray(im.convert("L"), dtype=np.int16)
        H = a.shape[0]
        bands = tuple(int(a[int(H * f0):int(H * f1)].mean()) for f0, f1 in ((0, .33), (.33, .66), (.66, 1)))
        sub = a if not box else a[box[1]:box[3], box[0]:box[2]]
        ys, xs = np.nonzero(sub > 225)
        if len(xs) > 20:
            ox, oy = (box[0], box[1]) if box else (0, 0)
            tb = (int(xs.min()) + ox, int(ys.min()) + oy, int(xs.max()) + ox, int(ys.max()) + oy)
        else:
            tb = None
        row = (tb, bands)
        if prev is None or tb != prev[0] or max(abs(b - c) for b, c in zip(bands, prev[1])) > 12:
            tbs = f"{tb} / {tb[2] - tb[0]}x{tb[3] - tb[1]}" if tb else "none"
            print(f"{t:7.3f}   {tbs:52s} {bands}")
        prev = row


# ------------------------------------------------------------------ testbed
def newest_project():
    best = None
    for p in glob.glob(os.path.join(HOME, "projects", "*")):
        ok = all(os.path.exists(os.path.join(p, f)) for f in ("edit.py", "words.json", "timeline.json", "public/clean.mp4"))
        if ok and (best is None or os.path.getmtime(os.path.join(p, "public", "clean.mp4")) > best[0]):
            best = (os.path.getmtime(os.path.join(p, "public", "clean.mp4")), p)
    return best[1] if best else None


def testbed(name, project=None):
    project = os.path.abspath(os.path.expanduser(project)) if project else newest_project()
    if not project:
        sys.exit("NO_FOOTAGE: there's no edited video yet to test on. Ask the creator for any short clip of them "
                 "talking (their next video is perfect), take it through steps 1 and 2 of SKILL.md (scaffold, cut, "
                 "words, cutout), then run testbed again with that project.")
    tb = os.path.join(work(name), "testbed")
    shutil.rmtree(tb, ignore_errors=True)
    os.makedirs(os.path.join(tb, "public"))
    os.makedirs(os.path.join(tb, "fx"))
    for f in ("words.json", "timeline.json"):
        shutil.copy(os.path.join(project, f), os.path.join(tb, f))
    for d in ("assets", "audio"):
        if os.path.exists(os.path.join(project, d)):
            os.symlink(os.path.join(project, d), os.path.join(tb, d))
    # the creator's CURRENT style (the build writes brand.css and fonts into public/, so those are never links)
    shutil.copytree(ST.STYLE_DIR, os.path.join(tb, "style"), ignore=shutil.ignore_patterns("board", "refs"))
    ppub = os.path.join(project, "public")
    for f in os.listdir(ppub):
        if f in ("index.html", "snapshots", "fx", "cards", "brand.css", "fonts") or f.startswith("."):
            continue
        s, t = os.path.join(ppub, f), os.path.join(tb, "public", f)
        if f.lower().endswith(MEDIA):
            os.symlink(s, t)
        elif os.path.isdir(s):
            shutil.copytree(s, t)
        else:
            shutil.copy(s, t)
    e = open(os.path.join(project, "edit.py")).read()
    e += '''

# ---- effect test (pipeline/effect.py testbed): this take with nothing on it but the new effect, as a showcase.
STYLE = "showcase"
for _k in ("CARDS", "OVERLAYS", "BOXES", "BEHIND", "NEEDS", "GENERATED"):
    if _k in globals():
        globals()[_k] = []
FX = [
    # dict(id="nx", layer="top", at=0.0, end=0.0, frames=[]),
]
KARAOKE = {**globals().get("KARAOKE", {}), "hide": []}   # add (at, end) when the effect carries the words itself
'''
    open(os.path.join(tb, "edit.py"), "w").write(e)
    w = json.load(open(os.path.join(tb, "words.json")))
    words = w.get("words", w) if isinstance(w, dict) else w
    state(name, project=project)
    print(f"testbed: {tb}\n  footage: {project} ({probe(os.path.join(ppub, 'clean.mp4'))['duration']}s)")
    print(f"  words: {len(words)} in words.json. Pick a line like the reference's (the same shape, about the same length).")
    print(f"  then: write {tb}/fx/<id>/fx.html + fx.js, set FX (and KARAOKE hide) at the end of {tb}/edit.py")


# ------------------------------------------------------------------ try + compare
def try_(name, fid, times):
    tb = os.path.join(work(name), "testbed")
    state(name, id=fid)
    subprocess.run([PY, os.path.join(KIT, "pipeline", "fxsandbox.py"), tb, "new", "--only", fid, "--at"]
                   + [str(t) for t in times] + ["--fresh"], check=True)


def side_by_side(ref, rs, re_, test, ts, te, out):
    d = max(re_ - rs, te - ts)
    fit = "scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    fc = (f"[0:v]trim={rs:.3f}:{re_:.3f},setpts=PTS-STARTPTS,{fit},tpad=stop_mode=clone:stop_duration={d:.3f}[a];"
          f"[1:v]trim={ts:.3f}:{te:.3f},setpts=PTS-STARTPTS,{fit},tpad=stop_mode=clone:stop_duration={d:.3f}[b];"
          f"[a][b]hstack=inputs=2,trim=0:{d:.3f}[v];"
          f"[1:a]atrim={ts:.3f}:{te:.3f},asetpts=PTS-STARTPTS,apad,atrim=0:{d:.3f},afade=in:d=0.08,"
          f"afade=out:st={max(0, d - 0.15):.3f}:d=0.15[au]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ref, "-i", test, "-filter_complex", fc, "-map", "[v]",
                    "-map", "[au]"] + ENC + [out], check=True)


def compare(name, rs, re_, ts, te, render=True):
    d = work(name)
    sb = os.path.join(d, "testbed", "work", "sandbox", "new", "public")
    test = os.path.join(d, "test.mp4")
    if render:
        if not os.path.exists(os.path.join(sb, "index.html")):
            sys.exit("nothing to render yet: run `try` first")
        hf(["check"], sb)
        print("rendering the test (the whole take, a few minutes) ...", flush=True)
        hf(["render", "-q", "draft", "--quiet", "-o", test], sb)
    side_by_side(os.path.join(d, "ref.mp4"), rs, re_, test, ts, te, os.path.join(d, "compare.mp4"))
    state(name, ref_window=[rs, re_], test_window=[ts, te])
    print(os.path.join(d, "compare.mp4"))


# ------------------------------------------------------------------ review
def theme(S, out):
    sys.path.insert(0, os.path.join(KIT, "pipeline"))
    from storyboard import theme_css
    return theme_css(S, out)


def review(name):
    d = work(name)
    R = json.load(open(os.path.join(d, "review.json")))
    out = os.path.join(d, "review")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "media"))
    fid = R["folder"]
    shutil.copy(os.path.join(d, "compare.mp4"), os.path.join(out, "media", f"{fid}.mp4"))
    li = lambda xs: "".join(f"<li>{esc(x)}</li>" for x in xs)                       # noqa: E731
    flag = f'<p class="flag">{esc(R["flag"])}</p>' if R.get("flag") else ""
    sec = f"""  <section class="fx" id="{esc(fid)}">
    <div class="film">
      <div class="labels" aria-hidden="true"><span>Reference</span><span>Yours</span></div>
      <video id="v-{esc(fid)}" src="media/{esc(fid)}.mp4" controls playsinline preload="metadata" aria-label="{esc(R['name'])}: the reference left, yours right"></video>
      <div class="src">{esc(R['source'])} · {esc(R['window'])}</div>
    </div>
    <div class="read">
      <h2>{esc(R['name'])}</h2>
      <p class="line">{esc(R['line'])}</p>
      <p class="does">{esc(R['does'])}</p>
      <div class="cols">
        <div><h3>Taken from the reference</h3><ul>{li(R['copied'])}</ul></div>
        <div><h3>Made yours</h3><ul>{li(R['changed'])}</ul></div>
      </div>
      <dl class="meta">
        <div><dt>Reach for it when</dt><dd>{esc(R['reach'])}</dd></div>
        <div><dt>You supply</dt><dd>{esc(R['supply'])}</dd></div>
      </dl>
      {flag}
      <p class="rec"><b>Claude recommends:</b> {esc(R['recommend'])}</p>
      <div class="verdict">
        <fieldset class="choices">
          <legend>Verdict</legend>
          <label><input type="radio" name="v-{esc(fid)}" value="keep"><span>Keep</span></label>
          <label><input type="radio" name="v-{esc(fid)}" value="fix"><span>Fix</span></label>
          <label><input type="radio" name="v-{esc(fid)}" value="drop"><span>Drop</span></label>
        </fieldset>
        <textarea aria-label="Note on {esc(R['name'])}" placeholder="What should change? (needed for Fix)"></textarea>
        <div class="row"><span class="status" aria-live="polite"></span></div>
      </div>
    </div>
  </section>"""
    proj = state(name).get("project", "")
    page = open(os.path.join(KIT, "effect", "review.html")).read()
    for k, v in [("__THEME__", theme(ST.load(), out)), ("__TITLE__", esc("New effect: " + R["name"])),
                 ("__DATE__", esc(datetime.date.today().strftime("%b %-d, %Y") if os.name != "nt" else datetime.date.today().isoformat())),
                 ("__TESTBED__", esc(os.path.basename(proj) or "your footage")), ("__EFFECTS__", sec)]:
        page = page.replace(k, v)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)
    files = sorted(f"{s}/{n}" for s in ("media", "fonts") for n in os.listdir(os.path.join(out, s)))
    json.dump(files, open(os.path.join(out, "files.json"), "w"), indent=1)
    print(f"{out}/index.html (+ {len(files)} files in files.json)")


# ------------------------------------------------------------------ keep
HEADER = """# My effects

Effects made for me (`{cmd}effect`) and my own versions of the kit's. Same table as the kit's `fx/LIBRARY.md`; a
folder here with the same name as one in the kit is the one that gets used. The kit's updates never touch this folder.

| folder | layer | what it does | reach for it when the line says | supply |
|---|---|---|---|---|
"""


def cell(s):
    return str(s).replace("|", "/").replace("\n", " ").strip()


def keep(name):
    d = work(name)
    R, S = json.load(open(os.path.join(d, "review.json"))), state(name)
    folder, fid = R["folder"], S["id"]
    dest = os.path.join(MINE, folder)
    os.makedirs(MINE, exist_ok=True)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(os.path.join(d, "testbed", "fx", fid), dest)
    for f in ("BREAKDOWN.md",):
        if os.path.exists(os.path.join(d, f)):
            shutil.copy(os.path.join(d, f), dest)
    ts, te = S["test_window"]
    test = os.path.join(d, "test.mp4")
    a, b = max(0.0, ts - 0.3), te + 0.3
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", test, "-t", f"{b - a:.3f}", "-vf",
                    "scale=540:960:flags=lanczos", "-af", f"afade=in:d=0.12,afade=out:st={b - a - 0.15:.3f}:d=0.15"]
                   + ENC + [os.path.join(dest, "preview.mp4")], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{(ts + te) / 2:.3f}", "-i", test, "-frames:v", "1", "-vf",
                    "scale=540:960:flags=lanczos", "-q:v", "3", os.path.join(dest, "preview.jpg")], check=True)
    lib = os.path.join(MINE, "LIBRARY.md")
    text = open(lib).read() if os.path.exists(lib) else HEADER.format(cmd=CMD)
    row = (f"| `{folder}` | {cell(R['layer'])} | {cell(R['does'])} | {cell(R['reach'])} | {cell(R['supply'])} |")
    lines = [ln for ln in text.rstrip("\n").split("\n") if not ln.startswith(f"| `{folder}`")]
    open(lib, "w").write("\n".join(lines + [row]) + "\n")
    log = os.path.join(EFFECTS, "LOG.md")
    if not os.path.exists(log):
        open(log, "w").write("# New effects\n\n| date | effect | from | seconds | verdict |\n|---|---|---|---|---|\n")
    with open(log, "a") as fh:
        fh.write(f"| {datetime.date.today().isoformat()} | `{folder}` | {cell(R['source'])} | {cell(R['window'])} | keep |\n")
    print(f"kept: {dest}  (row added to {lib})")
    library()


# ------------------------------------------------------------------ library page
def rows(path):
    if not os.path.exists(path):
        return []
    return [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in open(path) if ln.startswith("| `")]


def inline(s):
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(s))


def plain(s):
    return re.sub(r"[`*]", "", s)


def card(cells, base, cover=False):
    head, layer, does, reach, supply = (cells + [""] * 5)[:5]
    folder = re.match(r"`([^`]+)`", head).group(1)
    name = folder.replace("-", " ").capitalize()
    d = os.path.join(base, folder)
    mp4, jpg = os.path.join(d, "preview.mp4"), os.path.join(d, "preview.jpg")
    uri = lambda p: Path(p).as_uri()                                                  # noqa: E731
    if os.path.exists(mp4):
        # the creator's stills are frames of the effect itself (a cover); the kit's are the lab stand-in (a fallback)
        poster = (f' poster="{uri(jpg)}"' if cover else f' data-still="{uri(jpg)}"') if os.path.exists(jpg) else ""
        # "#t=0.4": without a cover, Safari paints nothing until it plays; this opens on a frame inside the effect
        media = (f'<video src="{uri(mp4)}{"" if cover else "#t=0.4"}"{poster} muted loop playsinline preload="metadata" '
                 f'aria-label="{esc(name)} preview, tap for sound"></video>')
    elif os.path.exists(jpg):
        media = f'<img src="{uri(jpg)}" alt="{esc(name)} preview" loading="lazy">'
    else:
        media = '<div class="none">No preview yet</div>'
    find = esc(" ".join([folder, name, plain(layer), plain(does), plain(reach), plain(supply)]).lower())
    return f"""    <article class="card" data-find="{find}">
      <div class="media">{media}</div>
      <div class="body">
        <h3>{esc(name)}</h3>
        <p class="tag"><button class="name" type="button" data-name="{esc(folder)}" title="Copy the name">{esc(folder)}</button><span>{esc(plain(layer))}</span></p>
        <p class="reach"><b>Reach for it when</b> {inline(reach)}</p>
        <details><summary>What it does</summary><p>{inline(does)}</p><p class="supply"><b>You supply</b> {inline(supply)}</p></details>
      </div>
    </article>"""


def section(title, note, cards):
    if not cards:
        return ""
    return f"""  <section class="group">
    <div class="ghead"><h2>{esc(title)}</h2><span class="count">{len(cards)}</span></div>
    <p class="note">{esc(note)}</p>
    <div class="grid">
{chr(10).join(cards)}
    </div>
  </section>"""


def library(open_it=False):
    os.makedirs(EFFECTS, exist_ok=True)
    mine = rows(os.path.join(MINE, "LIBRARY.md"))
    own = {re.match(r"`([^`]+)`", r[0]).group(1) for r in mine}
    kit = [r for r in rows(os.path.join(KIT, "fx", "LIBRARY.md")) if re.match(r"`([^`]+)`", r[0]).group(1) not in own]
    yours = section("Your effects", "Made for you from videos you sent, and your own versions of the kit's. "
                    "They're already in your brand style.", [card(r, MINE, cover=True) for r in mine])
    if not mine:
        yours = ('  <section class="group">\n    <div class="ghead"><h2>Your effects</h2><span class="count">0</span></div>\n'
                 f'    <p class="note">None yet. Send any video you like and the seconds the effect plays: <code>{CMD}effect clip.mp4 17-19</code></p>\n  </section>')
    sections = "\n".join([yours, section(
        "Kit", "Built by Justyn AI. The previews show the Justyn AI look; in your videos every one renders in your "
        "own brand colours, fonts and style.", [card(r, os.path.join(KIT, "fx")) for r in kit])])
    page = open(os.path.join(KIT, "effect", "library.html")).read()
    page = (page.replace("__THEME__", theme(ST.load(), EFFECTS)).replace("__TOTAL__", str(len(mine) + len(kit)))
            .replace("__CMD__", CMD).replace("__SECTIONS__", sections))
    out = os.path.join(EFFECTS, "index.html")
    open(out, "w", encoding="utf-8").write(page)
    print(f"{out}  ({len(mine)} yours, {len(kit)} kit)")
    if open_it:
        webbrowser.open(Path(out).as_uri())


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    step = a[0]
    if step == "library":
        return library("--open" in a)
    if len(a) < 2:
        sys.exit(__doc__)
    name = a[1]
    if step == "fetch":
        fetch(name, a[2])
    elif step == "look":
        look(name, float(a[2]), float(a[3]), float(a[a.index("--fps") + 1]) if "--fps" in a else None)
    elif step == "measure":
        measure(name, float(a[2]), float(a[3]), [int(x) for x in a[4].split(",")] if len(a) > 4 else None)
    elif step == "testbed":
        testbed(name, a[2] if len(a) > 2 else None)
    elif step == "try":
        try_(name, a[2], [float(x) for x in a[a.index("--at") + 1:]])
    elif step == "compare":
        compare(name, *[float(x) for x in a[2:6]], render="--no-render" not in a)
    elif step == "review":
        review(name)
    elif step == "keep":
        keep(name)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
