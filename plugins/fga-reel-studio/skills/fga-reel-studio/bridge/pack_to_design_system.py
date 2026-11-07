#!/usr/bin/env python3
"""One style pack, both lanes.

The Showcase / Hi-fi / Lo-fi lane reads a reel-kit style pack (style.json + STYLE.md + fonts).
The Quick lane reads design-system.json. This builds the second from the first, so nothing is typed twice and the two
lanes can never drift apart.

Run:  python3 pack_to_design_system.py <pack folder or style.json> [--look NAME] [--overrides FILE] [--out FILE]

  --look       a Quick caption style (italic_punch, serif_mix, yellow_key, small_top), or the name of a look defined in the
               pack's quick-overrides.json. A person who wants a different caption look per video picks one per video.
  --overrides  values a pack cannot hold (series title text, list-card fonts, named looks, extra rules). Default:
               quick-overrides.json inside the pack folder, if there is one. Format: templates/quick-overrides.example.json
  --out        where to write design-system.json. Default: inside the pack folder.

It prints how close the Quick lane's caption style is to the named look ("exact" or "nearest"), because the Quick lane
has four caption styles and the Showcase / Lo-fi lane can draw anything.
"""
import copy
import json
import os
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(STUDIO, "engine", "kit", "pipeline"))
import style as ST  # noqa: E402  (the kit's own loader: fills every missing pack field from its DEFAULT)

QUICK_CAPTIONS = {"italic_punch", "serif_mix", "yellow_key", "small_top"}
QUICK_HOOKS = {"bubbly", "editorial", "soft_serif", "poster", "grotesk"}
REQUIRED_RULES = ["Caption every spoken word."]
SAFE = {"top": 250, "bottom": 1480, "side": 60, "buttons_x": 940, "buttons_y": 1050}
SOUNDS = os.path.join(STUDIO, "engine", "quick", "reel-design-system", "assets", "sounds")


def merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def arg(flag, default=None):
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def find_style_json(p):
    p = os.path.abspath(os.path.expanduser(p))
    j = p if p.endswith(".json") else os.path.join(p, "style.json")
    if not os.path.exists(j):
        sys.exit(f"no style.json at {j}")
    return j


def find_overrides(pack_dir):
    given = arg("--overrides")
    if given:
        return os.path.abspath(os.path.expanduser(given))
    here = os.path.join(pack_dir, "quick-overrides.json")
    return here if os.path.exists(here) else None


def build(pack, ov, look):
    f, c = pack["fonts"], pack["colors"]
    ds = {
        "name": pack.get("creator", {}).get("name") or "My reel look",
        "fonts": {"captions": f["caption"]["family"], "titles": f["display"]["family"],
                  "numbers": f["display"]["family"], "accents": f["display"]["family"]},
        "colors": {"text": "#ffffff", "key": c["accent"], "outline": c["dark"], "accent": c["series"][0], "accent2": c["series"][-1]},
        "captions": {"style": "italic_punch", "px": 150, "y": 1360, "outline": 8,
                     "under_windows": {"px": 80, "y": 1400}, "notes": "One word at a time, key words in the key color"},
        "hook": {"style": "bubbly", "clears_on": "first spoken number", "notes": "Stacked lines pop in from the first frame"},
        "sounds": {"typing": "click1", "pop": "pop", "reveal": "sparkle", "transition": "swish", "volume_db": -14},
        "safe_zone": dict(SAFE),
        "rules": list(REQUIRED_RULES),
    }
    ds = merge(ds, ov.get("base", {}))
    fidelity = "pack defaults"
    looks = ov.get("looks", {})
    if look in looks:
        spec = looks[look]
        fidelity = spec.get("fidelity", "nearest")
        ds = merge(ds, {k: v for k, v in spec.items() if k != "fidelity"})
    elif look in QUICK_CAPTIONS:
        dl = looks.get(ov.get("default_look"), {})                                  # keep the tuned size, place and outline of the default look
        ds = merge(ds, {k: v for k, v in dl.items() if k != "fidelity"})
        ds["captions"]["style"] = look
        fidelity = "exact"
    elif look:
        sys.exit(f"unknown look '{look}'. Named looks: {', '.join(looks) or 'none'}. Quick styles: {', '.join(sorted(QUICK_CAPTIONS))}")
    rules = list(REQUIRED_RULES)
    for r in ov.get("base", {}).get("rules", []):
        if r not in rules:
            rules.append(r)
    ds["rules"] = rules
    return ds, fidelity


def check(ds):
    bad = []
    if ds["captions"].get("style") not in QUICK_CAPTIONS:
        bad.append(f"captions.style '{ds['captions'].get('style')}' is not one of {sorted(QUICK_CAPTIONS)}")
    if ds["hook"].get("style") not in QUICK_HOOKS:
        bad.append(f"hook.style '{ds['hook'].get('style')}' is not one of {sorted(QUICK_HOOKS)}")
    npc = ds.get("number_pop", {}).get("color")
    if npc and not (str(npc).startswith("#") or npc in ds["colors"]):
        bad.append(f"number_pop.color '{npc}' is neither a hex nor a key of colors")
    for k, v in ds["sounds"].items():
        if k != "volume_db" and not os.path.exists(os.path.join(SOUNDS, f"{v}.m4a")):
            bad.append(f"sounds.{k} = '{v}' has no file in reel-design-system/assets/sounds")
    for r in REQUIRED_RULES:
        if r not in ds["rules"]:
            bad.append("a required rule is missing: " + r)
    for k in ("top", "bottom", "side", "buttons_x", "buttons_y"):
        if k not in ds["safe_zone"]:
            bad.append("safe_zone." + k + " missing")
    return bad


def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        sys.exit(__doc__)
    sj = find_style_json(sys.argv[1])
    pack_dir = os.path.dirname(sj)
    pack = ST.load(sj)
    ovp = find_overrides(pack_dir)
    ov = json.load(open(ovp)) if ovp else {}
    look = arg("--look") or ov.get("default_look")
    ds, fidelity = build(pack, ov, look)
    problems = check(ds)
    if problems:
        sys.exit("design-system.json would be invalid:\n  " + "\n  ".join(problems))
    out = arg("--out") or os.path.join(pack_dir, "design-system.json")
    ds["_generated"] = f"Built by bridge/pack_to_design_system.py from {os.path.basename(pack_dir)}/style.json. Look: {look or 'pack defaults'}. Edit the pack or quick-overrides.json, not this file."
    json.dump(ds, open(out, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {out}")
    print(f"look: {look or 'pack defaults'}  ({fidelity}): Quick caption style {ds['captions']['style']}, key {ds['colors']['key']}")
    if fidelity == "nearest":
        print("note: the Quick lane has four caption styles, so this is the nearest one. For the exact look use the Showcase / Lo-fi lane.")


if __name__ == "__main__":
    main()
