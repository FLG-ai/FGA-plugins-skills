#!/usr/bin/env python3
"""Checks word timings against the real sound and fixes clipped starts and ends at every pause, where cuts happen.
Usage: python3 fix_timing.py <work folder>
Reads audio.wav and words.json, rewrites words.json, writes timing-report.txt. Standard library only."""
import json, math, sys, wave, array
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordfiles import write_readables

d = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else sys.exit(__doc__)
w = wave.open(str(d / 'audio.wav'))
sr = w.getframerate(); pcm = array.array('h', w.readframes(w.getnframes())); w.close()
hop = sr // 100  # 10 ms windows
env = [math.sqrt(sum(x * x for x in pcm[i:i + hop]) / hop) if i + hop <= len(pcm) else 0 for i in range(0, len(pcm), hop)]
srt = sorted(env); floor = srt[int(len(srt) * 0.2)] or 1
thr = max(floor * 4, 32768 * 10 ** (-42 / 20))  # 4x the room noise, and never below -42 dBFS
loud = lambda t: 0 <= int(t * 100) < len(env) and env[int(t * 100)] > thr

words = json.load(open(d / 'words.json')); log = []
for i, x in enumerate(words):
    prev_e = words[i - 1]['e'] if i else -9
    nxt_s = words[i + 1]['s'] if i + 1 < len(words) else 9e9
    if x['s'] - prev_e > 0.15:  # starts after a pause: walk back while the sound is already going
        s = x['s']
        while s - 0.01 > max(prev_e + 0.02, x['s'] - 0.35) and loud(s - 0.01): s -= 0.01
        if x['s'] - s >= 0.03: log.append(f"start  {x['t']:<14} [{i}] {x['s']:.2f} -> {s:.2f}"); x['s'] = round(s, 3)
    if nxt_s - x['e'] > 0.15:  # ends before a pause: walk forward while the sound is still going
        e = x['e']
        while e + 0.01 < min(nxt_s - 0.02, x['e'] + 0.45) and loud(e + 0.01): e += 0.01
        if e - x['e'] >= 0.03: log.append(f"end    {x['t']:<14} [{i}] {x['e']:.2f} -> {e:.2f}"); x['e'] = round(e, 3)
(d / 'words.json').write_text(json.dumps(words, indent=0)); write_readables(d, words)
(d / 'timing-report.txt').write_text('\n'.join(log) + '\n' if log else 'No clipped words found.\n')
print(json.dumps({'fixed': len(log)}))
