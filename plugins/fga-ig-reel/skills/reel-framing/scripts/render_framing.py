#!/usr/bin/env python3
"""Renders framing.json onto tight.mp4: per-shot zoom and drift, snap zooms, the opener lift and the grade.
The sound and timing are untouched, so words_tight.json still lines up. Writes framed.mp4 and framed_preview.mp4.
Usage: python3 render_framing.py <work folder>"""
import json, shutil, subprocess, sys
from pathlib import Path

def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
d = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else sys.exit(__doc__)
plan = json.load(open(d / 'framing.json')); words = json.load(open(d / 'words_tight.json'))
# split shots wherever a snap zoom starts or ends (snaps are word ranges on the tight timeline)
snaps = [(words[s['from']]['s'] - 0.04, words[s['to']]['e'] + 0.12) for s in plan.get('snaps', [])]
parts = []
for sh in plan['shots']:
    cuts = sorted({sh['start'], sh['end'], *[t for a, b in snaps for t in (a, b) if sh['start'] < t < sh['end']]})
    for a, b in zip(cuts, cuts[1:]):
        snap = any(x <= a + 0.001 and b <= y + 0.001 for x, y in snaps)
        parts.append({**sh, 'start': a, 'end': b, 'snap': snap, 'first': a == sh['start']})
fc = []
for i, p in enumerate(parts):
    fs, fe = round(p['start'] * 30), round(p['end'] * 30)
    if fe <= fs: continue
    dur = (fe - fs) / 30; full = p['end'] - p['start']
    z0, z1 = p['push']
    if p['snap']:
        Z = f"{p['base_zoom'] * 1.18:.4f}"
    else:
        # continue the shot's move across any snap split: progress measured on the whole shot
        sh = next(s for s in plan['shots'] if s['piece'] == p['piece']); off = p['start'] - sh['start']; span = sh['end'] - sh['start']
        pe = f"min(1,(t+{off:.3f})/{span:.3f})"
        if p['ease'] == 'out': pe = f"(1-pow(1-{pe},3))"
        Z = f"({z0}+({z1}-{z0})*{pe})"
        prev = parts[i - 1] if i else None
        if prev and prev['snap'] and prev['piece'] == p['piece']:   # ease back out of a snap zoom over 0.35 s instead of jumping
            Z = f"({Z}+({p['base_zoom'] * 1.18:.4f}-{Z})*max(0,1-t/0.35))"
    lift = f",eq=brightness='-{plan['opener_lift']}*max(0,1-t/0.25)':eval=frame" if (p['piece'] == 0 and p['first'] and plan.get('opener_lift')) else ''
    fc.append(f"[0:v]trim=start_frame={fs}:end_frame={fe},setpts=PTS-STARTPTS,scale=w='trunc(1080*{Z}/2)*2':h='trunc(1920*{Z}/2)*2':eval=frame:flags=bicubic,"
              f"crop=1080:1920:x='(iw-1080)*{p['fx']}':y='(ih-1920)*{p['fy']}',{plan['grade']}{lift},setsar=1[v{i}]")
n = len(fc)
fc.append(''.join(f'[v{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=0[v]')
F = ff('ffmpeg')
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'tight.mp4'), '-filter_complex', ';'.join(fc), '-map', '[v]', '-map', '0:a',
                '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-r', '30', '-c:a', 'copy', str(d / 'framed.mp4')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'framed.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'framed_preview.mp4')], check=True)
lines = [f"{s['start']:6.2f}-{s['end']:6.2f}  {s['kind']}  zoom {s['push'][0]}->{s['push'][1]}" for s in plan['shots']]
lines += [f"snap zoom: {words[s['from']]['t']} ... {words[s['to']]['t']}" for s in plan.get('snaps', [])]
(d / 'framing_report.txt').write_text('\n'.join(lines) + '\n')
print(json.dumps({'parts': n, 'snaps': len(snaps)}))
