#!/usr/bin/env python3
"""Setup: checks what reel-kit needs on this computer and installs its own pieces. Safe to run again any time.

Run:  sh setup/setup.sh [--check] [--matte] [--track] [--depth]   (finds or fetches a Python 3.12+, then runs this file with it)
  --check  report only, change nothing
  --matte  also install PyTorch for pipeline/matte.py (smoother cutouts for lo-fi, about 1 GB)
  --track  install tracking now (MediaPipe in .venv-mp + its models, about 410 MB) instead of on first use
  --depth  download the depth model now (99 MB) instead of on first use

Prints one STATUS line per piece. A MISSING line ends with the exact fix for this computer. Ends with READY or
NOT READY. Standard library only, so it runs before anything else is installed. Everything it installs goes in
$REEL_KIT_HOME (default ~/reel-kit: .venv/, vendor/, tools/, models/), next to the style pack and projects, never
inside the skill folder. On a Mac or Linux without ffmpeg or Node 22+, it fetches its own into tools/: no admin
password, no Homebrew, nothing system-wide.
"""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser(os.environ.get("REEL_KIT_HOME", "~/reel-kit"))
sys.path.insert(0, os.path.join(KIT, "pipeline"))
import models  # noqa: E402  (standard library only: the layered effects' models and MediaPipe venv)
WIN = os.name == "nt"
VENV = os.path.join(HOME, ".venv")                     # everything setup makes lives in HOME: the skill folder may be read-only
VENV_PY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")
HF = ["npx.cmd" if WIN else "npx", "-y", "hyperframes@0.8.139"]
GSAP_VERSION = "3.15.0"
GSAP_URL = f"https://cdn.jsdelivr.net/npm/gsap@{GSAP_VERSION}/dist/gsap.min.js"
GSAP_PATH = os.path.join(HOME, "vendor", "gsap.min.js")
CHECK = "--check" in sys.argv
OS = "macos" if sys.platform == "darwin" else "windows" if WIN else "linux"
ARCH = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "amd64"
TOOLS = os.path.join(HOME, "tools")                    # ffmpeg, Node and Python that setup fetched itself
BIN = os.path.join(TOOLS, "bin")                       # first on PATH for setup and the pipeline (common.py)
os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")
MARKER = os.path.join(HOME, ".setup-version")          # the kit release that last reached READY on this computer
AGAIN = f"check your internet connection, then run setup again: sh {os.path.join(KIT, 'setup', 'setup.sh')}"
FIX = {
    "ffmpeg": {"macos": AGAIN, "linux": AGAIN,
               "windows": "winget install --id Gyan.FFmpeg -e   (then reopen the terminal)"},
    "node": {"macos": AGAIN, "linux": AGAIN,
             "windows": "winget install --id OpenJS.NodeJS.LTS -e   (then reopen the terminal)"},
    "python": {"macos": f"sh {os.path.join(KIT, 'setup', 'setup.sh')}   (it fetches one)",
               "linux": f"sh {os.path.join(KIT, 'setup', 'setup.sh')}   (it fetches one)",
               "windows": "winget install --id Python.Python.3.12 -e"},
}

