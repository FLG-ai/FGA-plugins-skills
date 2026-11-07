#!/usr/bin/env python3
"""Build the UCL-style Google Doc tables for an archived course folder.

Usage: doc_tables.py "<course dir>" <out.json>
Reads _manifest.json, looks up each local file's Drive ID from the Drive for
Desktop xattr (no API call needed once a file has synced), and writes
{"groups": [{"heading", "markdown"}], "pending": [...]} for the Composio step.
Watch/Notes/Downloads all point at the Drive copies, never the platform, except
YouTube or Loom links which are used as-is.
"""
import json, os, re, subprocess, sys

d, out = sys.argv[1:3]
m = json.load(open(os.path.join(d, "_manifest.json")))


def did(p):
    r = subprocess.run(["xattr", "-p", "com.google.drivefs.item-id#S", p], capture_output=True, text=True)
    return r.stdout.strip() or None


def link(p, label):
    i = did(p) if os.path.exists(p) else None
    return f"[{label}](https://drive.google.com/file/d/{i}/view)" if i else None


MERGE = {"Filming Tutorial": "Tutorials", "Editing Tutorial": "Tutorials",
         "Caleb Ralston - Guest Speaker Round 2": "Bonus replays", "Launch Debrief Bonus Call": "Bonus replays"}


def group_of(sec):
    if re.match(r"(?:Lesson|Day|Module)\s*\d+\b", sec):   # drip challenge: one space per lesson
        return "Lessons"
    s = sec.split(": ", 1)[-1]
    if s in ("Daily Drop + Dare",):
        return s
    if "Foundation" in s or s == "Bonus":
        return "The Foundation"
    top = sec.split(": ", 1)[0]
    return MERGE.get(top, top)


groups, pending = {}, []
for x in m:
    g = group_of(x["section"])
    watch = []
    for i, v in enumerate(x["videos"]):
        if "youtube" in v or "loom" in v:
            watch.append(f"[Watch]({v})"); continue
        l = link(os.path.join(d, "_videos", x["md"][:-3] + ".mp4"), "Watch")
        if l:
            watch.append(l)
        elif x.get("src"):
            watch.append(f"[Watch]({x['src']})")   # video left on the platform on purpose
        else:
            watch.append("pending"); pending.append(x["n"])
    notes = link(os.path.join(d, x["md"]), "Notes") or "pending"
    dl = [link(os.path.join(d, "_attachments", f),
               f[3:].rsplit(".", 1)[0].replace(" — ", ", ").replace("—", ",")[:60]
               + f" ({f.rsplit('.', 1)[-1].upper()})") or "pending" for f in x["files"]]
    tr = ""
    if x.get("transcript"):
        tr = link(os.path.join(d, "_transcripts", x["transcript"]), "Transcript") or "pending"
    title = x["title"].replace("|", "/").strip()
    groups.setdefault(g, []).append(f"| {title} | {' '.join(watch) or 'text only'} | {tr} | {notes} | {'<br>'.join(dl) or ''} |")

res = {"groups": [], "pending": pending}
for g, rows in groups.items():
    md = f"## {g}\n\n| Lesson | Watch | Transcript | Notes | Downloads |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    res["groups"].append({"heading": g, "markdown": md})
json.dump(res, open(out, "w"), indent=1, ensure_ascii=False)
print([(g["heading"], g["markdown"].count("\n") - 4) for g in res["groups"]], "pending:", pending)
