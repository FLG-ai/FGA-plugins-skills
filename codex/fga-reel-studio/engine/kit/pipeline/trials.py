#!/usr/bin/env python3
"""Trials: post several versions of a reel as Instagram Trial Reels (through Zernio) and see which one wins.

The app ships inside the kit (KIT/trials/app) and runs from the creator's copy in HOME/trials/app. Everything the
creator owns stays outside what an update replaces:
- HOME/trials/.env holds their Zernio key; this script only ever creates it, empty, when it's missing. They paste
  the key on the Trials page, which checks it with Zernio and writes it there.
- HOME/trials/experiments.json (+ backups/) is their test history; the app writes it, this script never does.
- HOME/trials/app is their copy of the app. An update replaces a file only if it's still exactly what the kit
  installed (.reel-kit.json records that). A file they changed is kept; when the update changed it too, the new
  version waits in HOME/trials/updates/<version>/ for Claude to merge. Files they added are never touched. The
  whole app is copied to HOME/trials/app-backups/ before any update.

  PY pipeline/trials.py status            installed version, key set or not, running or not, waiting merges
  PY pipeline/trials.py install           install, or update to this kit's version (safe to run every time)
  PY pipeline/trials.py start [--no-open] start it in the background and open it (Trials for Mac, or the browser)
  PY pipeline/trials.py stop
  PY pipeline/trials.py app [--no]        Mac: install Trials for Mac (--no: they'd rather use the browser)
  PY pipeline/trials.py key               open the .env file (a fallback: the page has a box for the key)

Trials for Mac (their choice, asked once): a real Mac app in Applications (~/Applications when the main one isn't
writable) with its own window and Dock icon. It starts the server when it opens, and it answers trials://start, the
"Turn it back on" button on the "Trials is off" page a browser shows. The binary is built once from
KIT/trials/mac/Trials.swift; this script wraps it in Trials.app on their Mac, so macOS opens it without a warning.
"""
import hashlib
import json
import os
import plistlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

from common import HOME, KIT, VERSION

SRC = os.path.join(KIT, "trials", "app")
TRIALS = os.path.join(HOME, "trials")
APP = os.path.join(TRIALS, "app")
ENV = os.path.join(TRIALS, ".env")
MANIFEST = os.path.join(APP, ".reel-kit.json")
PID = os.path.join(TRIALS, "server.pid")
LOG = os.path.join(TRIALS, "server.log")
PORT = 5180
URL = f"http://127.0.0.1:{PORT}/"
LAUNCHER = os.environ.get("TRIALS_LAUNCHER") or ("/Applications/Trials.app" if os.access("/Applications", os.W_OK)
                                                  else os.path.expanduser("~/Applications/Trials.app"))   # env: tests
OLD_LAUNCHERS = [os.path.expanduser("~/Applications/Trials.app"), "/Applications/Trials.app"]   # moved from here
LAUNCHER_REV = "3"   # bump to rebuild every Trials for Mac on the next install, even within one kit version
MAC_BINARY = os.path.join(KIT, "trials", "mac", "Trials")   # built by dev/build_trials_mac.py from Trials.swift
PREFS = os.path.join(TRIALS, "prefs.json")   # {"macApp": true|false}: their answer to "Mac app or browser?"
LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/"
              "lsregister")
START = os.path.join(TRIALS, "start.sh")
SKIP = {"node_modules", "dist", ".git", ".reel-kit.json", ".DS_Store"}
ENV_TEMPLATE = """# Your Zernio API key goes after the = sign, with no spaces. Trials reads it from here.
# Reel Kit updates never touch this file.
ZERNIO_API_KEY=
"""


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def tree(root):
    """every file under root (relative path -> sha256), leaving out what npm and the build make"""
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in files:
            if f not in SKIP:
                p = os.path.join(d, f)
                out[os.path.relpath(p, root)] = sha(p)
    return out


def read_manifest():
    try:
        return json.load(open(MANIFEST))
    except (OSError, ValueError):
        return None


def has_key():
    try:
        for line in open(ENV):
            k, _, v = line.partition("=")
            if k.strip() == "ZERNIO_API_KEY" and v.strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