# Static builds fetched when the computer has no ffmpeg (or one without the VP9 encoder the cutout needs) or no
# Node 22+. Pinned with their checksums, so every computer gets the same tools.
FFMPEG_BASE = "https://ffmpeg.martin-riedl.de/download"
FFMPEG = {   # (os, arch): (build folder, ffmpeg.zip sha256, ffprobe.zip sha256), ffmpeg 9.0.2
    ("macos", "arm64"): ("macos/arm64/1789931890_9.0.2",
                         "c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924",
                         "fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6"),
    ("macos", "amd64"): ("macos/amd64/1789931006_9.0.2",
                         "7c6b4125b191cbf773832dc51f424cf2b6bb7da43007d1e066f95909e47cacd4",
                         "2322438ed2f6319a691291b247d09c69dcaa3a982460d1f269a7e1af335cfdfd"),
    ("linux", "arm64"): ("linux/arm64/1789931697_9.0.2",
                         "93a76ae90db5474eecdf951a729857c64f3de23567228d6a7d5e6e8e3cd1021b",
                         "bcbe80fb741c180083327afaf5434812e006b33cacde2016b9aeaf6936128330"),
    ("linux", "amd64"): ("linux/amd64/1789931100_9.0.2",
                         "fa8ecf4abbd290d98f7d188b8649cc6b391ae209a98452be955a15aab1909d7f",
                         "3f428c49070be3d24ec338602b76d412e401ffcb8a5641ef0e729181a232fc32"),
}
NODE_VERSION = "v22.23.3"
NODE = {     # (os, arch): (nodejs.org platform, tar.gz sha256)
    ("macos", "arm64"): ("darwin-arm64", "23b25245dcfb9af7262f8ff142e9e2e0af025368117329e7a7458a51e5922f53"),
    ("macos", "amd64"): ("darwin-x64", "8a677b0219178efd6eb0e475457c4afb452b521a92f6e67845a73bd85727f2a8"),
    ("linux", "arm64"): ("linux-arm64", "5ced2d48d1d7198739b7f86804de0171aefb6823b684b12341d3321afc3cb0b2"),
    ("linux", "amd64"): ("linux-x64", "1084aa36196bba4c3a5e69a1ee388a6e4ff729dad09445fbcd434b28fe3c24af"),
}
ok = True
SANDBOX = os.environ.get("CODEX_SANDBOX")   # Codex marks its sandboxed commands; the render browser can't start in it
FULL_ACCESS = "review the failed command and request only the required filesystem, network or browser-launch permission through Codex, then retry"


def status(name, good, detail="", fix=""):
    global ok
    ok = ok and good
    line = f"STATUS {name:<10} {'OK     ' if good else 'MISSING'} {detail}"
    if not good and fix:
        line += f"\n           fix: {fix}"
    print(line, flush=True)


def fetch_fx():
    """the kit's effects come down at setup, like ffmpeg: the install zips can't carry them (Claude's plugin upload
    takes 200 files at most, no zips inside). fx/BUNDLE.json names the file and its sha256; a kit installed from git
    has the effects loose and no BUNDLE.json. Unpacked into KIT/fx/ next to LIBRARY.md; fx/.unpacked holds the sha."""
    spec = os.path.join(KIT, "fx", "BUNDLE.json")
    if not os.path.exists(spec):
        return
    b = json.load(open(spec))
    done = os.path.join(KIT, "fx", ".unpacked")
    have = os.path.exists(done) and open(done).read().strip() == b["sha256"]
    if not have and not CHECK:
        cache = os.path.join(TOOLS, f"fx-{b['sha256'][:12]}.zip")   # kept, so a fresh copy of the kit unpacks offline
        if os.path.exists(cache) or (print("downloading the kit's effects (about 25 MB) ...", flush=True)
                                     or download(b["url"], cache, b["sha256"])):
            try:
                with zipfile.ZipFile(cache) as z:
                    names = z.namelist()
                    if all(n.startswith("fx/") and ".." not in n for n in names):
                        z.extractall(KIT)
                        with open(done, "w") as fh:
                            fh.write(b["sha256"] + "\n")
                        have = True
            except (OSError, zipfile.BadZipFile) as e:
                print(f"could not unpack the effects: {e}", flush=True)
                os.remove(cache)
    n = len([d for d in os.listdir(os.path.join(KIT, "fx")) if os.path.isdir(os.path.join(KIT, "fx", d))])
    status("effects", have, f"{n} in {os.path.join(KIT, 'fx')}",
           f"{AGAIN} (the skill folder has to be writable once, to unpack them: {KIT})")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def version_of(cmd):
    try:
        out = run(cmd)
        return (out.stdout + out.stderr).strip()
    except OSError:
        return ""


def download(url, dest, sha=None):
    """url -> dest, checked against sha256 when given. curl first: a fetched Python may not find the system's
    certificates, and curl always does. True when the file is there and matches."""
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        if shutil.which("curl"):
            subprocess.run(["curl", "-fsSL", "--retry", "2", "-o", tmp, url], check=True)
        else:
            urllib.request.urlretrieve(url, tmp)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"download failed: {url} ({e})", flush=True)
        return False
    if sha and hashlib.sha256(open(tmp, "rb").read()).hexdigest() != sha:
        os.remove(tmp)
        print(f"download didn't match its checksum: {url}", flush=True)
        return False
    os.replace(tmp, dest)
    return True


def link(target, name):
    """BIN/name -> target, replacing an older link"""
    os.makedirs(BIN, exist_ok=True)
    p = os.path.join(BIN, name)
    if os.path.lexists(p):
        os.remove(p)
    os.symlink(target, p)


