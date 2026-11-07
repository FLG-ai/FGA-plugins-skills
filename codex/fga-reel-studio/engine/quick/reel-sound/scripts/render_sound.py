#!/usr/bin/env python3
"""Mixes the sound cues under the voice of popped.mp4, evens out loudness for Instagram, and writes final.mp4.
Usage: python3 render_sound.py <work folder> <design-system.json>
Sounds are looked up by name in the design system's sounds/ folder, then in reel-design-system's starter sounds."""
import json, re, shutil, subprocess, sys
from pathlib import Path

def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
a = sys.argv[1:]
if len(a) < 2: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); dsp = Path(a[1]).expanduser().resolve()
plan = json.load(open(d / 'sound_plan.json')); F = ff('ffmpeg')
roots = [dsp.parent / 'sounds', Path(__file__).resolve().parents[2] / 'reel-design-system' / 'assets' / 'sounds']
def find(name):
    for r in roots:
        for ext in ('.m4a', '.wav', '.mp3'):
            if (r / (name + ext)).exists(): return r / (name + ext)
    sys.exit(f"Sound '{name}' not found in {roots[0]}. Add the file there or pick another sound.")
cmd = [F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'popped.mp4')]; fc = []
for k, c in enumerate(plan['cues']):
    cmd += ['-i', str(find(c['sound']))]; ms = int(c['t'] * 1000)
    fc.append(f"[{k + 1}:a]aresample=48000,aformat=channel_layouts=stereo,volume={c['gain']}dB,adelay={ms}|{ms}[s{k}]")
n = len(plan['cues'])
mix = '[0:a]aresample=48000,aformat=channel_layouts=stereo[v];' + (';'.join(fc) + ';' if fc else '')
mix += (f"[v]{''.join(f'[s{k}]' for k in range(n))}amix=inputs={n + 1}:normalize=0:duration=first," if n else '[v]')
mix += f"loudnorm=I={plan.get('voice_lufs', -14)}:TP=-2:LRA=11,alimiter=limit=0.89:level=disabled,aresample=48000[aout]"
cmd += ['-filter_complex', mix, '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(d / 'final.mp4')]
subprocess.run(cmd, check=True)
def measure(f):
    m = subprocess.run([F, '-nostdin', '-hide_banner', '-i', str(f), '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    i = re.findall(r'I:\s+(-?[\d.]+) LUFS', m); pk = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', m)
    return (float(i[-1]) if i else None), (float(pk[-1]) if pk else None)
target = plan.get('voice_lufs', -14); lu, _ = measure(d / 'final.mp4')
if lu is not None and abs(lu - target) > 0.7:  # one correction pass: shift the level, keep peaks under the limiter
    tmp = d / '_final_tmp.mp4'
    subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'final.mp4'), '-af', f'volume={target - lu:.2f}dB,alimiter=limit=0.84:level=disabled',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(d / 'final.mp4')
# Verify the encoded AAC true peak, which can exceed the filter ceiling.
# Re-master once when needed, then leave extra headroom for AAC overshoot.
lu, pk = measure(d / 'final.mp4')
if pk is not None and pk > -1.0:
    tmp = d / '_final_peak_tmp.mp4'
    subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'final.mp4'),
                    '-af', f'loudnorm=I={target}:TP=-2:LRA=11,aresample=48000',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(tmp)], check=True)
    tmp.replace(d / 'final.mp4')
    lu, pk = measure(d / 'final.mp4')
    if pk is not None and pk > -1.0:
        subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'final.mp4'),
                        '-af', f'volume={-1.5 - pk:.2f}dB', '-c:v', 'copy', '-c:a', 'aac',
                        '-b:a', '192k', '-movflags', '+faststart', str(tmp)], check=True)
        tmp.replace(d / 'final.mp4')
lu, pk = measure(d / 'final.mp4')
if lu is None or pk is None or abs(lu - target) > 1.5 or pk > -1.0:
    message = f'FAIL: encoded audio measures {lu} LUFS and {pk} dBFS true peak. Required: within 1.5 LU of {target}, peak at or below -1 dBFS. Review the mix before delivery.'
    (d / 'sound_report.txt').write_text(message + '\n')
    sys.exit(message)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'final.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'final_preview.mp4')], check=True)
l2, p2 = measure(d / 'final.mp4'); lufs, peak = [str(l2)], [str(p2)]
rep = [f"{c['t']:6.2f}  {c['sound']:<10} {c['gain']} dB  {c['why']}" for c in plan['cues']]
rep.append(f"\nLoudness {lufs[-1] if lufs else '?'} LUFS (target {plan.get('voice_lufs', -14)}), peak {peak[-1] if peak else '?'} dBFS")
(d / 'sound_report.txt').write_text('\n'.join(rep) + '\n')
print(json.dumps({'cues': n, 'lufs': lufs[-1] if lufs else None, 'peak': peak[-1] if peak else None}))
