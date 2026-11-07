#!/usr/bin/env python3
"""Package any skill that came with a course as an upload-ready .skill file.

Usage:
  pack_skills.py "<course dir>" [--dry-run]

claude.ai, Claude in Chrome and Cowork all take a skill as one zipped folder
with a SKILL.md at its root. A loose folder cannot be uploaded, and neither can
a bare SKILL.md. So anything a course ships as a skill gets packed here, into
`<course dir>/_skills/<name>.skill`, and the original folder is left alone.

What gets packed:
  - any folder inside the course that contains a SKILL.md
  - any .zip whose root holds a SKILL.md, renamed to .skill, contents untouched

What does NOT get packed, on purpose: prompt files, templates and worksheets.
A prompt is not a skill, and wrapping one in a folder with an invented SKILL.md
would put words in the creator's mouth. Those stay in PROMPTS.md and
PROMPTS.html where they are easy to copy.

Prints one line per packet, plus anything that looked close but had no SKILL.md.
"""
import os, re, shutil, sys, zipfile


def skill_name(text, fallback):
    """Prefer the name in the SKILL.md frontmatter, since folders are often just a number."""
    m = re.search(r"^name:\s*['\"]?([A-Za-z0-9][\w .\-]{1,60})", text, re.M)
    n = (m.group(1) if m else "").strip().strip("'\"")
    if not n:
        n = fallback
    n = re.sub(r"^\d{1,3}[ .\-_]*", "", n).strip()
    return re.sub(r"[/\\:]", "-", n) or fallback


d = sys.argv[1]
dry = "--dry-run" in sys.argv
out = os.path.join(d, "_skills")
made, near = [], []

for root, dirs, files in os.walk(d):
    if os.path.basename(root) == "_skills":
        dirs[:] = []
        continue
    if any(f.upper() == "SKILL.MD" for f in files):
        sm = [f for f in files if f.upper() == "SKILL.MD"][0]
        name = skill_name(open(os.path.join(root, sm), errors="ignore").read(2000), os.path.basename(root))
        dest = os.path.join(out, name + ".skill")
        made.append(dest)
        dirs[:] = []
        if dry:
            continue
        os.makedirs(out, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for r2, _, f2 in os.walk(root):
                for f in f2:
                    p = os.path.join(r2, f)
                    z.write(p, os.path.join(name, os.path.relpath(p, root)))
        continue
    for f in files:
        if f.lower().endswith(".skill"):
            # already a packet, usually filed under _attachments with a number prefix
            clean = re.sub(r"^\d{1,3}[ .\-_]+", "", f).strip()
            if clean in (".skill", "skill", ""):
                try:
                    with zipfile.ZipFile(os.path.join(root, f)) as z:
                        inner = [n for n in z.namelist() if n.upper().endswith("SKILL.MD")]
                        body = z.read(inner[0]).decode("utf-8", "ignore") if inner else ""
                    clean = skill_name(body, os.path.splitext(f)[0] or "skill") + ".skill"
                except Exception:
                    clean = (os.path.splitext(f)[0] or "skill") + ".skill"
            dest = os.path.join(out, clean)
            if os.path.abspath(os.path.join(root, f)) == os.path.abspath(dest):
                continue
            made.append(dest)
            if not dry:
                os.makedirs(out, exist_ok=True)
                shutil.copy2(os.path.join(root, f), dest)
            continue
        if f.lower().endswith(".zip"):
            p = os.path.join(root, f)
            try:
                with zipfile.ZipFile(p) as z:
                    names = z.namelist()
            except Exception:
                continue
            if any(n.upper().endswith("SKILL.MD") and n.count("/") <= 1 for n in names):
                dest = os.path.join(out, os.path.splitext(f)[0] + ".skill")
                made.append(dest)
                if not dry:
                    os.makedirs(out, exist_ok=True)
                    shutil.copy2(p, dest)
            else:
                near.append(p)

for m in sorted(set(made)):
    print(("would pack " if dry else "packed ") + os.path.relpath(m, d))
for n in near:
    print("zip with no SKILL.md at its root, left alone: " + os.path.relpath(n, d))
print(f"{len(set(made))} skill packets in {os.path.relpath(out, d)}" if made else "no skills found in this course")
