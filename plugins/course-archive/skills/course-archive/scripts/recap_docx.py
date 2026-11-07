#!/usr/bin/env python3
"""Turn recap markdown into Word documents she can read without a markdown viewer.

Usage:
  recap_docx.py "<course dir>"            every _recaps/*.md and COURSE RECAP.md
  recap_docx.py <file.md> [<file.md> ...]  just these

Writes <same name>.docx beside each .md. The markdown stays as the source copy
(it's what the course recap and search read), the .docx is what she opens and
what the Word index links to.

Handles exactly what the recap template uses: # and ## headings, - bullets,
1. numbered steps, **bold**, [links](...), | tables |, plain paragraphs.
Relative links (../_videos/x.mp4, _recaps/y.md) become Drive links from the
Drive for Desktop xattr. Outside Google Drive they stay relative file links,
which open the saved file as long as the folder stays together. A link to a .md recap points at its .docx twin when
there is one. A file Drive hasn't synced yet keeps its text without a link, so
re-run after the sync.
"""
import os, re, subprocess, sys
from docx import Document
from docx.enum.text import WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches

# <angle-bracket> link targets may hold spaces and parentheses, "(28 Sep 2026).mp4"
INLINE = re.compile(r"\*\*(.+?)\*\*|\[([^\]]+)\]\((?:<([^>]+)>|([^)\s]+))\)")
LINK = re.compile(r"\[([^\]]+)\]\((?:<([^>]+)>|([^)\s]+))\)")
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)


def did(p):
    try:
        r = subprocess.run(["xattr", "-p", "com.google.drivefs.item-id#S", p],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def resolve(url, here):
    """External links as they are, local paths to their Drive copy."""
    if re.match(r"https?://", url):
        return url
    p = os.path.normpath(os.path.join(os.path.dirname(here), url))
    if p.endswith(".md") and os.path.exists(p[:-3] + ".docx"):
        p = p[:-3] + ".docx"
    if not os.path.exists(p):
        return None
    if "/CloudStorage/GoogleDrive-" not in os.path.realpath(p):
        # no Google Drive for Desktop: link the file itself, relative to this document
        from urllib.parse import quote
        return quote(os.path.relpath(p, os.path.dirname(here)))
    i = did(p)
    if not i:
        return None
    kind = "drive/folders" if os.path.isdir(p) else "file/d"
    return f"https://drive.google.com/{kind}/{i}" + ("" if os.path.isdir(p) else "/view")


def hyperlink(par, url, text, bold=False):
    rid = par.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rid)
    r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color"); c.set(qn("w:val"), "1155CC"); rpr.append(c)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
    if bold:
        rpr.append(OxmlElement("w:b"))
    r.append(rpr)
    t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve")
    r.append(t); h.append(r); par._p.append(h)


def inline(par, text, here, missing):
    text = re.sub(r"`([^`]+)`", r"\1", text)   # code ticks around file names read as clutter
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            par.add_run(text[pos:m.start()])
        if m.group(1) is not None:
            inner = m.group(1)
            lm = LINK.fullmatch(inner)
            if lm:
                target = lm.group(2) or lm.group(3)
                u = resolve(target, here)
                if u:
                    hyperlink(par, u, lm.group(1), bold=True)
                else:
                    par.add_run(lm.group(1)).bold = True; missing.append(target)
            else:
                par.add_run(inner).bold = True
        else:
            target = m.group(3) or m.group(4)
            u = resolve(target, here)
            if u:
                hyperlink(par, u, m.group(2))
            else:
                par.add_run(m.group(2)); missing.append(target)
        pos = m.end()
    if pos < len(text):
        par.add_run(text[pos:])


def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), hexcol)
    tcPr.append(s)


def convert(md_path):
    doc = Document()
    sec = doc.sections[0]
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.9))
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(11)
    st.paragraph_format.space_after = Pt(6)
    for name, size in (("Heading 1", 20), ("Heading 2", 14)):
        h = doc.styles[name]
        h.font.name, h.font.size, h.font.color.rgb, h.font.bold = "Arial", Pt(size), ACCENT, True
        rpr = h.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(a), "Arial")
    missing = []
    lines = open(md_path, encoding="utf-8").read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1; continue
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in block
                    if not re.fullmatch(r"\|?[\s:\-|]+\|?", r.strip())]
            if rows:
                tbl = doc.add_table(rows=0, cols=len(rows[0])); tbl.style = "Table Grid"
                for n, r in enumerate(rows):
                    cells = tbl.add_row().cells
                    for k, txt in enumerate(r[:len(cells)]):
                        p = cells[k].paragraphs[0]
                        inline(p, txt, md_path, missing)
                        if n == 0:
                            for run in p.runs:
                                run.bold = True
                            shade(cells[k], "EEF2F7")
                doc.add_paragraph()
            continue
        if line.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                p = doc.add_paragraph(); r = p.add_run(lines[i]); r.font.name = "Courier New"; r.font.size = Pt(9.5)
                i += 1
            i += 1; continue
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            level = min(len(m.group(1)), 2)
            p = doc.add_heading("", level=level)
            inline(p, m.group(2), md_path, missing)
        elif re.match(r"^\s*[-*]\s+", line):
            indent = len(line) - len(line.lstrip())
            p = doc.add_paragraph(style="List Bullet 2" if indent >= 2 else "List Bullet")
            inline(p, re.sub(r"^\s*[-*]\s+", "", line), md_path, missing)
        elif re.match(r"^\s*\d+[.)]\s+", line):
            p = doc.add_paragraph(style="List Number")
            inline(p, re.sub(r"^\s*\d+[.)]\s+", "", line), md_path, missing)
        elif line.strip() == "---":
            pass
        else:
            p = doc.add_paragraph()
            inline(p, line.strip(), md_path, missing)
        i += 1
    out = md_path[:-3] + ".docx"
    doc.save(out)
    return out, missing


def targets(args):
    for a in args:
        if os.path.isdir(a):
            rd = os.path.join(a, "_recaps")
            # recaps mirror the module folders, so walk every level
            for root, dirs, files in os.walk(rd):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith(".md"):
                        yield os.path.join(root, f)
            cr = os.path.join(a, "COURSE RECAP.md")
            if os.path.exists(cr):
                yield cr          # last, so lesson recap .docx files exist to link to
        elif a.endswith(".md"):
            yield a


if __name__ == "__main__":
    total_missing = 0
    for md in targets(sys.argv[1:]):
        out, miss = convert(md)
        total_missing += len(miss)
        print(("ok  " if not miss else f"{len(miss)} unlinked {miss}  ") + out)
    if total_missing:
        print(f"{total_missing} links had no Drive copy yet: re-run once Drive has synced.")
