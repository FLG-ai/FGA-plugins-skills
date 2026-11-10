#!/usr/bin/env python3
"""Package: the two files creators install from.
- dist/reel-kit.zip: the skill, for hosts that install skills (Codex, ChatGPT Work, claude.ai). One folder named
  reel-kit with SKILL.md at its top.
- dist/reel-kit-plugin.zip: the Claude plugin (Claude Code, Claude Cowork). .claude-plugin/ at the top, so it is
  both a plugin to upload and a local marketplace Claude Code can add from a folder.
- dist/reel-kit-fx-<version>.zip: the kit's effects, for the skill zip only. Skill uploads (claude.ai, the Claude
  app's Skills) take 200 files at most and no zips inside, and the effects alone are about 250, so the skill zip
  carries fx/LIBRARY.md + fx/BUNDLE.json (url + sha256) and setup.py downloads and unpacks the rest. Put it at FX_URL
  before release (justyn-website: dist/reel-kit/kit/). The plugin zip carries the effects itself (no such limit).
Both leave out everything setup.py makes on the creator's computer (the Python environment, GSAP, models) and
everything only the kit's own tests use (dev/).
Run: python3 skills/reel-kit/setup/package.py   -> both zips in dist/ (at the repo root)
"""
import hashlib
import json
import os
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".venv", ".models", ".git", "dist", "dev", "__pycache__", "vendor", "snapshots", "node_modules",
             "fonts", "board", "docs"}           # fonts and boards are generated per pack; docs/ is the README's images
SKIP_FILES = {".DS_Store"}


ROOT = os.path.dirname(os.path.dirname(KIT))
PLUGIN_EXTRAS = [".claude-plugin", "commands", "agents", "LICENSE"]   # what the plugin adds around the skill


def kit_files():
    for root, dirs, files in os.walk(KIT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES or f.endswith(".pyc") or (f == "brand.css" and "packs" in root):
                continue
            yield os.path.join(root, f)


FX = os.path.join(KIT, "fx")
VER = open(os.path.join(KIT, "VERSION")).read().strip()
FX_URL = "https://justyn.ai/reel-kit/kit/fx-{ver}.zip"


def packed(p):
    """an effect file that goes in the effects download instead of the install zips"""
    return p.startswith(FX + os.sep) and p != os.path.join(FX, "LIBRARY.md")


def fx_zip(dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in kit_files():
            if packed(p):
                z.write(p, os.path.relpath(p, KIT))
    sha = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    return json.dumps({"url": FX_URL.format(ver=VER), "sha256": sha}, indent=1) + "\n"


def main():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    fxz = os.path.join(ROOT, "dist", f"reel-kit-fx-{VER}.zip")
    bundle = fx_zip(fxz)
    print(f"{fxz}  {os.path.getsize(fxz) / 1e6:.1f} MB  -> {FX_URL.format(ver=VER)}")
    skill = os.path.join(ROOT, "dist", "reel-kit.zip")
    with zipfile.ZipFile(skill, "w", zipfile.ZIP_DEFLATED) as z:
        n = 0
        for p in kit_files():
            if not packed(p):
                z.write(p, os.path.join("reel-kit", os.path.relpath(p, KIT)))
                n += 1
        z.writestr(os.path.join("reel-kit", "fx", "BUNDLE.json"), bundle)
        n += 1
    print(f"{skill}  {n} files, {os.path.getsize(skill) / 1e6:.1f} MB")

    plugin = os.path.join(ROOT, "dist", "reel-kit-plugin.zip")
    with zipfile.ZipFile(plugin, "w", zipfile.ZIP_DEFLATED) as z:
        n = 0
        for extra in PLUGIN_EXTRAS:
            src = os.path.join(ROOT, extra)
            walk = [(src, [], [""])] if os.path.isfile(src) else os.walk(src)
            for root, dirs, files in walk:
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for f in sorted(files):
                    if f in SKIP_FILES:
                        continue
                    p = os.path.join(root, f) if f else root
                    z.write(p, os.path.relpath(p, ROOT))
                    n += 1
        for p in kit_files():
            z.write(p, os.path.relpath(p, ROOT))
            n += 1
    print(f"{plugin}  {n} files, {os.path.getsize(plugin) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
