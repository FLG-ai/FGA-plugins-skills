#!/usr/bin/env python3
"""Builds the visual design system page: one self-contained HTML file (images and sounds embedded) that opens in any browser.

  python3 make_page.py <design-system folder>

The folder holds design-system.json, stills/ (from render_styles.py system), refs/ (frames named <id>_0.jpg..), and
sounds/ (the .m4a files they kept). Writes "<folder>/Reel Design System.html". Standard library plus ffmpeg (to shrink images).
"""
import base64, html, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FF = shutil.which('ffmpeg') or next((p for p in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', str(Path.home() / '.local/bin/ffmpeg')] if Path(p).exists()), None)
e = html.escape

def img(path, w=360):
    path = Path(path)
    if not path.exists(): return ''
    if FF:
        t = Path(tempfile.mkdtemp()) / 'x.jpg'
        subprocess.run([FF, '-nostdin', '-v', 'error', '-y', '-i', str(path), '-vf', f'scale={w}:-2', '-q:v', '4', str(t)])
        if t.exists(): path = t
    mime = 'image/jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()

def aud(path):
    return 'data:audio/mp4;base64,' + base64.b64encode(Path(path).read_bytes()).decode() if Path(path).exists() else ''

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    d = Path(sys.argv[1]).expanduser().resolve()
    ds = json.load(open(d / 'design-system.json'))
    c = ds.get('colors', {})
    # your look
    looks = []
    for k, label in [('captions', 'Captions'), ('hook', 'Hook header'), ('number', 'Number pop'), ('list', 'List cards'), ('wordpops', 'Word pops'), ('series', 'Series title')]:
        p = d / 'stills' / f'{k}.png'
        if not p.exists(): continue
        info = ds.get({'number': 'number_pop', 'list': 'list_cards', 'wordpops': 'word_pops', 'series': 'series_title'}.get(k, k), {})
        notes = (info.get('notes', '') if isinstance(info, dict) else '') or ('Always included: 01, 02, 03 up top with a ticked label' if k == 'list' else '')
        looks.append(f'<article class="card"><div class="media"><img src="{img(p)}" alt="{e(label)} example"></div><div class="body"><b>{e(label)}</b><p>{e(notes)}</p></div></article>')
    # fonts and colors
    fonts = ''.join(f'<li><span class="role">{e(role)}</span><span class="fname" style="font-family:\'{e(name)}\'">{e(name)}</span></li>' for role, name in ds.get('fonts', {}).items())
    sw = ''.join(f'<li><span class="sw" style="background:{e(v)}"></span><span>{e(k)}</span><code>{e(v)}</code></li>' for k, v in c.items())
    gf = '&'.join('family=' + n.replace(' ', '+') for n in sorted(set(ds.get('fonts', {}).values())))
    # sounds
    snd = ''.join(f'<button class="sfx" data-a="{e(k)}"><span class="pl">&#9654;</span><b>{e(k.replace("_", " "))}</b><small>{e(v)}</small>'
                  f'<audio id="a-{e(k)}" src="{aud(d / "sounds" / (str(v) + ".m4a"))}" preload="none"></audio></button>' for k, v in ds.get('sounds', {}).items() if k != 'volume_db')
    # references
    refs = []
    for r in ds.get('references', []):
        rid, who = r['id'], e(r.get('who', ''))
        frames = ''.join(f'<figure><img src="{img(d / "refs" / (rid + "_" + str(j) + ".jpg"), 240)}" alt="{who} frame"><figcaption>{e(cap)}</figcaption></figure>'
                         for j, cap in enumerate(r.get('captions', [])[:3]))
        refs.append(f'<article class="ref"><div class="strip">{frames}</div><div class="rb"><b>{e(r.get("who", ""))}</b><i>{e(r.get("title", ""))}</i>'
                    f'<span>{e(r.get("notes", ""))}</span><em>Borrowed: {e(r.get("borrowed", ""))}</em>'
                    + (f'<a href="{e(r["url"])}" target="_blank" rel="noopener">Watch the reel</a>' if r.get('url') else '') + '</div></article>')
    rules = ''.join(f'<li>{e(x)}</li>' for x in ds.get('rules', []))
    tpl = (HERE.parent / 'assets' / 'page.html').read_text()
    out = (tpl.replace('%%NAME%%', e(ds.get('name', 'My reel design system'))).replace('%%GF%%', gf).replace('%%LOOKS%%', ''.join(looks))
              .replace('%%FONTS%%', fonts).replace('%%SWATCHES%%', sw).replace('%%SOUNDS%%', snd).replace('%%REFS%%', ''.join(refs) or '<p>No references yet.</p>')
              .replace('%%RULES%%', rules))
    (d / 'Reel Design System.html').write_text(out)
    print(d / 'Reel Design System.html')

if __name__ == '__main__':
    main()
