#!/usr/bin/env python3
"""Finds stretches where the person looks down or turns away from the camera, and the words spoken then.
Usage: python3 lookdown.py <work folder> [--fps 5]
Writes lookdown.json. Uses the Mac's face detection, compiled once from lookdown.swift."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; CACHE = Path.home() / '.cache' / 'reel-tighten'
def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); fps = float(a[a.index('--fps') + 1]) if '--fps' in a else 5.0
exe = CACHE / 'lookdown'
if not exe.exists() or exe.stat().st_mtime < (HERE / 'lookdown.swift').stat().st_mtime:
    CACHE.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['swiftc', '-O', str(HERE / 'lookdown.swift'), '-o', str(exe)], capture_output=True, text=True)
    if r.returncode: sys.exit("Could not build the face checker. Install Apple's command line tools with: xcode-select --install")
tmp = Path(tempfile.mkdtemp())
subprocess.run([ff('ffmpeg'), '-nostdin', '-v', 'error', '-i', str(d / 'proxy.mp4'), '-vf', f'fps={fps},scale=360:-2', str(tmp / 'f_%05d.png')], check=True)
rows = json.loads(subprocess.run([str(exe), str(tmp), str(fps)], capture_output=True, text=True).stdout)
shutil.rmtree(tmp, ignore_errors=True)
pitches = sorted(r['pitch'] for r in rows if 'pitch' in r)
base = pitches[len(pitches) // 2] if pitches else 0  # their usual head angle
words = json.load(open(d / 'words.json'))
def away(r): return (not r['face']) or ('pitch' in r and r['pitch'] - base > 0.3)
spans, cur = [], None
for r in rows:
    if away(r): cur = [cur[0], r['t']] if cur else [r['t'], r['t']]
    else:
        if cur and cur[1] - cur[0] >= 0.4: spans.append(cur)
        cur = None
if cur and cur[1] - cur[0] >= 0.4: spans.append(cur)
out = []
for s, e in spans:
    ws = [w for w in words if w['e'] > s and w['s'] < e + 1 / fps]
    kind = 'no face' if all(not r['face'] for r in rows if s <= r['t'] <= e) else 'looking down'
    out.append({'start': round(s, 2), 'end': round(e + 1 / fps, 2), 'kind': kind, 'words': [w['i'] for w in ws], 'text': ' '.join(w['t'] for w in ws)})
json.dump({'usual_pitch': base, 'spans': out}, open(d / 'lookdown.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