def fetch_ffmpeg():
    """a static ffmpeg + ffprobe (with libvpx-vp9) into TOOLS/ffmpeg, linked from BIN"""
    import zipfile
    build = FFMPEG.get((OS, ARCH))
    if not build:
        return False
    print("fetching ffmpeg 9.0.2 into the kit's tools (about 80 MB, once) ...", flush=True)
    folder = os.path.join(TOOLS, "ffmpeg")
    for name, sha in (("ffmpeg", build[1]), ("ffprobe", build[2])):
        z = os.path.join(folder, f"{name}.zip")
        if not download(f"{FFMPEG_BASE}/{build[0]}/{name}.zip", z, sha):
            return False
        with zipfile.ZipFile(z) as zf:
            member = next(m for m in zf.namelist() if os.path.basename(m) == name)
            with zf.open(member) as src, open(os.path.join(folder, name), "wb") as out:
                shutil.copyfileobj(src, out)
        os.remove(z)
        os.chmod(os.path.join(folder, name), 0o755)
        link(os.path.join(folder, name), name)
    return True


def fetch_node():
    """Node 22 from nodejs.org into TOOLS/node, with node, npm and npx linked from BIN"""
    import tarfile
    build = NODE.get((OS, ARCH))
    if not build:
        return False
    print(f"fetching Node {NODE_VERSION} into the kit's tools (about 50 MB, once) ...", flush=True)
    name = f"node-{NODE_VERSION}-{build[0]}"
    tgz = os.path.join(TOOLS, f"{name}.tar.gz")
    if not download(f"https://nodejs.org/dist/{NODE_VERSION}/{name}.tar.gz", tgz, build[1]):
        return False
    with tarfile.open(tgz) as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(TOOLS, filter="data")
        else:
            tf.extractall(TOOLS)
    os.remove(tgz)
    dest = os.path.join(TOOLS, "node")
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(os.path.join(TOOLS, name), dest)
    for b in ("node", "npm", "npx"):
        link(os.path.join(dest, "bin", b), b)
    return True


def node_major():
    m = re.match(r"v(\d+)", version_of(["node", "--version"]) if shutil.which("node") else "")
    return int(m.group(1)) if m else 0


FRAME = """<!doctype html><html><head><meta charset="utf-8"><title>render test</title></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="1.000" data-fps="30" data-width="1080" data-height="1920"
 style="width:1080px;height:1920px;background:#222"></div>
<script src="vendor/gsap.min.js"></script>
<script>window.__timelines = window.__timelines || {}; window.__timelines["main"] = gsap.timeline({ paused: true }).to({}, { duration: 1 });</script>
</body></html>"""


BROWSER_FILE = os.path.join(HOME, "vendor", "browser-path.txt")     # a browser setup picked; the pipeline uses it
PLAYWRIGHT = "playwright@1.56.1"


def frame_test(browser=None):
    """one frame of a one-second composition with the render browser; returns (ok, output)"""
    import glob
    import tempfile
    d = tempfile.mkdtemp(prefix="reel-kit-render-test-")
    os.makedirs(os.path.join(d, "vendor"))
    shutil.copy(GSAP_PATH, os.path.join(d, "vendor", "gsap.min.js"))
    shutil.copy(os.path.join(KIT, "kit", "hyperframes.json"), d)
    with open(os.path.join(d, "index.html"), "w") as fh:
        fh.write(FRAME)
    env = dict(os.environ, **({"HYPERFRAMES_BROWSER_PATH": browser} if browser else {}))
    r = subprocess.run(HF + ["snapshot", "--at", "0.5", "--no-end", "--describe", "false"], cwd=d,
                       capture_output=True, text=True, env=env)
    good = r.returncode == 0 and bool(glob.glob(os.path.join(d, "snapshots", "frame-*.png")))
    shutil.rmtree(d, ignore_errors=True)
    return good, r.stdout + r.stderr


