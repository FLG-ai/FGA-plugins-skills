#!/usr/bin/env python3
"""Captions every word of framed.mp4 in the design system's style, one word at a time with a small pop.
Usage: python3 render_captions.py <work folder> <design-system.json>
Reads windowed.mp4 (from reel-windows) when it exists and is newer than framed.mp4, else framed.mp4.
Writes captioned.mp4, captioned_preview.mp4, captions.srt and captions_report.txt (safe-zone check). Needs Chrome and ffmpeg."""
import html, json, shutil, subprocess, sys, tempfile, re
from pathlib import Path

HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from caption_styles import FONTS, word_css
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if len(a) < 2: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); ds = json.load(open(Path(a[1]).expanduser()))
F = ff('ffmpeg'); FPS = 30; CELL = 420
cap = ds.get('captions', {}); style = cap.get('style', 'italic_punch'); colors = ds.get('colors', {})
sz = ds.get('safe_zone', {}); TOP, BOT, SIDE, BX, BY = sz.get('top', 250), sz.get('bottom', 1480), sz.get('side', 60), sz.get('buttons_x', 940), sz.get('buttons_y', 1050)
Y = cap.get('y', 400 if style == 'small_top' else 1360)            # centre of a normal caption
YS = min(cap.get('under_windows', {}).get('y', 1400), 1400)                     # centre of a small caption
SRC = d / 'windowed.mp4' if (d / 'windowed.mp4').exists() and (d / 'windowed.mp4').stat().st_mtime >= (d / 'framed.mp4').stat().st_mtime else d / 'framed.mp4'
words = json.load(open(d / 'words_tight.json')); plan = json.load(open(d / 'captions_plan.json'))
inr = lambda i, rs: any(x <= i <= y for x, y in rs)
key = set(plan.get('key', []))
units = []
for k, w in enumerate(words):
    if inr(w['i'], plan.get('skip', [])): continue
    nxt = words[k + 1]['s'] if k + 1 < len(words) else w['e'] + 0.5
    end = nxt if nxt - w['e'] < 0.6 else w['e'] + 0.35               # hold to the next word, or a beat after a pause
    fs, fe = round(w['s'] * FPS), max(round(end * FPS), round(w['s'] * FPS) + 4)
    t = re.sub(r'[.,!?;:"]+$', '', w['t']).strip() or w['t']
    units.append({'i': w['i'], 'text': t, 'key': w['i'] in key, 'small': inr(w['i'], plan.get('small', [])), 'fs': fs, 'fe': fe})
for u, v in zip(units, units[1:]): u['fe'] = min(u['fe'], v['fs'])   # never overlap the next word

# draw each distinct word once at three pop scales, with a fit-to-width step so long words shrink
tmp = Path(tempfile.mkdtemp()); cells, meas = {}, {}
for u in units:
    lower = (Y if not u['small'] else YS) + CELL / 2 > BY
    ow = cap.get('outline', 8)
    maxw = ((2 * (BX - 540) - 20) if lower else (1080 - 2 * SIDE - 20)) / 1.06 - 2 * ow   # allow for the pop, the outline and italic overhang
    u['key_id'] = f"{u['text']}|{u['key']}|{u['small']}"
    cells.setdefault(u['key_id'], (u, maxw))
items = list(cells.items())
def page(batch):
    body = ''
    for n, (kid, (u, maxw)) in enumerate(batch):
        for s, sc in enumerate((0.82, 1.06, 1.0)):
            body += (f'<div class="c" style="top:{(n * 3 + s) * CELL}px"><span class="w" data-max="{maxw}" data-id="{n}_{s}" style="{word_css(style, colors, u["key"], u["small"])};'
                     f'transform:scale({sc})">{html.escape(u["text"])}</span></div>')
    js = ('<script>document.fonts.ready.then(()=>{document.querySelectorAll(".w").forEach(e=>{const m=+e.dataset.max;let f=parseFloat(getComputedStyle(e).fontSize);'
          'let n=0;while(e.offsetWidth>m&&n<40){f*=0.95;e.style.fontSize=f+"px";n++}const r=e.getBoundingClientRect();e.dataset.w=Math.round(e.offsetWidth);e.dataset.h=Math.round(e.offsetHeight)});'
          'document.body.dataset.done=1})</script>')
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>*{{margin:0}}body{{width:1080px;background:transparent}}'
            f'.c{{position:absolute;left:0;width:1080px;height:{CELL}px;display:flex;align-items:center;justify-content:center}}.w{{white-space:nowrap;display:inline-block}}</style></head>'
            f'<body style="height:{len(batch) * 3 * CELL}px">{body}{js}</body></html>')
