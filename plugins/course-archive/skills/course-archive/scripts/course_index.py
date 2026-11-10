#!/usr/bin/env python3
"""Build the course index tables for any archived course folder.

Usage:
  course_index.py "<course dir>" <out.json> [--title "Course name"] [--md] [--docx]
                  [--newest-first]

Order: lesson 1 first, then 2, 3 and on, within every section .Pass --newest-first only for a live feed (community posts, a
challenge still dripping) where the latest item matters most.

--docx writes `<course dir>/<Course>, course index.docx`, the one sheet she
opens. One table per section, one row per lesson, every cell a hyperlink:

  | # | Lesson | Video | Transcript | Notes | Bonuses |

  Video       the saved copy in your Drive (public YouTube or Loom as-is)
  Transcript  the transcript markdown and/or PDF
  Notes       the lesson notes from the module page, its Notion-style PDF,
              class-notes attachments
  Bonuses     everything else: skills, workbooks, slides, prompt packs,
              downloads. Course-wide extras (_skills/*.skill, PROMPTS) get
              their own row at the end.

"no video" / "none" fill an empty cell, "pending sync" means the file is on
disk but Drive has not given it an ID yet, so run it again after the sync.

--md writes `COURSE INDEX.md` (the older three-column Lesson | Watch |
Materials layout) as the offline copy.

Links point at the Drive copy, never the platform, except YouTube and Loom.
Drive IDs come from the Drive for Desktop xattr, so no API call is needed once
a file has synced. A `.gdoc` or `.gsheet` pointer file is read for its doc id.

Works with or without `_manifest.json`. With one, it uses the recorded section,
video and file lists. Without one, it walks the folder: top-level subfolders are
sections, every markdown file that is not an index or a Notes sidecar is a
lesson, and files are matched to a lesson by name prefix or stem.

Writes {"title", "groups": [{"heading", "markdown"}], "pending": [...],
"counts": {...}} for the Google Doc step, and with --md also writes
`<course dir>/COURSE INDEX.md` as the local copy.
"""
import json, os, re, subprocess, sys

SKIP_DIRS = {"_recaps", "_skills", "_attachments", "_videos", "_transcripts", "_superseded", "_assets", "_images", "_files"}
SKIP_MD = re.compile(r"^(index|course index|course recap|readme|prompts)\.md$", re.I)
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
DOC_EXT = {".gdoc", ".gsheet", ".gslides"}