def running():
    try:
        with urllib.request.urlopen(URL + "api/zernio/status", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def pending():
    """update folders still holding new versions of files the creator changed"""
    root = os.path.join(TRIALS, "updates")
    if not os.path.isdir(root):
        return []
    return sorted(os.path.join(root, v, rel) for v in os.listdir(root) for rel in tree(os.path.join(root, v)))


def npm_install():
    print("installing the app's packages (a minute, once per update) ...", flush=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    r = subprocess.run([npm, "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=APP)
    if r.returncode:
        sys.exit("npm install failed: run setup again (it installs Node), then this again")


START_SH = """#!/bin/sh
# Starts Trials if it's off and returns once it answers. Trials for Mac runs this when it opens.
# Written by Reel Kit (pipeline/trials.py) on every install and update: change pipeline/trials.py, not this file.
export PATH={path}:/usr/bin:/bin
export TRIALS_DATA_DIR={trials} REEL_KIT_HOME={home}
URL={url}
up() {{ curl -fs -m 2 "${{URL}}api/zernio/status" >/dev/null; }}
up && exit 0
cd {app} || exit 1
nohup npx vite --host 127.0.0.1 --port {port} --strictPort >>{log} 2>&1 </dev/null &
echo $! >{pid}
i=0
while ! up && [ $i -lt 60 ]; do sleep 0.5; i=$((i+1)); done
"""


def draw_icon(path):
    """a test tube with the leader green in it, on a macOS-shaped tile: 1024 px, made into an .icns"""
    from PIL import Image, ImageDraw
    big = 2048
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    m = 200
    d.rounded_rectangle((m, m, big - m, big - m), radius=370, fill=(246, 246, 246, 255))
    tube = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    t = ImageDraw.Draw(tube)
    w, top, bottom = 360, 520, 1600
    x0, x1 = big // 2 - w // 2, big // 2 + w // 2
    open_top = (False, False, True, True)   # round at the bottom only: the top of a tube is open
    edge, ink, glass, green = 64, (38, 38, 38, 255), (246, 246, 246, 255), (57, 168, 69, 255)
    t.rounded_rectangle((x0, top, x1, bottom), radius=w // 2, fill=ink, corners=open_top)
    t.rounded_rectangle((x0 + edge, top, x1 - edge, bottom - edge), radius=w // 2 - edge, fill=glass, corners=open_top)
    t.rounded_rectangle((x0 + edge, 1080, x1 - edge, bottom - edge), radius=w // 2 - edge, fill=green, corners=open_top)
    t.rounded_rectangle((x0 - 70, top - 64, x1 + 70, top + 20), radius=42, fill=(38, 38, 38, 255))
    tube = tube.rotate(-28, resample=Image.BICUBIC, center=(big // 2, big // 2 + 40))
    tile.alpha_composite(tube)
    tile = tile.resize((1024, 1024), Image.LANCZOS)
    iconset = path + ".iconset"
    os.makedirs(iconset, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        tile.resize((size, size), Image.LANCZOS).save(os.path.join(iconset, f"icon_{size}x{size}.png"))
        tile.resize((size * 2, size * 2), Image.LANCZOS).save(os.path.join(iconset, f"icon_{size}x{size}@2x.png"))
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", path], check=True)
    shutil.rmtree(iconset)


def prefs():
    try:
        return json.load(open(PREFS))
    except (OSError, ValueError):
        return {}


def mac_app_path():
    """where Trials for Mac is installed, or None (also finds one an earlier version put in the other Applications)"""
    for path in [LAUNCHER] + [p for p in OLD_LAUNCHERS if p != LAUNCHER and not os.environ.get("TRIALS_LAUNCHER")]:
        try:
            if plistlib.load(open(os.path.join(path, "Contents", "Info.plist"), "rb")).get(
                    "CFBundleIdentifier") == "com.reelkit.trials":
                return path
        except OSError:
            pass
    return None


def remove_mac_app(path):
    subprocess.run([LSREGISTER, "-u", path], capture_output=True)
    shutil.rmtree(path)


def mac(build=False):
    """macOS: writes start.sh, and builds or updates Trials for Mac when they chose it (build=True: they just did).
    Prints MAC_APP <path>, MAC_APP no (they chose the browser) or MAC_APP ask (they haven't chosen yet)."""
    if sys.platform != "darwin":
        return
    npx = shutil.which("npx")
    q = lambda p: "'" + p.replace("'", "'\\''") + "'"
    with open(START, "w") as f:
        f.write(START_SH.format(path=q(os.path.dirname(npx)) if npx else "/usr/local/bin:/opt/homebrew/bin",
                                trials=q(TRIALS), home=q(HOME), url=URL, app=q(APP), port=PORT, log=q(LOG), pid=q(PID)))
    os.chmod(START, 0o755)
    have = mac_app_path()
    if not build and not have:
        print("MAC_APP " + ("no" if prefs().get("macApp") is False else "ask"))
        return
    try:
        info = plistlib.load(open(os.path.join(LAUNCHER, "Contents", "Info.plist"), "rb"))
        current = (have == LAUNCHER and info.get("CFBundleShortVersionString") == VERSION
                   and info.get("ReelKitStart") == START and info.get("ReelKitLauncher") == LAUNCHER_REV
                   and info.get("CFBundleExecutable") == "Trials")
    except OSError:
        current = False
    if not current:
        if have:
            remove_mac_app(have)   # an older build, or one an earlier version put in the other Applications
        contents = os.path.join(LAUNCHER, "Contents")
        os.makedirs(os.path.join(contents, "MacOS"))
        os.makedirs(os.path.join(contents, "Resources"))
        binary = os.path.join(contents, "MacOS", "Trials")
        shutil.copyfile(MAC_BINARY, binary)   # a plain copy: no download flag, so macOS opens it without a warning
        os.chmod(binary, 0o755)
        plistlib.dump({
            "CFBundleExecutable": "Trials",
            "CFBundleIdentifier": "com.reelkit.trials",
            "CFBundleName": "Trials",
            "CFBundleDisplayName": "Trials",
            "CFBundlePackageType": "APPL",
            "CFBundleIconFile": "Trials",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
            "CFBundleURLTypes": [{"CFBundleURLName": "Trials", "CFBundleURLSchemes": ["trials"]}],
            "ReelKitURL": URL,
            "ReelKitStart": START,
            "ReelKitLauncher": LAUNCHER_REV,
        }, open(os.path.join(contents, "Info.plist"), "wb"))
        try:
            draw_icon(os.path.join(contents, "Resources", "Trials.icns"))
        except Exception as e:   # no Pillow or iconutil: the app still works, with the default icon
            print(f"(app icon skipped: {e})")
        subprocess.run(["xattr", "-cr", LAUNCHER], capture_output=True)
        subprocess.run(["codesign", "--force", "--deep", "-s", "-", LAUNCHER], capture_output=True)
        subprocess.run([LSREGISTER, "-f", LAUNCHER], capture_output=True)
    if build:
        json.dump(dict(prefs(), macApp=True), open(PREFS, "w"))
    print(f"MAC_APP {LAUNCHER}")


def no_mac_app():
    """they'd rather use the browser: remember it (so nobody asks again) and remove the app if there is one"""
    have = mac_app_path() if sys.platform == "darwin" else None
    if have:
        remove_mac_app(have)
    json.dump(dict(prefs(), macApp=False), open(PREFS, "w"))
    print("MAC_APP no" + (f" (removed {have})" if have else ""))


def install():
    if not os.path.isdir(SRC):
        sys.exit(f"this kit has no Trials app at {SRC}")
    os.makedirs(TRIALS, exist_ok=True)
    if not os.path.exists(ENV):
        with open(ENV, "w") as f:
            f.write(ENV_TEMPLATE)
    new = tree(SRC)

    if not os.path.isdir(APP):
        shutil.copytree(SRC, APP, ignore=shutil.ignore_patterns(*SKIP))
        json.dump({"version": VERSION, "files": new}, open(MANIFEST, "w"), indent=1)
        npm_install()
        mac()
        print(f"INSTALLED Trials {VERSION} in {APP}")
        return

    old = read_manifest()
    if old is None:
        # An app folder we didn't record (copied in by hand): treat every file in it as theirs.
        old = {"version": "unknown", "files": {}}
        have = tree(APP)
        mine = set(have)
    else:
        have = tree(APP)
        # Theirs: shipped files they edited or deleted. Files they added aren't in old["files"] and are never touched.
        mine = {rel for rel, h in old["files"].items() if have.get(rel) != h}
    if old.get("version") == VERSION and all(old["files"].get(rel) == h for rel, h in new.items()):
        if not os.path.isdir(os.path.join(APP, "node_modules")):
            npm_install()
        mac()
        print(f"UP TO DATE Trials {VERSION}" + (f" ({len(mine)} file(s) you changed, kept)" if mine else ""))
        return

    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    backup = os.path.join(TRIALS, "app-backups", f"{old.get('version', 'unknown')}-{stamp}")
    shutil.copytree(APP, backup, ignore=shutil.ignore_patterns("node_modules", "dist"))

    updated, kept, merge = [], [], []
    for rel, h in new.items():
        dst = os.path.join(APP, rel)
        if rel in mine:
            if h != old["files"].get(rel) and have.get(rel) != h:
                # They changed it and so did the kit: keep theirs, park the new one for a merge.
                park = os.path.join(TRIALS, "updates", VERSION, rel)
                os.makedirs(os.path.dirname(park), exist_ok=True)
                shutil.copy2(os.path.join(SRC, rel), park)
                merge.append(rel)
            else:
                kept.append(rel)
        elif have.get(rel) != h:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(SRC, rel), dst)
            updated.append(rel)
    for rel in old["files"]:
        if rel not in new and rel not in mine and os.path.exists(os.path.join(APP, rel)):
            os.remove(os.path.join(APP, rel))      # the kit dropped it and they never changed it
            updated.append(rel)

    json.dump({"version": VERSION, "files": new}, open(MANIFEST, "w"), indent=1)
    if {"package.json", "package-lock.json"} & set(updated) or not os.path.isdir(os.path.join(APP, "node_modules")):
        npm_install()
    mac()
    print(f"UPDATED Trials {old.get('version')} -> {VERSION}: {len(updated)} file(s) updated")
    print(f"backup of the app before the update: {backup}")
    for rel in kept:
        print(f"KEPT {rel} (you changed it; the update didn't)")
    for rel in merge:
        print(f"MERGE {rel}: yours is in the app, the new version is {os.path.join(TRIALS, 'updates', VERSION, rel)}")


def start(open_it=True):
    if not os.path.isdir(os.path.join(APP, "node_modules")):
        install()
    if not running():
        npx = "npx.cmd" if os.name == "nt" else "npx"
        env = dict(os.environ, TRIALS_DATA_DIR=TRIALS, REEL_KIT_HOME=HOME)
        log = open(LOG, "a")
        p = subprocess.Popen([npx, "vite", "--host", "127.0.0.1", "--port", str(PORT), "--strictPort"], cwd=APP,
                             env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)
        open(PID, "w").write(str(p.pid))
        for _ in range(60):
            if running():
                break
            if p.poll() is not None:
                sys.exit(f"Trials didn't start. Last lines of {LOG}:\n" + "".join(open(LOG).readlines()[-15:]))
            time.sleep(0.5)
        else:
            sys.exit(f"Trials didn't answer on {URL} within 30 seconds. See {LOG}")
    print(f"RUNNING {URL}")
    if not has_key():
        print("NO KEY: they paste their Zernio key on the Trials page (it opens on that screen)")
    app = mac_app_path() if sys.platform == "darwin" else None
    if open_it and app:
        subprocess.run(["open", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"OPENED Trials for Mac ({app})")
    elif open_it:
        opener = {"darwin": ["open"], "win32": ["cmd", "/c", "start", ""]}.get(sys.platform, ["xdg-open"])
        subprocess.run(opener + [URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop():
    """stops Trials however it was started: from here (its own process group) or by the launcher (start.sh)"""
    pids = set()
    try:
        pids.add(int(open(PID).read()))
    except (OSError, ValueError):
        pass
    if running() and shutil.which("lsof"):   # whatever is serving Trials' port is Trials (running() checked its API)
        out = subprocess.run(["lsof", "-ti", f"tcp:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
        pids |= {int(x) for x in out.split() if x.isdigit()}
    for pid in pids:
        for kill in ((lambda: os.killpg(pid, signal.SIGTERM)) if hasattr(os, "killpg") else None,
                     lambda: os.kill(pid, signal.SIGTERM)):
            try:
                kill and kill()
            except OSError:
                pass
    for _ in range(20):
        if not running():
            break
        time.sleep(0.25)
    if os.path.exists(PID):
        os.remove(PID)
    print("STOPPED" if not running() else f"something else is answering on {URL}")


def status():
    m = read_manifest()
    print(f"app      {m['version'] if m else ('not installed' if not os.path.isdir(APP) else 'installed by hand')}"
          f" (kit {VERSION}) {APP}")
    print(f"key      {'set' if has_key() else 'MISSING, goes in ' + ENV}")
    print(f"server   {'RUNNING ' + URL if running() else 'stopped'}")
    if sys.platform == "darwin":
        app = mac_app_path()
        choice = prefs().get("macApp")
        print(f"mac app  {app or ('no, they use the browser' if choice is False else 'not chosen yet')}")
    if m:
        have = tree(APP)
        mine = [rel for rel, h in m["files"].items() if have.get(rel) != h]
        if mine:
            print(f"yours    {len(mine)} file(s) you changed: " + ", ".join(mine))
    for p in pending():
        print(f"MERGE    {p}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "install":
        install()
    elif cmd == "start":
        start("--no-open" not in sys.argv)
    elif cmd == "stop":
        stop()
    elif cmd == "app":
        if sys.platform != "darwin":
            sys.exit("Trials for Mac is for Macs: everywhere else Trials opens in the browser")
        no_mac_app() if "--no" in sys.argv else mac(build=True)
    elif cmd == "key":
        if not os.path.exists(ENV):
            install()
        opener = {"darwin": ["open", "-t"], "win32": ["notepad"]}.get(sys.platform, ["xdg-open"])
        subprocess.run(opener + [ENV])
        print(f"opened {ENV}")
    else:
        status()
