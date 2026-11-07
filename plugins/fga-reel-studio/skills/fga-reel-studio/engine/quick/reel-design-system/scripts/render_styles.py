#!/usr/bin/env python3
"""Renders reel style stills over a real frame with headless Chrome. Standard library only.

  python3 render_styles.py options  <out_dir> [--bg frame.jpg]
      One labelled still per starter option (captions A-D, titles A-E, number pops A-C, word pops A-B),
      plus options.jpg, a contact sheet to show the person when they pick.
  python3 render_styles.py system   <design-system.json> <out_dir> [--bg frame.jpg]
      One still per element of their finished design system: captions, hook, number, list, wordpops, series.
"""
import json, shutil, subprocess, sys, tempfile, html
from pathlib import Path

CHROME = next((p for p in ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                           '/Applications/Chromium.app/Contents/MacOS/Chromium', shutil.which('google-chrome') or '']
               if p and Path(p).exists()), None)
FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;800;900&family=Instrument+Serif:ital@0;1'
         '&family=Gloock&family=Anton&family=Montserrat:ital,wght@1,900&family=Calistoga&family=Archivo+Black'
         '&family=Bricolage+Grotesque:opsz,wght@12..96,800&display=block" rel="stylesheet">')

def ol(w, c='#14080f', drop=0):
    s = f'-webkit-text-stroke:{w}px {c};paint-order:stroke fill;'
    return s + (f'text-shadow:0 {drop}px 0 {c};' if drop else 'text-shadow:0 2px 3px rgba(0,0,0,.5),0 0 18px rgba(0,0,0,.55);')

# ---- caption styles: one sample line, the key word picked out ----
def caption(style, c):
    key, txt, out = c.get('key', '#ffe94d'), c.get('text', '#ffffff'), c.get('outline', '#14080f')
    if style == 'italic_punch':
        w = lambda s, k=False: f'<span style="font:italic 900 150px/1 Montserrat;text-transform:uppercase;letter-spacing:-.02em;color:{key if k else txt};{ol(8, out, 7)}">{s}</span>'
    elif style == 'serif_mix':
        w = lambda s, k=False: (f'<span style="font:italic 400 210px/1 \'Instrument Serif\';color:{key if k else txt};{ol(5, out, 4)}">{s}</span>' if k else
                                f'<span style="font:900 150px/1 \'Inter Tight\';letter-spacing:-.015em;color:{txt};{ol(8, out)}">{s}</span>')
    elif style == 'yellow_key':
        w = lambda s, k=False: f'<span style="font:900 150px/1 \'Inter Tight\';letter-spacing:-.015em;color:{key if k else txt};{ol(10, out)}">{s}</span>'
    else:  # small_top: small white rounded sans above the head
        w = lambda s, k=False: (f'<span style="font:italic 400 92px/1 \'Instrument Serif\';color:{txt};{ol(0)}">{s}</span>' if k else
                                f'<span style="font:800 66px/1 \'Inter Tight\';color:{txt};{ol(0)}">{s}</span>')
    return w

CAPTIONS = {'A': ('italic_punch', 'Italic punch caps, outlined, key words in a color'),
            'B': ('serif_mix', 'Bold sans with key words in a big serif italic'),
            'C': ('yellow_key', 'Heavy sans, key words change color'),
            'D': ('small_top', 'Small and clean, sits above your head')}
TITLES = {'A': ('bubbly', 'Bubbly and outlined (Calistoga)'), 'B': ('editorial', 'Bold sans plus a giant serif (Inter Tight + Gloock)'),
          'C': ('soft_serif', 'Soft serif italic (Instrument Serif)'), 'D': ('poster', 'Tall poster caps (Anton)'),
          'E': ('grotesk', 'Chunky modern sans (Bricolage Grotesque)')}
NUMBERS = {'A': ('#ffe94d', 'Anton', 'Giant yellow, outlined'), 'B': ('#ffffff', 'Anton', 'Giant white, outlined'),
           'C': ('#f6e7a1', 'Gloock', 'Giant butter serif')}
WORDPOPS = {'A': ('Instrument Serif', 'italic', 'Serif italic words scattered around you'),
            'B': ('Calistoga', 'normal', 'Bubbly words scattered around you')}