def did(p):
    """Drive file id from the Drive for Desktop xattr, or None."""
    try:
        r = subprocess.run(["xattr", "-p", "com.google.drivefs.item-id#S", p],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def gdoc_url(p):
    """A .gdoc/.gsheet pointer file carries its own url."""
    try:
        j = json.load(open(p))
        return j.get("url") or j.get("doc_id") and f"https://docs.google.com/open?id={j['doc_id']}"
    except Exception:
        return None


COURSE_DIR = None   # set in main, for relative links outside Google Drive


def in_drive(p):
    """Under a Google Drive for Desktop folder, where files get a Drive id."""
    return "/CloudStorage/GoogleDrive-" in os.path.realpath(p)


def local_link(path, label):
    """Not on Drive (someone without Drive for Desktop): link the file itself,
    relative to the course folder, which is where the index .docx sits."""
    from urllib.parse import quote
    rel = os.path.relpath(path, COURSE_DIR or os.path.dirname(path))
    return f"[{label}]({quote(rel)})"


def link(path, label):
    if not path or not os.path.exists(path):
        return None
    if not in_drive(path):
        return local_link(path, label)
    if os.path.splitext(path)[1].lower() in DOC_EXT:
        u = gdoc_url(path)
        return f"[{label}]({u})" if u else None
    i = did(path)
    return f"[{label}](https://drive.google.com/file/d/{i}/view)" if i else None


def pretty(name):
    """File name to a readable label: drop the number prefix and the extension."""
    stem, ext = os.path.splitext(os.path.basename(name))
    stem = re.sub(r"^\d{1,3}[ .\-_]+", "", stem)
    stem = stem.replace(" — ", ", ").replace("—", ",").strip()
    return f"{stem[:70]} ({ext.lstrip('.').upper()})" if ext else stem[:70]


def kind_of(path, lesson_md=None):
    """Which column a lesson file belongs in: transcript, notes or bonus."""
    name = os.path.basename(path).lower()
    if "_transcripts" in path or "transcript" in name:
        return "transcript"
    if lesson_md and os.path.splitext(os.path.basename(path))[0] == os.path.splitext(os.path.basename(lesson_md))[0]:
        return "notes"            # the notes markdown or its Notion-style PDF twin
    if re.search(r"notes?\b", name) and name.endswith((".md", ".pdf")):
        return "notes"
    return "bonus"


def M(kind, md):
    return {"kind": kind, "md": md}


def is_public(u):
    return any(h in u for h in ("youtube.com", "youtu.be", "loom.com", "vimeo.com"))


def local_video(d, stem):
    """The saved copy of a lesson's video, whatever the naming, or None."""
    for base in (os.path.join(d, "_videos", stem), os.path.join(d, stem)):
        for suffix in ("", " - video", " - VIDEO"):
            for ext in VIDEO_EXT:
                got = link(base + suffix + ext, "Watch")
                if got:
                    return got
    vd = os.path.join(d, "_videos")
    if stem and os.path.isdir(vd):
        for v in sorted(os.listdir(vd)):
            if v.startswith(stem) and os.path.splitext(v)[1].lower() in VIDEO_EXT:
                return link(os.path.join(vd, v), "Watch")
    return None


def from_manifest(d, m):
    """Manifests differ by adapter, so read the keys loosely."""
    rows = []
    for x in m:
        stem = os.path.splitext(x.get("md") or "")[0] or x.get("stem") or ""
        lesson = x.get("title") or stem
        vids = x.get("videos") or ([x["video"]] if x.get("video") else [])
        files = x.get("files") or x.get("attachments") or []
        watch = []
        for v in vids:
            if is_public(v):
                watch.append(f"[Watch]({v})")
            else:
                watch.append(local_video(d, stem) or "pending sync")
        if not watch:
            # the manifest can be silent about video even when the file was saved
            got = local_video(d, stem)
            if got:
                watch.append(got)
        mats = []
        md = x.get("md") or (stem + ".md" if stem else "")
        if md and os.path.exists(os.path.join(d, md)):
            mats.append(M("notes", link(os.path.join(d, md), "Notes") or "pending sync (Notes)"))
        for f in files:
            p = os.path.join(d, f) if os.sep in f else os.path.join(d, "_attachments", f)
            if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                continue          # a video uploaded as an attachment is the Watch link, not a bonus
            mats.append(M(kind_of(p, md), link(p, pretty(f)) or f"pending sync ({pretty(f)})"))
        for key, label, kind in (("transcript", "Transcript", "transcript"), ("pdf", "PDF", "notes"),
                                 ("notes_pdf", "PDF", "notes")):
            v = x.get(key)
            if v and os.path.exists(os.path.join(d, v)):
                mats.append(M(kind, link(os.path.join(d, v), label) or f"pending sync ({label})"))
        # a Notion-style PDF or transcript saved beside the notes, not named in the manifest
        for extra, label, kind in ((stem + ".pdf", "PDF", "notes"),
                                   (os.path.join("_transcripts", stem + ".md"), "Transcript", "transcript")):
            p = os.path.join(d, extra)
            if stem and os.path.exists(p) and not any(label in m2["md"] for m2 in mats):
                mats.append(M(kind, link(p, label) or f"pending sync ({label})"))
        rows.append({"section": x.get("section") or "Lessons", "lesson": lesson,
                     "stem": stem or "%02d" % x.get("n", 0) if x.get("n") else stem,
                     "watch": watch, "materials": mats})
    return rows


PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{1,3})(?=[ .\-_])")
BONUS_DIRS = []      # (parent dir, lesson stem or None, folder path), filled by walk_folder


