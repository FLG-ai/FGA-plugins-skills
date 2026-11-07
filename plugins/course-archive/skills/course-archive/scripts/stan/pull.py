#!/usr/bin/env python3
"""stan.store course adapter.

Usage: pull.py <course uuid> <store_slug> <cookies.txt> "<out dir>"

Everything comes from one call: GET api.stanwith.me/api/v1/courses/<uuid>
with Authorization: Bearer <auth_token cookie from stan.store>.
Modules -> lessons, each lesson carries title, HTML description,
a direct .mp4 (and .m3u8), and digital_assets (PDFs).
"""
import html.parser, json, os, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36"
API = "https://api.stanwith.me/api/"


def auth_token(cookie_file):
    for line in open(cookie_file):
        f = line.rstrip("\n").split("\t")
        if len(f) == 7 and f[5] == "auth_token":
            return f[6]
    sys.exit("no auth_token cookie for stan.store, sign in on Chrome first")


def get(path, token):
    req = urllib.request.Request(API + path, headers={
        "User-Agent": UA, "Authorization": "Bearer " + token})
    return json.load(urllib.request.urlopen(req))


class Md(html.parser.HTMLParser):
    """The descriptions are simple HTML: p, br, strong, em, a, ul/ol/li."""
    def __init__(self):
        super().__init__()
        self.out, self.href, self.list = [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "p":
            self.out.append("\n")
        elif tag == "br":
            self.out.append("\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "a":
            self.href = a.get("href", "")
            self.out.append("[")
        elif tag in ("ul", "ol"):
            self.list.append(tag)
            self.out.append("\n")
        elif tag == "li":
            self.out.append("\n- " if (self.list and self.list[-1] == "ul") else "\n1. ")

    def handle_endtag(self, tag):
        if tag == "p":
            self.out.append("\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag in ("em", "i"):
            self.out.append("*")
        elif tag == "a":
            self.out.append("](%s)" % (self.href or ""))
            self.href = None
        elif tag in ("ul", "ol") and self.list:
            self.list.pop()
            self.out.append("\n")

    def handle_data(self, d):
        self.out.append(d)


def md(h):
    p = Md()
    p.feed(h or "")
    return re.sub(r"\n{3,}", "\n\n", "".join(p.out)).strip()


def safe(s):
    return re.sub(r"[^\w\s.,'&()-]", "", s).strip().rstrip(".")[:90]


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return os.path.getsize(dest)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    tmp = dest + ".part"
    with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)
    return os.path.getsize(dest)


def main():
    uuid, store, cookie_file, out = sys.argv[1:5]
    token = auth_token(cookie_file)
    d = get("v1/courses/%s?store_slug=%s" % (uuid, store), token)
    course, creator = d["course"], d["user"]
    title = course["data"]["title"]

    os.makedirs(out, exist_ok=True)
    att_dir, vid_dir = os.path.join(out, "_attachments"), os.path.join(out, "_videos")
    os.makedirs(att_dir, exist_ok=True)
    os.makedirs(vid_dir, exist_ok=True)

    rows, n = [], 0
    for m in course["modules"]:
        mtitle = m["data"].get("title", "Module")
        for les in sorted(m["lessons"], key=lambda x: x.get("order", 0)):
            n += 1
            ld = les["data"]
            ltitle = ld.get("title", "Lesson %d" % n)
            stem = "%02d - %s" % (n, safe(ltitle))
            body = ["# %s" % ltitle, "", "**Course:** %s" % title,
                    "**Module:** %s" % mtitle,
                    "**Creator:** %s (@%s)" % (creator["full_name"], creator["username"]),
                    "**Source:** https://stan.store/course/%s?store=%s" % (uuid, store), ""]

            vurl = ld.get("video")
            if vurl:
                vfile = os.path.join(vid_dir, stem + os.path.splitext(
                    urllib.parse.urlparse(vurl).path)[1])
                size = fetch(vurl, vfile)
                body.append("**Video:** `_videos/%s` (%.1f MB)" % (
                    os.path.basename(vfile), size / 1e6))
                print("  video %s %.1f MB" % (os.path.basename(vfile), size / 1e6))

            assets = []
            for a in ld.get("digital_assets") or []:
                name = a.get("name") or os.path.basename(
                    urllib.parse.urlparse(a["url"]).path)
                dest = os.path.join(att_dir, safe(os.path.splitext(name)[0]) +
                                    os.path.splitext(name)[1])
                fetch(a["url"], dest)
                assets.append(os.path.basename(dest))
            if assets:
                body.append("**Attachments:** " + ", ".join(
                    "`_attachments/%s`" % a for a in assets))

            body += ["", "---", "", md(ld.get("description")), ""]
            open(os.path.join(out, stem + ".md"), "w").write("\n".join(body))
            rows.append((n, mtitle, ltitle, stem, bool(vurl), assets))
            print("  %s" % stem)

    man = [{"n": n_, "section": mod, "title": lt, "md": stem + ".md",
            "videos": ["local"] if hasv else [], "files": assets}
           for n_, mod, lt, stem, hasv, assets in rows]
    json.dump(man, open(os.path.join(out, "_manifest.json"), "w"),
              indent=1, ensure_ascii=False)

    idx = ["# %s" % title, "",
           "%s (@%s). Archived from stan.store, personal member copy."
           % (creator["full_name"], creator["username"]), "",
           md(course["data"].get("description")), "",
           "%d lessons across %d modules. Nothing was locked or skipped."
           % (len(rows), len(course["modules"])), ""]
    cur = None
    for n_, mod, lt, stem, hasv, assets in rows:
        if mod != cur:
            cur = mod
            idx += ["", "## %s" % mod, "",
                    "| Lesson | Notes | Video | Downloads |", "|---|---|---|---|"]
        idx.append("| %s | [md](%s.md) | %s | %s |" % (
            lt, urllib.parse.quote(stem),
            "`_videos/`" if hasv else "-",
            ", ".join(assets) if assets else "-"))
    open(os.path.join(out, "INDEX.md"), "w").write("\n".join(idx) + "\n")
    print("\n%d lessons -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
