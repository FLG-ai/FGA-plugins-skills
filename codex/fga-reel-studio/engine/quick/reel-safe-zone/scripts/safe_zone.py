#!/usr/bin/env python3
"""Reel Safe Zone: check a finished reel for text that Instagram's buttons, caption or header will cover.
Usage: python3 safe_zone.py <video> [--fps 4] [--out <folder>]
Writes <video name> - safe zone check/ with report.md, flagged.jpg (each problem, zone shaded, text boxed)
and overview.jpg (the whole reel with the red zone drawn on). Standard library only, plus ffmpeg and the
Mac's built-in text recognition (compiled once from rzcheck.swift)."""
import json, os, shutil, subprocess, sys, tempfile, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path.home() / '.cache' / 'reel-safe-zone'
ZONE_NAMES = {'top': 'top 250 px (Reels header and camera icon)',
              'bottom': 'bottom, below 1480 px (username, caption, music line)',
              'left edge': 'left edge (60 px)', 'right edge': 'right edge (60 px)',
              'buttons': 'right-hand buttons (like, comment, share)'}

def tool(name):
    for p in [shutil.which(name), f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}', str(Path.home() / '.local/bin' / name)]:
        if p and os.path.exists(p): return p
    sys.exit(f'{name} not found. Install it with: brew install ffmpeg')

def checker():
    src, out = HERE / 'rzcheck.swift', CACHE / 'rzcheck'
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        CACHE.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(['swiftc', '-O', str(src), '-o', str(out)], capture_output=True, text=True)
        if r.returncode: sys.exit('Could not build the text checker. Install Apple\'s command line tools with: xcode-select --install\n' + r.stderr[-800:])
    return str(out)

def ts(t): return f'{int(t // 60)}:{t % 60:04.1f}'

