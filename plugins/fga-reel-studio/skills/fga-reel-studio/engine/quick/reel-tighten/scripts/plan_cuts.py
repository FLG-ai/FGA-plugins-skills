#!/usr/bin/env python3
"""Drafts the cut plan from words.json: keeps every word, splits wherever a pause runs longer than --gap,
and drops filler sounds (um, uh, erm). Writes plan.json for Claude and the person to edit before rendering.
Usage: python3 plan_cuts.py <work folder> [--gap 0.35]"""
import json, re, sys, math, wave, array
from pathlib import Path

a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve()
gap = float(a[a.index('--gap') + 1]) if '--gap' in a else 0.35
words = json.load(open(d / 'words.json'))
# move word edges off silence the speech model folded into a word, so pauses inside words get cut too
wv = wave.open(str(d / 'audio.wav')); sr = wv.getframerate(); pcm = array.array('h', wv.readframes(wv.getnframes())); wv.close()
hop = sr // 100; env = [math.sqrt(sum(x * x for x in pcm[i:i + hop]) / hop) if i + hop <= len(pcm) else 0 for i in range(0, len(pcm), hop)]
srt = sorted(env); thr = max((srt[int(len(srt) * 0.2)] or 1) * 4, 32768 * 10 ** (-42 / 20))
loud = lambda t: 0 <= int(t * 100) < len(env) and env[int(t * 100)] > thr
moved = 0
for w in words:
    s, e = w['s'], w['e']
    while s < e - 0.05 and not loud(s): s += 0.01
    while e > s + 0.05 and not loud(e - 0.01): e -= 0.01
    if s - w['s'] >= gap or w['e'] - e >= gap: w['s'], w['e'] = round(s, 3), round(min(w['e'], e + 0.05), 3); moved += 1
if moved:
    (d / 'words.before-tighten.json').write_text(json.dumps(json.load(open(d / 'words.json')), indent=0))
    (d / 'words.json').write_text(json.dumps(words, indent=0))
    with open(d / 'lines.txt', 'w') as f:  # keep the reading file in step with the moved edges
        line, last = [], None
        for w in words:
            if last is not None and w['s'] - last > 0.9: f.write(' '.join(line) + '\n'); line = []
            line.append(f"{w['t']}[{w['i']}@{w['s']:.2f}]"); last = w['e']
        f.write(' '.join(line) + '\n')
FILL = {'um', 'uh', 'erm', 'umm', 'uhh', 'hmm', 'mm'}
norm = lambda t: re.sub(r'[^a-z0-9\']', '', t.lower())
keep, notes, cur = [], [], None
for w in words:
    if norm(w['t']) in FILL:
        notes.append(f"cut filler '{w['t']}' [{w['i']}] at {w['s']:.2f}"); continue
    if cur and w['s'] - words[cur[1]]['e'] <= gap: cur[1] = w['i']
    else:
        if cur: keep.append(cur)
        cur = [w['i'], w['i']]
if cur: keep.append(cur)
for x, y in zip(keep, keep[1:]):
    p = words[y[0]]['s'] - words[x[1]]['e']
    notes.append(f"pause {p:.2f}s cut between [{x[1]}] '{words[x[1]]['t']}' and [{y[0]}] '{words[y[0]]['t']}'")
if words and words[keep[0][0]]['s'] > 0.3: notes.insert(0, f"dead air at the start cut: {words[keep[0][0]]['s']:.2f}s")
# flag repeated words next to each other for Claude to judge (stutter or emphasis)
for x, y in zip(words, words[1:]):
    if norm(x['t']) and norm(x['t']) == norm(y['t']): notes.append(f"repeat '{x['t']}' [{x['i']}] and [{y['i']}]: decide")
json.dump({'keep': keep, 'cut_notes': notes, 'flag_actions': []}, open(d / 'plan.json', 'w'), indent=1)
print(json.dumps({'pieces': len(keep), 'notes': len(notes), 'silences_inside_words_fixed': moved}))
