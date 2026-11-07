#!/usr/bin/env python3
"""Drafts sound_plan.json from the text moments: a pop on list cards, numbers and the call to action, the reveal sound on the
series title, and a soft click on each word pop. Merges sounds that land within half a second of each other.
Usage: python3 plan_sound.py <work folder> <design-system.json>"""
import json, sys
from pathlib import Path

a = sys.argv[1:]
if len(a) < 2: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve(); ds = json.load(open(Path(a[1]).expanduser()))
snd = ds.get('sounds', {}); vol = snd.get('volume_db', -14)
pop, reveal, click = snd.get('pop', 'pop'), snd.get('reveal', snd.get('pop', 'pop')), snd.get('typing', 'click1')
words = json.load(open(d / 'words_tight.json')); plan = json.load(open(d / 'pops_plan.json'))
ws = lambda i: words[i]['s'] if 0 <= i < len(words) else 0.0
cues = []
for el in plan['elements']:
    t = el.get('at', ws(el['at_word']) if 'at_word' in el else 0.0)
    kind = el['type']
    if kind in ('list', 'number', 'cta'): cues.append({'t': round(t, 3), 'sound': pop, 'gain': vol, 'why': f"{kind}: {el.get('label') or el.get('text') or el.get('big')}"})
    elif kind == 'series': cues.append({'t': round(max(0, t - 0.15), 3), 'sound': reveal, 'gain': vol + 2, 'why': 'series title'})
    elif kind == 'word': cues.append({'t': round(t, 3), 'sound': click, 'gain': vol - 2, 'why': f"word pop: {el['text']}"})
cues.sort(key=lambda c: c['t']); merged = []
for c in cues:
    if merged and c['t'] - merged[-1]['t'] < 0.5 and c['sound'] == merged[-1]['sound']: continue
    merged.append(c)
json.dump({'cues': merged, 'voice_lufs': -14}, open(d / 'sound_plan.json', 'w'), indent=1)
print(json.dumps({'cues': len(merged)}))
