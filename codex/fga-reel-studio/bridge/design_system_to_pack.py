#!/usr/bin/env python3
"""The other direction: a Quick-lane design-system.json (built from someone's inspo reels) becomes a reel-kit style pack,
so the same person gets the same look in the Showcase / Hi-fi / Lo-fi lane.

Run:  python3 design_system_to_pack.py <design-system.json> --out <new pack folder> [--force]

Writes <out>/style.json, <out>/STYLE.md and <out>/quick-overrides.json (the picks a pack cannot hold). It never overwrites an existing pack unless you pass --force.
Then fetch the fonts and build brand.css with the kit:   "$PY" "$KIT/pipeline/style.py" <out>/style.json
"""
import json
import os
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(STUDIO, "engine", "kit", "pipeline"))
import style as ST  # noqa: E402

SINGLE_WEIGHT = {"Gloock", "Calistoga", "Anton", "Instrument Serif", "Bebas Neue", "DM Serif Display", "Playfair Display"}
LOOK_NOTES = {
    "italic_punch": "Heavy italic caps with an outline and a hard shadow, key words in the key color.",
    "serif_mix": "Bold sans words, key words switch to a big serif italic in the key color.",
    "yellow_key": "Heavy sans one word at a time, key words change to the key color.",
    "small_top": "Small clean captions above the head, key words in a light serif italic.",
}


def arg(flag, default=None):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def font(name, role_bold=800):
    return {"family": name, "italic": False, "weight": 400 if name in SINGLE_WEIGHT else role_bold}


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--") or not arg("--out"):
        sys.exit(__doc__)
    ds = json.load(open(os.path.expanduser(sys.argv[1])))
    out = os.path.abspath(os.path.expanduser(arg("--out")))
    if os.path.exists(os.path.join(out, "style.json")) and "--force" not in sys.argv:
        sys.exit(f"{out}/style.json already exists. Pass --force to replace it.")
    os.makedirs(out, exist_ok=True)
    f, c, cap = ds.get("fonts", {}), ds.get("colors", {}), ds.get("captions", {})
    style = cap.get("style", "italic_punch")
    key = c.get("key", "#ffe94d")
    pack = {
        "creator": {"name": ds.get("name", ""), "handle": "", "site": ""},
        "fonts": {"display": font(f.get("titles", "Inter Tight")), "text": font(f.get("captions", "Inter Tight"), 700),
                  "mono": {"family": "JetBrains Mono", "italic": False, "weight": 500}, "caption": font(f.get("captions", "Inter Tight"))},
        "colors": {"accent": key, "caption_ink": c.get("text", "#FFFFFF"), "ink": c.get("outline", "#14080f"), "dark": c.get("outline", "#14080f"),
                   "series": [x for x in (key, c.get("accent"), c.get("accent2")) if x]},
        "grounds": {"grid": False, "radius": 34},
        "captions": {"hifi": {"box": False, "uppercase": style == "italic_punch", "size": 64, "y": 1300},
                     "lofi": {"box": False, "uppercase": style == "italic_punch", "size": 92, "y": min(cap.get("y", 1318), 1318)}},
        "motion": "punchy" if style in ("italic_punch", "yellow_key") else "normal",
        "sound": {"sfx": "normal", "music": "none"},
        "modes": {
            "hifi": {"hook": "two-line", "captions": "words", "bw": False, "j_lead": 0.2},
            "lofi": {"captions": "single", "max_words": 1, "max_chars": 14, "text_boxes": True, "bw": False, "j_lead": 0.2},
            "showcase": {"density": "high", "j_lead": 0.2,
                         "motif": (ds.get("series_title", {}).get("text", "").replace("|", " / ") or "")},
        },
    }
    pack = ST.merge(ST.DEFAULT, pack)
    json.dump(pack, open(os.path.join(out, "style.json"), "w"), indent=2, ensure_ascii=False)
    lines = [f"# {ds.get('name', 'Reel look')}: reel style", "",
             "Built from the Quick lane design system by bridge/design_system_to_pack.py. Edit this file and style.json as the look settles.", "",
             "## Type", f"- Captions: {f.get('captions', '')}", f"- Titles: {f.get('titles', '')}", f"- Numbers: {f.get('numbers', '')}",
             f"- Accents: {f.get('accents', '')}", "", "## Colour", f"- Key: {key}"]
    for k in ("text", "outline", "accent", "accent2"):
        if c.get(k):
            lines.append(f"- {k}: {c[k]}")
    lines += ["", "## Captions", f"- {LOOK_NOTES.get(style, style)} {cap.get('notes', '')}".strip(), "- Every spoken word is captioned.", ""]
    for sec in ("hook", "number_pop", "list_cards", "word_pops", "series_title"):
        if ds.get(sec):
            lines += [f"## {sec.replace('_', ' ').title()}", "- " + json.dumps(ds[sec], ensure_ascii=False), ""]
    lines += ["## Rules"] + [f"- {r}" for r in ds.get("rules", [])] + ["", "## Hi-fi", "Two-line hook, captions one word at a time.", "",
              "## Lo-fi", "One word at a time, white text boxes for the hook and the call to action.", "",
              "## Showcase", "A different technique on each beat. The series title is the recurring motif.", "",
              "## Safe zone", "Nothing above y 250 or below y 1480. Nothing within 60 px of the sides. Nothing past x 940 below y 1050.", ""]
    open(os.path.join(out, "STYLE.md"), "w").write("\n".join(lines))
    # everything a pack cannot hold goes into quick-overrides.json, so design-system.json can be rebuilt from the pack
    # later without losing a pick (pack_to_design_system.py reads this file)
    base = {k: ds[k] for k in ("name", "hook", "number_pop", "list_cards", "word_pops", "series_title", "sounds",
                               "safe_zone", "rules", "references", "grade", "extras", "windows") if k in ds}
    base["fonts"] = {k: f[k] for k in ("titles", "numbers", "accents") if k in f}
    base["colors"] = {k: c[k] for k in ("text", "outline", "accent", "accent2") if k in c}
    overrides = {"_about": "Values the style pack cannot hold, for the Quick lane. Written by bridge/design_system_to_pack.py, read by "
                           "bridge/pack_to_design_system.py. Edit freely, then rebuild design-system.json.",
                 "default_look": "My look",
                 "base": base,
                 "looks": {"My look": {"fidelity": "exact", "captions": cap, "colors": {"key": key}}}}
    json.dump(overrides, open(os.path.join(out, "quick-overrides.json"), "w"), indent=2, ensure_ascii=False)
    print(f"wrote {out}/style.json, {out}/STYLE.md and {out}/quick-overrides.json")
    print('next: "$PY" "$KIT/pipeline/style.py" "%s/style.json"   (downloads the fonts, writes brand.css)' % out)


if __name__ == "__main__":
    main()
