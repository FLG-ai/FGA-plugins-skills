#!/usr/bin/env python3
"""Applies spelling fixes to words.json and saves them for next time.
Usage: python3 spelling.py <work folder> "Al=AI" "colour=color" ...
A fix matches one whole word, ignoring case and trailing punctuation, which is kept. Fixes are added to corrections.json."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordfiles import write_readables

d = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else sys.exit(__doc__)
cf = d / 'corrections.json'
fixes = json.load(open(cf)) if cf.exists() else {}
for pair in sys.argv[2:]:
    a, b = pair.split('=', 1); fixes[a.strip().lower()] = b.strip()
words = json.load(open(d / 'words.json')); n = 0
for w in words:
    core = w['t'].rstrip('.,!?;:'); tail = w['t'][len(core):]
    if core.lower() in fixes and core != fixes[core.lower()]:
        w['t'] = fixes[core.lower()] + tail; n += 1
(d / 'words.json').write_text(json.dumps(words, indent=0)); write_readables(d, words); cf.write_text(json.dumps(fixes, indent=1))
print(json.dumps({'changed': n, 'fixes': fixes}))
