"""Frame I/O and helpers for pre-rendered effects (fx/<id>/gen.py): read a window of the video's footage or matte as
numpy arrays, write it back as a clip the composition can seek frame by frame, and read the creator's look. A
pre-rendered effect replaces the footage for a window with a clip whose frame n is the same moment as frame n of
clean.mp4, so the speaker's lips stay in sync.

  for i, rgb in fxlib.frames(P, a, b): ...           rgb uint8 HxWx3, i = video frame index (round(t * 30))
  for i, al in fxlib.alpha(P, a, b): ...             al uint8 HxW, from subject.webm
  for i, px in fxlib.rgba(P, a, b): ...              the cutout itself, uint8 HxWx4
  w = fxlib.Writer(path); w.write(rgb); w.close()    all-intra H.264 (every frame seekable), or alpha=True for VP9 + alpha
  fxlib.tag(id, src, a, b, cls, track)               the <video> tag that plays a clip made for window a..b
  fxlib.scene(prefix, a, b, frame)                   the room as layers: plate, desk, the speaker, mic (plate_finish.py)
  fxlib.tracks(P)                                    work/tracks/track.json (track.py)
  fxlib.room(P, frame[, empty=True])                 the room behind the speaker at live levels (plate_finish.py)
  fxlib.crop_at(P, t)                                which FRAMES crop the video is in at t ("WIDE", "CLOSE"...)
  fxlib.entry(P, id), fxlib.word_at(P, text, after)  an effect's edit.FX entry (end resolved), a word's start time
  S = fxlib.pack(P); fxlib.font(P, role, size)       the creator's colours, fonts and name (the project's style pack)
  fxlib.headshot(P)                                  the creator's photo (assets/, the pack, or None: draw a placeholder)
Run it with PY: setup puts the kit's pipeline on PY's import path, so a gen.py in <project>/fx/<id>/ can `import fxlib`.
"""
import functools
import json
import os
import re
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from common import HOME  # noqa: E402  (importing common puts the kit's own ffmpeg first on PATH, even from a gen.py)

FPS = 30


def fr(t):
    return round(t * FPS)


def size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
    return tuple(int(v) for v in out.split(",")[:2])


# without this the default conversion lands about 2 levels dark, which shows at a seam in a dark room (measured in a render)
ACCURATE = "scale=in_color_matrix=bt709:in_range=tv:out_range=pc:flags=accurate_rnd+full_chroma_int+bitexact"


