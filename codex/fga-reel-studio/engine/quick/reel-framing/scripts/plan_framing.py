#!/usr/bin/env python3
"""Plans the framing for every piece of tight.mp4: face-based zoom and position, an opener that starts wider,
a slow drift on every shot, and a zoom step on cuts tighten marked as big moves. Writes framing.json to edit.
Usage: python3 plan_framing.py <work folder> [--face 0.21] [--grade cool|calm_reds|none] [--ds design-system.json]
  --face: face height as a share of the frame, default 0.18
  --grade: cool (default, a light cool grade), calm_reds (reds and magentas -16% saturation, very light smoothing, nothing
           lightened) or none. Without the flag, the "grade" key of --ds is used when it is there."""
import json, shutil, statistics, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; CACHE = Path.home() / '.cache' / 'reel-framing'
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); target = float(a[a.index('--face') + 1]) if '--face' in a else 0.18
exe = CACHE / 'facefind'
if not exe.exists() or exe.stat().st_mtime < (HERE / 'facefind.swift').stat().st_mtime:
    CACHE.mkdir(parents=True, exist_ok=True)
    if subprocess.run(['swiftc', '-O', str(HERE / 'facefind.swift'), '-o', str(exe)], capture_output=True).returncode:
        sys.exit("Could not build the face finder. Install Apple's command line tools with: xcode-select --install")
tmp = Path(tempfile.mkdtemp()); fps = 3.0
subprocess.run([ff('ffmpeg'), '-nostdin', '-v', 'error', '-i', str(d / 'tight.mp4'), '-vf', f'fps={fps},scale=360:640', str(tmp / 'f_%05d.png')], check=True)
faces = json.loads(subprocess.run([str(exe), str(tmp), str(fps)], capture_output=True, text=True).stdout); shutil.rmtree(tmp, ignore_errors=True)
segs = json.load(open(d / 'segments.json'))
clamp = lambda v, lo, hi: max(lo, min(hi, v))
shots, t0 = [], 0.0
for k, g in enumerate(segs):
    dur = (g['fe'] - g['fs']) / 30 if 'fe' in g else g['e'] - g['s']
    fs = [f for f in faces if 'h' in f and t0 <= f['t'] < t0 + dur] or [f for f in faces if 'h' in f]
    if fs:
        cx, cy, h = (statistics.median(f[x] for f in fs) for x in ('cx', 'cy', 'h'))
        z = clamp(target / h, 1.0, 1.6)
        fx = clamp((cx - 0.5 / z) / (1 - 1 / z), 0, 1) if z > 1.001 else 0.5
        fy = clamp((cy - 0.42 / z) / (1 - 1 / z), 0, 1) if z > 1.001 else 0.5
    else:
        z, fx, fy = 1.0, 0.5, 0.5
    if k == 0:
        zo = max(1.0, z * 0.88); move = {'kind': 'opener', 'push': [round(zo * 1.12, 3), round(zo, 3)], 'ease': 'linear'}
    elif g.get('jump', 0) > 6:
        move = {'kind': 'zoom step (hides a jumpy cut)', 'push': [round(z * 1.16, 3), round(z * 1.10, 3)], 'ease': 'out'}
    else:
        move = {'kind': 'drift', 'push': [round(z * 1.08, 3), round(z, 3)], 'ease': 'linear'}
    shots.append({'piece': k, 'start': round(t0, 3), 'end': round(t0 + dur, 3), 'fx': round(fx, 3), 'fy': round(fy, 3), 'base_zoom': round(z, 3), **move})
    t0 += dur
# the last shot runs to the real end of tight.mp4, so no frame is dropped
real = float(subprocess.run([ff('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', str(d / 'tight.mp4')], capture_output=True, text=True).stdout.strip() or t0)
if shots: shots[-1]['end'] = round(max(real, shots[-1]['end']), 3)
GRADES = {'cool': 'eq=contrast=1.04:saturation=0.94:gamma=1.03,colorbalance=bm=0.02:rm=-0.01',
          'calm_reds': 'huesaturation=saturation=-0.16:colors=r+m:strength=6,bilateral=sigmaS=4:sigmaR=0.035',
          'none': 'null'}
gname = a[a.index('--grade') + 1] if '--grade' in a else None
if gname is None and '--ds' in a:
    try: gname = json.load(open(Path(a[a.index('--ds') + 1]).expanduser())).get('grade')
    except Exception: gname = None
gname = gname or 'cool'
if gname not in GRADES: sys.exit(f"--grade must be one of {', '.join(GRADES)}")
plan = {'shots': shots, 'snaps': [], 'opener_lift': 0.10, 'grade_name': gname, 'grade': GRADES[gname]}
json.dump(plan, open(d / 'framing.json', 'w'), indent=1)
print(json.dumps({'grade': gname, 'shots': len(shots), 'zoom_steps': sum(1 for s in shots if s['kind'].startswith('zoom')), 'faces_found': sum(1 for f in faces if 'h' in f), 'frames_checked': len(faces)}))
