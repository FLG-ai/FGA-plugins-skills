"""Google Doc index tables for a HighLevel course built with build.py.

Usage: doc_tables.py "<course dir>" <materials.txt or -> <out.json>
One table per section: Lesson | Watch | Transcript | Notes | Downloads.
Watch, Transcript and Notes point at the Drive copies (Drive IDs from the
Drive for Desktop xattr). Downloads use the public original links where they
open without a login : lesson Files on the portal CDN,
Google template copy links, Canva, Dropbox. materials.txt is the
"post8|name|url" list gathered from the lesson pages (~ and ^ are CDN prefixes).
"""
import json, os, re, subprocess, sys

d, mats, out = sys.argv[1:4]
m = json.load(open(os.path.join(d, '_manifest.json')))
CDN = 'https://cdn.courses.apisystem.tech/memberships/pgpToP1Qu87lbuAwPPVT/'


def did(p):
    r = subprocess.run(['xattr', '-p', 'com.google.drivefs.item-id#S', p], capture_output=True, text=True)
    return r.stdout.strip() or None


pending = []


def drive(p, label):
    i = did(p) if os.path.exists(p) else None
    if not i:
        pending.append(os.path.basename(p))
        return 'pending'
    return f'[{label}](https://drive.google.com/file/d/{i}/view)'


files = {}
if mats != '-' and os.path.exists(mats):
    for line in open(mats):
        p, name, u = line.rstrip('\n').split('|')
        u = u.replace('~', CDN).replace('^', 'https://assets.cdn.filesafe.space/')
        files.setdefault(p, []).append((name, u))


def short(name):
    n = re.sub(r'\.(pdf|docx?|xlsx?)$', '', name)
    n = re.sub(r'^(LG|FGF|TN)[ _]+', '', n).replace('_', ' ').strip()
    kind = 'Slides' if 'Slides' in n else 'Chat log' if 'Chat' in n else 'Transcript' if re.search(r'Tran+s?cr', n) else None
    return kind or n[:50]


groups, order = {}, []
for x in m:
    sec, stem = x['section'], x['stem']
    if sec not in groups:
        groups[sec] = []; order.append(sec)
    vids = []
    if x['video']:
        vids.append(os.path.join(d, '_videos', stem + '.mp4'))
    for i, _ in enumerate([e for e in x.get('embeds', []) if 'vimeo.com' in e or re.search(r'\.(mp4|mov|m4v)(\?|$)', e)], 1):
        n = len([e for e in x.get('embeds', []) if 'vimeo.com' in e or re.search(r'\.(mp4|mov|m4v)(\?|$)', e)])
        vids.append(os.path.join(d, '_videos', f"{stem} - video {i}.mp4" if n > 1 else f"{stem} - video.mp4"))
    watch = [drive(v, 'Watch' if len(vids) == 1 else f'Video {k}') for k, v in enumerate(vids, 1)]
    tr = drive(os.path.join(d, x['transcript']), 'Transcript') if x.get('transcript') else ''
    notes = drive(os.path.join(d, stem + '.md'), 'Notes')
    body = open(os.path.join(d, stem + '.md')).read()
    dl, seen, kinds = [], set(), set()
    # links written in the lesson text first, then the lesson's Files, skipping a Files entry
    # whose kind (slides, chat log, transcript) the text already links (Phase 1 posts both)
    for lab, u in re.findall(r'\[([^\]]{2,60})\]\((https://(?:docs\.google\.com/(?:document|spreadsheets)/d/[^)\s]+|www\.canva\.com/design/[^)\s]+|www\.dropbox\.com/s/[^)\s]+|assets\.cdn\.filesafe\.space/[^)\s]+\.pdf))\)', body):
        if u in seen:
            continue
        seen.add(u)
        lab = re.sub(r'[*>]+', '', lab).strip() or 'File'
        kinds.add(short(lab).lower())
        dl.append(f'[{lab[:50]}]({u})')
    for name, u in files.get(x['post_id'][:8], []):
        if x['post_id'][:8] == '1ccd0d0a' and 'November 6th' not in name:
            continue
        lab = 'Transcript PDF' if name.startswith('GMT') and '.transcript' in name else 'Chat log' if name.startswith('GMT') else short(name)
        k = lab.lower().replace(' pdf', '')
        if k in kinds:
            continue
        if lab in seen:
            lab = name[:50]
        seen.add(lab)
        dl.append(f'[{lab}]({u})')
    title = x['title'].replace('|', '/').strip()
    groups[sec].append(f"| {title} | {' '.join(watch) or 'text only'} | {tr} | {notes} | {'<br>'.join(dl)} |")

res = {'groups': [], 'pending': pending}
for g in order:
    md = f"## {g}\n\n| Lesson | Watch | Transcript | Notes | Downloads |\n|---|---|---|---|---|\n" + '\n'.join(groups[g]) + '\n'
    res['groups'].append({'heading': g, 'markdown': md})
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
print([(g['heading'], g['markdown'].count('\n') - 4) for g in res['groups']], 'pending:', pending)