def _pipe(path, a, b, pix, dec=()):
    n0, n1 = fr(a), max(fr(b), fr(a) + 1)
    W, H = size(path)
    vf = ["-vf", ACCURATE] if pix == "rgb24" else []
    cmd = ["ffmpeg", "-v", "error", *dec, "-ss", f"{max(0, n0 - 0.34) / FPS:.4f}", "-i", path, "-frames:v", str(n1 - n0), *vf,
           "-f", "rawvideo", "-pix_fmt", pix, "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return p, n0, n1, W, H


def _read(p, n0, n1, W, H, ch):
    """frames off an ffmpeg pipe; a caller that stops early (next(frames(...))) ends ffmpeg quietly"""
    try:
        for i in range(n0, n1):
            buf = p.stdout.read(W * H * ch)
            if len(buf) < W * H * ch:
                break
            yield i, np.frombuffer(buf, np.uint8).reshape(H, W, ch)
    finally:
        if p.poll() is None:
            p.kill()
        p.stdout.close()
        p.wait()


def frames(project, a, b, src="public/clean.mp4"):
    """(i, rgb) for every frame of a..b of a clip in the project (clean.mp4 by default), i = round(t * 30) in that clip"""
    p, n0, n1, W, H = _pipe(os.path.join(project, src), a, b, "rgb24")
    yield from _read(p, n0, n1, W, H, 3)


def alpha(project, a, b, src="public/subject.webm"):
    p, n0, n1, W, H = _pipe(os.path.join(project, src), a, b, "rgba", dec=("-c:v", "libvpx-vp9"))
    for i, px in _read(p, n0, n1, W, H, 4):
        yield i, px[:, :, 3]


def rgba(project, a, b, src="public/subject.webm"):
    p, n0, n1, W, H = _pipe(os.path.join(project, src), a, b, "rgba", dec=("-c:v", "libvpx-vp9"))
    yield from _read(p, n0, n1, W, H, 4)


# the way back from frames() levels to the video's: both codecs, so a clip that takes over from the live picture lands
# at the same levels (untagged VP9 went through the default conversion and came out a level or three off in blue)
ENCODE = ["-vf", "scale=out_color_matrix=bt709:out_range=tv:in_range=pc:flags=accurate_rnd+full_chroma_int+bitexact",
          "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]


class Writer:
    """an all-intra clip: every frame a keyframe, so the renderer's seeks land exactly. alpha=True: VP9 + alpha (.webm)"""

    def __init__(self, path, w=1080, h=1920, alpha=False, crf=None):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.alpha = alpha
        pix = "rgba" if alpha else "rgb24"
        codec = (["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", str(crf or 18), "-row-mt", "1",
                  "-deadline", "good", "-cpu-used", "2", "-auto-alt-ref", "0", "-g", "1", *ENCODE] if alpha else
                 ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf or 14), "-pix_fmt", "yuv420p", "-g", "1",
                  *ENCODE, "-movflags", "+faststart"])
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{w}x{h}",
                                   "-r", str(FPS), "-i", "-", *codec, path], stdin=subprocess.PIPE)

    def write(self, a):
        self.p.stdin.write(np.asarray(a, np.uint8).tobytes())

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def clip_start(t):
    return max(0.0, fr(t) / FPS - 0.002)


def tag(tag_id, src, a, b, cls="", track="{{T0}}", style=""):
    """<video> for a clip that was pre-rendered for window a..b (its frame 0 is video frame round(a*30))"""
    d = (fr(b) - fr(a)) / FPS
    return (f'<video id="{tag_id}" class="{cls}" src="{src}" muted playsinline data-start="{clip_start(a):.4f}" '
            f'data-media-start="0.0010" data-duration="{d:.4f}" data-track-index="{track}" style="{style}"></video>')


def scene(prefix, a, b, frame, parts=("plate", "desk", "subject", "mic"), tracks="T0 T1 T2 T3 T4 T5 T6 T7 T8 T9".split(), style="position:absolute;left:0;top:0;width:1080px;height:1920px;"):
    """the room as separate layers for window a..b, in stack order, one <video> per part (ids <prefix>-plate, <prefix>-desk,
    <prefix>-subject, <prefix>-mic). Put these in a cam FX and move any of them with GSAP. frame = the FRAMES crop the
    video is in at a (crop_at). Every layer is colour matched to clean.mp4: on its own this stack looks exactly like
    the live shot. A shoot with no desk or mic in front of the speaker has empty (transparent) desk and mic layers."""
    out = []
    d = (fr(b) - fr(a)) / FPS
    for k, part in enumerate(parts):
        if part == "subject":
            src, ms = "subject.webm", fr(a) / FPS + 0.001
        else:
            src, ms = f"plates/{part}_{frame}." + ("mp4" if part == "plate" else "webm"), 0.001
        out.append(f'<video id="{prefix}-{part}" class="g" src="{src}" muted playsinline data-start="{clip_start(a):.4f}" data-media-start="{ms:.4f}" '
                   f'data-duration="{d:.4f}" data-track-index="{{{{{tracks[k]}}}}}" style="{style}"></video>')
    return "\n".join(out)


def tracks(project):
    """work/tracks/track.json from pipeline/track.py: per-frame head, mouth, hands, shoulders on the video's own frame"""
    path = os.path.join(project, "work", "tracks", "track.json")
    if not os.path.exists(path):
        sys.exit(f"no {path}: run PY {os.path.join(_HERE, 'track.py')} {project} first")
    return json.load(open(path))