def title_html(kind, c):
    a1, a2, a3 = c.get('accent', '#ddd0ff'), c.get('key', '#ffe94d'), c.get('accent2', '#ffb3d1')
    if kind == 'bubbly':
        b = lambda s, px, col, r: f'<div style="font:400 {px}px/1.05 Calistoga;color:{col};{ol(10, "#2b1660", 8)}transform:rotate({r}deg)">{s}</div>'
        return b('I posted every day for', 76, a1, -2) + b('30', 230, a2, -4) + b('days straight', 130, '#fff3c4', 2) + b('what I learned', 86, a3, -3)
    if kind == 'editorial':
        return (f'<div style="font:900 118px/1 \'Inter Tight\';color:#fff;{ol(0)}">LET\'S GET</div>'
                f'<div style="font:400 330px/.9 Gloock;color:#f6e7a1;transform:scaleX(.86);{ol(0)}">real</div>')
    if kind == 'soft_serif':
        return (f'<div style="font:italic 400 158px/1.05 \'Instrument Serif\';color:{a1};{ol(0)}">30 days straight</div>'
                f'<div style="font:italic 400 120px/1.05 \'Instrument Serif\';color:{a1};{ol(0)}">what I learned</div>')
    if kind == 'poster':
        return (f'<div style="font:400 92px/1 Anton;color:#fff;{ol(7, "#14080f", 6)}">I POSTED EVERY DAY FOR</div>'
                f'<div style="font:400 300px/.92 Anton;color:{a2};{ol(14, "#14080f", 14)}transform:rotate(-3deg)">30</div>'
                f'<div style="font:400 120px/1 Anton;color:#fff;{ol(10, "#14080f", 8)}">DAYS STRAIGHT</div>')
    return (f'<div style="font:800 96px/1 \'Bricolage Grotesque\';color:#fff;letter-spacing:-.02em;{ol(0)}">I posted every day for</div>'
            f'<div style="font:800 260px/.95 \'Bricolage Grotesque\';color:{a2};letter-spacing:-.04em;{ol(0)}">30</div>'
            f'<div style="font:800 120px/1 \'Bricolage Grotesque\';color:#fff;letter-spacing:-.02em;{ol(0)}">days straight</div>')

def series_html(st, c):
    font = st.get('font', 'Calistoga'); words = st.get('text', 'my series|part 1').split('|')
    cols = [c.get('accent', '#ddd0ff'), '#fff3c4', c.get('accent2', '#ffb3d1')]
    o = ol(10, '#2b1660', 8) if font == 'Calistoga' else ol(8, c.get('outline', '#14080f'), 7)
    return ''.join(f'<div style="font:400 {150 if i < len(words) - 1 else 110}px/1.05 \'{font}\';color:{cols[i % 3]};{o}transform:rotate({(-4, 3, -6)[i % 3]}deg)">{html.escape(w)}</div>' for i, w in enumerate(words))

def page(bg, inner, label=''):
    lab = (f'<div style="position:absolute;left:24px;top:24px;font:800 64px/1 \'Inter Tight\';color:#fff;background:#111;'
           f'padding:10px 24px;border-radius:16px">{html.escape(label)}</div>') if label else ''
    back = f"url('{bg}') center/cover" if bg else 'linear-gradient(160deg,#5b6b78,#2c3338 60%,#1b1f22)'
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>*{{margin:0;box-sizing:border-box}}'
            f'body{{width:1080px;height:1920px;overflow:hidden;background:{back};position:relative}}'
            f'.zone{{position:absolute;inset:0;pointer-events:none}}</style></head><body>{inner}{lab}</body></html>')

def at(y, inner, x=540):
    return f'<div style="position:absolute;left:0;right:0;top:{y}px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:4px">{inner}</div>'

