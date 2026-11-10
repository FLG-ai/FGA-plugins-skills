"""Shared helpers for the reel pipeline.

Every script takes the project folder as its first argument (for example ~/reel-kit/projects/<slug>) and reads that
project's edit.py: the one file that describes a video (source clip, keep ranges, shots, captions, cards,
behind-head moments, camera, sound). Kit files (fonts, css, sfx, card library) come from this repo.
"""
import importlib.util
import json
import os
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # this repo
HOME = os.path.expanduser(os.environ.get("REEL_KIT_HOME", "~/reel-kit"))  # the creator's style, projects, the kit's tools
BIN = os.path.join(HOME, "tools", "bin")                  # ffmpeg, ffprobe and Node that setup fetched, when it had to
if os.path.isdir(BIN):
    os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")   # every subprocess below finds them first
try:
    VERSION = open(os.path.join(KIT, "VERSION")).read().strip()                 # the kit release (VERSION file)
except OSError:
    VERSION = "unknown"


def _venv_py(root):
    return os.path.join(root, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(root, ".venv", "bin", "python")


# setup.py installs into HOME (the skill folder can be read-only); a .venv / vendor inside the kit is a dev fallback
PY = next((p for p in (_venv_py(HOME), _venv_py(KIT)) if os.path.exists(p)), _venv_py(HOME))
VENDOR = next((d for d in (os.path.join(HOME, "vendor"), os.path.join(KIT, "kit", "vendor"))
               if os.path.exists(os.path.join(d, "gsap.min.js"))), os.path.join(HOME, "vendor"))
MODELS = os.path.join(HOME, "models")
_BROWSER = os.path.join(HOME, "vendor", "browser-path.txt")      # setup picked a render browser (Linux on ARM)
if os.path.exists(_BROWSER) and not os.environ.get("HYPERFRAMES_BROWSER_PATH"):
    _b = open(_BROWSER).read().strip()
    if os.path.exists(_b):
        os.environ["HYPERFRAMES_BROWSER_PATH"] = _b              # every HyperFrames call below inherits it
HF = ["npx.cmd" if os.name == "nt" else "npx", "-y", "hyperframes@0.8.139"]                               # pinned: every reel renders the same way
FPS = 30


def q(t):
    """snap a time to its frame"""
    return round(t * FPS) / FPS


def clip_start(t):
    """a clip's data-start for the frame that holds t: 2ms early so the renderer never shows it a frame late (never
    before 0: a negative data-start fails the check)"""
    return max(0.0, q(t) - 0.002)


def project_arg():
    if len(sys.argv) < 2 or not os.path.isdir(os.path.expanduser(sys.argv[1])):
        sys.exit(f"usage: {os.path.basename(sys.argv[0])} <project folder> [options]")
    return os.path.abspath(os.path.expanduser(sys.argv[1]))


def load_edit(project):
    """import <project>/edit.py as a module, with PROJECT set and kit defaults filled in"""
    path = os.path.join(project, "edit.py")
    spec = importlib.util.spec_from_file_location("edit", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PROJECT = project
    m.MODE = pack_mode(project, getattr(m, "STYLE", "hifi"))
    if not hasattr(m, "J_LEAD") and "j_lead" in m.MODE:
        m.J_LEAD = m.MODE["j_lead"]
    for k, v in DEFAULTS.items():
        if not hasattr(m, k):
            setattr(m, k, v)
    if m.CAM_ORIGIN is None:
        m.CAM_ORIGIN = (540, 760) if m.CANVAS[0] < m.CANVAS[1] else (m.CANVAS[0] // 2, 400)
    return m


def pack_mode(project, mode):
    """the creator's settings for this mode, from the pack the project was made with (else their current pack)"""
    import style as ST
    local = os.path.join(project, "style", "style.json")
    return dict(ST.load(local if os.path.exists(local) else None).get("modes", {}).get(mode, {}))


def wide(E):
    return E.CANVAS[0] > E.CANVAS[1]


DEFAULTS = dict(
    J_LEAD=0.30,          # J-cut: the next line's audio leads its picture by this much
    HOLD=1.30,            # picture keeps running after the last word (end hold / end card)
    FIXES={},             # whisper mishearings -> the real word
    PROMPT="",            # whisper prompt with the names and terms in the script
    HOOK=None,
    BEHIND=[],
    CUT_WINDOWS=[],
    BW=[],
    CAMERA={},
    END_CARD=None,        # opt-in only
    CARD_SFX=[],
    FX=[],                # hand-built motion graphics: [dict(id, layer, at, end, note)], files in <project>/fx/<id>/
    TITLE="Reel",
    CANVAS=(1080, 1920),  # output size: (1080, 1920) the 9:16 reel; (1920, 1080) the 16:9 wide cut of the same edit
    CAM_ORIGIN=None,      # where the camera scales from (px); default (540, 760), (960, 400) on a wide canvas
    GRADES=[],            # [(start, end, "warm"|"moody"|css filter)]: looks the script asks for, over the house grade
    NEEDS=[],             # storyboard: [(beat id, what the creator should send)], assets the edit is waiting on
    GENERATED=[],         # storyboard: [(beat id, what a connected generator made, which model)], tagged so they can cut it
)


BROWSER_BLOCKED = ("MachPortRendezvousServer",)                   # a macOS sandbox (Codex) refusing the browser


def hf(args, cwd):
    """run the pinned HyperFrames CLI in cwd. On failure print the end of its output and the fix, then stop: a
    sandbox that blocks the headless browser (Codex's default on macOS) gets told exactly that"""
    r = subprocess.run(HF + list(args), cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        out = r.stdout + r.stderr
        print(out[-2500:], file=sys.stderr)
        again = f"  cd \"{cwd}\" && {' '.join(HF + list(args))}"
        if any(s in out for s in BROWSER_BLOCKED) or (os.environ.get("CODEX_SANDBOX") and "Failed to launch the browser" in out):
            sys.exit("The render browser can't start here: this agent's sandbox blocks headless Chrome. Give the "
                     "session full access (Codex: Full access, or `codex --sandbox danger-full-access`) or run this "
                     f"outside the sandbox:\n{again}")
        if "Failed to launch the browser" in out:
            sys.exit("The render browser failed to start (its error is above). Run `python3 setup/setup.py`: it tests "
                     f"the browser and installs one that works on this computer. Then rerun:\n{again}")
        sys.exit(f"hyperframes {args[0]} failed. Rerun it to see everything:\n{again}")
    return r


def timeline(project):
    return json.load(open(os.path.join(project, "timeline.json")))


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)
