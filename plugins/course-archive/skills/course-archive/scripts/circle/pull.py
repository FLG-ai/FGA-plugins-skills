#!/usr/bin/env python3
"""Archive one or more Circle.so spaces (course or post spaces) to markdown.

Usage: pull.py [--no-media] <community host> <cookies.txt> <output dir> <space> [<space> ...]
  space = slug or id, optionally slug::regex to keep only matching post/lesson titles.
  space = slug or id. Course spaces come first in the order given, numbering
  runs on across spaces so everything shares one folder.

Writes NN Title.md per lesson/post, _attachments/, INDEX.md, and
_manifest.json (every item's video ids, files and md name) which
videos.sh and the Google Doc step read.
cookies.txt is a Netscape cookie file from your logged-in Chrome (scripts/cookies.py).
Undripped or locked lessons are listed as skipped, never forced.
"""
import http.cookiejar, json, os, re, sys, time, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skool"))
from build import block, safe  # same TipTap flavour as Skool

args = sys.argv[1:]
SKIP_AV = "--no-media" in args
args = [a for a in args if a != "--no-media"]
AV = {".mov", ".mp4", ".m4v", ".webm", ".avi", ".mkv", ".mp3", ".m4a", ".wav"}
host, cookies, out, *wanted = args
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
jar = http.cookiejar.MozillaCookieJar(cookies)
jar.load(ignore_discard=True, ignore_expires=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path, raw=False):
    url = path if path.startswith("http") else f"https://{host}/internal_api/{path}"
    r = op.open(urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA}), timeout=120)
    body = r.read()
    return body if raw else json.loads(body)


VID = r"(?:wistia\.(?:com|net)/(?:medias|embed/iframe)/([a-z0-9]{10}))|(?:(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]{11}))|(?:loom\.com/(?:share|embed)/([0-9a-f]{32}))|(?:vimeo\.com/(?:video/)?(\d+))"


def video_links(text):
    seen, outl = set(), []
    for m in re.finditer(VID, text or ""):
        w, y, l, v = m.groups()
        url = (f"https://fast.wistia.net/embed/iframe/{w}" if w else f"https://www.youtube.com/watch?v={y}" if y
               else f"https://www.loom.com/share/{l}" if l else f"https://vimeo.com/{v}")
        if url not in seen:
            seen.add(url); outl.append(url)
    return outl


def secs(v):
    """Circle gives duration as seconds (attachments) or "MM:SS" / "H:MM:SS" (featured_media)."""
    if isinstance(v, (int, float)):
        return round(v)
    if isinstance(v, str) and ":" in v:
        n = 0
        for part in v.split(":"):
            n = n * 60 + int(part or 0)
        return n
    return 0


def render(rb):
    """TipTap body -> markdown, resolving embed nodes through sgids_to_object_map."""
    smap = rb.get("sgids_to_object_map") or {}
    nodes = []
    for x in (rb.get("body") or {}).get("content") or []:
        if x.get("type") == "file":
            continue
        if x.get("type") == "embed":
            sg = (x.get("attrs") or {}).get("sgid") or ""
            obj = next((v for k, v in smap.items() if k.startswith(sg) or sg.startswith(k)), {})
            u = obj.get("url") or (x.get("attrs") or {}).get("url")
            if u:
                v = video_links(u + (obj.get("html") or ""))
                u = v[0] if v else u
                nodes.append({"type": "paragraph", "content": [{"type": "text", "text": "Embedded: " + u,
                              "marks": [{"type": "link", "attrs": {"href": u}}]}]})
            continue
        nodes.append(x)
    return re.sub(r"\n{3,}", "\n\n", block(nodes)).strip()


spaces = get("spaces?per_page=200")["records"]
os.makedirs(out, exist_ok=True)
att_dir = os.path.join(out, "_attachments")
index = ["# " + os.path.basename(out.rstrip("/")), "", f"Source: https://{host}", "",
         f"Pulled {time.strftime('%Y-%m-%d')}.", ""]
manifest, skipped, n = [], [], 0


