#!/usr/bin/env python3
"""Pull every prompt out of an archived course and make it copyable.

Usage:
  prompts_export.py "<course dir>" [--check-pdfs]

Why this exists: a prompt is the part of a class people actually reuse, and it is
the part most likely to get clipped. TUB's own PDF export cuts long prompts, and
a prompt pasted out of a PDF arrives with broken line breaks.

What it writes, at the course root:

  PROMPTS.md    every prompt as a fenced block, grouped by lesson, full text,
                nothing truncated. Plain markdown, so it pastes into anything.
  PROMPTS.html  the same prompts, each in its own card with a Copy button, and
                the whole page pastes into Google Docs or Notion as rich text
                with the monospace blocks intact.

A prompt is any fenced code block, any block quote longer than 200 characters,
and any run of indented lines that follows a line naming a prompt (a heading or
a bolded line containing "prompt", "template", "script" or "framework").

--check-pdfs also compares each lesson's PDF text layer against its markdown and
reports any prompt that appears cut short in the PDF, so a clipped render gets
caught instead of being filed.
"""
import html, json, os, re, sys

SKIP_DIRS = {"_videos", "_superseded", "_assets", "_images"}
PROMPT_CUE = re.compile(r"(prompt|template|script|framework|instructions)", re.I)


def lessons(d):
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        for f in sorted(files):
            if f.lower().endswith(".md") and f.upper() not in ("INDEX.MD", "PROMPTS.MD", "COURSE INDEX.MD"):
                yield os.path.join(root, f)


def extract(text):
    """Return [(label, prompt_text)] for one markdown file."""
    out, lines, i = [], text.split("\n"), 0
    heading = ""
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            heading = ln.lstrip("# ").strip()
        m = re.match(r"^\s*```", ln)
        if m:
            j = i + 1
            buf = []
            while j < len(lines) and not re.match(r"^\s*```", lines[j]):
                buf.append(lines[j]); j += 1
            body = "\n".join(buf).strip()
            if body:
                out.append((heading or "Prompt", body))
            i = j + 1
            continue
        if ln.startswith(">"):
            j, buf = i, []
            while j < len(lines) and lines[j].startswith(">"):
                buf.append(lines[j].lstrip("> ").rstrip()); j += 1
            body = "\n".join(buf).strip()
            if len(body) > 200:
                out.append((heading or "Prompt", body))
            i = j
            continue
        if PROMPT_CUE.search(ln) and (ln.startswith("**") or ln.startswith("#")):
            j, buf = i + 1, []
            while j < len(lines) and (lines[j].startswith("    ") or lines[j].startswith("\t")):
                buf.append(lines[j].strip()); j += 1
            body = "\n".join(buf).strip()
            if len(body) > 120:
                out.append((re.sub(r"[*#]", "", ln).strip() or heading, body))
            i = j if j > i + 1 else i + 1
            continue
        i += 1
    return out


def check_pdfs(d, found):
    """Flag prompts that look cut short in the rendered PDF."""
    try:
        import fitz
    except ImportError:
        return ["pymupdf not installed, PDF check skipped (pip3 install --user pymupdf)"]
    bad = []
    for path, items in found.items():
        pdf = os.path.splitext(path)[0] + ".pdf"
        pdf = pdf.replace(" - Notes.pdf", ".pdf")
        if not os.path.exists(pdf):
            continue
        text = " ".join(p.get_text() for p in fitz.open(pdf))
        flat = re.sub(r"\s+", " ", text)
        for label, body in items:
            head = re.sub(r"\s+", " ", body)[:60]
            tail = re.sub(r"\s+", " ", body)[-60:]
            if head and head in flat and tail and tail not in flat:
                bad.append(f"{os.path.basename(pdf)}: prompt '{label[:40]}' is in the PDF but its ending is missing")
    return bad


CSS = """body{font:15px/1.6 -apple-system,Segoe UI,sans-serif;max-width:900px;margin:0 auto;padding:28px 18px 70px;color:#17181a;background:#fbfaf8}
h1{font-size:30px;margin:0 0 6px}h2{font-size:17px;margin:30px 0 8px;border-bottom:1px solid #e3ded6;padding-bottom:5px}
.card{border:1px solid #e3ded6;border-radius:9px;background:#fff;margin:0 0 12px;overflow:hidden}
.top{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;background:#f4f1ec;font-size:13px;font-weight:600}
button{font:500 12.5px inherit;border:1px solid #cfc7bb;background:#fff;border-radius:6px;padding:4px 10px;cursor:pointer}
button:hover{background:#f0ece5}
pre{margin:0;padding:12px 14px;white-space:pre-wrap;word-break:break-word;font:13px/1.55 ui-monospace,Menlo,monospace}
.lead{color:#6b655c;margin:0 0 22px}
@media(prefers-color-scheme:dark){body{background:#14140f;color:#eceae4}.card{background:#1c1b17;border-color:#302d27}.top{background:#242219}button{background:#242219;color:#eceae4;border-color:#3a362e}h2{border-color:#302d27}.lead{color:#a29c90}}"""


def main():
    d = sys.argv[1]
    title = os.path.basename(os.path.normpath(d))
    found, total = {}, 0
    for path in lessons(d):
        items = extract(open(path, errors="ignore").read())
        if items:
            found[path] = items
            total += len(items)

    md = [f"# {title}, every prompt", "",
          f"{total} prompts from {len(found)} lessons, copied out in full. "
          f"Nothing here is truncated, and the fenced blocks paste straight into Claude or ChatGPT.", ""]
    hp = [f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)} prompts</title><style>{CSS}</style>",
          f"<h1>{html.escape(title)}</h1>",
          f"<p class='lead'>{total} prompts from {len(found)} lessons, in full. Each block has a copy button, "
          f"and the whole page pastes into Docs or Notion as rich text.</p>"]
    for path, items in found.items():
        lesson = re.sub(r"^\d{1,3}[ .\-_]+", "", os.path.splitext(os.path.basename(path))[0])
        md += [f"## {lesson}", ""]
        hp.append(f"<h2>{html.escape(lesson)}</h2>")
        for n, (label, body) in enumerate(items, 1):
            md += [f"**{label}**", "", "```", body, "```", ""]
            hp.append(
                f"<div class='card'><div class='top'><span>{html.escape(label[:90])}</span>"
                f"<button onclick=\"navigator.clipboard.writeText(this.closest('.card').querySelector('pre').innerText)"
                f".then(()=>{{this.textContent='Copied';setTimeout(()=>this.textContent='Copy',1200)}})\">Copy</button></div>"
                f"<pre>{html.escape(body)}</pre></div>")

    open(os.path.join(d, "PROMPTS.md"), "w").write("\n".join(md))
    open(os.path.join(d, "PROMPTS.html"), "w").write("\n".join(hp))
    print(f"{total} prompts from {len(found)} lessons -> PROMPTS.md and PROMPTS.html")

    if "--check-pdfs" in sys.argv:
        for line in check_pdfs(d, found) or ["PDF check: no clipped prompts found"]:
            print(line)


if __name__ == "__main__":
    main()
