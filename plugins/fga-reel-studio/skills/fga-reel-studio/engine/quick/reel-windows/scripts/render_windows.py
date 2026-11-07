#!/usr/bin/env python3
"""Puts the person's own images and clips on the reel: a floating window (rounded corners, soft shadow, a small rise as it
fades in), a small square, or a full-bleed cutaway while the voice keeps going. Private details can be blurred.
Usage: python3 render_windows.py <work folder> [design-system.json]
Reads windows_plan.json: {"windows": [{"mode": "window" | "square" | "fullbleed", "src": "<image or video path>",
  "at_word": 12, "until_word": 20, "w": 900, "x": null, "y": null, "crop": [x, y, w, h], "focus_y": 0.3, "blur": [[x, y, w, h]], "tail": 0.25}]}
  at_word and until_word are word indexes in words_tight.json. crop and blur boxes are fractions (0 to 1) of the picture. crop picks
  the part to show (blur boxes then refer to the cropped picture). A picture too tall to fit is cropped to the window, focus_y says
  where (0 top, 1 bottom, default 0.3).
Reads framed.mp4 and words_tight.json. Writes windowed.mp4, windowed_preview.mp4 and windows_report.txt."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve()
ds = json.load(open(Path(a[1]).expanduser())) if len(a) > 1 else {}
S = {'radius': 34, 'w': 900, 'y': 640, 'bottom': 1360, 'rise': 18, 'square': 560, 'square_x': 260, 'square_y': 785, **ds.get('windows', {})}
F, FP = ff('ffmpeg'), ff('ffprobe'); FPS, W, H = 30, 1080, 1920
words = json.load(open(d / 'words_tight.json')); plan = json.load(open(d / 'windows_plan.json'))['windows']
if not plan: sys.exit('windows_plan.json has no windows')
for k, w in enumerate(plan, 1):
    a_, u_ = w.get('at_word'), w.get('until_word')
    if not (isinstance(a_, int) and isinstance(u_, int) and 0 <= a_ <= u_ < len(words)):
        sys.exit(f'window {k}: at_word and until_word must be word numbers in words_tight.json (0 to {len(words) - 1}) with at_word first. Got {a_} and {u_}.')
base = d / 'framed.mp4'
total = float(subprocess.run([FP, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(base)], capture_output=True, text=True).stdout)

def probe(p):
    r = subprocess.run([FP, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,nb_frames,duration', '-of', 'json', str(p)], capture_output=True, text=True)
    s = json.loads(r.stdout)['streams'][0]; return int(s['width']), int(s['height']), p.suffix.lower() in ('.mp4', '.mov', '.m4v', '.webm', '.mkv')
tmp = Path(tempfile.mkdtemp()); inputs, chains, report, cur = ['-i', str(base)], [], [], '0:v'
n_in = 1
for k, w in enumerate(plan):
    src = Path(w['src']).expanduser()
    if not src.exists(): sys.exit(f"window {k + 1}: {src} not found")
    mw, mh, is_video = probe(src)
    pre = ''
    if w.get('crop'):                                                              # show only this part of the picture
        cx, cy, cw, ch = w['crop']; pre = f'crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy},'; mw, mh = int(mw * cw), int(mh * ch)
    mode = w.get('mode', 'window'); cropped = False; fy = w.get('focus_y', 0.3)
    t0 = words[w['at_word']]['s']; t1 = min(words[w['until_word']]['e'] + w.get('tail', 0.25), total)
    if mode == 'fullbleed': ww, hh, x, y, rad = W, H, 0, 0, 0
    elif mode == 'square': ww = hh = int(w.get('w', S['square'])); x = int(w.get('x') or S['square_x']); y = int(w.get('y') or S['square_y']); rad = S['radius']
    else:
        ww = min(int(w.get('w') or S['w']), 984); y = int(w.get('y') or S['y']); hh = round(ww * mh / mw)
        if y + hh > S['bottom']:                                                    # windows end by y 1360 so the small captions fit under them
            hh2 = S['bottom'] - y; ww2 = round(hh2 * mw / mh)
            if ww2 >= 620: ww, hh = ww2, hh2                                        # shrink the whole picture to fit
            else: y = min(y, 560); hh = S['bottom'] - y; ww = min(ww, 840); cropped = True   # a tall picture (a phone screenshot): show a crop of it at a readable width
        ww, hh = ww // 2 * 2, hh // 2 * 2; x = int(w.get('x') or (W - ww) // 2); rad = S['radius']
    ww, hh = ww // 2 * 2, hh // 2 * 2
    dur = t1 - t0
    # media input: a still loops, a clip plays from its start and holds its last frame
    inputs += (['-loop', '1', '-framerate', str(FPS), '-t', f'{dur + 0.5:.3f}', '-i', str(src)] if not is_video else ['-t', f'{dur:.3f}', '-i', str(src)])
    mi = n_in; n_in += 1
    chain = f"[{mi}:v]" + ("tpad=stop_mode=clone:stop_duration=60," if is_video else "") + pre + f"fps={FPS},format=rgba"
    stream = f"m{k}"
    for b, box in enumerate(w.get('blur', [])):                                   # private details: blurred on the original picture, before it is scaled or cropped
        bx, by, bw, bh = [min(max(float(v), 0.0), 1.0) for v in box]
        bw, bh = min(bw, 1.0 - bx), min(bh, 1.0 - by)
        if bw <= 0 or bh <= 0: continue
        px, py, pw, ph = int(bx * mw), int(by * mh), max(2, int(bw * mw)), max(2, int(bh * mh))
        chain += f",split[a{k}_{b}][b{k}_{b}];[b{k}_{b}]crop={pw}:{ph}:{px}:{py},gblur=sigma=24[z{k}_{b}];[a{k}_{b}][z{k}_{b}]overlay={px}:{py}"
    chain += f",scale={ww}:{hh}:force_original_aspect_ratio=increase,crop={ww}:{hh}:(iw-ow)/2:(ih-oh)*{fy if cropped else 0.5}"
    if rad:
        mask = Image.new('L', (ww, hh), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, ww - 1, hh - 1), radius=rad, fill=255); mp = tmp / f'mask{k}.png'; mask.save(mp)
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{dur + 0.5:.3f}', '-i', str(mp)]; ki = n_in; n_in += 1
        chains.append(chain + f"[r{k}];[{ki}:v]format=gray[g{k}];[r{k}][g{k}]alphamerge")
        chain = None
    else:
        chains.append(chain)
    last = chains[-1]
    fade = f",setpts=PTS-STARTPTS+{t0:.3f}/TB,fade=t=in:st={t0:.3f}:d={0.15 if mode == 'fullbleed' else 0.25}:alpha=1,fade=t=out:st={max(t0, t1 - 0.15):.3f}:d=0.15:alpha=1"
    chains[-1] = last + fade + f"[{stream}]"
    rise = 0 if mode == 'fullbleed' else S['rise']
    ymove = f"{y}+{rise}*max(0,1-(t-{t0:.3f})/0.25)"
    if rad:                                                                       # a soft shadow under it, no border
        pad = 40; sh = Image.new('RGBA', (ww + 2 * pad, hh + 2 * pad), (0, 0, 0, 0)); sa = Image.new('L', sh.size, 0)
        ImageDraw.Draw(sa).rounded_rectangle((pad, pad + 12, pad + ww, pad + 12 + hh), radius=rad, fill=115); sa = sa.filter(ImageFilter.GaussianBlur(22)); sh.putalpha(sa)
        sp = tmp / f'shadow{k}.png'; sh.save(sp)
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{dur + 0.5:.3f}', '-i', str(sp)]; si = n_in; n_in += 1
        chains.append(f"[{si}:v]format=rgba,setpts=PTS-STARTPTS+{t0:.3f}/TB,fade=t=in:st={t0:.3f}:d=0.25:alpha=1,fade=t=out:st={max(t0, t1 - 0.15):.3f}:d=0.15:alpha=1[s{k}]")
        chains.append(f"[{cur}][s{k}]overlay=x={x - pad}:y='{y - pad}+{rise}*max(0,1-(t-{t0:.3f})/0.25)':enable='between(t,{t0:.3f},{t1:.3f})':eof_action=pass[sv{k}]"); cur = f"sv{k}"
    chains.append(f"[{cur}][{stream}]overlay=x={x}:y='{ymove}':enable='between(t,{t0:.3f},{t1:.3f})':eof_action=pass[v{k}]"); cur = f"v{k}"
    report.append(f"{k + 1}. {mode:9s} {t0:6.2f}-{t1:6.2f}s  {ww}x{hh} at ({x},{y})  bottom {y + hh}" + ("  tall picture, cropped" if cropped else "") + ("  <- below 1360, shrink it or move it up" if mode != 'fullbleed' and y + hh > S['bottom'] else "") + f"  {'clip' if is_video else 'image'} {src.name}" + (f"  blurred {len(w['blur'])} area(s)" if w.get('blur') else ''))
subprocess.run([F, '-nostdin', '-v', 'error', '-y'] + inputs + ['-filter_complex', ';'.join(chains), '-map', f'[{cur}]', '-map', '0:a', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-r', str(FPS), '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(d / 'windowed.mp4')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'windowed.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'windowed_preview.mp4')], check=True)
(d / 'windows_report.txt').write_text(f"{len(plan)} window(s) on {total:.1f}s of video\n" + '\n'.join(report) + '\nCheck: a frame in the middle of each window, nothing private readable, nothing covering the face for long.\n')
print(json.dumps({'windows': len(plan), 'file': 'windowed.mp4'}))