def has_skill(p):
    for _, _, fs in os.walk(p):
        if "SKILL.md" in fs:
            return True
    return False


def folder_link(p, label):
    if not in_drive(p):
        return local_link(p, label)
    i = did(p)
    return f"[{label}](https://drive.google.com/drive/folders/{i})" if i else None


def from_map(d, mp):
    """_course_map.json: the hand-written map for a course the folder walk can't
    read, such as two editions side by side, or videos split into chapters.

    {"lessons": [{"section": "...", "n": 1, "lesson": "...",
                  "video": [...], "transcript": [...], "notes": [...],
                  "bonus": [...], "recap": "_recaps/01 x - Recap.md"}]}

    Paths are relative to the course folder, folders are fine (linked as a
    folder), and http links pass through as they are. Labels come from
    {"path": ..., "label": ...} entries or the file name."""
    def one(x, default):
        if isinstance(x, dict):
            path, label = x["path"], x.get("label")
        else:
            path, label = x, None
        if re.match(r"https?://", path):
            return f"[{label or default}]({path})"
        full = os.path.join(d, path)
        label = label or (os.path.basename(path.rstrip("/")) + " (folder)" if os.path.isdir(full) else
                          pretty(path) if default == "file" else default)
        got = folder_link(full, label) if os.path.isdir(full) else link(full, label)
        return got or f"pending sync ({label})"

    rows = []
    for x in mp["lessons"]:
        mats = []
        for key, kind, default in (("transcript", "transcript", "file"), ("notes", "notes", "file"),
                                   ("bonus", "bonus", "file")):
            for item in x.get(key, []):
                mats.append(M(kind, one(item, default)))
        rows.append({"section": x.get("section") or "Lessons", "lesson": x["lesson"],
                     "stem": "%02d %s" % (x["n"], x["lesson"]) if "n" in x else x["lesson"],
                     "watch": [one(v, "Watch") for v in x.get("video", [])], "materials": mats,
                     "recap_fixed": os.path.join(d, x["recap"]) if x.get("recap") else None})
    return rows


