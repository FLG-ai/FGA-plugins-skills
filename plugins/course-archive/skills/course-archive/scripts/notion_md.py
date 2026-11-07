#!/usr/bin/env python3
"""Markdown copy of a TUB Connect page (or any Notion block record), full text.

The markdown twin of notion_pdf.py. Same source, same walk: every toggle opened,
every code block and prompt kept whole, nothing truncated. Use it wherever a
lesson needs a Notes.md or a prompt or skill needs its library file.

Usage:
  python3 notion_md.py <tubconnect item id or slug> "<out.md>" [--cookies cookies.txt] [--front]
  python3 notion_md.py --record page.json "<out.md>" [--front]

--front writes the Prompt Library frontmatter (id, slug, title, categories,
accessTags, promptType, notionUrl, visitCount) used in TUB Connect Library/
Prompts and Skills. Without it you get a Notes.md header instead.

Ids rotate on TUB's side (all of them did before 26 Sep 2026), so prefer the
slug, which survives renames.
"""
import json, subprocess, sys, datetime

API = 'https://tubconnect.com/api/public/pages/'


def fetch(ref, cookies=None):
    cmd = ['curl', '-s', '-m', '60', API + ref]
    if cookies:
        cmd[1:1] = ['-b', cookies]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(r.stdout)


def rt(items):
    out = []
    for t in items or []:
        s = t.get('plain_text', '')
        a = t.get('annotations', {}) or {}
        if a.get('code') and s.strip():
            s = f'`{s}`'
        if a.get('bold') and s.strip():
            s = f'**{s}**'
        if a.get('italic') and s.strip():
            s = f'_{s}_'
        if a.get('strikethrough') and s.strip():
            s = f'~~{s}~~'
        if t.get('href'):
            s = f'[{s}]({t["href"]})'
        out.append(s)
    return ''.join(out)


def render(bs, depth=0):
    pad = '  ' * depth
    out = []
    n = 0
    for b in bs or []:
        t = b.get('type')
        d = b.get(t, {}) or {}
        kids = b.get('children') or []
        n = n + 1 if t == 'numbered_list_item' else 0
        if t in ('heading_1', 'heading_2', 'heading_3'):
            out.append('\n' + '#' * (int(t[-1]) + 1) + ' ' + rt(d.get('rich_text')) + '\n')
            out += render(kids, depth)
        elif t == 'paragraph':
            txt = rt(d.get('rich_text'))
            out.append(pad + txt if txt.strip() else '')
            out += render(kids, depth + 1)
        elif t == 'bulleted_list_item':
            out.append(f'{pad}- {rt(d.get("rich_text"))}')
            out += render(kids, depth + 1)
        elif t == 'numbered_list_item':
            out.append(f'{pad}{n}. {rt(d.get("rich_text"))}')
            out += render(kids, depth + 1)
        elif t == 'to_do':
            out.append(f'{pad}- [{"x" if d.get("checked") else " "}] {rt(d.get("rich_text"))}')
            out += render(kids, depth + 1)
        elif t == 'toggle':
            out.append(f'{pad}**▾ {rt(d.get("rich_text"))}**')
            out += render(kids, depth + 1)
        elif t == 'quote':
            for line in rt(d.get('rich_text')).split('\n'):
                out.append(f'{pad}> {line}')
            out += render(kids, depth + 1)
        elif t == 'callout':
            icon = (d.get('icon') or {}).get('emoji', '')
            out.append(f'{pad}> {icon} {rt(d.get("rich_text"))}'.rstrip())
            for line in render(kids, 0):
                out.append(f'{pad}> {line}' if line else f'{pad}>')
        elif t == 'code':
            code = ''.join(x.get('plain_text', '') for x in d.get('rich_text', []))
            out.append(f'{pad}```{d.get("language", "")}')
            out += [pad + line for line in code.split('\n')]
            out.append(f'{pad}```')
            cap = rt(d.get('caption'))
            if cap:
                out.append(f'{pad}_{cap}_')
        elif t == 'divider':
            out.append('\n---\n')
        elif t == 'table':
            rows = [r for r in kids if r.get('type') == 'table_row']
            for i, r in enumerate(rows):
                cells = [rt(c).replace('|', '\\|').replace('\n', ' ') for c in r['table_row'].get('cells', [])]
                out.append('| ' + ' | '.join(cells) + ' |')
                if i == 0:
                    out.append('|' + '---|' * len(cells))
        elif t == 'image':
            cap = rt(d.get('caption'))
            out.append(f'{pad}_[image{": " + cap if cap else ""}]_')
        elif t in ('file', 'pdf', 'video', 'embed', 'bookmark', 'link_preview'):
            url = d.get('url') or (d.get('file') or d.get('external') or {}).get('url', '')
            name = d.get('name') or rt(d.get('caption')) or t
            out.append(f'{pad}[{name}]({url})' if url else f'{pad}_[{t}]_')
        elif t in ('column_list', 'column', 'synced_block'):
            out += render(kids, depth)
        elif t == 'child_page':
            out.append(f'{pad}_[sub-page: {d.get("title", "")}]_')
        else:
            txt = rt(d.get('rich_text')) if isinstance(d, dict) else ''
            if txt:
                out.append(pad + txt)
            out += render(kids, depth)
    return out


def names(xs):
    return [x.get('name') if isinstance(x, dict) else x for x in (xs or [])]


def make(rec, out, front=False):
    c = rec.get('content') or {}
    blocks = c.get('blocks') if isinstance(c, dict) else None
    blocks = blocks or rec.get('blocks') or []
    body = '\n'.join(render(blocks))
    while '\n\n\n' in body:
        body = body.replace('\n\n\n', '\n\n')
    title = rec.get('title', '')
    if front:
        q = lambda v: json.dumps(v, ensure_ascii=False)
        head = ('---\n'
                f'id: {q(rec.get("id"))}\n'
                f'slug: {q(rec.get("slug"))}\n'
                f'title: {q(title)}\n'
                f'categories: {q(names(rec.get("categories")))}\n'
                f'accessTags: {q(names(rec.get("accessTags")))}\n'
                f'promptType: {q(rec.get("promptType"))}\n'
                f'notionUrl: {q(rec.get("notionUrl"))}\n'
                f'visitCount: {rec.get("visitCount", 0)}\n'
                '---\n\n'
                f'# {title}\n\n{rec.get("description") or ""}\n\n')
    else:
        edited = (rec.get('lastEditedTime') or '')[:10]
        head = (f'# {title}\n\n'
                f'_TUB Connect | slug `{rec.get("slug")}` | page last edited {edited}_\n\n'
                f'Full text from the Notion source, every toggle opened. Written '
                f'{datetime.date.today().isoformat()}.\n\n---\n\n')
    open(out, 'w').write(head + body.strip() + '\n')
    return len(body.split())


if __name__ == '__main__':
    a = sys.argv[1:]
    front = '--front' in a
    cookies = a[a.index('--cookies') + 1] if '--cookies' in a else None
    a = [x for i, x in enumerate(a) if x != '--front' and x != '--cookies' and (i == 0 or a[i - 1] != '--cookies')]
    if a[0] == '--record':
        rec = json.load(open(a[1]))
        out = a[2]
    else:
        rec = fetch(a[0], cookies)
        out = a[1]
    w = make(rec, out, front)
    print(f'{w} words -> {out}')
