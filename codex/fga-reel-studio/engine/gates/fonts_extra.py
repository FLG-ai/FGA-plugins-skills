#!/usr/bin/env python3
"""Extra Google fonts for one reel-kit project, for looks that need more than the pack's four font roles: downloads
TTFs into <project>/style/fonts/ and appends @font-face rules to <project>/style/brand.css. A system font (for
example Helvetica Neue on a Mac) is used by name for local renders.
Run: "$PY" fonts_extra.py <project>
"""
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kit")), "pipeline"))   # the kit that sits beside the gates
import style as ST  # noqa: E402

EXTRA = {
    "Calistoga": {(0, 400)},                                   # the series header
    "Montserrat": {(0, 700), (0, 800), (0, 900), (1, 700), (1, 800), (1, 900)},   # Italic Punch captions
    "Anton": {(0, 400)},                                       # outlined job-card numbers
    "Archivo Black": {(0, 400)},
    "Instrument Serif": {(0, 400), (1, 400)},
    "Gloock": {(0, 400)},
    "Inter Tight": {(0, 400), (0, 500), (0, 600), (0, 700), (0, 800), (0, 900), (1, 800), (1, 900)},
    "JetBrains Mono": {(0, 500), (0, 700)},
}


def main():
    project = os.path.abspath(os.path.expanduser(sys.argv[1]))
    sty = os.path.join(project, "style")
    fonts = os.path.join(sty, "fonts")
    os.makedirs(fonts, exist_ok=True)
    rules = []
    for family, pairs in EXTRA.items():
        css = ST._fetch_css(family, pairs) or "".join(ST._fetch_css(family, {p}) or "" for p in sorted(pairs))
        for block in re.findall(r"@font-face\s*{[^}]*}", css or ""):
            style = re.search(r"font-style:\s*(\w+)", block).group(1)
            weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
            src = re.search(r"url\((https://[^)]+\.ttf)\)", block)
            if not src:
                continue
            name = f"{family.replace(' ', '')}-{style}-{weight}.ttf"
            path = os.path.join(fonts, name)
            if not os.path.exists(path):
                urllib.request.urlretrieve(src.group(1), path)
            rules.append(f"@font-face {{ font-family:'{family}'; src:url('fonts/{name}') format('truetype'); "
                         f"font-style:{style}; font-weight:{weight}; font-display:block; }}")
    brand = os.path.join(sty, "brand.css")
    text = open(brand).read() if os.path.exists(brand) else ""
    text = text.split("/* extra fonts */")[0]
    with open(brand, "w") as fh:
        fh.write(text.rstrip() + "\n/* extra fonts */\n" + "\n".join(sorted(set(rules))) + "\n")
    print(f"{len(set(rules))} extra faces -> {brand}")


if __name__ == "__main__":
    main()