# ------------------------------------------------------------------ the room (plate.py + plate_finish.py)
def room(project, frame, empty=False):
    """float32 HxWx3 RGB at live levels (what frames() gives for clean.mp4): the room behind the speaker in this crop.
    empty=False: the room as the take saw it, the empty room only where the speaker always sat (they're in place:
    it can't pop against the live shot). empty=True: the empty room alone (they've left or moved off their spot).
    Without an empty-room stretch the two are the same, and the patch the speaker always covered is filled."""
    name = f"room_empty_{frame}.npy" if empty else f"room_{frame}.npy"
    path = os.path.join(project, "work", "c", name)
    if not os.path.exists(path):
        sys.exit(f"no {path}: this effect needs the room. On a locked-off shot run PY {os.path.join(_HERE, 'plate.py')} "
                 f"{project}, then plate_finish.py (edit.py EMPTY or EMPTY_CLIP: the empty room)")
    return np.load(path)


def crop_at(project, t):
    """the FRAMES crop the video is in at output time t (timeline.json shots)"""
    shots = json.load(open(os.path.join(project, "timeline.json")))["shots"]
    return [s["frame"] for s in shots if s["t"] <= t + 1e-6][-1] if shots else "WIDE"


# ------------------------------------------------------------------ the edit: an effect's window and the words
def entry(project, fid):
    """edit.FX entry `fid` as a dict, with "end" resolved to seconds ("end" = when the last thing on screen ends)"""
    from common import load_edit, timeline
    E = load_edit(project)
    for F in getattr(E, "FX", []):
        if F["id"] == fid:
            F = dict(F)
            if F.get("end") == "end":
                TL = timeline(project)
                F["end"] = round(TL["total_audio"] * FPS) / FPS if E.END_CARD else TL["total"]
            return F
    sys.exit(f"no FX entry with id {fid!r} in {project}/edit.py")


def words(project):
    """words.json on the output timeline: [(start, end, text)]"""
    return [(w["start"], w["end"], w["text"]) for w in json.load(open(os.path.join(project, "words.json")))]


def _norm(text):
    return re.sub(r"[^a-z0-9%$']", "", str(text).lower())


def word_at(project, text, after=0.0):
    """the start of the first word matching `text` at or after `after` (like wordAt in fx.js), or None"""
    want = _norm(text)
    for a, _, w in words(project):
        if a >= after - 0.001 and _norm(w) == want:
            return a
    return None


# ------------------------------------------------------------------ the creator's look (the project's style pack)
def headshot(project):
    """the creator's photo: <project>/assets/headshot.*, then the project's pack (style/headshot.*), then the creator's
    current pack ($REEL_KIT_HOME/style/headshot.*); None when there is none (draw a placeholder)"""
    for d in (os.path.join(project, "assets"), os.path.join(project, "style"), os.path.join(HOME, "style")):
        for x in ("jpg", "jpeg", "png", "webp"):
            if os.path.exists(os.path.join(d, f"headshot.{x}")):
                return os.path.join(d, f"headshot.{x}")
    return None


_NAMED = {"white": "#FFFFFF", "black": "#000000", "transparent": "rgba(0,0,0,0)"}


def colour(c):
    """'#RGB', '#RRGGBB', '#RRGGBBAA', 'rgb(r,g,b)' or 'rgba(r,g,b,a)' -> (r, g, b, a) ints 0-255"""
    c = _NAMED.get(str(c).strip().lower(), str(c).strip())
    if c.startswith("#"):
        h = c[1:]
        h = "".join(ch * 2 for ch in h) if len(h) in (3, 4) else h
        v = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
        return tuple(v + [255]) if len(v) == 3 else tuple(v[:4])
    m = re.match(r"rgba?\(([^)]*)\)", c)
    if not m:
        raise ValueError(f"colour not understood: {c} (use #RRGGBB or rgba(r,g,b,a))")
    parts = [x for x in re.split(r"[\s,/]+", m.group(1)) if x]
    rgb = [round(float(x[:-1]) * 2.55) if x.endswith("%") else round(float(x)) for x in parts[:3]]
    a = parts[3] if len(parts) > 3 else "1"
    a = float(a[:-1]) / 100 if a.endswith("%") else float(a)
    return tuple(max(0, min(255, v)) for v in rgb) + (max(0, min(255, round(a * 255))),)


