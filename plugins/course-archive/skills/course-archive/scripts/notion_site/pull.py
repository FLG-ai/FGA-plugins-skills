#!/usr/bin/env python3
"""Archive a PUBLIC Notion site (notion.site) to markdown, databases included.

Usage: pull.py <public url or page id> "<out dir>"

No login and no integration token: notion.site serves the same private /api/v3
endpoints the web app uses. loadCachedPageChunkV2 gives the page tree,
queryCollection gives each database's rows, and every row is itself a page whose
body is fetched the same way. Writes INDEX.md, one markdown file per database
(properties as a table) and per sub-page, plus _manifest.json.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

url, out = sys.argv[1:3]
host = re.search(r"https?://([^/]+)", url).group(1) if url.startswith("http") else "www.notion.so"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def post(path, body):
    r = urllib.request.urlopen(urllib.request.Request(
        f"https://{host}/api/v3/{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA}), timeout=120)
    return json.loads(r.read())


def page_id(u):
    if not u.startswith("http"):
        return u
    h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=60).read().decode("utf-8", "replace")
    m = re.search(r'"pageId":"([0-9a-f-]{36})"', h)
    if m:
        return m.group(1)
    raw = re.search(r"([0-9a-f]{32})(?:\?|$|#)", u).group(1)
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def val(v):
    v = v.get("value", v)
    return v.get("value", v)


def chunk(pid):
    return post("loadCachedPageChunkV2", {"page": {"id": pid}, "limit": 400,
                                          "cursor": {"stack": []}, "chunkNumber": 0, "verticalColumns": False})


def rich(t):
    """Notion rich text array -> markdown."""
    o = []
    for seg in t or []:
        if not seg:
            continue
        s = seg[0] if isinstance(seg[0], str) else str(seg[0])
        for a in ((seg[1] if len(seg) > 1 else None) or []):
            if not a:
                continue
            k = a[0]
            if k == "b": s = f"**{s}**"
            elif k == "i": s = f"*{s}*"
            elif k == "c": s = f"`{s}`"
            elif k == "s": s = f"~~{s}~~"
            elif k == "a": s = f"[{s}]({a[1]})"
        o.append(s)
    return "".join(o).replace("—", ", ")


PFX = {"header": "# ", "sub_header": "## ", "sub_sub_header": "### ", "bulleted_list": "- ",
       "numbered_list": "1. ", "to_do": "- [ ] ", "quote": "> ", "toggle": "- "}


def body_md(pid, blocks, depth=0, seen=None):
    seen = seen if seen is not None else set()
    if pid in seen:
        return []
    seen.add(pid)
    b = blocks.get(pid)
    if not b:
        return []
    out = []
    for cid in (val(b).get("content") or []):
        c = blocks.get(cid)
        if not c:
            continue
        x = val(c); t = x.get("type"); p = x.get("properties") or {}
        txt = rich(p.get("title"))
        if t == "divider":
            out.append("---")
        elif t == "code":
            out.append("```\n" + txt + "\n```")
        elif t == "callout":
            out.append("> " + txt.replace("\n", "\n> "))
        elif t in ("image", "video", "file", "pdf", "embed", "bookmark"):
            src = rich(p.get("source")) or (x.get("format") or {}).get("display_source") or ""
            out.append(f"[{t}]({src})" if src else f"_{t}_")
        elif t in ("page", "collection_view", "collection_view_page"):
            continue                      # handled as its own file
        elif txt or t in PFX:
            out.append(PFX.get(t, "") + txt)
        out += ["  " + l for l in body_md(cid, blocks, depth + 1, seen)]
    return [l for l in out if l is not None]


def prop_text(schema, props, key):
    spec = schema.get(key) or {}
    v = (props or {}).get(key)
    ty = spec.get("type")
    if v is None:
        return ""
    if ty in ("multi_select", "select"):
        return rich(v).replace(",", ", ")
    if ty == "checkbox":
        return "yes" if rich(v) == "Yes" else ""
    if ty == "date":
        try:
            dv = v[0][1][0][1]
            return dv.get("start_date", "")
        except Exception:
            return ""
    return rich(v)


ATT = []                                  # (block id, attachment url, filename)


def note_attachment(blocks):
    for k, v in blocks.items():
        x = val(v)
        if x.get("type") in ("file", "image", "pdf", "video", "audio"):
            src = (x.get("properties") or {}).get("source") or []
            u = src[0][0] if src and src[0] else ""
            if u.startswith("attachment:"):
                ATT.append((k, u, u.split(":")[-1]))


def fetch_attachments(out):
    """Notion attachments need a signed url: getSignedFileUrls, one permissionRecord per block."""
    if not ATT:
        return {}
    att_dir = os.path.join(out, "_attachments")
    os.makedirs(att_dir, exist_ok=True)
    got = {}
    res = post("getSignedFileUrls", {"urls": [{"permissionRecord": {"table": "block", "id": b}, "url": u}
                                              for b, u, _ in ATT]})
    for (b, u, name), su in zip(ATT, res.get("signedUrls") or []):
        dest = os.path.join(att_dir, name)
        if not os.path.exists(dest):
            try:
                data = urllib.request.urlopen(urllib.request.Request(su, headers={"User-Agent": UA}), timeout=300).read()
            except Exception as e:
                print("attachment failed:", name, e); continue
            open(dest, "wb").write(data)
        got[u] = name
    return got


def safe(s, n=80):
    s = re.sub(r"[^\w\s\-.,&()'’]+", "", s or "").strip()
    return re.sub(r"\s+", " ", s)[:n].strip(" .") or "untitled"


pid = page_id(url)
os.makedirs(out, exist_ok=True)
root = chunk(pid)
rm = root["recordMap"]
blocks = dict(rm.get("block") or {})
top = val(blocks[pid])
title = rich((top.get("properties") or {}).get("title")) or "Notion page"
note_attachment(blocks)
index = [f"# {title}", "", f"Source: {url}", "", f"Archived {time.strftime('%Y-%m-%d')}.", ""]
manifest, n = [], 0

intro = body_md(pid, blocks)
if intro:
    index += ["", "## Page text", ""] + intro + [""]

# --- databases ---
views = [(val(v).get("collection_id"), (val(v).get("view_ids") or [None])[0], val(v).get("space_id"))
         for v in blocks.values() if val(v).get("type") in ("collection_view", "collection_view_page")]
index += ["", "## Databases", ""]
for cid, vid, sid in views:
    coll = val((rm.get("collection") or {}).get(cid, {}))
    cname = rich(coll.get("name")) or "Database"
    schema = coll.get("schema") or {}
    cols = [(k, s.get("name")) for k, s in schema.items() if s.get("name")]
    cols.sort(key=lambda kv: 0 if kv[0] == "title" else 1)
    res = post("queryCollection?src=initial_load", {
        "source": {"type": "collection", "id": cid, "spaceId": sid},
        "collectionView": {"id": vid, "spaceId": sid},
        "loader": {"reducers": {"collection_group_results": {"type": "results", "limit": 500}},
                   "sort": [], "searchQuery": "", "userTimeZone": "Europe/Dublin", "type": "results"}})
    ids = ((res.get("result") or {}).get("reducerResults") or {}).get("collection_group_results", {}).get("blockIds") or []
    rb = dict((res.get("recordMap") or {}).get("block") or {})
    n += 1
    fname = f"{n:02d} {safe(cname)}.md"
    lines = [f"# {cname}", "", f"Source: {url}  ", f"{len(ids)} rows.", "",
             "| " + " | ".join(c[1] for c in cols) + " |",
             "|" + "---|" * len(cols)]
    bodies = []
    for rid in ids:
        r = val(rb.get(rid, {}))
        props = r.get("properties") or {}
        cells = [prop_text(schema, props, k).replace("|", "/").replace("\n", " ") for k, _ in cols]
        lines.append("| " + " | ".join(cells) + " |")
        rowname = cells[0] if cells else rid
        try:
            sub = chunk(rid)
            sb = dict(sub["recordMap"]["block"])
            note_attachment(sb)
            md = body_md(rid, sb)
        except Exception:
            md = []
        if md:
            bodies += ["", f"### {rowname}", ""] + md
        time.sleep(0.2)
    if bodies:
        lines += ["", "---", "", "## Row notes", ""] + bodies
    open(os.path.join(out, fname), "w").write("\n".join(lines) + "\n")
    manifest.append({"n": n, "title": cname, "kind": "database", "rows": len(ids), "md": fname})
    index.append(f"- [{cname}](<{fname}>) ({len(ids)} rows)")

# --- sub pages ---
subs = [(k, rich((val(v).get("properties") or {}).get("title")))
        for k, v in blocks.items() if val(v).get("type") == "page" and k != pid]
if subs:
    index += ["", "## Sub-pages", ""]
for sid_, sname in subs:
    try:
        sub = chunk(sid_)
        sb = dict(sub["recordMap"]["block"])
        note_attachment(sb)
        md = body_md(sid_, sb)
    except Exception as e:
        md = [f"_could not load: {e}_"]
    n += 1
    fname = f"{n:02d} {safe(sname)}.md"
    open(os.path.join(out, fname), "w").write(
        "\n".join([f"# {sname}", "", f"Source: https://{host}/{sid_.replace('-', '')}", "", "---", ""] + md) + "\n")
    manifest.append({"n": n, "title": sname, "kind": "page", "md": fname})
    index.append(f"- [{sname}](<{fname}>)")

got = fetch_attachments(out)
for f in os.listdir(out):                 # point every attachment: ref at the local copy
    if not f.endswith(".md"):
        continue
    fp = os.path.join(out, f); t = open(fp).read(); o = t
    for u, name in got.items():
        t = t.replace(u, "_attachments/" + urllib.parse.quote(name))
    if t != o:
        open(fp, "w").write(t)
for u, name in got.items():
    index = [l.replace(u, "_attachments/" + urllib.parse.quote(name)) for l in index]
print(f"{len(got)} attachments downloaded")

open(os.path.join(out, "INDEX.md"), "w").write("\n".join(index) + "\n")
json.dump(manifest, open(os.path.join(out, "_manifest.json"), "w"), indent=1, ensure_ascii=False)
print(f"{n} files written ({sum(x.get('rows', 0) for x in manifest)} database rows) -> {out}")