def linux_browser():
    """Linux on ARM (Claude Cowork's VM, Raspberry Pi, ARM servers) has no headless Chrome build, and Ubuntu's
    chromium-browser is a snap wrapper that won't start in a VM or container: install Playwright's Chromium into
    HOME/browsers instead and remember it. Returns the path that renders, or None."""
    dest = os.path.join(HOME, "browsers")
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=dest)
    print("installing a render browser that works on this Linux (Chromium, about 200 MB, once) ...", flush=True)
    root = hasattr(os, "geteuid") and os.geteuid() == 0
    cmd = ["npx", "-y", PLAYWRIGHT, "install"] + (["--with-deps"] if root else []) + ["chromium"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode and not root:
        print("note: if it still can't start, its system libraries are missing: "
              f"sudo npx -y {PLAYWRIGHT} install-deps chromium", flush=True)
    import glob
    found = sorted(glob.glob(os.path.join(dest, "chromium_headless_shell-*", "*", "headless_shell"))) + \
        sorted(glob.glob(os.path.join(dest, "chromium-*", "*", "chrome")))
    for b in found:
        if frame_test(b)[0]:
            os.makedirs(os.path.dirname(BROWSER_FILE), exist_ok=True)
            with open(BROWSER_FILE, "w") as fh:
                fh.write(b)
            return b
    return None


def render_test():
    """launch the render browser for real: one frame of a one-second composition. READY has to mean it can render"""
    saved = open(BROWSER_FILE).read().strip() if os.path.exists(BROWSER_FILE) else None
    good, out = frame_test(saved if saved and os.path.exists(saved) else None)
    if not good and OS == "linux" and not SANDBOX and not CHECK:
        b = linux_browser()
        if b:
            good, out = True, ""
            print(f"render browser: {b}", flush=True)
    if good:
        status("render", True, "the render browser launched and drew a frame")
    elif SANDBOX or "MachPortRendezvousServer" in out:
        status("render", False, "render probe failed in a sandboxed session, inspect the error before changing permissions", FULL_ACCESS)
    else:
        status("render", False, "the test frame failed:\n" + out[-1200:],
               f"{' '.join(HF)} browser ensure, or point HYPERFRAMES_BROWSER_PATH at any Chrome or Chromium")


def find_python():
    """this Python if it is 3.12+, else the newest python3.1x on PATH (or Homebrew's), else None (local change: the kit's build.py uses f-string syntax that only parses on 3.12+)"""
    if sys.version_info >= (3, 12):
        return sys.executable
    names = ["python3.13", "python3.12"] + (["py"] if WIN else [])
    extra = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
    for c in [shutil.which(n) for n in names] + [p for p in extra if os.path.exists(p)]:
        if not c:
            continue
        m = re.search(r"Python 3\.(\d+)", version_of([c, "--version"]))
        if m and int(m.group(1)) >= 12:
            return c
    return None


TEXT = (".html", ".js", ".py", ".md", ".css", ".json", ".svg", ".txt")   # the files dev/release.py fingerprints


def salvage(old):
    """copy the effects and cards the creator made or changed in a hand-installed kit into HOME/fx/ and HOME/cards/,
    their own library that updates never touch. Anything whose text files all match a release (setup/shipped.json)
    is the kit's own and stays behind. Returns the names copied."""
    try:
        known = json.load(open(os.path.join(KIT, "setup", "shipped.json")))
    except (OSError, ValueError):
        return []
    saved = []
    for top in ("fx", "cards"):
        src_top = os.path.join(old, top)
        if not os.path.isdir(src_top):
            continue
        rows = {}
        head = []
        lib = os.path.join(src_top, "LIBRARY.md")
        if os.path.exists(lib):
            for line in open(lib, errors="ignore"):
                if line.startswith("| folder") or (head and line.startswith("|---") and len(head) == 1):
                    head.append(line)
                m = re.match(r"\|\s*`([^`]+)`", line)
                if m:
                    rows[m.group(1)] = line
        for name in sorted(os.listdir(src_top)):
            folder = os.path.join(src_top, name)
            if not os.path.isdir(folder) or name == "__pycache__":
                continue
            mine = False
            for d, dirs, names in os.walk(folder):
                dirs[:] = [x for x in dirs if x != "__pycache__"]
                for n in names:
                    if n.endswith(TEXT):
                        full = os.path.join(d, n)
                        rel = os.path.relpath(full, old).replace(os.sep, "/")
                        if hashlib.sha256(open(full, "rb").read()).hexdigest() not in known.get(rel, []):
                            mine = True
            if not mine:
                continue
            dest = os.path.join(HOME, top, name)
            if os.path.exists(dest):
                dest = os.path.join(HOME, top, name + "-from-old-kit")
                if os.path.exists(dest):
                    continue
            shutil.copytree(folder, dest, ignore=shutil.ignore_patterns("__pycache__"))
            saved.append(f"{top}/{os.path.basename(dest)}")
            mylib = os.path.join(HOME, top, "LIBRARY.md")
            if not os.path.exists(mylib):
                title = "My effects" if top == "fx" else "My cards"
                with open(mylib, "w") as fh:
                    fh.write(f"# {title}\n\nThe creator's own {'effects' if top == 'fx' else 'cards'} and their "
                             f"versions of the kit's. Updates never touch this folder; a folder here with the same "
                             f"name as one in the kit is theirs and wins.\n\n")
                    fh.write("".join(head) if len(head) == 2 else "| folder | what it does |\n|---|---|\n")
            row = rows.get(name) or f"| `{name}` | (from the old kit: describe it) |\n"
            if os.path.basename(dest) != name:
                row = row.replace(f"`{name}`", f"`{os.path.basename(dest)}`", 1)
            with open(mylib, "a") as fh:
                fh.write(row if row.endswith("\n") else row + "\n")
    return saved


def archive_old_skill():
    """the plugin replaces a reel-kit installed by hand into Claude Code's skills folder (0.3.0 and earlier, or the
    bridge zip). Left there, it takes the bare /reel-kit name and keeps running the old kit, so move it (a link
    is moved as a link, its target untouched) into HOME/old-skill/. Only when this kit is the installed plugin."""
    kit = os.path.realpath(KIT)
    if f"{os.sep}plugins{os.sep}" not in kit and f"{os.sep}plugin_" not in kit:   # Claude Code's cache; the desktop app's uploads
        return
    roots = {os.path.expanduser("~/.claude")}
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        roots.add(os.path.expanduser(os.environ["CLAUDE_CONFIG_DIR"]))
    for root in sorted(roots):
        old = os.path.join(root, "skills", "reel-kit")
        if not os.path.lexists(old) or os.path.realpath(old) == kit:
            continue
        try:
            head = open(os.path.join(old, "SKILL.md"), errors="ignore").read(400)
        except OSError:
            continue
        if not re.search(r"^name:\s*reel-kit\s*$", head, re.M):
            continue
        try:
            oldver = open(os.path.join(old, "VERSION")).read().strip()
        except OSError:
            oldver = "0.2"
        dest = os.path.join(HOME, "old-skill", f"reel-kit-{oldver}")
        n = 2
        while os.path.lexists(dest):
            dest = os.path.join(HOME, "old-skill", f"reel-kit-{oldver}-{n}")
            n += 1
        if CHECK:
            print(f"STATUS old-skill  FOUND   {old} (setup moves it to {os.path.dirname(dest)})", flush=True)
            continue
        saved = salvage(old)
        if saved:
            print(f"STATUS my-fx      KEPT    {len(saved)} effects and cards you made or changed, copied into your own "
                  f"library ({os.path.join(HOME, 'fx')}, {os.path.join(HOME, 'cards')}), which updates never touch: "
                  f"{', '.join(saved)}", flush=True)
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(old, dest)
        except OSError as e:
            print(f"STATUS old-skill  FOUND   an old Reel Kit is still in {old} and couldn't be moved ({e}). Remove it "
                  f"(in Cowork: Customize > Skills, delete reel-kit), so only the plugin loads.", flush=True)
            continue
        print(f"STATUS old-skill  MOVED   the old Reel Kit ({oldver}) was in {old}; the plugin replaces it, so it's "
              f"archived in {dest}. Start a new session so only the plugin loads.", flush=True)


def layered():
    """STATUS lines for tracking (MediaPipe in its own venv, pipeline/track.py) and depth (pipeline/depth.py)"""
    again = f"sh {os.path.join(KIT, 'setup', 'setup.sh')}"
    for flag, name in (("--track", "track"), ("--depth", "depth")):
        if flag in sys.argv and not CHECK:
            try:
                if name == "track":
                    models.mp_python()
                    for n in models.TRACK_MODELS:
                        models.path(n)
                else:
                    models.path(models.DEPTH_MODEL)
            except SystemExit as e:              # a failed download says why; the STATUS line below says what to run
                print(e, flush=True)
    v = models.mp_version()
    got = [n for n in models.TRACK_MODELS if models.have(n)]
    if v and len(got) == len(models.TRACK_MODELS):
        if not CHECK:
            models.pth(models.MP_PY)
        status("track", True, f"mediapipe {v} in {models.VENV_MP} ({models.du(models.VENV_MP) / 1e6:.0f} MB), "
               f"{len(got)} models in {models.MODELS}")
    elif "--track" in sys.argv:
        status("track", False, "MediaPipe or its models didn't install", f"{again} --track")
    else:
        print(f"STATUS track      LATER   installs on first use (pipeline/track.py): MediaPipe in {models.VENV_MP}, "
              f"about 390 MB and 1 to 2 minutes, plus 21 MB of models", flush=True)
    if models.have(models.DEPTH_MODEL):
        status("depth", True, f"{models.DEPTH_MODEL} in {models.MODELS}")
    elif "--depth" in sys.argv:
        status("depth", False, "the depth model didn't download", f"{again} --depth")
    else:
        print(f"STATUS depth      LATER   downloads on first use (pipeline/depth.py): {models.DEPTH_MODEL}, 99 MB",
              flush=True)


def main():
    ver = open(os.path.join(KIT, "VERSION")).read().strip() if os.path.exists(os.path.join(KIT, "VERSION")) else "unknown"
    print(f"reel-kit {ver} setup on {OS} ({platform.machine()}), kit at {KIT}", flush=True)
    archive_old_skill()
    fetch_fx()
    if SANDBOX:
        net = " with the network off" if os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED") else ""
        print(f"note: running inside Codex's sandbox ({SANDBOX}){net}. Rendering launches a headless browser, which "
              f"may need permission for browser launch: {FULL_ACCESS}", flush=True)
    # Python 3.12+ for the kit's environment (a stock Mac's python3 is 3.9: setup.sh fetches a newer one)
    base = find_python()
    status("python", bool(base), (version_of([base, "--version"]) + f" ({base})") if base else platform.python_version(),
           FIX["python"][OS])

    # ffmpeg / ffprobe, with the VP9 encoder the cutout needs: the kit's own static build when the computer's won't do
    def vp9():
        return "libvpx-vp9" in version_of(["ffmpeg", "-hide_banner", "-encoders"])
    have = bool(shutil.which("ffmpeg") and shutil.which("ffprobe")) and vp9()
    if not have and not CHECK and fetch_ffmpeg():
        have = bool(shutil.which("ffmpeg")) and vp9()
    detail = version_of(["ffmpeg", "-version"]).split("\n")[0][:60] if have else ""
    status("ffmpeg", have, detail + (f" ({shutil.which('ffmpeg')})" if have else ""), FIX["ffmpeg"][OS])

    # Node 22+ (HyperFrames refuses older): the kit's own copy when the computer has none or an older one
    if node_major() < 22 and not CHECK:
        fetch_node()
    v = version_of(["node", "--version"]) if shutil.which("node") else ""
    status("node", node_major() >= 22, v + ("" if node_major() >= 22 else " (needs 22+)") +
           (f" ({shutil.which('node')})" if node_major() >= 22 else ""), FIX["node"][OS])

    # the kit's own Python environment
    reqs = os.path.join(KIT, "setup", "requirements.txt")
    def venv_runs():
        try:
            return run([VENV_PY, "-c", "import sys"]).returncode == 0
        except OSError:
            return False
    if os.path.isdir(VENV) and not venv_runs() and not CHECK and base:
        # its Python is gone (a Homebrew or uv upgrade, a deleted install): a venv can't be repaired in place
        print("the kit's Python environment points at a Python that no longer exists: rebuilding it ...", flush=True)
        shutil.rmtree(VENV, ignore_errors=True)
    if not os.path.exists(VENV_PY) and not CHECK and base:
        print(f"creating .venv with {base} ...", flush=True)
        os.makedirs(HOME, exist_ok=True)
        subprocess.run([base, "-m", "venv", VENV], check=True)
    if os.path.exists(VENV_PY) and not CHECK:
        print("installing Python packages (numpy, scipy, pillow, opencv, onnxruntime, faster-whisper, yt-dlp) ...", flush=True)
        r = subprocess.run([VENV_PY, "-m", "pip", "install", "-q", "--upgrade", "pip"], capture_output=True)
        r = subprocess.run([VENV_PY, "-m", "pip", "install", "-q", "-r", reqs], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1500:], flush=True)
        models.pth(VENV_PY)          # an effect's gen.py run with the kit's Python can `import fxlib` from any folder
    probe = run([VENV_PY, "-c", "import numpy, scipy, PIL, faster_whisper, yt_dlp, cv2, onnxruntime, fontTools, pymunk, "
                 "fxlib"]) if os.path.exists(VENV_PY) else None
    status("venv", bool(probe and probe.returncode == 0), VENV_PY,
           f"sh {os.path.join(KIT, 'setup', 'setup.sh')}")

    # GSAP (standard license, downloaded here rather than committed)
    if not os.path.exists(GSAP_PATH) and not CHECK:
        download(GSAP_URL, GSAP_PATH)
    good = os.path.exists(GSAP_PATH) and f"GSAP {GSAP_VERSION}" in open(GSAP_PATH, errors="ignore").read(400)
    status("gsap", good, GSAP_VERSION, f"download {GSAP_URL} to {GSAP_PATH}")

    # HyperFrames (renders the video in headless Chrome) and its Chrome
    if shutil.which("npx" if not WIN else "npx.cmd"):
        hv = version_of(HF + ["--version"])
        status("hyperfrm", "0.8.139" in hv, "hyperframes 0.8.139",
               FULL_ACCESS if SANDBOX else "check your internet connection, then run setup again")
        if not CHECK:
            print("making sure the render browser is installed ...", flush=True)
            r = run(HF + ["browser", "ensure"])
            if r.returncode:
                print((r.stdout + r.stderr)[-800:], flush=True)
        chrome = run(HF + ["browser", "path"])
        found = chrome.returncode == 0 and bool(chrome.stdout.strip())
        if OS != "linux" or found:                  # on Linux the render step installs a browser that works
            status("chrome", found, "found" if found else "", FULL_ACCESS if SANDBOX else f"{' '.join(HF)} browser ensure")
        if os.path.exists(GSAP_PATH) and (found or OS == "linux"):
            render_test()
    else:
        status("hyperfrm", False, "needs Node first", FIX["node"][OS])

    # the transcription model (downloaded once, about 1.5 GB, into the Hugging Face cache)
    if os.path.exists(VENV_PY):
        have = run([VENV_PY, "-c", "from faster_whisper.utils import download_model; download_model('medium', local_files_only=True)"])
        if have.returncode and not CHECK:
            print("downloading the transcription model (Whisper medium, about 1.5 GB, once) ...", flush=True)
            subprocess.run([VENV_PY, "-c", "from faster_whisper.utils import download_model; download_model('medium')"])
            have = run([VENV_PY, "-c", "from faster_whisper.utils import download_model; download_model('medium', local_files_only=True)"])
        status("whisper", have.returncode == 0, "medium", "check your internet connection, then run setup again")

    # optional: smoother cutouts
    if "--matte" in sys.argv and os.path.exists(VENV_PY):
        if not CHECK:
            cmd = [VENV_PY, "-m", "pip", "install", "-q", "torch"]
            if OS == "linux" and not shutil.which("nvidia-smi"):
                cmd += ["--index-url", "https://download.pytorch.org/whl/cpu"]
            print("installing PyTorch (about 1 GB) ...", flush=True)
            subprocess.run(cmd)
        t = run([VENV_PY, "-c", "import torch; print(torch.__version__)"])
        status("matte", t.returncode == 0, t.stdout.strip(), "python3 setup/setup.py --matte")

    # optional: tracking and depth for the layered effects. Not needed for READY: track.py and depth.py fetch them
    # the first time an effect needs them (--track / --depth fetches them now)
    if os.path.exists(VENV_PY):
        layered()

    # the creator's style (made by onboarding, not by setup)
    pack = os.path.join(HOME, "style", "style.json")
    print(f"STATUS style      {'OK     ' if os.path.exists(pack) else 'NONE YET'} "
          f"{pack if os.path.exists(pack) else 'next: build it with /reel-kit-style (in Claude Code: /reel-kit:reel-kit-style), in a new chat'}",
          flush=True)
    if ok and not CHECK:
        with open(MARKER, "w") as fh:
            fh.write(ver + "\n")
    if ok:
        print("Reel Kit is part of the AI Video Editing Masterclass by Justyn (@justyn.ai).", flush=True)
    print("READY" if ok else "NOT READY: apply the fixes above, then run setup again", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
