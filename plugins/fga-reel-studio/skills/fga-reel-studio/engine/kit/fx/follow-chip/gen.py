#!/usr/bin/env python3
"""follow-chip: put the creator's own handle and headshot on the chip, and check the chip clears the face.

Fills the block between the two markers at the top of <project>/fx/<id>/fx.js: HANDLE from the creator's style pack
(its handle, else its site, else its name) and HEADSHOT (their photo, copied into the folder). The rest of fx.js (the
line under the handle, the cue words) is left as it is. Then it prints when each beat lands on this video's words, the
sounds to add, and a warning when the speaker's chin comes down behind the chip.

Run: PY fx/<id>/gen.py <project> [<id>]
  reads   <project>/edit.py (the FX entry <id>), the style pack (creator), the headshot (fxlib.headshot: assets/headshot.*,
          else the pack's headshot.jpg), words.json, and when there is one work/tracks/track.json
  writes  <project>/fx/<id>/fx.js (the marked block; the folder's fx.html and fx.js are copied in first if missing)
          and the headshot, copied in
<id> defaults to this script's folder name. Rerun it after the creator changes their handle or photo.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
CHIP_TOP, CHIP_X = 1150, (190, 890)      # fx.html .fc-chip: where the chip sits
BEGIN = "// ---- gen.py rewrites the lines between these two markers ----"
END = "// ---- end of gen.py's block ----"

try:
    import fxlib                      # setup puts the kit's pipeline on PY's import path
except ImportError:                   # an older setup, or the effects lab: REEL_KIT, else the kit this folder came from
    for _k in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        if _k and os.path.exists(os.path.join(_k, "pipeline", "fxlib.py")):
            sys.path.insert(0, os.path.join(os.path.abspath(_k), "pipeline"))
            break
    import fxlib


def const(js, name):
    """a constant from fx.js: a quoted string, or a {key: number} object"""
    m = re.search(rf"var {name} = (.*?);", js)
    if not m:
        return None
    v = m.group(1).strip()
    if v.startswith("{"):
        return {k: float(x) for k, x in re.findall(r"(\w+):\s*(-?[\d.]+)", v)}
    return json.loads('"' + v[1:-1].replace('"', '\\"') + '"') if v[:1] in "'\"" else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    out = os.path.join(project, "fx", fid)
    os.makedirs(out, exist_ok=True)
    for f in ("fx.html", "fx.js"):
        if not os.path.exists(os.path.join(out, f)):
            shutil.copy(os.path.join(HERE, f), os.path.join(out, f))

    who = fxlib.pack(project)["creator"]
    handle = next((v.strip() for v in (who.get("handle"), who.get("site"), who.get("name")) if v and v.strip()), "")
    if not handle:
        print("no handle, site or name in the style pack (creator): the chip keeps '@yourhandle'; add one to style.json")
        handle = "@yourhandle"
    shot, name = fxlib.headshot(project), ""
    if shot:
        name = "headshot" + os.path.splitext(shot)[1].lower()
        if os.path.realpath(shot) != os.path.realpath(os.path.join(out, name)):
            shutil.copy(shot, os.path.join(out, name))
    else:
        print("no headshot (assets/headshot.jpg, or headshot.jpg in the style pack): the placeholder glyph stays")

    path = os.path.join(out, "fx.js")
    js = open(path, encoding="utf-8").read()
    i, j = js.index(BEGIN), js.index(END)
    block = "\n".join([BEGIN,
                       f"var HANDLE = {json.dumps(handle, ensure_ascii=False)};   // from the creator's style pack (gen.py)",
                       f"var HEADSHOT = {json.dumps(name)};   // copied in by gen.py; '' = the placeholder glyph", ""])
    js = js[:i] + block + js[j:]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(js)

    # when each beat lands on this video's words (the same rules as fx.js), and the sounds
    def word(w, after, fallback):
        t = fxlib.word_at(project, w, after) if w and os.path.exists(os.path.join(project, "words.json")) else None
        return fallback if t is None or t >= B else t
    T = const(js, "T") or dict(lead=0.03, fchip=0.03, fpress=0.33, fsub=0.54)
    sub, sub_on = const(js, "SUB"), const(js, "SUB_ON")
    chip = max(A, word(const(js, "CHIP_ON"), A, A + T["fchip"] + T["lead"]) - T["lead"])
    press = word(const(js, "PRESS_ON"), chip, chip + T["fpress"])
    subt = (word(sub_on, press, None) if sub_on else press + T["fsub"]) if sub else None
    print(f"wrote the HANDLE / HEADSHOT block of {path}: {handle!r}, " + (f"headshot {name}" if name else "placeholder glyph"))
    print(f"chip {chip:.2f}, press {press:.2f}, " + (f"line under the handle {subt:.2f}" if subt is not None else
                                                     f"no line under the handle ({sub_on!r} is not spoken after the press)"))
    if press - chip < 0.2:
        print("the press lands as the chip arrives: put CHIP_ON on an earlier word, or PRESS_ON on a later one")

    tpath = os.path.join(project, "work", "tracks", "track.json")
    if os.path.exists(tpath):
        frames = fxlib.tracks(project)["frames"][round(A * FPS):round(B * FPS)]
        chins = [f["face"]["chin"] for f in frames if f and f.get("face") and CHIP_X[0] < f["face"]["cx"] < CHIP_X[1]]
        if chins and max(chins) > CHIP_TOP - 8:
            print(f"the chin comes down to y {max(chins):.0f} here: the chip (y {CHIP_TOP}-{CHIP_TOP + 120}) covers it; "
                  "end the window earlier or move .fc-chip up in fx.html")
    print("SOUND sfx (time = the visual event):")
    print(f'    ({chip + 0.12:.3f}, "pop", -17),     # the chip arrives')
    print(f'    ({press:.3f}, "click", -13),     # the Follow press')
    print(f'    ({press + 0.1:.3f}, "pop", -19),     # it turns to Following')
    if subt is not None:
        print(f'    ({subt:.3f}, "tick", -16),     # the line under the handle')
    print(f"frames=[{chip + 0.3:.2f}, {press + 0.3:.2f}, {min(B - 0.05, (subt or press) + 0.6):.2f}]")


if __name__ == "__main__":
    main()
