#!/usr/bin/env python3
"""Makes the working copy of a raw video: upright, 1080x1920, 30 fps (proxy.mp4) plus 16 kHz mono audio (audio.wav).
Usage: python3 prepare.py <video> [--out <work folder>]
The work folder defaults to "<video name> - reel work" next to the video. The original is never changed."""
import shutil, subprocess, sys, json
from pathlib import Path

def ff(name):
    for p in [shutil.which(name), f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}', str(Path.home() / '.local/bin' / name)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{name} not found. Install it with: brew install ffmpeg')

a = sys.argv[1:]
if not a: sys.exit(__doc__)
src = Path(a[0]).expanduser().resolve()
out = Path(a[a.index('--out') + 1]).expanduser() if '--out' in a else src.parent / f'{src.stem} - reel work'
out.mkdir(parents=True, exist_ok=True)
F = ff('ffmpeg')
# ffmpeg applies the phone's rotation flag by default, so the copy comes out upright.
# Scale to fill 1080x1920 and crop the overflow from the centre (a landscape clip becomes a centre crop).
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(src),
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p',
                '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                str(out / 'proxy.mp4')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(out / 'proxy.mp4'), '-vn', '-ac', '1', '-ar', '16000', str(out / 'audio.wav')], check=True)
probe = subprocess.run([ff('ffprobe'), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out / 'proxy.mp4')], capture_output=True, text=True).stdout.strip()
(out / 'source.json').write_text(json.dumps({'source': str(src), 'duration': float(probe or 0)}, indent=1))
print(json.dumps({'work_folder': str(out), 'duration': float(probe or 0)}))
