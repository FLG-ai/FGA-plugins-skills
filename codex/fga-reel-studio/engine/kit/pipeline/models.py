"""The models the layered effects use, fetched on first use into $REEL_KIT_HOME/models and checked against a pinned
sha256, and the MediaPipe environment track.py runs in ($REEL_KIT_HOME/.venv-mp). Standard library only: setup.py
imports it before anything else is installed. Nothing large ever goes into the kit itself.

  models.path(name)      -> the model file, downloaded and verified the first time it is asked for
  models.have(name)      -> True when it is already there (no download)
  models.mp_python()     -> the MediaPipe venv's python, made the first time it is needed (about 390 MB, 1-2 minutes)
"""
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import HOME, MODELS, PY  # noqa: E402

# name: (bytes, [(url, sha256), ...]). Official sources only; the first one that downloads and matches is kept.
MODEL = {
    # Depth Anything V2 Small (Apache-2.0), the ONNX export on Hugging Face, pinned to a commit
    "depth_anything_v2_small.onnx": (99060839, [
        ("https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/"
         "4472b7362082ad9968fee890ca0f1e5aca36b93d/onnx/model.onnx",
         "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c")]),
    # MediaPipe task models (Apache-2.0), Google's model bucket
    "face_landmarker.task": (3758596, [
        ("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
         "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff")]),
    "hand_landmarker.task": (7819105, [
        ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
         "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1")]),
    # the pose model the effects were built with is only served as "latest"; version 1 is the fallback if that moves
    "pose_landmarker_full.task": (9398198, [
        ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
         "4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad"),
        ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
         "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1")]),
}
TRACK_MODELS = ("face_landmarker.task", "hand_landmarker.task", "pose_landmarker_full.task")
DEPTH_MODEL = "depth_anything_v2_small.onnx"

VENV_MP = os.path.join(HOME, ".venv-mp")             # MediaPipe pins its own numpy and OpenCV: its own venv
MP_PY = os.path.join(VENV_MP, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_MP, "bin", "python")
# the version the effects were built on; Intel Macs get the last release that ships a build for them
INTEL_MAC = sys.platform == "darwin" and platform.machine().lower() in ("x86_64", "amd64")
MEDIAPIPE = "mediapipe==0.10.21" if INTEL_MAC else "mediapipe==1.2.2"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fetch(url, dest):
    """url -> dest. curl first: a fetched Python may not find the system's certificates, curl always does"""
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-fsSL", "--retry", "2", "-o", dest, url])
        return r.returncode == 0
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except OSError:
        return False


def have(name):
    return os.path.exists(os.path.join(MODELS, name))


def path(name, quiet=False):
    """the model file in MODELS, downloaded and checked against its sha256 the first time. Exits with the fix when it
    can't be fetched (no network, or a file that doesn't match: never use a model we didn't pin)"""
    dest = os.path.join(MODELS, name)
    if os.path.exists(dest):
        return dest
    size, sources = MODEL[name]
    os.makedirs(MODELS, exist_ok=True)
    if not quiet:
        print(f"downloading {name} ({size / 1e6:.0f} MB, once) into {MODELS} ...", flush=True)
    tmp = dest + ".part"
    for url, want in sources:
        if _fetch(url, tmp) and os.path.exists(tmp):
            if sha256(tmp) == want:
                os.replace(tmp, dest)
                return dest
            print(f"  {url} didn't match its checksum, not using it", flush=True)
        if os.path.exists(tmp):
            os.remove(tmp)
    sys.exit(f"could not download {name}: check the internet connection and run it again "
             f"(or put the file at {dest}; its sha256 must be one of {[s for _, s in sources]})")


def mp_version():
    """the MediaPipe version in .venv-mp, or None when it isn't installed (or its Python is gone)"""
    if not os.path.exists(MP_PY):
        return None
    try:
        r = subprocess.run([MP_PY, "-c", "import mediapipe; print(mediapipe.__version__)"], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def mp_python(install=True):
    """the MediaPipe venv's python; with install, makes $REEL_KIT_HOME/.venv-mp first when it's missing or broken"""
    if mp_version():
        return MP_PY
    if not install:
        return None
    base = PY if os.path.exists(PY) else sys.executable          # the kit's own Python, like the main venv
    print(f"installing MediaPipe for tracking into {VENV_MP} ({MEDIAPIPE}, about 390 MB, 1 to 2 minutes, once) ...",
          flush=True)
    shutil.rmtree(VENV_MP, ignore_errors=True)
    r = subprocess.run([base, "-m", "venv", VENV_MP])
    if r.returncode == 0:
        subprocess.run([MP_PY, "-m", "pip", "install", "-q", "--upgrade", "pip"], capture_output=True)
        r = subprocess.run([MP_PY, "-m", "pip", "install", "-q", MEDIAPIPE], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1500:], flush=True)
    if not mp_version():
        sys.exit(f"MediaPipe didn't install into {VENV_MP}. Check the internet connection, then run "
                 f"`{base} {os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'setup', 'setup.py')} --track`")
    pth(MP_PY)
    return MP_PY


def pth(python):
    """put the kit's pipeline on a venv's import path (reel-kit.pth), so an effect's gen.py run with that Python can
    `import fxlib` from any folder. setup.py rewrites it on every run, so it follows the kit when it updates"""
    try:
        site = subprocess.run([python, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                              capture_output=True, text=True, check=True).stdout.strip()
        with open(os.path.join(site, "reel-kit.pth"), "w") as fh:
            fh.write(os.path.dirname(os.path.abspath(__file__)) + "\n")
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def du(folder):
    """bytes on disk under a folder"""
    total = 0
    for d, _, names in os.walk(folder):
        for n in names:
            p = os.path.join(d, n)
            if not os.path.islink(p):
                total += os.path.getsize(p)
    return total


if __name__ == "__main__":
    # PY pipeline/models.py [names...]: fetch and verify (all of them with no names)
    for n in sys.argv[1:] or MODEL:
        p = path(n)
        print(f"{n}  {os.path.getsize(p) / 1e6:.1f} MB  sha256 {sha256(p)}")
