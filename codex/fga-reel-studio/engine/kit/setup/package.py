#!/usr/bin/env python3
"""Package: the skill as one zip for hosts that install skills by upload (Claude Cowork, claude.ai, ChatGPT).
The zip holds one folder named reel-kit with SKILL.md at its top, and leaves out everything setup.py makes on the
creator's computer (the Python environment, GSAP, models) and everything only the kit's own tests use (dev/).
Run: python3 setup/package.py   -> dist/reel-kit.zip
"""
import os
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".venv", ".models", ".git", "dist", "dev", "__pycache__", "vendor", "snapshots", "node_modules",
             "fonts", "board", "docs"}           # fonts and boards are generated per pack; docs/ is the README's images
SKIP_FILES = {".DS_Store"}


def main():
    out = os.path.join(KIT, "dist", "reel-kit.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(KIT):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                if f in SKIP_FILES or f.endswith(".pyc") or (f == "brand.css" and "packs" in root):
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.join("reel-kit", os.path.relpath(p, KIT)))
                n += 1
    print(f"{out}  {n} files, {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
