#!/usr/bin/env python3
"""Renders the tightened take from plan.json and moves every kept word onto the new timeline.
Usage: python3 render_tight.py <work folder>
Writes tight.mp4 (1080x1920), tight_preview.mp4 (720p), words_tight.json, segments.json and cut_report.txt."""
import json, math, shutil, subprocess, sys, wave, array
from pathlib import Path

def ff(n):
    for p in [shutil.which(n), f'/opt/homebrew/bin/{n}', f'/usr/local/bin/{n}', str(Path.home() / '.local/bin' / n)]:
        if p and Path(p).exists(): return p
    sys.exit(f'{n} not found. Install it with: brew install ffmpeg')
d = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else sys.exit(__doc__)
F = ff('ffmpeg'); words = json.load(open(d / 'words.json')); plan = json.load(open(d / 'plan.json'))
# loudness envelope, to keep cuts off the edges of words
w = wave.open(str(d / 'audio.wav')); sr = w.getframerate(); pcm = array.array('h', w.readframes(w.getnframes())); w.close()
hop = sr // 100; env = [math.sqrt(sum(x * x for x in pcm[i:i + hop]) / hop) if i + hop <= len(pcm) else 0 for i in range(0, len(pcm), hop)]
srt = sorted(env); thr = max((srt[int(len(srt) * 0.2)] or 1) * 4, 32768 * 10 ** (-42 / 20))
loud1 = lambda t: 0 <= int(t * 100) < len(env) and env[int(t * 100)] > thr
loud = lambda t: loud1(t) or loud1(t + 0.01) or loud1(t + 0.02)
segs, report = [], []
keep = sorted(plan['keep'])
for k, (a, b) in enumerate(keep):
    prev_e = words[keep[k - 1][1]]['e'] if k else 0.0
    next_s = words[keep[k + 1][0]]['s'] if k + 1 < len(keep) else words[-1]['e'] + 1
    s = max(words[a]['s'] - 0.06, (prev_e + words[a]['s']) / 2 if k else 0)
    e = min(words[b]['e'] + 0.12, (words[b]['e'] + next_s) / 2)
    while s > max(0, words[a]['s'] - 0.25) and loud(s): s -= 0.01      # still sound at the in point: back off
    while e < words[b]['e'] + 0.35 and loud(e): e += 0.01              # still sound at the out point: run on
    fs, fe = round(s * 30), round(e * 30)  # whole frames, so picture and sound cut at exactly the same point
    segs.append({'from_word': a, 'to_word': b, 'fs': fs, 'fe': fe, 's': fs / 30, 'e': fe / 30})
# render in one pass (trim + concat) so every piece keeps its exact length and sound never drifts from picture
fc = []
for i, g in enumerate(segs):
    dur = g['e'] - g['s']
    fc.append(f"[0:v]trim=start_frame={g['fs']}:end_frame={g['fe']},setpts=PTS-STARTPTS[v{i}]")
    fc.append(f"[0:a]aresample=48000,atrim=start_sample={g['fs'] * 1600}:end_sample={g['fe'] * 1600},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={max(0, dur - 0.01):.4f}:d=0.01[a{i}]")
fc.append(''.join(f'[v{i}][a{i}]' for i in range(len(segs))) + f'concat=n={len(segs)}:v=1:a=1[v][a]')
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'proxy.mp4'), '-filter_complex', ';'.join(fc), '-map', '[v]', '-map', '[a]',
                '-c:v', 'libx264', '-crf', '17', '-preset', 'fast', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(d / 'tight.mp4')], check=True)
subprocess.run([F, '-nostdin', '-v', 'error', '-y', '-i', str(d / 'tight.mp4'), '-vf', 'scale=720:-2', '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'aac', str(d / 'tight_preview.mp4')], check=True)
# words on the new timeline, plus how much each cut jumps visually (for the framing step)
t, out = 0.0, []
for g in segs:
    g['out_start'] = round(t, 3)
    for i in range(g['from_word'], g['to_word'] + 1):
        x = words[i]; out.append({'t': x['t'], 's': round(t + x['s'] - g['s'], 3), 'e': round(t + x['e'] - g['s'], 3), 'i': len(out), 'src': x['i']})
    t += g['e'] - g['s']
def frame(ts):
    r = subprocess.run([F, '-nostdin', '-v', 'error', '-ss', f'{max(0, ts):.3f}', '-i', str(d / 'proxy.mp4'), '-frames:v', '1', '-vf', 'scale=32:56,format=gray', '-f', 'rawvideo', '-'], capture_output=True)
    return r.stdout
for k in range(1, len(segs)):
    x, y = frame(segs[k - 1]['e'] - 0.04), frame(segs[k]['s'] + 0.02)
    jump = sum(abs(p - q) for p, q in zip(x, y)) / max(1, len(x))
    segs[k]['jump'] = round(jump, 1)
    report.append(f"cut {k} at {segs[k]['out_start']:.2f}s, before '{words[segs[k]['from_word']]['t']}': jump {jump:.1f}" + ('  <- big move, hide with a zoom step' if jump > 6 else ''))
for k, g in enumerate(segs):
    if loud1(g['e'] - 0.01) or loud1(g['e'] - 0.02):
        report.append(f"piece {k + 1} ends while sound is still going, after '{words[g['to_word']]['t']}': check it doesn't end on part of the next word")
json.dump(out, open(d / 'words_tight.json', 'w'), indent=0)
with open(d / 'sentences_tight.txt', 'w') as f:  # sentences with indexes and times on the tight video
    cur = []
    for x in out:
        cur.append(x)
        if x['t'].rstrip('"\')').endswith(('.', '?', '!')):
            f.write(f"words {cur[0]['i']}-{cur[-1]['i']}  {cur[0]['s']:6.2f}-{cur[-1]['e']:6.2f}  | {' '.join(y['t'] for y in cur)}\n"); cur = []
    if cur: f.write(f"words {cur[0]['i']}-{cur[-1]['i']}  {cur[0]['s']:6.2f}-{cur[-1]['e']:6.2f}  | {' '.join(y['t'] for y in cur)}\n")
json.dump(segs, open(d / 'segments.json', 'w'), indent=1)
(d / 'cut_report.txt').write_text(f'{len(segs)} pieces, {t:.1f}s long (from {words[-1]["e"]:.1f}s of talking)\n' + '\n'.join(report) + '\n')
print(json.dumps({'pieces': len(segs), 'length': round(t, 2), 'big_jumps': sum(1 for g in segs if g.get('jump', 0) > 6)}))