def walk_folder(d):
    """No manifest: read the folder itself."""
    rows = []
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        # a folder that belongs to one lesson (same date or number prefix), or any
        # folder of skills, is that lesson's bonus pack, never a section of lessons
        stems = [os.path.splitext(f)[0] for f in files if f.lower().endswith(".md")]
        keep = []
        for x in dirs:
            m = PREFIX.match(x)
            owner = next((s for s in stems if m and s.startswith(m.group(1))), None)
            if owner or (root != d and has_skill(os.path.join(root, x))) or \
                    (has_skill(os.path.join(root, x)) and not any(f.endswith(".md") for f in os.listdir(os.path.join(root, x)) if PREFIX.match(f))):
                BONUS_DIRS.append((root, owner, os.path.join(root, x)))
            else:
                keep.append(x)
        dirs[:] = keep
        rel = os.path.relpath(root, d)
        section = "Lessons" if rel == "." else rel.replace(os.sep, " / ")
        mds = sorted(f for f in files if f.lower().endswith(".md")
                     and not SKIP_MD.match(f) and not f.endswith(" - Notes.md"))
        # a course can ship video plus transcript and no markdown at all
        vids = sorted(f for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXT)
        keys = [os.path.splitext(f)[0] for f in mds]
        for v in vids:
            k = re.sub(r"\s*-\s*VIDEO$", "", os.path.splitext(v)[0], flags=re.I)
            if k not in keys and not any(k.startswith(x) or x.startswith(k) for x in keys):
                keys.append(k)
                mds.append(None)
        for idx, stem in enumerate(keys):
            f = mds[idx] if idx < len(mds) and mds[idx] else None
            watch, mats = [], []
            # video: _videos at the course root, then beside the notes, then the "- VIDEO" naming
            cands = [os.path.join(d, "_videos", stem), os.path.join(root, stem),
                     os.path.join(root, stem + " - VIDEO")]
            for cand in cands:
                for ext in VIDEO_EXT:
                    got = link(cand + ext, "Watch")
                    if got:
                        watch.append(got)
                        break
                if watch:
                    break
            for vd in dict.fromkeys([os.path.join(d, "_videos"), os.path.join(root, "_videos")]):
                if watch or not os.path.isdir(vd):
                    continue
                # "00 Kick-off Call (28 Sep 2026).mp4" still belongs to "00 Kick-off Call"
                for v in sorted(os.listdir(vd)):
                    if v.startswith(stem) and os.path.splitext(v)[1].lower() in VIDEO_EXT:
                        got = link(os.path.join(vd, v), "Watch")
                        if got:
                            watch.append(got); break
            if not watch and f:
                body = open(os.path.join(root, f), errors="ignore").read(6000)
                pub = re.findall(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|loom\.com|vimeo\.com)/\S+", body)
                if pub:
                    watch.append(f"[Watch]({pub[0].rstrip(').,')})")
            if f:
                mats.append(M("notes", link(os.path.join(root, f), "Notes") or "pending sync (Notes)"))
            # siblings that belong to this lesson: same stem, or the numbered prefix
            num = re.match(r"^(\d{1,3})", stem)
            for sib in sorted(files):
                if sib == f or sib.lower().endswith(".md") and sib != stem + " - Notes.md":
                    continue
                sibstem = os.path.splitext(sib)[0]
                same = sibstem.startswith(stem) or (num and sib.startswith(num.group(1) + " "))
                if same and os.path.splitext(sib)[1].lower() not in VIDEO_EXT:
                    sp = os.path.join(root, sib)
                    mats.append(M(kind_of(sp, f), link(sp, pretty(sib)) or f"pending sync ({pretty(sib)})"))
            for sub in ("_attachments", "_transcripts"):
                for base in {root, d}:
                    p = os.path.join(base, sub)
                    if os.path.isdir(p):
                        for a in sorted(os.listdir(p)):
                            # a number prefix only counts beside the notes, never across sections
                            if a.startswith(stem) or (base == root and num and a.startswith(num.group(1) + " ")):
                                ap = os.path.join(p, a)
                                mats.append(M(kind_of(ap, f), link(ap, pretty(a)) or f"pending sync ({pretty(a)})"))
            rows.append({"section": section, "lesson": re.sub(r"^\d{1,3}[ .\-_]+", "", stem),
                         "stem": stem, "watch": watch, "materials": mats, "root": root})
    for parent, owner, p in BONUS_DIRS:
        label = os.path.basename(p) + " (folder)"
        entry = M("bonus", folder_link(p, label) or f"pending sync ({label})")
        target = next((r for r in rows if owner and r["stem"] == owner and r.get("root") == parent), None)
        if target:
            target["materials"].append(entry)
        else:
            EXTRA_BONUS.append(entry)
    return rows


def recap_path(d, r):
    """_recaps/<module folder>/<lesson stem> - Recap.md, mirroring the course
    folders so two modules' "01 Intro" never collide. A course with a
    manifest and one flat folder keeps them all at _recaps/."""
    sub = os.path.relpath(r["root"], d) if r.get("root") else "."
    base = r.get("stem") or re.sub(r"[^\w .,&()'-]+", "", r["lesson"])[:80]
    std = os.path.normpath(os.path.join(d, "_recaps", sub, f"{base} - Recap.md"))
    if not os.path.exists(std):
        # courses kept inside a holding folder keep their own _recaps beside them:
        # <holder>/_recaps/<module>/<stem> - Recap.md
        parts = sub.split(os.sep)
        if len(parts) > 1:
            alt = os.path.normpath(os.path.join(d, parts[0], "_recaps", *parts[1:], f"{base} - Recap.md"))
            if os.path.exists(alt):
                return alt
    return std


