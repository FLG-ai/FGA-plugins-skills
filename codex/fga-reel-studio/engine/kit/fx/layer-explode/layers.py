#!/usr/bin/env python3
"""layer-explode, step 1 of 4: the sheets that are files. With the plate tools' room (built from the empty-room stretch
the creator films) there is nothing to repair: the ROOM sheet is that room as a clip, and ME is public/subject.webm as
it is (gen.py points at it). Two room clips, at live levels so nothing pops while the speaker is flat on the room:

  room.mp4        room_<FRAME>.npy: the room as the take sees it
  room_empty.mp4  room_empty_<FRAME>.npy when the plate tools write one: the room with nothing moved back in (a chair
                  that swung when the speaker got up); the rig shows it once the sheets have separated

Without a room plate the room comes from the window's own frames (a locked-off shot): the patch the speaker always
covers is inpainted and shows as a smooth patch on the ROOM sheet once ME leaves it. Film the empty room instead.
A mic in the speaker's matte rides on the ME sheet (there is no separate MIC sheet), so nothing is ever doubled.

Run: PY fx/<id>/layers.py <project> [<id>]   -> work/fx/<id>/stage/<id>/; then gen.py, calib.py, prerender.py.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, W, H = 30, 1080, 1920
ROOM_LIFT = (0.0, 0.0, 0.0)          # levels added to the room sheet (R, G, B): calib.py prints what is left on the room after the LUT


def _pipeline():
    """the kit's pipeline on the import path: REEL_KIT, this folder's grandparent when it runs in the library, else
    PY's own (setup puts the pipeline on PY's import path)"""
    for c in (os.environ.get("REEL_KIT", ""), os.path.join(HERE, "..", "..")):
        p = os.path.join(c, "pipeline") if c else ""
        if p and os.path.exists(os.path.join(p, "fxlib.py")):
            sys.path.insert(0, os.path.abspath(p))
            return
    import importlib.util
    if importlib.util.find_spec("fxlib") is None:
        sys.exit("can't import the kit's fxlib: run this with the kit's PY (setup puts the pipeline on its path), or set REEL_KIT=<the kit folder>")


_pipeline()
import fxlib  # noqa: E402


def window(project, fid):
    """the effect's window (its edit.FX entry) and the crop the video is in there"""
    F = fxlib.entry(project, fid)
    A, B = float(F["at"]), float(F["end"])
    TL = json.load(open(os.path.join(project, "timeline.json")))
    if any(A + 0.5 / FPS < c < B - 0.5 / FPS for c in TL.get("picture_cuts", []) + TL.get("reframes", [])):
        sys.exit(f"{fid}: the window spans a picture change: the room only matches one framing. End it on the cut")
    return A, B, fxlib.crop_at(project, A)


def room_npy(project, frame, empty=False):
    """the room behind the speaker on this crop at live levels (plate_finish.py: work/c/room_<FRAME>.npy), or None"""
    p = os.path.join(project, "work", "c", f"room_{'empty_' if empty else ''}{frame}.npy")
    return fxlib.room(project, frame, empty=empty).astype(np.float32) if os.path.exists(p) else None


def plate_mode(project):
    """'empty' (the plate came from a real empty room), 'fallback' (the patch the speaker always covered is inpainted and
    shows once they move) or None (no plate tools run)"""
    p = os.path.join(project, "work", "plate", "plate.json")
    return json.load(open(p)).get("mode") if os.path.exists(p) else None


def room_from_window(project, A, B):
    """no plate: the window's frames, median where the speaker isn't, the always-covered patch inpainted"""
    import cv2
    stack, oks = [], []
    for k, ((_, rgb), (_, al)) in enumerate(zip(fxlib.frames(project, A, B), fxlib.alpha(project, A, B))):
        if k % 2:
            continue
        stack.append(rgb.astype(np.float32))
        oks.append(cv2.dilate((al > 8).astype(np.uint8), np.ones((31, 31), np.uint8)) == 0)
    stack, oks = np.stack(stack), np.stack(oks)
    cnt = oks.sum(axis=0)
    room = (stack * oks[..., None]).sum(axis=0) / np.maximum(cnt, 1)[..., None]
    hole = (cnt == 0).astype(np.uint8) * 255
    small = cv2.resize(np.clip(room, 0, 255).astype(np.uint8), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    fill = cv2.inpaint(small, cv2.resize(hole, (W // 4, H // 4), interpolation=cv2.INTER_NEAREST), 8, cv2.INPAINT_TELEA)
    fill = cv2.GaussianBlur(cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32), (0, 0), 6)
    a = cv2.GaussianBlur((hole > 0).astype(np.float32), (0, 0), 5)[..., None]
    return room * (1 - a) + fill * a


def write(im, path, n):
    w = fxlib.Writer(path, crf=12)
    u8 = np.clip(im + np.array(ROOM_LIFT, np.float32) + 0.5, 0, 255).astype(np.uint8)
    for _ in range(n):
        w.write(u8)
    w.close()
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("id", nargs="?", default=os.path.basename(HERE))
    args = ap.parse_args()
    project, fid = os.path.abspath(os.path.expanduser(args.project)), args.id
    A, B, frame = window(project, fid)
    stage = os.path.join(project, "work", "fx", fid, "stage", fid)
    os.makedirs(stage, exist_ok=True)
    n = fxlib.fr(B) - fxlib.fr(A) + 1
    room = room_npy(project, frame)
    if plate_mode(project) == "fallback":
        print("WARNING: this plate is the FALLBACK (no empty room was filmed): the patch the speaker always covered is "
              "inpainted, and the ROOM sheet shows it for the whole time ME is lifted off it (a smeared shape where they sat). "
              "Film 5 s of the empty room (edit.py EMPTY or EMPTY_CLIP) and rerun the plate tools for the real thing")
    if room is None:
        print(f"no room_{frame}.npy from the plate tools: the room comes from the window's frames (the patch behind the speaker is invented)")
        room = room_from_window(project, A, B)
    write(room, os.path.join(stage, "room.mp4"), n)
    empty = room_npy(project, frame, empty=True)
    old = os.path.join(stage, "room_empty.mp4")
    if empty is not None and float(np.abs(empty - room).max()) > 0.5:      # no empty room filmed: the two are the same file's worth
        write(empty, old, n)
    elif os.path.exists(old):
        os.remove(old)
    mic = os.path.join(project, "public", "plates", f"mic_{frame}.webm")
    if os.path.exists(mic):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", mic, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                             capture_output=True).stdout
        if len(raw) >= W * H * 4 and np.frombuffer(raw[:W * H * 4], np.uint8)[3::4].max() > 30:
            print("a mic layer: it stays on the ME sheet with the speaker (the matte has it), so the stack never shows two mics")


if __name__ == "__main__":
    main()
