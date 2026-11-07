"""Writes the two reading files from words.json so they always match it. Used by transcribe, fix_timing and spelling."""
from pathlib import Path

def write_readables(d, words):
    d = Path(d)
    with open(d / 'sentences.txt', 'w') as f:  # real sentences, split at . ? !
        cur = []
        for w in words:
            cur.append(w)
            if w['t'].rstrip('"\')').endswith(('.', '?', '!')) and not w['t'].lower().rstrip('.') in ('p.m', 'a.m', 'mr', 'mrs', 'dr', 'vs'):
                f.write(f"words {cur[0]['i']}-{cur[-1]['i']}  {cur[0]['s']:6.2f}-{cur[-1]['e']:6.2f}  | {' '.join(x['t'] for x in cur)}\n"); cur = []
        if cur: f.write(f"words {cur[0]['i']}-{cur[-1]['i']}  {cur[0]['s']:6.2f}-{cur[-1]['e']:6.2f}  | {' '.join(x['t'] for x in cur)}\n")
    with open(d / 'lines.txt', 'w') as f:  # split at every pause over 0.9 s
        line, last = [], None
        for w in words:
            if last is not None and w['s'] - last > 0.9: f.write(' '.join(line) + '\n'); line = []
            line.append(f"{w['t']}[{w['i']}@{w['s']:.2f}]"); last = w['e']
        f.write(' '.join(line) + '\n')