def lesson_no(r):
    m = re.match(r"^(\d{1,4})", r.get("stem") or "")
    return int(m.group(1)) if m else None


def put_in_order(rows, newest_first=False):
    """Lesson 1 first within each section, sections in the order they first appear.
    Rows with no number keep their place after the numbered ones."""
    secs = []
    for r in rows:
        if r["section"] not in secs:
            secs.append(r["section"])
    out = []
    for s in secs:
        mine = [r for r in rows if r["section"] == s]
        numbered = sorted([r for r in mine if lesson_no(r) is not None], key=lesson_no)
        rest = [r for r in mine if lesson_no(r) is None]
        part = numbered + rest
        out += list(reversed(part)) if newest_first else part
    return out


EXTRA_BONUS = []


def extras_row(d):
    """Course-wide bonuses that belong to no single lesson."""
    mats = list(EXTRA_BONUS)
    sk = os.path.join(d, "_skills")
    if os.path.isdir(sk):
        for f in sorted(os.listdir(sk)):
            if f.endswith(".skill"):
                mats.append(M("bonus", link(os.path.join(sk, f), f) or f"pending sync ({f})"))
    for f, label in (("PROMPTS.html", "All prompts, copy buttons (HTML)"), ("PROMPTS.md", "All prompts (MD)")):
        if os.path.exists(os.path.join(d, f)):
            mats.append(M("bonus", link(os.path.join(d, f), label) or f"pending sync ({label})"))
    return {"section": "Course extras", "lesson": "Skills and prompts for the whole course", "stem": "",
            "watch": [], "materials": mats} if mats else None


MDLINK = re.compile(r"\[([^\]]+)\]\((\S+?)\)")


