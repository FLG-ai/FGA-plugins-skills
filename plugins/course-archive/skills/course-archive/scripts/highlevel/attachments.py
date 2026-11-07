"""Download files linked from lesson bodies into _attachments/ and add a local link
next to each. Handles filesafe.space PDFs, Google Docs/Sheets template links
(exported as docx/xlsx), drive.google.com file links and Dropbox /s/ links.
Real filename from content-disposition. Canva and Drive folders stay links.
Usage: attachments.py "<course dir>"
"""
import glob, os, re, sys, urllib.parse, requests
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'}
d = sys.argv[1]; A = os.path.join(d, '_attachments'); os.makedirs(A, exist_ok=True)
PAT = re.compile(r'\((https://(?:assets\.cdn\.filesafe\.space/\S+?\.(?:pdf|docx?|xlsx?|pptx?|zip|png|jpe?g)'
                 r'|docs\.google\.com/(?:document|spreadsheets|presentation)/d/[\w-]+[^)\s]*'
                 r'|drive\.google\.com/(?:file/d/|uc\?)[^)\s]+'
                 r'|www\.dropbox\.com/s/[^)\s]+))\)')
cache = {}
taken = {}  # filename -> url, so a re-run overwrites its own files instead of making copies

def fetch(u):
    if u in cache: return cache[u]
    g = re.search(r'docs\.google\.com/(document|spreadsheets|presentation)/d/([\w-]+)', u)
    f = re.search(r'drive\.google\.com/(?:file/d/|uc\?.*id=)([\w-]+)', u)
    if g:
        fmt = {'document': 'docx', 'spreadsheets': 'xlsx', 'presentation': 'pptx'}[g.group(1)]
        url = f'https://docs.google.com/{g.group(1)}/d/{g.group(2)}/export?format={fmt}'
    elif f:
        url = f'https://drive.google.com/uc?export=download&id={f.group(1)}'
    elif 'dropbox.com' in u:
        url = re.sub(r'([?&])dl=0', r'\1dl=1', u) if 'dl=' in u else u + ('&' if '?' in u else '?') + 'dl=1'
    else:
        url = u
    try:
        r = requests.get(url, headers=UA, timeout=180)
        cd = r.headers.get('content-disposition', '')
        if not r.ok or 'text/html' in r.headers.get('content-type', ''):
            print('skip', r.status_code, u[:90]); cache[u] = None; return None
        m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)', cd)
        name = urllib.parse.unquote(m.group(1)) if m else os.path.basename(urllib.parse.urlparse(u).path)
        name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
        path = os.path.join(A, name)
        if taken.get(name, u) != u:
            b, e = os.path.splitext(name); name = f'{b} ({len(cache)}){e}'; path = os.path.join(A, name)
        taken[name] = u
        open(path, 'wb').write(r.content); cache[u] = name; print('got', name)
    except Exception as e:
        print('fail', u[:90], e); cache[u] = None
    return cache[u]

n = 0
for p in sorted(glob.glob(os.path.join(d, '[0-9]*.md'))):
    s = open(p).read()
    def sub(m):
        global n
        name = fetch(m.group(1))
        if not name: return m.group(0)
        n += 1
        return f'{m.group(0)} (local copy: [_attachments/{name}](<_attachments/{name}>))'
    s2 = PAT.sub(sub, s)
    if s2 != s: open(p, 'w').write(s2)
print(n, 'links pointed at local copies,', len([v for v in cache.values() if v]), 'files')