def _style_json(project):
    local = os.path.join(project, "style", "style.json")
    return local if os.path.exists(local) else None             # else the creator's current pack, like build.py


def _font_dirs(project):
    return [os.path.join(project, "style", "fonts"), os.path.join(HOME, "style", "fonts")]


def _font_file(dirs, family, weight, italic):
    """the pack's TTF for this family (style.py names them <Family>-<normal|italic>-<weight>.ttf): the right style
    first (a missing italic falls back to upright), then the nearest weight that exists"""
    stem = re.escape(family.replace(" ", ""))
    for d in dirs:
        if not os.path.isdir(d):
            continue
        best = None
        for f in os.listdir(d):
            m = re.match(rf"{stem}-(normal|italic)-(\d+)\.ttf$", f)
            if m:
                w = int(m.group(2))
                score = ((m.group(1) == "italic") != bool(italic), abs(w - int(weight)), w < int(weight))
                if best is None or score < best[0]:
                    best = (score, os.path.join(d, f))
        if best:
            return best[1]
    return None


@functools.lru_cache(maxsize=None)
def _pack(project):
    import style as ST
    S = ST.load(_style_json(project))
    out = {k: v for k, v in S.items() if k not in ("colors", "fonts", "creator", "_path")}
    out["colors"] = {k: ([colour(x) for x in v] if isinstance(v, list) else colour(v)) for k, v in S["colors"].items()}
    cr = S.get("creator") or {}
    out["creator"] = {k: str(cr.get(k) or "") for k in ("name", "handle", "site")}
    dirs = _font_dirs(project)
    fonts = {}
    for role, f in S["fonts"].items():
        path = _font_file(dirs, f["family"], f.get("weight", 400), f.get("italic", False))
        if path is None:                     # a project made without its fonts: fetch the pack's once (Google Fonts)
            try:
                ST.font_faces(S, dirs[0])
            except Exception as e:           # offline: font() falls back to a plain face and says so
                print(f"fxlib: could not fetch the pack's fonts ({e})", file=sys.stderr)
            path = _font_file(dirs, f["family"], f.get("weight", 400), f.get("italic", False))
        fonts[role] = dict(f, path=path)
    out["fonts"] = fonts
    out["_path"] = S.get("_path")
    return out


def pack(project):
    """the project's style pack: <project>/style/style.json over the kit default (style.DEFAULT).
    S["colors"][role] (r, g, b, a) ints 0-255 (series: a list of them); S["creator"] {"name", "handle", "site"};
    S["fonts"][role] the pack's font entry plus "path", its TTF in <project>/style/fonts/ (None if there is none)"""
    return _pack(os.path.abspath(os.path.expanduser(project)))


@functools.lru_cache(maxsize=None)
def _font(project, role, size):
    from PIL import ImageFont
    f = pack(project)["fonts"][role]
    if not f.get("path"):
        print(f"fxlib: no font file for {f['family']} ({role}): using a plain face", file=sys.stderr)
        try:
            return ImageFont.load_default(size=size)
        except TypeError:                    # Pillow before 10.1
            return ImageFont.load_default()
    font = ImageFont.truetype(f["path"], size)
    try:                                     # a variable font: set its weight axis to the pack's weight
        axes = font.get_variation_axes()
        names = [a.get("name", b"") for a in axes]
        names = [(n.decode() if isinstance(n, bytes) else str(n)).lower() for n in names]
        font.set_variation_by_axes([f.get("weight", 400) if n == "weight" else a.get("default", 0)
                                    for n, a in zip(names, axes)])
    except Exception:                        # a static file (the usual case): nothing to set
        pass
    return font


def font(project, role, size):
    """PIL ImageFont for display | text | mono | caption at the pack's weight (and italic, when the pack has one)"""
    return _font(os.path.abspath(os.path.expanduser(project)), role, int(size))
