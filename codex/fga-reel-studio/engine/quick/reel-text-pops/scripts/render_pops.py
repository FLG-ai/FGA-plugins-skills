#!/usr/bin/env python3
"""Adds the big text moments from pops_plan.json to captioned.mp4, each popping in on its word, in the design system's look.
Usage: python3 render_pops.py <work folder> <design-system.json>
Writes popped.mp4, popped_preview.mp4 and pops_report.txt (timings and safe-zone check). Needs Chrome and ffmpeg."""
import html, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@800;900&family=Instrument+Serif:ital@0;1&family=Gloock'
         '&family=Anton&family=Montserrat:ital,wght@1,900&family=Calistoga&family=Archivo+Black&family=Bricolage+Grotesque:opsz,wght@12..96,800&display=block" rel="stylesheet">')
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if len(a) < 2: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); ds = json.load(open(Path(a[1]).expanduser()))
F = ff('ffmpeg'); FPS = 30; e = html.escape
c = ds.get('colors', {}); KEY, TXT, OUT = c.get('key', '#ffe94d'), c.get('text', '#ffffff'), c.get('outline', '#14080f')
PAL = [c.get('accent', '#ddd0ff'), KEY, c.get('accent2', '#ffb3d1'), '#fff3c4', TXT]
sz = ds.get('safe_zone', {}); TOP, BOT, SIDE, BX, BY = sz.get('top', 250), sz.get('bottom', 1480), sz.get('side', 60), sz.get('buttons_x', 940), sz.get('buttons_y', 1050)
words = json.load(open(d / 'words_tight.json')); plan = json.load(open(d / 'pops_plan.json'))
total = round(float(subprocess.run([ff('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(d / 'captioned.mp4')], capture_output=True, text=True).stdout) * FPS)

def ol(w, col=OUT, drop=0): return f'-webkit-text-stroke:{w}px {col};paint-order:stroke fill;text-shadow:0 {drop}px 0 {col},0 14px 30px rgba(0,0,0,.35);'
HOOK = {  # font, outline colour, weight/style per hook style
    'bubbly': ("Calistoga", '#2b1660', '400', 'normal'), 'editorial': ("'Inter Tight'", OUT, '900', 'normal'),
    'soft_serif': ("'Instrument Serif'", OUT, '400', 'italic'), 'poster': ("Anton", OUT, '400', 'normal'), 'grotesk': ("'Bricolage Grotesque'", OUT, '800', 'normal')}
hf = HOOK.get(ds.get('hook', {}).get('style', 'bubbly'), HOOK['bubbly'])
SIZE = {'small': 78, 'mid': 124, 'big': 220}
def line(text, px, col, rot=0, font=hf):
    fam, oc, wt, st = font
    return (f'<div class="fit" style="font:{st} {wt} {px}px/1.05 {fam};color:{col};{ol(max(6, px // 16), oc, max(5, px // 18))}'
            f'transform:rotate({rot}deg);white-space:nowrap">{e(text)}</div>')
def block(top, inner, center=False):
    pos = f'top:{top}px' if not center else f'top:{top}px;transform:translateY(-50%)'
    return f'<div class="el" style="position:absolute;left:0;right:0;{pos};display:flex;flex-direction:column;align-items:center;text-align:center;gap:6px">{inner}</div>'

def element_html(el, idx_line=None):
    t = el['type']
    if t == 'hook':
        # each hook line is its own layer, drawn inside the full stack so it sits exactly where it will in the finished header
        inner = ''.join(f'<div style="visibility:{"visible" if i == idx_line else "hidden"}">{line(x["text"], SIZE.get(x.get("size", "mid"), 124), PAL[i % len(PAL)] if x.get("size") != "big" else KEY, (-2, -4, 2, -3)[i % 4])}</div>'
                        for i, x in enumerate(el['lines']))
        return block(el.get('top', 270), inner)
    if t == 'number':
        np_ = ds.get('number_pop', {}); col = np_.get('color', 'key'); col = col if str(col).startswith('#') else c.get(col, KEY)
        fam = f"'{np_.get('font', 'Anton')}'"
        inner = (f'<div class="fit" style="font:400 {np_.get("px", 460)}px/.9 {fam};color:{col};{ol(16, OUT, 18)}transform:rotate({np_.get("rotate", -4)}deg)">{e(el["text"])}</div>'
                 + (f'<div class="fit" style="font:400 130px/1 Anton;color:{TXT};{ol(11, OUT, 10)}transform:rotate({np_.get("rotate", -4)}deg);margin-top:-8px">{e(el["sub"])}</div>' if el.get('sub') else ''))
        return block(el.get('y', 960), inner, center=True)
    if t == 'list':
        lc = ds.get('list_cards', {})
        inner = (f'<div style="font:400 150px/.95 \'{lc.get("number_font", "Anton")}\';color:{KEY};{ol(9, OUT, 9)}transform:rotate(-3deg)">{e(el["n"])}</div>'
                 f'<div class="fit" style="font:400 66px/1.1 \'{lc.get("label_font", "Archivo Black")}\';color:{KEY};{ol(9, OUT, 8)}transform:rotate(-3deg);white-space:nowrap">&#10003; {e(el["label"])}</div>')
        return block(lc.get('y', 330), inner)
    if t == 'word':
        wp = ds.get('word_pops', {}); fam = wp.get('font', 'Instrument Serif'); st = wp.get('font_style', 'italic')
        o = ol(9, '#2b1660', 7) if fam == 'Calistoga' else ol(4, OUT, 3)
        return (f'<div class="el" style="position:absolute;left:{el.get("x", 140)}px;top:{el.get("y", 520)}px;font:{st} 400 130px/1 \'{fam}\';'
                f'color:{el.get("color", PAL[el.get("_i", 0) % len(PAL)])};{o}transform:rotate({el.get("rot", -6)}deg);white-space:nowrap">{e(el["text"])}</div>')
    if t == 'series':
        stf = ds.get('series_title', {}).get('font', 'Calistoga'); font = (f"'{stf}'", '#2b1660' if stf == 'Calistoga' else OUT, '400', 'normal')
        ls = el['lines']; inner = ''.join(line(x, 150 if i < len(ls) - 1 else 110, PAL[i % len(PAL)], (-4, 3, -2, -7)[i % 4], font) for i, x in enumerate(ls))
        return block(el.get('y', 1000), inner, center=True)
    if t == 'cta':
        stf = ds.get('series_title', {}).get('font', 'Calistoga'); font = (f"'{stf}'", '#2b1660' if stf == 'Calistoga' else OUT, '400', 'normal')
        return block(el.get('top', 280), line(el.get('small', 'comment'), 110, PAL[0], -4, font) + line(el['big'], 150, '#fff3c4', 2, font))
    raise SystemExit(f'unknown type {t}')

def wstart(i): return words[i]['s'] if 0 <= i < len(words) else total / FPS
layers = []  # each layer: html, start frame, end frame, label
for k, el in enumerate(plan['elements']):
    el['_i'] = k
    start = el.get('at', wstart(el['at_word']) if 'at_word' in el else 0.0)
    end = wstart(el['until_word']) if 'until_word' in el else (total / FPS if el['type'] in ('cta',) else start + el.get('hold', 2.5))
    if el['type'] == 'hook':
        for i, x in enumerate(el['lines']):
            layers.append({'html': element_html(el, i), 'fs': round((start + 0.12 * i) * FPS), 'fe': round(end * FPS), 'label': f"hook: {x['text']}"})
    elif el['type'] == 'series':
        layers.append({'html': element_html(el), 'fs': round(start * FPS), 'fe': round(end * FPS), 'label': 'series: ' + ' / '.join(el['lines'])})
    else:
        layers.append({'html': element_html(el), 'fs': round(start * FPS), 'fe': round(end * FPS), 'label': f"{el['type']}: {el.get('text') or el.get('label') or el.get('big')}"})

# draw every layer at three pop scales (one tall page per layer), measure it, crop the three frames
tmp = Path(tempfile.mkdtemp()); rep = []
JS = (f'<script>/* fit wide text so it clears the side edges and the button column */' 'document.fonts.ready.then(()=>{document.querySelectorAll(".fit").forEach(x=>{let f=parseFloat(getComputedStyle(x).fontSize),n=0;'
      f'while(x.getBoundingClientRect().width>{2 * (BX - 540) - 10}&&n<40){{f*=0.95;x.style.fontSize=f+"px";n++}}}});'
      'document.querySelectorAll(".page").forEach((p,i)=>{let b=null;p.querySelectorAll(".el *").forEach(z=>{if(getComputedStyle(z).visibility=="hidden"||!z.textContent.trim())return;const r=z.getBoundingClientRect();'
      'if(!r.width)return;b=b?{l:Math.min(b.l,r.left),t:Math.min(b.t,r.top),r:Math.max(b.r,r.right),b:Math.max(b.b,r.bottom)}:{l:r.left,t:r.top,r:r.right,b:r.bottom}});'
      'if(b)p.dataset.box=[b.l,b.t-i*1920,b.r,b.b-i*1920].map(Math.round).join(",")})})</script>')
for n, L in enumerate(layers):
    pages = ''.join(f'<div class="page" style="position:absolute;left:0;top:{s * 1920}px;width:1080px;height:1920px;overflow:hidden">'
                    f'<div style="position:absolute;inset:0;transform:scale({sc});transform-origin:50% 45%">{L["html"]}</div></div>' for s, sc in enumerate((0.84, 1.06, 1.0)))
    pf = tmp / f'l{n}.html'
    pf.write_text(f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>*{{margin:0;box-sizing:border-box}}body{{width:1080px;height:5760px;background:transparent}}</style></head><body>{pages}{JS}</body></html>')
    png = tmp / f'l{n}.png'
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--default-background-color=00000000', '--window-size=1080,5760',
                    '--virtual-time-budget=10000', f'--screenshot={png}', f'file://{pf}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--window-size=1080,5760', '--virtual-time-budget=10000', '--dump-dom', f'file://{pf}'], capture_output=True, text=True).stdout
    boxes = re.findall(r'data-box="([-\d,]+)"', dom); box = [int(v) for v in boxes[-1].split(',')] if boxes else None
    for s in range(3):
        subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(png), '-vf', f'crop=1080:1920:0:{s * 1920}', str(tmp / f'l{n}_{s}.png')], check=True)
    if box:
        x0, y0, x1, y1 = box
        bad = [m for m, cnd in (('top', y0 < TOP), ('bottom', y1 > BOT), ('side', x0 < SIDE or x1 > 1080 - SIDE), ('buttons', x1 > BX and y1 > BY)) if cnd]
        if bad: rep.append(f"{L['label']}: {', '.join(bad)} (box {box})")

# overlay every layer frame-exactly: pop frame 1, pop frame 2, then the settled frame until its end.
# Each image input only exists for its own window (-t and -itsoffset), so the render stays quick.
cmd = [F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'captioned.mp4')]
fc, last, idx = [], '[0:v]', 1
for n, L in enumerate(layers):
    fs, fe = L['fs'], max(L['fe'], L['fs'] + 3)
    for s, (a0, a1) in enumerate(((fs, fs + 1), (fs + 1, fs + 2), (fs + 2, fe))):
        cmd += ['-loop', '1', '-framerate', str(FPS), '-t', f'{(a1 - a0) / FPS:.4f}', '-itsoffset', f'{a0 / FPS:.4f}', '-i', str(tmp / f'l{n}_{s}.png')]
        out = f'[o{idx}]'; fc.append(f"{last}[{idx}:v]overlay=0:0:eof_action=pass:repeatlast=0{out}"); last = out; idx += 1
fc.append(f'{last}format=yuv420p[v]')
cmd += ['-filter_complex', ';'.join(fc), '-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-r', str(FPS), '-c:a', 'copy', str(d / 'popped.mp4')]
subprocess.run(cmd, check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'popped.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'popped_preview.mp4')], check=True)
lines = [f"{L['fs'] / FPS:6.2f}-{L['fe'] / FPS:6.2f}  {L['label']}" for L in layers]
(d / 'pops_report.txt').write_text('\n'.join(lines) + '\n\n' + ('\n'.join(rep) if rep else 'Every text moment is inside the safe zone.') + '\n')
shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps({'layers': len(layers), 'safe_zone_problems': len(rep)}))
