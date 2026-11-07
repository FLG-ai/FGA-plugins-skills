#!/usr/bin/env python3
"""Drafts captions_plan.json: which words are key words (colored or styled differently), which to show small, which to skip.
Usage: python3 plan_captions.py <work folder>
Key word guesses: numbers, names (capitalised mid-sentence), and long or emphatic words. Claude and the person edit the list."""
import json, re, sys
from pathlib import Path

d = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else sys.exit(__doc__)
words = json.load(open(d / 'words_tight.json'))
STOP = set('the a an and or but so to of in on at for with from by it its is are was were be been i you we they he she my your our this that these those just really very like what when where how then than as if not no yes do did done have has had will would could should can me him her them us'.split())
key = []
for k, w in enumerate(words):
    core = re.sub(r"[^\w'$%]", '', w['t'])
    prev_end = k == 0 or words[k - 1]['t'].rstrip().endswith(('.', '?', '!'))
    if not core or core.lower() in STOP: continue
    if re.search(r'\d', core) or (core[0].isupper() and not prev_end and not re.match(r"^I('|$)", core)) or len(core) >= 9:
        key.append(w['i'])
small = []
if (d / 'windows_plan.json').exists():                           # a window or square on screen: those words drop to the small caption below it
    small = [[w['at_word'], w['until_word']] for w in json.load(open(d / 'windows_plan.json')).get('windows', []) if w.get('mode', 'window') != 'fullbleed']
json.dump({'key': key, 'small': small, 'skip': [], 'notes': 'small and skip are word index ranges [first, last]'}, open(d / 'captions_plan.json', 'w'), indent=1)
print(json.dumps({'words': len(words), 'key_guesses': len(key), 'key_words': [words[i]['t'] for i in key]}))