def main():
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    video = Path(args[0]).expanduser().resolve()
    fps = float(args[args.index('--fps') + 1]) if '--fps' in args else 4.0
    out = Path(args[args.index('--out') + 1]).expanduser() if '--out' in args else video.parent / f'{video.stem} - safe zone check'
    out.mkdir(parents=True, exist_ok=True)
    ff, fp = tool('ffmpeg'), tool('ffprobe')
    w, h = [int(x) for x in subprocess.run([fp, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                             '-of', 'csv=p=0', str(video)], capture_output=True, text=True).stdout.strip().split(',')[:2]]
    dur = float(subprocess.run([fp, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)],
                               capture_output=True, text=True).stdout.strip() or 0)
    note = '' if abs(w / h - 9 / 16) < 0.02 else f'\n> Note: this video is {w}x{h}, not 9:16. The zones assume a full-screen vertical reel, so treat the result as a guide.\n'
    tmp = Path(tempfile.mkdtemp(prefix='rz_'))
    try:
        subprocess.run([ff, '-nostdin', '-v', 'error', '-i', str(video), '-vf', f'fps={fps},scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
                        str(tmp / 'f_%05d.png')], check=True)
        subprocess.run([checker(), str(tmp), str(tmp / 'out'), str(fps)], check=True)
        hits = json.load(open(tmp / 'out' / 'hits.json'))['hits']
        # one problem per zone: each hit counts once, under its most serious zone; nearby times merge into ranges
        PRI = ['left edge', 'right edge', 'buttons', 'top', 'bottom']
        events = []
        for z in PRI:
            zh = sorted([x for x in hits if min(x['zones'], key=PRI.index) == z], key=lambda r: r['t'])
            if not zh: continue
            ranges = []
            for x in zh:
                if ranges and x['t'] - ranges[-1][1] <= 1.0: ranges[-1][1] = x['t']
                else: ranges.append([x['t'], x['t']])
            uniq = []
            for s in sorted({x['text'].strip() for x in zh}, key=lambda s: -len(s)):
                if not any(s.lower() in u.lower() for u in uniq): uniq.append(s)
            frames = [x['frame'] for x in zh]
            events.append({'zones': [z], 'start': ranges[0][0], 'end': ranges[-1][1], 'ranges': ranges, 'frames': frames,
                           'text': ', '.join(f'"{s[:30]}"' for s in uniq[:4]) + (f' and {len(uniq) - 4} more' if len(uniq) > 4 else '')})
        events.sort(key=lambda e: e['start'])
        # flagged sheet: one annotated frame per problem
        sel = tmp / 'sel'; sel.mkdir()
        picks = []
        for e in events:
            for r0, r1 in e['ranges']:
                fr = [f for f in e['frames'] if r0 * fps - 0.5 <= f <= r1 * fps + 0.5]
                if fr: picks.append((r0, fr[len(fr) // 2]))
        for i, (_, f) in enumerate(sorted(set(picks))[:32]):
            src = tmp / 'out' / f'flag_{f:05d}.jpg'
            if src.exists(): shutil.copy(src, sel / f'{i:03d}.jpg')
        n = len(list(sel.glob('*.jpg')))
        if n:
            cols = min(4, n)
            subprocess.run([ff, '-nostdin', '-v', 'error', '-y', '-i', str(sel / '%03d.jpg'), '-vf', f'scale=270:480,tile={cols}x{math.ceil(n / cols)}:padding=6:color=white',
                            '-frames:v', '1', '-q:v', '3', str(out / 'flagged.jpg')], check=True)
        # overview: the whole reel with the zone drawn on
        step = max(1.0, dur / 24)
        zone = ('drawbox=x=0:y=0:w=1080:h=250:color=red@0.3:t=fill,drawbox=x=0:y=1480:w=1080:h=440:color=red@0.3:t=fill,'
                'drawbox=x=0:y=250:w=60:h=1230:color=red@0.3:t=fill,drawbox=x=1020:y=250:w=60:h=800:color=red@0.3:t=fill,'
                'drawbox=x=940:y=1050:w=140:h=430:color=red@0.3:t=fill')
        subprocess.run([ff, '-nostdin', '-v', 'error', '-y', '-i', str(video), '-vf',
                        f'fps=1/{step:.3f},scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,{zone},scale=180:320,tile=8x3:padding=4:color=white',
                        '-frames:v', '1', '-q:v', '3', str(out / 'overview.jpg')], check=True)
        lines = [f'# Safe zone check: {video.name}', '', f'Checked {ts(dur)} at {fps:g} frames a second against Instagram Reels\' red zone (1080x1920: top 250 px, below 1480 px, 60 px at each side, and the button column right of 940 px below 1050 px).', note]
        if not events:
            lines += ['**All clear.** No on-screen text sits in the red zone.', '', 'Still worth a glance at `overview.jpg`: the check reads text, so a logo or sticker without letters is not checked.']
        else:
            lines += [f'**Problems in {len(events)} area{"s" if len(events) != 1 else ""}.** Move these inside the safe area. Each one is boxed in red in `flagged.jpg`.', '',
                      '| Covered by | When | Text it caught |', '|---|---|---|']
            for e in events:
                when = ', '.join(ts(a) if a == b else f'{ts(a)} to {ts(b)}' for a, b in e['ranges'][:8]) + (' and more' if len(e['ranges']) > 8 else '')
                lines.append(f"| {ZONE_NAMES.get(e['zones'][0], e['zones'][0])} | {when} | {e['text'].replace('|', '/')} |")
            lines += ['', 'Fixes: keep text between 250 px and 1480 px from the top, at least 60 px from each side, and left of 940 px in the lower third, where the like, comment and share buttons sit.']
            lines += ['', 'Text the check picks up from the background (a sign, a shirt, a screenshot) can show up here too. Skip anything that isn\'t your own text.']
        (out / 'report.md').write_text('\n'.join(lines) + '\n')
        print(json.dumps({'out': str(out), 'problems': len(events), 'events': [{'when': ts(e['start']), 'text': e['text'], 'zones': e['zones']} for e in events]}, indent=1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