def caption_line(style, c, y=None):
    w = caption(style, c)
    yy = y or (400 if style == 'small_top' else 1220)
    return at(yy, f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px">{w("this")}{w("changed", True)}</div>')

def number_html(col, font, c):
    return at(560, f'<div style="font:400 560px/.9 {font};color:{col};{ol(16, c.get("outline", "#14080f"), 18)}transform:rotate(-4deg)">10</div>'
                   f'<div style="font:400 130px/1 Anton;color:#fff;{ol(11, "#14080f", 10)}transform:rotate(-4deg)">DAYS IN A ROW</div>')

def list_html(c):
    k = c.get('key', '#ffe94d')
    return at(330, f'<div style="font:400 150px/.95 Anton;color:{k};{ol(9, "#14080f", 9)}transform:rotate(-3deg)">01</div>'
                   f'<div style="font:400 66px/1.1 \'Archivo Black\';color:{k};{ol(9, "#14080f", 8)}transform:rotate(-3deg)">&#10003; planned my week</div>')

def wordpops_html(font, style, c, spots=None):
    cols = [c.get('accent', '#ddd0ff'), c.get('key', '#ffe94d'), c.get('accent2', '#ffb3d1'), '#ffffff']
    spots = [tuple(s) for s in spots] if spots else [(150, 520, -8, 'sticky'), (640, 640, 6, 'weird'), (120, 1010, 5, 'cringe'), (470, 1180, -6, 'awkward')]
    return ''.join(f'<div style="position:absolute;left:{x}px;top:{y}px;font:{style} 400 130px/1 \'{font}\';color:{cols[i]};'
                   f'{ol(0) if font != "Calistoga" else ol(9, "#2b1660", 7)}transform:rotate({r}deg)">{t}</div>' for i, (x, y, r, t) in enumerate(spots))

def shoot(html_text, out_png, tmp):
    f = Path(tmp) / (Path(out_png).stem + '.html'); f.write_text(html_text)
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1080,1920',
                    '--virtual-time-budget=9000', f'--screenshot={out_png}', f'file://{f}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def sheet(pngs, out, cols=4):
    ff = shutil.which('ffmpeg') or next((p for p in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', str(Path.home() / '.local/bin/ffmpeg')] if Path(p).exists()), None)
    if not ff or not pngs: return
    d = Path(tempfile.mkdtemp())
    for i, p in enumerate(pngs): shutil.copy(p, d / f'{i:03d}.png')
    rows = -(-len(pngs) // cols)
    subprocess.run([ff, '-nostdin', '-v', 'error', '-y', '-i', str(d / '%03d.png'), '-vf', f'scale=270:480,tile={cols}x{rows}:padding=8:color=white',
                    '-frames:v', '1', '-q:v', '3', str(out)])
    shutil.rmtree(d, ignore_errors=True)

def main():
    if not CHROME: sys.exit('Google Chrome is needed to draw the styles. Install it from https://www.google.com/chrome/')
    a = sys.argv[1:]
    bg = Path(a[a.index('--bg') + 1]).resolve().as_uri() if '--bg' in a else ''
    tmp = tempfile.mkdtemp()
    if a and a[0] == 'options':
        out = Path(a[1]); out.mkdir(parents=True, exist_ok=True); c = {}; made = []
        for k, (st, _) in CAPTIONS.items(): made.append(out / f'caption_{k}.png'); shoot(page(bg, caption_line(st, c), f'Captions {k}'), made[-1], tmp)
        for k, (kind, _) in TITLES.items(): made.append(out / f'title_{k}.png'); shoot(page(bg, at(300, title_html(kind, c)), f'Title {k}'), made[-1], tmp)
        for k, (col, font, _) in NUMBERS.items(): made.append(out / f'number_{k}.png'); shoot(page(bg, number_html(col, font, c), f'Number {k}'), made[-1], tmp)
        for k, (font, style, _) in WORDPOPS.items(): made.append(out / f'wordpops_{k}.png'); shoot(page(bg, wordpops_html(font, style, c), f'Word pops {k}'), made[-1], tmp)
        sheet(made, out / 'options.jpg')
        print(json.dumps({'sheet': str(out / 'options.jpg'), 'captions': {k: v[1] for k, v in CAPTIONS.items()}, 'titles': {k: v[1] for k, v in TITLES.items()},
                          'numbers': {k: v[2] for k, v in NUMBERS.items()}, 'wordpops': {k: v[2] for k, v in WORDPOPS.items()}}, indent=1))
    elif a and a[0] == 'system':
        ds = json.load(open(a[1])); out = Path(a[2]); out.mkdir(parents=True, exist_ok=True); c = ds.get('colors', {})
        cap = ds.get('captions', {}).get('style', 'italic_punch'); made = []
        numcol = ds.get('number_pop', {}).get('color', 'key'); numcol = numcol if numcol.startswith('#') else c.get(numcol, '#ffe94d')
        capy = ds.get('captions', {}).get('y')
        spots = ds.get('word_pops', {}).get('spots')
        jobs = {'captions': caption_line(cap, c, capy), 'hook': at(300, title_html(ds.get('hook', {}).get('style', 'bubbly'), c)),
                'number': number_html(numcol, ds.get('number_pop', {}).get('font', 'Anton'), c),
                'list': list_html(c) + caption_line(cap, c, capy),
                'wordpops': wordpops_html(ds.get('word_pops', {}).get('font', 'Instrument Serif'), ds.get('word_pops', {}).get('font_style', 'italic'), c, spots),
                'series': at(820, series_html(ds.get('series_title', {}), c)) if ds.get('series_title') else ''}
        for k, inner in jobs.items():
            if inner: made.append(out / f'{k}.png'); shoot(page(bg, inner), made[-1], tmp)
        sheet(made, out / 'system.jpg', cols=3)
        print(json.dumps({'stills': [str(m) for m in made], 'sheet': str(out / 'system.jpg')}, indent=1))
    else:
        sys.exit(__doc__)
    shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
