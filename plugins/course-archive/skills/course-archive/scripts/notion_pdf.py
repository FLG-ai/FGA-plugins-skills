"""Notion-style PDF of a TUB Connect page (or any Notion block record).

Course material downloads are Notion-faithful PDFs,
never TUB's own PDF export. Every toggle open, prompts wrapped in full, cover,
icon, callouts, tables and images as on the Notion page.

Usage:
  python3 notion_pdf.py <tubconnect item id or slug> "<out.pdf>" [--images-from old.pdf]
  python3 notion_pdf.py --record page.json "<out.pdf>" [--images-from old.pdf]

Images: TUB's stored S3 links expire about an hour after TUB syncs a page. Order
of attempts per image: the live link, then images pulled from a PDF (the file
given with --images-from, else TUB's own export fetched for this purpose and
discarded), matched in page order, then a visible placeholder. The summary line
says how many came from where.

Renderer: headless Google Chrome when present (Mac), else WeasyPrint (cloud
sandbox: pip install weasyprint). Both read the same HTML.
"""
import base64, html, json, os, shutil, subprocess, sys, tempfile, urllib.request

API = 'https://tubconnect.com/api/public/pages/'
UA = {'User-Agent': 'Mozilla/5.0'}
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

COLORS = {'gray': '#787774', 'brown': '#9f6b53', 'orange': '#d9730d', 'yellow': '#cb912f', 'green': '#448361',
          'blue': '#337ea9', 'purple': '#9065b0', 'pink': '#c14c8a', 'red': '#d44c47'}