def write_docx(rows, title, path, intro, course_recap=None):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.shared import Pt, RGBColor, Inches

    doc = Document()
    sec = doc.sections[0]          # portrait, US Letter
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.6))
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(9.5)
    for name, size in (("Heading 1", 20), ("Heading 2", 14)):
        h = doc.styles[name]
        h.font.name, h.font.size, h.font.bold = "Arial", Pt(size), True
        h.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        rpr = h.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(a), "Arial")

    def shade(cell, hexcol):
        tcPr = cell._tc.get_or_add_tcPr()
        s = OxmlElement("w:shd")
        s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), hexcol)
        tcPr.append(s)

    def hyperlink(par, url, text):
        rid = par.part.relate_to(url, RT.HYPERLINK, is_external=True)
        h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rid)
        r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
        c = OxmlElement("w:color"); c.set(qn("w:val"), "1155CC"); rpr.append(c)
        u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
        r.append(rpr); tx = OxmlElement("w:t"); tx.text = text
        tx.set(qn("xml:space"), "preserve"); r.append(tx); h.append(r)
        par._p.append(h)

    def fill(cell, items, empty):
        par = cell.paragraphs[0]
        items = [x for x in items if x]
        if not items:
            run = par.add_run(empty); run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            return
        for i, s in enumerate(items):
            if i:
                par = cell.add_paragraph()
            m = MDLINK.search(s)
            if m:
                hyperlink(par, m.group(2), m.group(1))
            else:
                run = par.add_run(s); run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    def relabel(items, word):
        # "Notes"/"PDF"/"x (MD)" read better as the column word plus the format
        out = []
        for s in items:
            m = MDLINK.search(s)
            if not m:
                out.append(s); continue
            lab, url = m.groups()
            if lab not in ("Notes", "Transcript", "PDF", "Recap"):
                out.append(s); continue      # a real file name says more than a generic label
            fmt = "PDF" if lab == "PDF" else None
            out.append(f"[{word}{' (' + fmt + ')' if fmt else ''}]({url})" if fmt else s)
        return out

    doc.add_heading(f"{title}, course index", level=1)
    doc.add_paragraph(intro)
    if course_recap:
        par = doc.add_paragraph(); par.add_run("Start here: ").bold = True
        m = MDLINK.search(course_recap)
        if m:
            hyperlink(par, m.group(2), "Course recap, the whole course on one page")
        else:
            par.add_run(course_recap)
    heads = ["#", "Lesson", "Recap", "Video", "Transcript", "Notes", "Bonuses"]
    widths = [0.3, 1.75, 0.6, 0.8, 0.95, 1.15, 1.75]   # 7.3in, the portrait page inside its margins
    secs = []
    for r in rows:
        if r["section"] not in secs:
            secs.append(r["section"])
    n = 0
    for s in secs:
        if len(secs) > 1 or s != "Lessons":
            doc.add_heading(s, level=2)
        tbl = doc.add_table(rows=1, cols=len(heads))
        tbl.style = "Table Grid"; tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        for i, h in enumerate(heads):
            c = tbl.rows[0].cells[i]; c.text = ""
            run = c.paragraphs[0].add_run(h); run.bold = True
            shade(c, "F2F2F2")
        for r in [x for x in rows if x["section"] == s]:
            cells = tbl.add_row().cells
            if r["section"] != "Course extras":
                n += 1
                cells[0].text = str(lesson_no(r) if lesson_no(r) is not None else n)
            cells[1].text = re.sub(r"^\d{1,3}[.)]?\s+", "", r["lesson"])
            by = lambda k: [m["md"] for m in r["materials"] if m["kind"] == k]
            extra = r["section"] == "Course extras"
            fill(cells[2], relabel(by("recap"), "Recap"), "" if extra else "not written yet")
            fill(cells[3], r["watch"], "" if extra else "no video")
            fill(cells[4], relabel(by("transcript"), "Transcript"), "" if extra else "none")
            fill(cells[5], relabel(by("notes"), "Notes"), "" if extra else "none")
            fill(cells[6], by("bonus"), "none")
        for i, w in enumerate(widths):
            tbl.columns[i].width = Inches(w)
        for row in tbl.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
        doc.add_paragraph()
    doc.save(path)


