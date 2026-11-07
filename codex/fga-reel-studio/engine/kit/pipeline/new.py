#!/usr/bin/env python3
"""New: scaffold a video project -> $REEL_KIT_HOME/projects/<slug>/ (default ~/reel-kit/projects/<slug>/), with the
creator's style pack copied in and a starter edit.py.
Run: PY pipeline/new.py <slug> "<source clip path>" ["Title"] --mode hifi|lofi|showcase
FRAMES are seeded from the clip: 4K landscape gets two 9:16 crops (WIDE, CLOSE), anything else full frame + a 1.25x CLOSE.
The style pack is copied, not linked, so an old project still renders the same after the creator changes their style.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KIT, VENDOR  # noqa: E402
import style as ST  # noqa: E402

STARTER = '''"""{title}: the one file that describes this video. Read modes/{mode_doc}, then copy what you need from
examples/{mode}/edit.py. Times are on the OUTPUT timeline unless marked source."""
TITLE = "{title}"
STYLE = "{mode}"                    # hifi (modes/HIFI.md), lofi (modes/LOFI.md) or showcase (modes/SHOWCASE.md)
SRC = "{src}"

# ---- cut (source seconds): keep ranges from silencedetect, last clean take of every line
KEEP = []
# 9:16 crops of the source (w, h, x, y): seeded from its size, then measure on a frame of THIS shoot (face, eyes, chin)
FRAMES = {frames}
SHOTS = [(0.000, "WIDE")]           # add CLOSE/WIDE changes; hide them under cards where you can
HOLD = {hold}                         # picture after the last word: hi-fi 0.6 (1.3 with an end card), lo-fi 0.04
FIXES = {{}}                         # transcription mishearings -> the real word
PROMPT = ""                         # names, products and numbers in the script, to help transcription

# ---- after words.py: captions (start, text, kind[, end]); kinds "", "big", "thesis", "strike"; *word* = accent
CAPS = []
HOOK = None                         # dict(eyebrow=, h1=, h2=, off=, shot_end=[, tag=])
BEHIND = []                         # moments behind the speaker's head
CUT_WINDOWS = []                    # where the cutout plays (never across a picture change)
BW = []                             # black-and-white beats, at most two
CAMERA = dict(punch=[], pushes=[], open=(1.04, 0.45))
CARDS = []                          # (id, "cards/<id>.mp4", start, end, "light"|"dark", "what it shows")
END_CARD = None                     # opt-in only
SOUND = dict(sfx=[], music=None)    # music is off by default: the creator adds a track in their posting app
CARD_SFX = []
NEEDS = []                          # (beat id, what the creator should send: a screenshot, a clip, a logo)
GENERATED = []                      # (beat id, what a connected generator made, which model); empty without one
{extra}'''

SHOWCASE = '''
# ---- showcase (modes/SHOWCASE.md): the lo-fi type system + one hand-built motion graphic per beat
KARAOKE = dict(huge=[], hide=[])    # huge: lines set at 124px; hide: windows an effect carries the words in
BOXES = []                          # native text boxes (hook, CTA) when no effect carries them
OVERLAYS = []
FX = []                             # dict(id, layer behind|cam|top|over, at, end, frames=[...], note=); files in fx/<id>/
GRADES = []                         # (start, end, "warm"|"moody"|css filter): looks the script asks for
J_LEADS = None                      # per-join J-cut leads, when one shot must stop early (a lean-in to the phone)
'''
LOFI = '''
KARAOKE = {}                        # dict(huge=[(start, end)], hide=[(start, end)])
BOXES = []                          # Instagram-style text boxes: hook, chapter labels, CTA
OVERLAYS = []                       # real screenshots or clips dropped on top of the speaker
'''
EXTRA = {"lofi": LOFI, "showcase": SHOWCASE}


def frames_for(src):
    """FRAMES seeded from the clip's size: 4K landscape -> two 9:16 crops; anything else -> full frame + a 1.25x CLOSE"""
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
    try:
        w, h = (int(x) for x in out.split(",")[:2])
    except ValueError:
        sys.exit(f"could not read the video size of {src}: is it a video file?")
    if w > h:
        # landscape: a full-height 9:16 window in the middle, and a tighter one 1.6x in (move both onto the face)
        ww = round(h * 9 / 16) // 2 * 2
        cw, ch = round(ww / 1.6) // 2 * 2, round(h / 1.6) // 2 * 2
        return (f'{{"WIDE": ({ww}, {h}, {(w - ww) // 2}, 0), '
                f'"CLOSE": ({cw}, {ch}, {(w - cw) // 2}, {round(h * 0.18)})}}')
    cw, ch = round(w * 0.8) // 2 * 2, round(h * 0.8) // 2 * 2
    return f'{{"WIDE": ({w}, {h}, 0, 0), "CLOSE": ({cw}, {ch}, {(w - cw) // 2}, {(h - ch) // 2})}}'


def copy_pack(project):
    """the creator's style pack (style.json, brand.css, fonts/) -> <project>/style/"""
    src = ST.STYLE_DIR
    if not os.path.exists(os.path.join(src, "style.json")):
        sys.exit(f"no style pack at {src}: run onboarding first (onboarding/ONBOARDING.md), or point REEL_KIT_HOME at one")
    dest = os.path.join(project, "style")
    os.makedirs(dest, exist_ok=True)
    S = ST.load(os.path.join(src, "style.json"))
    if not os.path.exists(os.path.join(src, "brand.css")):
        ST.write(S, src)
    for f in ("style.json", "brand.css", "STYLE.md"):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), dest)
    if os.path.isdir(os.path.join(src, "fonts")):
        shutil.copytree(os.path.join(src, "fonts"), os.path.join(dest, "fonts"), dirs_exist_ok=True)


def main():
    argv = sys.argv[1:]
    mode = None
    for flag in ("--mode", "--style"):
        if flag in argv:
            i = argv.index(flag)
            mode = argv[i + 1] if i + 1 < len(argv) else None
            argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2 or mode not in ("hifi", "lofi", "showcase"):
        sys.exit(__doc__ + "\n--mode hifi|lofi|showcase is required: the creator picks the mode, never guess it.")
    slug, src = args[0], os.path.abspath(os.path.expanduser(args[1]))
    if not os.path.exists(src):
        sys.exit(f"source clip not found: {src}")
    title = args[2] if len(args) > 2 else slug.replace("-", " ").title()
    project = os.path.join(ST.HOME, "projects", slug)
    if os.path.exists(os.path.join(project, "edit.py")):
        sys.exit(f"{project}/edit.py already exists")
    for d in ("assets", "audio", "cards", "fx", "public/cards", "public/media", "renders", "storyboard", "work"):
        os.makedirs(os.path.join(project, d), exist_ok=True)
    copy_pack(project)
    if not os.path.exists(os.path.join(VENDOR, "gsap.min.js")):
        sys.exit(f"{VENDOR}/gsap.min.js is missing: run python3 setup/setup.py first")
    shutil.copytree(VENDOR, os.path.join(project, "public", "vendor"), dirs_exist_ok=True)
    shutil.copy(os.path.join(KIT, "kit", "hyperframes.json"), os.path.join(project, "public"))
    with open(os.path.join(project, "edit.py"), "w") as fh:
        fh.write(STARTER.format(title=title, src=src, mode=mode, mode_doc=f"{mode.upper()}.md", hold=0.6 if mode == "hifi" else 0.04 if mode == "lofi" else 0.5,
                                frames=frames_for(src), extra=EXTRA.get(mode, "")))
    print(project)


if __name__ == "__main__":
    main()
