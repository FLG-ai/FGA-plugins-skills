"""Build a course archive from a HighLevel client-portal categories dump.

Usage: build.py <categories.json> "<out dir>" <portal host> <product id> [section order regex ...]

categories.json is the response of
  GET services.leadconnectorhq.com/clientportal-middleware/memberships/locations/<loc>/user-purchase/categories?product_id=<id>
(see api.py). Every lesson's HTML body, video file and caption file are in it.
Videos and .srt captions sit on public CDNs (filesafe.space, storage.googleapis.com,
cdn.courses.apisystem.tech), so they download with no login.
Writes one markdown file per lesson, INDEX.md and _manifest.json (for the video
and transcript steps). Section order: pass regexes in the order you want, since
the platform's sequenceNo values collide.
"""
import html, json, os, re, sys

CDN = 'https://cdn.courses.apisystem.tech'


def absu(u):
    return CDN + u if u and u.startswith('/') else u


def safe(s):
    s = re.sub(r'[\\/:*?"<>|#\[\]]', '', html.unescape(s)).strip()
    return re.sub(r'\s+', ' ', s)[:90].rstrip(' .')


def md(h):
    """Small HTML to markdown for Quill bodies."""
    h = h or ''
    h = re.sub(r'<(?:iframe|video|embed|source)[^>]*src="([^"]+)"[^>]*>(?:\s*</(?:iframe|video|embed)>)?',
               lambda m: f'\n\n\u25b6 Embedded video: {absu(html.unescape(m.group(1)))}\n\n', h)
    h = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', lambda m: f'\n![]({absu(html.unescape(m.group(1)))})\n', h)
    h = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>',
               lambda m: f'[{re.sub("<[^>]+>", "", m.group(2)).strip() or m.group(1)}]({html.unescape(m.group(1))})', h, flags=re.S)
    h = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: '\n\n' + '#' * (int(m.group(1)) + 1) + ' ' + m.group(2) + '\n\n', h, flags=re.S)
    h = re.sub(r'</?(strong|b)(\s[^>]*)?>', '**', h)
    h = re.sub(r'</?(em|i)(\s[^>]*)?>', '*', h)
    h = re.sub(r'<li[^>]*>', '\n- ', h)
    h = re.sub(r'<br\s*/?>', '\n', h)
    h = re.sub(r'</(p|div|ul|ol|li|blockquote)>', '\n', h)
    h = re.sub(r'<[^>]+>', '', h)
    h = html.unescape(h).replace(' ', ' ')
    h = re.sub(r'\*\*\s*\*\*', '', h)
    h = re.sub(r'[ \t]+\n', '\n', h)
    return re.sub(r'\n{3,}', '\n\n', h).strip()


def main():
    src, out, host, product = sys.argv[1:5]
    order = sys.argv[5:]
    cats = json.load(open(src))['categories']

    def rank(c):
        for i, rx in enumerate(order):
            if re.search(rx, c['title'], re.I):
                return (i, c['sequenceNo'])
        return (len(order), c['sequenceNo'])

    cats.sort(key=rank)
    os.makedirs(out, exist_ok=True)
    manifest, idx, n = [], [], 0
    for c in cats:
        sec = html.unescape(c['title']).strip()
        idx.append(f'\n## {sec}\n')
        for p in sorted(c.get('posts', []), key=lambda p: p['sequenceNo']):
            n += 1
            title = html.unescape(p['title']).strip()
            stem = f'{n:02d} {safe(title)}'
            src_url = f'https://{host}/courses/products/{product}/categories/{c["id"]}/posts/{p["id"]}'
            v = p.get('video') or {}
            vurl = absu(v.get('url'))
            subs = {k: absu(u) for k, u in ((v.get('metaData') or {}).get('subtitles') or {}).items()}
            locked = p.get('visibility') != 'published' or p.get('lockedByPost') or p.get('lockedByCategory')
            lines = [f'# {title}', '', f'Section: {sec}', f'Source: {src_url}']
            if vurl:
                lines += [f'Video: [_videos/{stem}.mp4](<_videos/{stem}.mp4>) (original: {vurl})',
                          f'Transcript: [_transcripts/{stem}.md](<_transcripts/{stem}.md>)']
            lines += ['', md(p.get('description')) or '*(no written notes on this lesson)*', '']
            open(os.path.join(out, stem + '.md'), 'w').write('\n'.join(lines))
            embeds = [absu(html.unescape(u)) for u in re.findall(r'<(?:iframe|video|embed|source)[^>]*src="([^"]+)"', p.get('description') or '')]
            manifest.append({'embeds': embeds, 'n': n, 'stem': stem, 'title': title, 'section': sec, 'post_id': p['id'],
                             'video': vurl, 'subtitles': subs, 'locked': bool(locked)})
            idx.append(f'- [{title}](<{stem}.md>)' + (' (video)' if vurl else ''))
    mp = os.path.join(out, '_manifest.json')
    if os.path.exists(mp):  # re-run: keep what the transcript and video steps recorded
        old = {x['stem']: x for x in json.load(open(mp))}
        for x in manifest:
            for k, v in old.get(x['stem'], {}).items():
                x.setdefault(k, v)
    json.dump(manifest, open(mp, 'w'), indent=1)
    return manifest, idx


if __name__ == '__main__':
    m, idx = main()
    open(os.path.join(sys.argv[2], '_index_body.md'), 'w').write('\n'.join(idx) + '\n')
    print(len(m), 'lessons,', sum(1 for x in m if x['video']), 'videos,', sum(1 for x in m if x['subtitles']), 'with captions')
