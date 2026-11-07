#!/usr/bin/env python3
"""AI Employee Bootcamp hub (aiemployeebootcamp.co), TUB / Callan Faulkner.

Usage: python3 pull.py cookies.txt "<course dir>"

Auth is the hub.sid cookie from your Chrome (cookies.py aiemployeebootcamp).
/api/me gives tier and expiry, /api/resources lists everything with lock state
(is_unlocked, is_released). Per-session transcript and class-notes PDFs appear
there as signed Supabase urls (1 hour) once posted, titled "... [session:N]".
Replays are unlisted YouTube embeds on /hub/sessions, not in the API: grab the
id from the iframe in Chrome, then download with a current yt-dlp through
`uvx --python 3.12 --from "yt-dlp[default]" yt-dlp --js-runtimes node` (the
Python 3.9 yt-dlp is too old for YouTube). The Quantum Leap Pack is
/downloads/the-quantum-leap-pack.pdf (cookie). The Social Growth Kit is a TUB
page: notion_pdf.py / notion_md.py, and its skill zips download through
tubconnect.com/api/images/notion/<block id> (read the ids from the rendered page,
the S3 urls in the API expire). Re-runs skip files already on disk.
"""
import http.cookiejar, json, os, re, sys, requests, fitz

UA = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36'
H = 'https://aiemployeebootcamp.co'


def pdf_md(pdf, md, title, transcript=False):
    t = '\n'.join(p.get_text() for p in fitz.open(pdf))
    if transcript:
        out, buf = [], []
        for l in (x.strip() for x in t.splitlines()):
            if re.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?', l):
                if buf: out.append(' '.join(buf)); buf = []
                out.append(f'\n**[{l}]**'); continue
            if not l or re.fullmatch(r'\d+ / \d+|\d+|®', l): continue
            buf.append(l)
        if buf: out.append(' '.join(buf))
        t = '\n'.join(out)
    open(md, 'w').write(f'# {title}\n\nOriginal PDF: `{os.path.basename(pdf)}` beside this file.\n\n{t}\n')


def main(cookies, out):
    cj = http.cookiejar.MozillaCookieJar(cookies); cj.load(ignore_discard=True, ignore_expires=True)
    s = requests.Session(); s.cookies = cj; s.headers['User-Agent'] = UA
    me = s.get(H + '/api/me').json()
    print('tier', me.get('tier'), 'until', me.get('expires_at'))
    for d in ('_transcripts', '_attachments', 'Bonuses'): os.makedirs(f'{out}/{d}', exist_ok=True)
    for r in s.get(H + '/api/resources').json():
        state = 'open' if r['is_unlocked'] and r['is_released'] else 'LOCKED/unreleased'
        print(f"{r['kind']:9} {state:17} {r['title']}")
        u = r.get('url') or ''
        if 'supabase' not in u or state != 'open': continue
        name = u.split('?')[0].rsplit('/', 1)[1]
        m = re.search(r'\[session:(\d+)\]', r['title']); n = int(m.group(1)) if m else 99
        tr = '/transcript/' in u
        pdf = f"{out}/{'_transcripts' if tr else '_attachments'}/{name}"
        if not os.path.exists(pdf):
            open(pdf, 'wb').write(requests.get(u, headers={'User-Agent': UA}).content)
            base = re.sub(r'\s*\[session:\d+\]', '', r['title'])
            pdf_md(pdf, pdf.rsplit('/', 1)[0] + f'/{n:02d} {base}.md', base, tr)
            print('   saved', name)
    q = f'{out}/Bonuses/The Quantum Leap Pack.pdf'
    if not os.path.exists(q):
        r = s.get(H + '/downloads/the-quantum-leap-pack.pdf')
        if r.ok and r.content[:4] == b'%PDF': open(q, 'wb').write(r.content); print('   saved Quantum Leap Pack')


if __name__ == '__main__':
    main(*sys.argv[1:3])