def write_item(title, section, src, rb, featured=None, created=None, native=None):
    global n
    n += 1
    fname = f"{n:02d} {safe(title, 80, strip_emoji=True)}.md"
    fm = featured or {}
    vids = video_links((fm.get("content") or "") + (fm.get("html") or ""))
    body_vids = video_links(json.dumps(rb.get("sgids_to_object_map") or {}))
    vids += [v for v in body_vids if v not in vids]
    lines = [f"# {title}", "", f"Section: {section}  ", f"Source: {src}  "]
    if created:
        lines.append(f"Posted: {created[:10]}  ")
    lines.append("")
    for i, v in enumerate(vids):
        lines.append(f"**Video{'' if len(vids) == 1 else f' {i+1}'}:** {v}  ")
    if vids:
        lines.append("")
    files = {a["signed_id"]: a for a in (rb.get("inline_attachments") or []) + (rb.get("attachments") or []) if a.get("url")}
    saved, media = [], []
    if native and native.get("url"):          # Circle's own lesson/post video (featured_media)
        media.append({"name": native.get("filename") or "video", "url": native["url"],
                      "vtt": native.get("webvtt_file_url"),
                      "hls": (native.get("video_variants") or {}).get("hls") or native.get("playback_url"),
                      "seconds": secs(native.get("duration"))})
        vids.append(native["url"])
    for a in files.values():
        name = a.get("filename") or "file"
        if os.path.splitext(name)[1].lower() in AV and SKIP_AV:
            media.append({"name": name, "url": a["url"], "vtt": a.get("webvtt_file_url"),
                          "hls": (a.get("video_variants") or {}).get("hls"),
                          "seconds": secs((a.get("metadata") or {}).get("duration"))})
            vids.append(a["url"]); continue
        os.makedirs(att_dir, exist_ok=True)
        fn = f"{n:02d} {safe(name, 90)}"
        p = os.path.join(att_dir, fn)
        if not os.path.exists(p):
            open(p, "wb").write(get(a["url"], raw=True))
        saved.append(fn)
    if saved:
        lines += ["**Downloads:**", ""] + [f"- [{f[3:]}](<_attachments/{f}>)" for f in saved] + [""]
    if media:
        lines += ["**Uploaded media (not downloaded):**", ""] + [
            f"- [{x['name']}](<{x['url']}>)" + (f" ({x['seconds']//60} min)" if x['seconds'] else "") for x in media] + [""]
    body = render(rb)
    lines += ["---", "", body or "_No text, video only._", ""]
    open(os.path.join(out, fname), "w").write("\n".join(lines))
    manifest.append({"n": n, "title": title, "section": section, "md": fname, "videos": vids,
                     "files": saved, "media": media, "src": src, "date": (created or "")[:10]})
    index.append(f"- [{title}](<{fname}>)" + (f" ({len(vids)} video)" if vids else "") + (f" ({len(saved)} download)" if saved else ""))
    time.sleep(0.25)


for want in wanted:
    want, _, only = want.partition("::")          # slug::regex pulls just the matching posts
    keep = re.compile(only, re.I).search if only else (lambda t: True)
    sp = next(s for s in spaces if str(s["id"]) == want or s["slug"] == want)
    base = f"https://{host}/c/{sp['slug']}"
    if sp.get("post_type") == "course":
        last = None
        for sec in get(f"courses/{sp['id']}/sections")["records"]:
            for les in [l for l in (sec.get("lessons") or []) if keep(l.get("name") or "")]:
                try:
                    d = get(f"courses/{sp['id']}/sections/{sec['id']}/lessons/{les['id']}")
                except Exception as e:
                    skipped.append(f"{les['name']} ({e})"); continue
                if d.get("is_dripped") is False:
                    skipped.append(f"{les['name']} (not dripped yet)"); continue
                if sec["name"] != last:
                    index += ["", f"## {sp['name']}: {sec['name']}", ""]; last = sec["name"]
                write_item(d["name"].strip(), f"{sp['name']}: {sec['name']}", f"{base}/sections/{sec['id']}/lessons/{les['id']}",
                           d.get("rich_text_body") or {}, d.get("featured_media_embed"),
                           native=d.get("featured_media"))
    else:
        posts, page = [], 1
        while True:
            r = get(f"spaces/{sp['id']}/posts?per_page=50&page={page}&sort=oldest")
            posts += r["records"]
            if not r.get("has_next_page"):
                break
            page += 1
        posts = [p for p in posts if keep((p.get("name") or "").strip())]
        index += ["", f"## {sp['name']}", ""]
        for p in sorted(posts, key=lambda p: p.get("created_at") or ""):
            write_item((p.get("name") or "Untitled").strip(), sp["name"], f"{base}/{p['slug']}",
                       p.get("tiptap_body") or {}, None, p.get("created_at"),
                       native=p.get("featured_media"))

if skipped:
    index += ["", "## Skipped", ""] + [f"- {s}" for s in skipped]
open(os.path.join(out, "INDEX.md"), "w").write("\n".join(index) + "\n")
json.dump(manifest, open(os.path.join(out, "_manifest.json"), "w"), indent=1, ensure_ascii=False)
print(f"{len(manifest)} items written, {len(skipped)} skipped -> {out}")
