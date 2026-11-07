#!/usr/bin/env python3
"""Turn a skool-<group>.json export from harvest.js.txt into a markdown archive.

Usage: build.py <export.json> <output dir>
"""
import json, os, re, sys


def esc(t):
    return t.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")


def ms(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    s = v // 1000
    return f"{s//3600:d}:{(s%3600)//60:02d}:{s%60:02d}" if s >= 3600 else f"{s//60:d}:{s%60:02d}"


def inline(nodes):
    out = []
    for n in nodes or []:
        t = n.get("type")
        if t == "hardBreak":
            out.append("  \n")
            continue
        if t == "image":
            a = n.get("attrs") or {}
            out.append(f"![{a.get('alt') or ''}]({a.get('src') or a.get('originalSrc') or ''})")
            continue
        if t != "text":
            out.append(block([n]).strip())
            continue
        s = esc(n.get("text") or "")
        href = None
        for m in n.get("marks") or []:
            mt = m.get("type")
            at = m.get("attrs") or {}
            if mt == "bold":
                s = f"**{s}**"
            elif mt == "italic":
                s = f"*{s}*"
            elif mt == "code":
                s = f"`{n.get('text')}`"
            elif mt == "videoTimestamp":
                s = f"`{n.get('text')}`"
            elif mt == "link":
                href = at.get("href")
        if href:
            s = f"[{s}]({href})"
        out.append(s)
    return "".join(out)


def block(nodes, depth=0):
    lines = []
    for n in nodes or []:
        t = n.get("type")
        c = n.get("content") or []
        a = n.get("attrs") or {}
        if t == "paragraph":
            lines += [inline(c), ""]
        elif t == "heading":
            lines += ["#" * min(int(a.get("level") or 2), 6) + " " + inline(c), ""]
        elif t in ("bulletList", "unorderedList", "orderedList"):
            start = int(a.get("start") or 1)
            for i, li in enumerate(c):
                mark = f"{start+i}." if t == "orderedList" else "-"
                body = block(li.get("content") or [], depth + 1).rstrip()
                if not body:
                    continue
                bl = body.split("\n")
                lines.append("  " * depth + f"{mark} {bl[0]}")
                for x in bl[1:]:
                    lines.append("  " * depth + ("  " + x if x.strip() else ""))
            lines.append("")
        elif t == "listItem":
            lines.append(block(c, depth).rstrip())
        elif t == "blockquote":
            for x in block(c, depth).rstrip().split("\n"):
                lines.append("> " + x if x.strip() else ">")
            lines.append("")
        elif t == "horizontalRule":
            lines += ["---", ""]
        elif t == "codeBlock":
            lines += ["```" + (a.get("language") or ""),
                      "".join(x.get("text") or "" for x in c), "```", ""]
        elif t == "image":
            lines += [f"![{a.get('alt') or ''}]({a.get('src') or a.get('originalSrc') or ''})", ""]
        elif t == "text":
            lines += [inline([n]), ""]
        elif c:
            lines += [block(c, depth).rstrip(), ""]
    return "\n".join(lines)


def to_md(desc):
    """Skool bodies are TipTap JSON behind a [v2] prefix."""
    if not desc:
        return ""
    if desc.startswith("[v2]"):
        desc = desc[4:]
    try:
        doc = json.loads(desc)
    except Exception:
        return desc
    if isinstance(doc, dict):
        doc = doc.get("content") or [doc]
    return re.sub(r"\n{3,}", "\n\n", block(doc)).strip()


def safe(s, n=70, strip_emoji=False):
    s = s or "untitled"
    if strip_emoji:  # keeps folder paths typeable in a shell
        s = re.sub(r"[^\w\s\-&,.()+']", "", s, flags=re.UNICODE)
    s = re.sub(r"[\\/:*?\"<>|]", "-", s)
    s = re.sub(r"\s+", " ", s).strip().strip(".")
    return s[:n] or "untitled"


def main(src, out):
    data = json.load(open(src))
    group = data.get("group", "skool")
    index = [f"# {group} — classroom archive", "",
             f"Pulled {data.get('pulledAt','')[:10]} from skool.com/{group}/classroom.", ""]
    if data.get("skipped"):
        index += ["Locked on this account at pull time, not included:", ""]
        index += [f"- {t}" for t in data["skipped"]] + [""]

    counts = {}
    for c in data["courses"]:
        folder = f"{c['order']:02d} {safe(c['title'], 50, strip_emoji=True)}"
        d = os.path.join(out, folder)
        os.makedirs(d, exist_ok=True)
        index += [f"## {c['title']}", ""]
        written, section = 0, None
        for i, it in enumerate(c["items"], 1):
            title = it.get("title") or "untitled"
            if it.get("error"):  # section header, no payload of its own
                section = title
                index += [f"**{title}** (section)", ""]
                continue
            fn = f"{i:02d} {safe(title)}.md"
            body = [f"# {title}", ""]
            if section:
                body.append(f"- Section: {section}")
            if it.get("video"):
                dur = ms(it.get("videoMs"))
                body.append(f"- Video: {it['video']}" + (f"  ({dur})" if dur else ""))
            body += [f"- Source: https://www.skool.com/{group}/classroom/{c['slug']}?md={it['id']}", ""]
            res = it.get("resources")
            if isinstance(res, str):
                try:
                    res = json.loads(res)
                except Exception:
                    res = None
            if res:
                body += ["## Resources", ""]
                body += [f"- [{r.get('title') or r.get('link')}]({r.get('link')})" for r in res]
                body.append("")
            md = to_md(it.get("desc"))
            if md:
                body += ["## Notes", "", md, ""]
            open(os.path.join(d, fn), "w").write("\n".join(body).rstrip() + "\n")
            written += 1
            tags = (" · video" if it.get("video") else "") + (f" · {len(res)} resource(s)" if res else "")
            index.append(f"- [{title}]({folder}/{fn}){tags}")
        index.append("")
        counts[c["title"]] = written

    open(os.path.join(out, "INDEX.md"), "w").write("\n".join(index).rstrip() + "\n")
    print(json.dumps(counts, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