BGS = {'gray': '#f1f1ef', 'brown': '#f4eeee', 'orange': '#fbecdd', 'yellow': '#fbf3db', 'green': '#edf3ec',
       'blue': '#e7f3f8', 'purple': '#f6f3f9', 'pink': '#faf1f5', 'red': '#fdebec', 'default': '#f1f1ef'}

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: #37352f; font-size: 14.5px; line-height: 1.55; margin: 0; }
.wrap { max-width: 760px; margin: 0 auto; padding: 0 8px; }
.cover { width: 100%; height: 200px; object-fit: cover; display: block; margin-bottom: 8px; }
.icon { font-size: 64px; line-height: 1; margin: 8px 0 4px; }
h1.title { font-size: 36px; font-weight: 700; margin: 8px 0 18px; line-height: 1.2; }
h1 { font-size: 26px; font-weight: 600; margin: 30px 0 6px; } h2 { font-size: 21px; font-weight: 600; margin: 24px 0 4px; }
h3 { font-size: 17px; font-weight: 600; margin: 18px 0 2px; }
p { margin: 3px 0; } ul, ol { margin: 2px 0; padding-left: 24px; } li { margin: 2px 0; }
hr { border: 0; border-top: 1px solid #e9e9e7; margin: 14px 0; }
a { color: #37352f; text-decoration: underline; text-decoration-color: #c7c6c4; }
code { background: #f1f1ef; color: #eb5757; padding: 1px 4px; border-radius: 4px; font-size: 85%;
  font-family: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace; }
.code { background: #f7f6f3; border-radius: 4px; margin: 6px 0; padding: 26px 16px 14px; position: relative; }
.code .lang { position: absolute; top: 6px; left: 16px; font-size: 11px; color: #9b9a97; text-transform: capitalize; }
.code pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 11px; line-height: 1.5;
  font-family: "SFMono-Regular", Menlo, Consolas, "DejaVu Sans Mono", monospace; }
.callout { display: flex; gap: 10px; border-radius: 4px; padding: 14px 16px; margin: 6px 0; }
.cicon { font-size: 18px; line-height: 1.4; } .cbody { flex: 1; min-width: 0; }
.toggle { margin: 3px 0; } .tri { display: inline-block; width: 20px; font-size: 12px; }
.toggle .tbody { padding-left: 22px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13.5px; }
th, td { border: 1px solid #e9e9e7; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f7f6f3; font-weight: 600; }
img { max-width: 100%; border-radius: 3px; margin: 6px 0; }
.cap { font-size: 12.5px; color: #787774; margin: 2px 0 8px; }
.bookmark { border: 1px solid #e9e9e7; border-radius: 4px; padding: 12px 14px; margin: 6px 0; font-size: 13px; word-break: break-all; }
blockquote { border-left: 3px solid #37352f; margin: 6px 0; padding: 0 14px; }
.meta { color: #9b9a97; font-size: 12px; margin-bottom: 16px; }
.todo { margin: 3px 0; }
"""


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def data_uri(b):
    mime = 'image/jpeg' if b[:3] == b'\xff\xd8\xff' else 'image/gif' if b[:4] == b'GIF8' else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(b).decode()


def pdf_images(pdf_bytes, has_cover=True):
    """Images in page order, deduped, icons (<60px) dropped. TUB's export always opens with a
    wide banner; when the Notion page itself has no cover, that banner is not one of its images."""
    import fitz
    d, seen, out = fitz.open(stream=pdf_bytes, filetype='pdf'), set(), []
    for p in d:
        for im in p.get_images(full=True):
            x = im[0]
            if x in seen: continue
            seen.add(x)
            e = d.extract_image(x)
            if e['width'] < 60 or e['height'] < 60: continue
            if not has_cover and not out and p.number == 0 and e['width'] > 2.5 * e['height']: continue
            out.append(e['image'])
    return out


def build_html(rec, fallback_pdf=None, item_ref=None):
    page, blocks = rec['content']['page'], rec['content']['blocks']
    stats = {'live': 0, 'pdf': 0, 'missing': 0}
    pool = {'imgs': None}

    def fallback_pool():
        if pool['imgs'] is None:
            b = fallback_pdf
            if b is None and item_ref:
                try:
                    b = get(API + item_ref + '/download/pdf', 120)
                    if not b.startswith(b'%PDF'): b = None
                except Exception:
                    b = None
            pool['imgs'] = pdf_images(b, bool(cover_url)) if b else []
        return pool['imgs']

    order = []  # every image url in page order, cover first, so pdf images map by position

    def walk(bs):
        for b in bs:
            if b['type'] == 'image':
                d = b['image']; order.append((d.get('file') or d.get('external') or {}).get('url'))
            walk(b.get('children') or [])
    cover_url = ((page.get('cover') or {}).get('file') or (page.get('cover') or {}).get('external') or {}).get('url')
    if cover_url: order.append(cover_url)
    walk(blocks)
    # TUB's PDF puts the cover first, then body images in order
    order = ([cover_url] if cover_url else []) + [u for u in order if u != cover_url]

    def img(url):
        if not url: stats['missing'] += 1; return None
        try:
            b = get(url, 30); stats['live'] += 1; return data_uri(b)
        except Exception:
            pass
        imgs, pos = fallback_pool(), order.index(url) if url in order else -1
        if 0 <= pos < len(imgs):
            stats['pdf'] += 1; return data_uri(imgs[pos])
        stats['missing'] += 1; return None

    def rt(items):
        out = []
        for t in items or []:
            s = html.escape(t.get('plain_text', '')).replace('\n', '<br>')
            a = t.get('annotations', {})
            if a.get('code'): s = f'<code>{s}</code>'
            if a.get('bold'): s = f'<b>{s}</b>'
            if a.get('italic'): s = f'<i>{s}</i>'
            if a.get('strikethrough'): s = f'<s>{s}</s>'
            if a.get('underline'): s = f'<u>{s}</u>'
            c = a.get('color', 'default')
            if c.endswith('_background'): s = f'<span style="background:{BGS.get(c[:-11], "#f1f1ef")}">{s}</span>'
            elif c in COLORS: s = f'<span style="color:{COLORS[c]}">{s}</span>'
            if t.get('href'): s = f'<a href="{html.escape(t["href"])}">{s}</a>'
            out.append(s)
        return ''.join(out)

    def kids(b):
        return render(b.get('children') or [])

    def render(bs):
        h, i = [], 0
        while i < len(bs):
            b = bs[i]; t = b['type']; d = b.get(t, {}) or {}
            if t in ('bulleted_list_item', 'numbered_list_item'):
                tag, items = ('ul' if t == 'bulleted_list_item' else 'ol'), []
                while i < len(bs) and bs[i]['type'] == t:
                    bb = bs[i]; items.append(f'<li>{rt(bb[t].get("rich_text"))}{kids(bb)}</li>'); i += 1
                h.append(f'<{tag}>{"".join(items)}</{tag}>'); continue
            if t == 'paragraph':
                h.append(f'<p>{rt(d.get("rich_text")) or "&nbsp;"}</p>{kids(b)}')
            elif t in ('heading_1', 'heading_2', 'heading_3'):
                n, inner = t[-1], rt(d.get('rich_text'))
                if d.get('is_toggleable'):
                    h.append(f'<div class="toggle"><h{n}><span class="tri">▾</span>{inner}</h{n}><div class="tbody">{kids(b)}</div></div>')
                else:
                    h.append(f'<h{n}>{inner}</h{n}>{kids(b)}')
            elif t == 'toggle':
                h.append(f'<div class="toggle"><div><span class="tri">▾</span>{rt(d.get("rich_text"))}</div><div class="tbody">{kids(b)}</div></div>')
            elif t == 'callout':
                ic = (d.get('icon') or {}).get('emoji', '')
                bg = BGS.get((d.get('color') or 'default').replace('_background', ''), '#f1f1ef')
                h.append(f'<div class="callout" style="background:{bg}"><div class="cicon">{ic}</div><div class="cbody"><div>{rt(d.get("rich_text"))}</div>{kids(b)}</div></div>')
            elif t == 'quote':
                h.append(f'<blockquote>{rt(d.get("rich_text"))}{kids(b)}</blockquote>')
            elif t == 'code':
                code = html.escape(''.join(x.get('plain_text', '') for x in d.get('rich_text', [])))
                cap = rt(d.get('caption'))
                h.append(f'<div class="code"><div class="lang">{html.escape(d.get("language", ""))}</div><pre>{code}</pre></div>' + (f'<div class="cap">{cap}</div>' if cap else ''))
            elif t == 'divider':
                h.append('<hr>')
            elif t == 'image':
                src = img((d.get('file') or d.get('external') or {}).get('url'))
                cap = rt(d.get('caption'))
                h.append((f'<img src="{src}">' if src else '<div class="cap">[image not available from TUB]</div>') + (f'<div class="cap">{cap}</div>' if cap else ''))
            elif t in ('bookmark', 'embed', 'video', 'link_preview', 'file', 'pdf'):
                u = (d.get('url') or (d.get('external') or {}).get('url') or (d.get('file') or {}).get('url') or '').split('?X-Amz')[0]
                if u: h.append(f'<div class="bookmark">{t.replace("_", " ").title()}: <a href="{html.escape(u)}">{html.escape(u)}</a></div>')
            elif t == 'table':
                trs = []
                for ri, r in enumerate(b.get('children') or []):
                    tag = 'th' if (ri == 0 and d.get('has_column_header')) else 'td'
                    trs.append('<tr>' + ''.join(f'<{tag}>{rt(c)}</{tag}>' for c in r['table_row']['cells']) + '</tr>')
                h.append(f'<table>{"".join(trs)}</table>')
            elif t == 'to_do':
                h.append(f'<div class="todo">{"☑" if d.get("checked") else "☐"} {rt(d.get("rich_text"))}</div>{kids(b)}')
            else:
                txt = rt(d.get('rich_text')) if isinstance(d, dict) else ''
                if txt: h.append(f'<p>{txt}</p>')
                h.append(kids(b))
            i += 1
        return ''.join(h)

    body = render(blocks)
    cover = img(cover_url) if cover_url else None
    title = rec.get('title', '')
    icon = (page.get('icon') or {}).get('emoji', '')
    edited = (rec.get('lastEditedTime') or '')[:10]
    meta = f'Notion copy of the TUB Connect page. Page last edited {edited}. All toggles expanded.'
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{CSS}</style></head><body>'
           + (f'<img class="cover" src="{cover}">' if cover else '')
           + f'<div class="wrap"><div class="icon">{icon}</div><h1 class="title">{html.escape(title)}</h1><div class="meta">{meta}</div>{body}</div></body></html>')
    return doc, stats


def to_pdf(doc_html, out_pdf):
    if os.path.exists(CHROME) or shutil.which('google-chrome') or shutil.which('chromium'):
        exe = CHROME if os.path.exists(CHROME) else (shutil.which('google-chrome') or shutil.which('chromium'))
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
            f.write(doc_html)
        subprocess.run([exe, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                        f'--print-to-pdf={os.path.abspath(out_pdf)}', 'file://' + f.name],
                       check=True, capture_output=True, timeout=300)
        os.unlink(f.name)
        return 'chrome'
    from weasyprint import HTML  # cloud sandbox: pip install weasyprint
    HTML(string=doc_html).write_pdf(out_pdf)
    return 'weasyprint'


def make(item_ref=None, out_pdf='out.pdf', record=None, images_from=None):
    rec = record if record is not None else json.loads(get(API + item_ref))
    rec = rec.get('page', rec)
    fb = open(images_from, 'rb').read() if images_from else None
    doc, stats = build_html(rec, fb, item_ref or rec.get('id'))
    engine = to_pdf(doc, out_pdf)
    print(f'{out_pdf}: {engine}, images live {stats["live"]}, from pdf {stats["pdf"]}, missing {stats["missing"]}')
    return stats


if __name__ == '__main__':
    a = sys.argv[1:]
    imgs = None
    if '--images-from' in a:
        k = a.index('--images-from'); imgs = a[k + 1]; del a[k:k + 2]
    if a[0] == '--record':
        make(out_pdf=a[2], record=json.load(open(a[1])), images_from=imgs)
    else:
        make(a[0], a[1], images_from=imgs)