PER = 12
for b in range(0, len(items), PER):
    batch = items[b:b + PER]; pf = tmp / f'p{b}.html'; pf.write_text(page(batch)); png = tmp / f'p{b}.png'
    h = len(batch) * 3 * CELL
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--default-background-color=00000000', f'--window-size=1080,{h}',
                    '--virtual-time-budget=10000', f'--screenshot={png}', f'file://{pf}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', f'--window-size=1080,{h}', '--virtual-time-budget=10000', '--dump-dom', f'file://{pf}'],
                         capture_output=True, text=True).stdout
    for n, (kid, _) in enumerate(batch):
        m = re.search(rf'data-id="{n}_2"[^>]*data-w="(\d+)" data-h="(\d+)"', dom) or re.search(rf'data-w="(\d+)" data-h="(\d+)"[^>]*data-id="{n}_2"', dom)
        meas[kid] = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        for s in range(3):
            out = tmp / f'cell_{b + n}_{s}.png'
            subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(png), '-vf', f'crop=1080:{CELL}:0:{(n * 3 + s) * CELL}', str(out)], check=True)
        cells[kid] = (b + n, cells[kid][1])

# two caption tracks (normal and small) as image sequences with exact frame timings, overlaid at their own heights
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=black@0:s=1080x{CELL},format=rgba', '-frames:v', '1', str(tmp / 'blank.png')], check=True)
total = round(float(subprocess.run([ff('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(SRC)], capture_output=True, text=True).stdout) * FPS)
def track(small):
    # one link per video frame, pointing at the right caption image, so every word lands on its exact frame
    td = tmp / f'track_{int(small)}'; td.mkdir()
    frames = [tmp / 'blank.png'] * total
    for u in [x for x in units if x['small'] == small]:
        n = cells[u['key_id']][0]
        for f in range(u['fs'], min(u['fe'], total)):
            s = 0 if f == u['fs'] else 1 if f == u['fs'] + 1 else 2
            frames[f] = tmp / f'cell_{n}_{s}.png'
    for f, src in enumerate(frames): (td / f'f_{f:05d}.png').symlink_to(src)
    return td
t0, t1 = track(False), track(True)
fc = (f"[1:v]format=rgba[c0];[2:v]format=rgba[c1];[0:v][c0]overlay=0:{int(Y - CELL / 2)}:eof_action=pass[x];"
      f"[x][c1]overlay=0:{int(YS - CELL / 2)}:eof_action=pass,format=yuv420p[v]")
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(SRC), '-framerate', str(FPS), '-i', str(t0 / 'f_%05d.png'), '-framerate', str(FPS), '-i', str(t1 / 'f_%05d.png'),
                '-filter_complex', fc, '-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-r', str(FPS), '-c:a', 'copy', str(d / 'captioned.mp4')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'captioned.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'captioned_preview.mp4')], check=True)
# safe-zone check from the measured size of every word, and an .srt for the record
rep = []
for u in units:
    w, h = meas.get(u['key_id'], (0, 0)); cy = YS if u['small'] else Y
    x0, x1, y0, y1 = 540 - w / 2, 540 + w / 2, cy - h / 2, cy + h / 2
    bad = [n for n, c in (('top', y0 < TOP), ('bottom', y1 > BOT), ('side', x0 < SIDE or x1 > 1080 - SIDE), ('buttons', x1 > BX and y1 > BY)) if c]
    if bad: rep.append(f"'{u['text']}' at {u['fs'] / FPS:.2f}s: {', '.join(bad)} (w {w}, h {h})")
tc = lambda f: f"{int(f // FPS // 3600):02d}:{int(f // FPS % 3600 // 60):02d}:{int(f // FPS % 60):02d},{int(f % FPS * 1000 / FPS):03d}"
(d / 'captions.srt').write_text(''.join(f"{n + 1}\n{tc(u['fs'])} --> {tc(u['fe'])}\n{u['text']}\n\n" for n, u in enumerate(units)))
(d / 'captions_report.txt').write_text(f"{len(units)} words captioned, {len(words) - len(units)} skipped by plan\n" + ('\n'.join(rep) if rep else 'Every caption is inside the safe zone.') + '\n')
shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps({'captioned': len(units), 'skipped': len(words) - len(units), 'safe_zone_problems': len(rep)}))
