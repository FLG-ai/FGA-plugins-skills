#!/usr/bin/env python3
"""Finds the best cover frames in the reel: sharp, eyes open, facing the camera. Saves the top six as numbered stills
and a sheet to pick from. Usage: python3 find_frames.py <work folder> [--video proxy.mp4] [--image still.jpg ...]
--image adds stills from their camera roll to the candidates."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; CACHE = Path.home() / '.cache' / 'reel-cover'
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); F = ff('ffmpeg')
video = d / (a[a.index('--video') + 1] if '--video' in a else 'proxy.mp4')
extra = [Path(x).expanduser() for i, x in enumerate(a) if i and a[i - 1] == '--image']
exe = CACHE / 'facequality'
if not exe.exists() or exe.stat().st_mtime < (HERE / 'facequality.swift').stat().st_mtime:
    CACHE.mkdir(parents=True, exist_ok=True)
    if subprocess.run(['swiftc', '-O', str(HERE / 'facequality.swift'), '-o', str(exe)], capture_output=True).returncode:
        sys.exit("Could not build the face checker. Install Apple's command line tools with: xcode-select --install")
tmp = Path(tempfile.mkdtemp()); fps = 4
subprocess.run([F, '-nostdin', '-v', 'error', '-i', str(video), '-vf', f'fps={fps},scale=540:-2', str(tmp / 'f_%05d.png')], check=True)
for k, img in enumerate(extra): subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(img), '-vf', 'scale=540:-2', str(tmp / f'x_{k:03d}.png')], check=True)
rows = json.loads(subprocess.run([str(exe), str(tmp)], capture_output=True, text=True).stdout)
def score(r):
    if not r.get('h'): return -1
    s = r['q'] - 0.6 * abs(r.get('yaw', 0)) - 0.4 * max(0, r.get('pitch', 0))   # facing the camera, not looking down
    return s + (0.05 if r['file'].startswith('x_') else 0)
best = []
for r in sorted(rows, key=score, reverse=True):
    if score(r) < 0: break
    t = (int(r['file'][2:7]) - 1) / fps if r['file'].startswith('f_') else None
    if t is not None and any(b['t'] is not None and abs(b['t'] - t) < 1.5 for b in best): continue   # spread them out
    best.append({**r, 't': t, 'source': str(extra[int(r['file'][2:5])]) if t is None else str(video)})
    if len(best) == 6: break
cd = d / 'cover'; cd.mkdir(exist_ok=True)
for n, b in enumerate(best, 1):
    out = cd / f'candidate_{n}.jpg'
    if b['t'] is not None: subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-ss', f"{b['t']:.3f}", '-i', b['source'], '-frames:v', '1', '-q:v', '2', str(out)], check=True)
    else: subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', b['source'], '-q:v', '2', str(out)], check=True)
    b['still'] = str(out)
    subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(out), '-vf', f"scale=270:-2,drawtext=text='{n}':x=12:y=10:fontsize=44:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8", str(tmp / f's_{n}.png')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(tmp / 's_%d.png'), '-vf', f'tile={min(6, len(best))}x1:padding=6:color=white', '-frames:v', '1', '-q:v', '3', str(cd / 'candidates.jpg')], check=True)
json.dump(best, open(cd / 'candidates.json', 'w'), indent=1); shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps([{'n': n, 't': b['t'], 'quality': round(b['q'], 2)} for n, b in enumerate(best, 1)]))