def main():
    global COURSE_DIR
    d, out = sys.argv[1], sys.argv[2]
    COURSE_DIR = d
    title = None
    if "--title" in sys.argv:
        title = sys.argv[sys.argv.index("--title") + 1]
    title = title or os.path.basename(os.path.normpath(d))
    mpath = os.path.join(d, "_manifest.json")
    cmap = os.path.join(d, "_course_map.json")
    if os.path.exists(cmap):
        rows = from_map(d, json.load(open(cmap)))
    elif os.path.exists(mpath):
        try:
            rows = from_manifest(d, json.load(open(mpath)))
        except Exception:
            rows = walk_folder(d)
    else:
        rows = walk_folder(d)
    if not rows:
        rows = walk_folder(d)
    rows = put_in_order(rows, "--newest-first" in sys.argv)
    # the plain-English recap for each lesson, written in Step 6 to _recaps/<stem> - Recap.md
    rd = os.path.join(d, "_recaps")
    # Notion choice: _recaps/notion.json maps each recap .md path (relative to
    # _recaps) and "COURSE RECAP" to a Notion page url, and those links win
    notion = {}
    if os.path.exists(os.path.join(rd, "notion.json")):
        notion = json.load(open(os.path.join(rd, "notion.json")))
    for r in rows:
        r["recap_md"] = r.get("recap_fixed") or recap_path(d, r)
        rel = os.path.relpath(r["recap_md"], rd)
        if rel in notion:
            r["materials"].insert(0, M("recap", f"[Recap]({notion[rel]})"))
            continue
        for p in (r["recap_md"][:-3] + ".docx", r["recap_md"]):
            if os.path.exists(p):
                r["materials"].insert(0, M("recap", link(p, "Recap") or "pending sync (Recap)"))
                break
    no_recap = [r["lesson"] for r in rows if r["section"] != "Course extras" and not any(m["kind"] == "recap" for m in r["materials"])]
    ex = extras_row(d)
    if ex:
        rows.append(ex)

    groups, pending = [], []
    seen = []
    for r in rows:
        if r["section"] not in seen:
            seen.append(r["section"])
    # a column nobody can fill is noise: drop Watch when the course has no video at all
    any_video = any(r["watch"] for r in rows)
    any_mats = any(r["materials"] for r in rows)
    head = ["Lesson"] + (["Watch"] if any_video else []) + (["Materials"] if any_mats else [])
    for sec in seen:
        lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * len(head)) + " |"]
        for r in [x for x in rows if x["section"] == sec]:
            cells = [r["lesson"]]
            if any_video:
                cells.append(" ".join(r["watch"]) if r["watch"] else "no video")
            if any_mats:
                cells.append(", ".join(m["md"] for m in r["materials"]) or "none")
            if any("pending sync" in c for c in cells):
                pending.append(r["lesson"])
            lines.append("| " + " | ".join(cells) + " |")
        groups.append({"heading": sec, "markdown": "\n".join(lines)})

    res = {"title": title, "groups": groups, "pending": sorted(set(pending)),
           "no_recap": no_recap,
           "lessons": [{"section": r["section"], "lesson": r["lesson"], "stem": r.get("stem"),
                        "folder": r.get("root") or d, "recap_md": r.get("recap_md"),
                        "has_recap": any(m["kind"] == "recap" for m in r["materials"])}
                       for r in rows if r["section"] != "Course extras"],
           "counts": {"lessons": sum(1 for r in rows if r["section"] != "Course extras"), "missing_recaps": len(no_recap), "sections": len(groups),
                      "with_video": sum(1 for r in rows if r["watch"]),
                      "pending": len(set(pending))}}
    json.dump(res, open(out, "w"), indent=1)

    if "--md" in sys.argv:
        n, sec = res["counts"]["lessons"], res["counts"]["sections"]
        bits = [f"{n} lessons" + (f" across {sec} sections" if sec > 1 else "")]
        if res["counts"]["with_video"]:
            bits.append("Watch links go to the saved copy in Drive, or to YouTube or Loom where the video is public")
        md = [f"# {title}, course index", "", ". ".join(bits) + ".", ""]
        for g in groups:
            md += [f"## {g['heading']}", "", g["markdown"], ""]
        open(os.path.join(d, "COURSE INDEX.md"), "w").write("\n".join(md))
    if "--docx" in sys.argv:
        n = res["counts"]["lessons"]
        intro = (f"{n} lessons in course order. Every link opens the copy saved in your Drive "
                 "(YouTube and Loom stay as their own links). \"pending sync\" means Drive hadn't "
                 "finished uploading that file yet, so run the index again later. The links click through in Word, "
                 "Pages or Google Drive, not in a quick file preview.") if in_drive(d) else (
                 f"{n} lessons in course order. Every link opens the saved file in this folder, so keep "
                 "this document inside the course folder (YouTube and Loom stay as their own links). The links "
                 "click through in Word or Pages, not in a quick file preview.")
        dp = os.path.join(d, f"{title}, course index.docx")
        cr = os.path.join(d, "COURSE RECAP.docx")
        if not os.path.exists(cr):
            cr = os.path.join(d, "COURSE RECAP.md")
        nj = os.path.join(d, "_recaps", "notion.json")
        nurl = json.load(open(nj)).get("COURSE RECAP") if os.path.exists(nj) else None
        write_docx(rows, title, dp, intro,
                   f"[Course recap]({nurl})" if nurl else
                   (link(cr, "Course recap") or "Course recap: pending sync") if os.path.exists(cr) else None)
        print("docx ->", dp)
    print(json.dumps(res["counts"]), "->", out)


if __name__ == "__main__":
    main()
