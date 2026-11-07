#!/usr/bin/env python3
"""Makes the cover: the picked frame with the hook on it in the design system's hook style, sized so the text stays above
the face and inside the profile grid's 3:4 crop. Writes cover/cover_<version>.jpg and a grid preview for each version.
Usage: python3 make_cover.py <work folder> <design-system.json> --pick <n> [--lines '[{"text":"..","size":"small|mid|big"}]']
Without --lines it uses the hook from pops_plan.json. Makes version A (all lines) and B (without the last line)."""
import html, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@800;900&family=Instrument+Serif:ital@0;1&family=Gloock'
         '&family=Anton&family=Calistoga&family=Bricolage+Grotesque:opsz,wght@12..96,800&display=block" rel="stylesheet">')
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if len(a) < 2 or '--pick' not in a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); ds = json.load(open(Path(a[1]).expanduser())); pick = int(a[a.index('--pick') + 1])
cd = d / 'cover'; cands = json.load(open(cd / 'candidates.json')); cand = cands[pick - 1]; F = ff('ffmpeg')
if '--lines' in a: lines = json.loads(a[a.index('--lines') + 1])
else:
    hook = next((el for el in json.load(open(d / 'pops_plan.json'))['elements'] if el['type'] == 'hook'), None)
    if not hook: sys.exit('No hook in pops_plan.json. Pass --lines.')
    lines = hook['lines']
c = ds.get('colors', {}); KEY, OUT = c.get('key', '#ffe94d'), c.get('outline', '#14080f')
PAL = [c.get('accent', '#ddd0ff'), KEY, '#fff3c4', c.get('accent2', '#ffb3d1')]
HOOK = {'bubbly': ("Calistoga", '#2b1660', '400', 'normal'), 'editorial': ("'Inter Tight'", OUT, '900', 'normal'),
        'soft_serif': ("'Instrument Serif'", OUT, '400', 'italic'), 'poster': ("Anton", OUT, '400', 'normal'), 'grotesk': ("'Bricolage Grotesque'", OUT, '800', 'normal')}
fam, oc, wt, st = HOOK.get(ds.get('hook', {}).get('style', 'bubbly'), HOOK['bubbly'])
SIZE = {'small': 84, 'mid': 140, 'big': 250}
# where the face sits on the full-size still (candidate boxes are fractions of the frame)
GRID_TOP, GRID_BOT = 240, 1680
face_top = cand.get('y', 0.35) * 1920 if cand.get('h') else 1100
limit = max(GRID_TOP + 200, face_top - 90)               # text must end above the hair (the face box starts at the forehead)
tmp = Path(tempfile.mkdtemp()); still = Path(cand['still'])
bg = tmp / 'bg.jpg'; subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(still), '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920', '-q:v', '2', str(bg)], check=True)
made = []
for ver, ls in (('A', lines), ('B', lines[:-1] if len(lines) > 2 else None)):
    if not ls: continue
    body = ''.join(f'<div style="font:{st} {wt} {SIZE.get(x.get("size", "mid"), 140)}px/1.05 {fam};color:{KEY if x.get("size") == "big" else PAL[i % len(PAL)]};'
                   f'-webkit-text-stroke:{max(7, SIZE.get(x.get("size", "mid"), 140) // 16)}px {oc};paint-order:stroke fill;text-shadow:0 8px 0 {oc},0 14px 30px rgba(0,0,0,.35);'
                   f'transform:rotate({(-2, -4, 2, -3)[i % 4]}deg);white-space:nowrap">{html.escape(x["text"])}</div>' for i, x in enumerate(ls))
    js = (f'<script>document.fonts.ready.then(()=>{{const b=document.getElementById("b");let s=1;const fit=()=>{{b.style.transform="scale("+s+")";'
          f'const r=b.getBoundingClientRect();return r.bottom<={limit}&&r.left>=70&&r.right<=1010}};while(!fit()&&s>0.5)s-=0.02;document.body.dataset.scale=s.toFixed(2);'
          f'const r=b.getBoundingClientRect();document.body.dataset.box=[r.left,r.top,r.right,r.bottom].map(Math.round).join(",")}})</script>')
    page = (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>*{{margin:0}}body{{width:1080px;height:1920px;background:url(bg.jpg) center/cover;position:relative;overflow:hidden}}'
            f'#b{{position:absolute;left:0;right:0;top:{GRID_TOP + 40}px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:6px;transform-origin:50% 0}}</style></head>'
            f'<body><div id="b">{body}</div>{js}</body></html>')
    pf = tmp / f'{ver}.html'; pf.write_text(page); png = tmp / f'{ver}.png'
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1080,1920', '--virtual-time-budget=9000', f'--screenshot={png}', f'file://{pf}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--window-size=1080,1920', '--virtual-time-budget=9000', '--dump-dom', f'file://{pf}'], capture_output=True, text=True).stdout
    sc = re.search(r'data-scale="([\d.]+)"', dom); box = re.search(r'data-box="([-\d,]+)"', dom)
    out = cd / f'cover_{ver}.jpg'; subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(png), '-q:v', '2', str(out)], check=True)
    grid = cd / f'cover_{ver}_grid.jpg'
    subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(png), '-vf', f'crop=1080:{GRID_BOT - GRID_TOP}:0:{GRID_TOP},scale=360:-2', '-q:v', '3', str(grid)], check=True)
    made.append({'version': ver, 'cover': str(out), 'grid_preview': str(grid), 'text_scale': float(sc.group(1)) if sc else None, 'text_box': box.group(1) if box else None})
subprocess.run([F, '-nostdin', '-v', 'error', '-y'] + sum((['-i', m['cover']] for m in made), []) + ['-filter_complex', ''.join(f'[{i}]scale=360:-2[s{i}];' for i in range(len(made))) + ''.join(f'[s{i}]' for i in range(len(made))) + f'hstack=inputs={len(made)}' if len(made) > 1 else '[s0]copy', '-q:v', '3', str(cd / 'versions.jpg')], check=True)
shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps({'face_top': round(face_top), 'text_must_end_above': round(limit), 'versions': made}, indent=1))
