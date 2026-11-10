#!/usr/bin/env python3
"""Track: where the speaker's head, mouth, hands and shoulders are on every frame of clean.mp4, so graphics can lock to
the body.
-> <project>/work/tracks/track.json {fps, frames: [...]}, one entry per video frame, all in video pixels (the canvas
   clean.mp4 was cut to):
   face: {cx, cy, w, h, top, chin, roll, yaw, pitch, mouth:[x, y], open, eyes:[[x,y],[x,y]], forehead:[x,y], nose:[x,y]} or null
   hands: [{side, wrist, palm, thumb, index, middle, pinky, pinch, span}] (0, 1 or 2)
   pose: {ls, rs, le, re, lw, rw} shoulders, elbows, wrists or null
Coordinates are smoothed over 5 frames (centred), never across a picture cut or reframe.
MediaPipe pins its own numpy and OpenCV, so it runs in its own venv ($REEL_KIT_HOME/.venv-mp). Run it with PY like
everything else: the first run makes that venv (about 390 MB, 1 to 2 minutes) and fetches the three models (21 MB,
checked against their sha256), then hands over to it. About 1 minute per 30 seconds of video on a laptop.
Run: PY pipeline/track.py <project>
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402

FPS = 30


def face_options(vision, BaseOptions):
    return vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=models.path("face_landmarker.task")),
                                        running_mode=vision.RunningMode.VIDEO, num_faces=1, output_facial_transformation_matrixes=True)


def hand_options(vision, BaseOptions):
    return vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=models.path("hand_landmarker.task")),
                                        running_mode=vision.RunningMode.VIDEO, num_hands=2, min_hand_detection_confidence=0.4,
                                        min_tracking_confidence=0.4)


def pose_options(vision, BaseOptions):
    return vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=models.path("pose_landmarker_full.task")),
                                        running_mode=vision.RunningMode.VIDEO, num_poses=1)


def face_entry(lm, mat, W, H):
    import numpy as np
    P = lambda i: [lm[i].x * W, lm[i].y * H]          # noqa: E731
    xs, ys = [p.x * W for p in lm], [p.y * H for p in lm]
    le, re = P(33), P(263)
    roll = math.degrees(math.atan2(re[1] - le[1], re[0] - le[0]))
    yaw = pitch = 0.0
    if mat is not None:
        R = np.array(mat)[:3, :3]
        yaw = math.degrees(math.atan2(R[0, 2], R[2, 2]))
        pitch = math.degrees(math.asin(max(-1, min(1, -R[1, 2]))))
    up, lo = P(13), P(14)
    return dict(cx=(min(xs) + max(xs)) / 2, cy=(min(ys) + max(ys)) / 2, w=max(xs) - min(xs), h=max(ys) - min(ys),
                top=min(ys), chin=P(152)[1], roll=roll, yaw=yaw, pitch=pitch, mouth=[(up[0] + lo[0]) / 2, (up[1] + lo[1]) / 2],
                open=math.hypot(up[0] - lo[0], up[1] - lo[1]), eyes=[P(468) if len(lm) > 468 else le, P(473) if len(lm) > 473 else re],
                forehead=P(10), nose=P(1))


def hand_entry(lm, side, W, H):
    P = lambda i: [lm[i].x * W, lm[i].y * H]          # noqa: E731
    palm = [sum(lm[i].x for i in (0, 5, 17)) / 3 * W, sum(lm[i].y for i in (0, 5, 17)) / 3 * H]
    th, ix = P(4), P(8)
    return dict(side=side, wrist=P(0), palm=palm, thumb=th, index=ix, middle=P(12), pinky=P(20), pinch=math.hypot(th[0] - ix[0], th[1] - ix[1]),
                span=math.hypot(P(5)[0] - P(17)[0], P(5)[1] - P(17)[1]))


def smooth(entries, cuts, keys):
    """centred 5-frame mean on the listed numeric keys, never across a picture cut"""
    import numpy as np
    n = len(entries)
    seg = np.zeros(n, int)
    for c in cuts:
        seg[round(c * FPS):] += 1
    out = [dict(e) if e else None for e in entries]
    for i, e in enumerate(entries):
        if not e:
            continue
        idx = [j for j in range(max(0, i - 2), min(n, i + 3)) if entries[j] and seg[j] == seg[i]]
        for k in keys:
            v = e[k]
            if isinstance(v, list) and v and isinstance(v[0], list):
                out[i][k] = [[float(np.mean([entries[j][k][m][d] for j in idx])) for d in (0, 1)] for m in range(len(v))]
            elif isinstance(v, list):
                out[i][k] = [float(np.mean([entries[j][k][d] for j in idx])) for d in range(len(v))]
            else:
                out[i][k] = float(np.mean([entries[j][k] for j in idx]))
    return out


def handover():
    """this Python has no MediaPipe (the kit's main venv never does): run this same script in .venv-mp, making it first"""
    mp_py = models.mp_python()
    for n in models.TRACK_MODELS:                    # fetched here so a failed download says so before any frames run
        models.path(n)
    sys.exit(subprocess.run([mp_py, os.path.abspath(__file__)] + sys.argv[1:]).returncode)


def main():
    if len(sys.argv) < 2 or not os.path.isdir(os.path.expanduser(sys.argv[1])):
        sys.exit(__doc__)
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
    except ImportError:
        return handover()
    import numpy as np
    project = os.path.abspath(os.path.expanduser(sys.argv[1]))
    src = os.path.join(project, "public", "clean.mp4")
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src],
                         capture_output=True, text=True, check=True).stdout.strip()
    W, H = (int(v) for v in out.split(",")[:2])          # the video's own canvas (1080x1920)
    S = 0.5                                             # detect at half size
    w, h = int(W * S), int(H * S)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    fl = vision.FaceLandmarker.create_from_options(face_options(vision, BaseOptions))
    hl = vision.HandLandmarker.create_from_options(hand_options(vision, BaseOptions))
    pl = vision.PoseLandmarker.create_from_options(pose_options(vision, BaseOptions))
    faces, hands, poses, n = [], [], [], 0
    while True:
        buf = dec.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        im = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.frombuffer(buf, np.uint8).reshape(h, w, 3))
        ms = int(n * 1000 / FPS)
        r = fl.detect_for_video(im, ms)
        faces.append(face_entry(r.face_landmarks[0], r.facial_transformation_matrixes[0] if r.facial_transformation_matrixes else None, W, H) if r.face_landmarks else None)
        r = hl.detect_for_video(im, ms)
        hands.append([hand_entry(lm, hd[0].category_name, W, H) for lm, hd in zip(r.hand_landmarks, r.handedness)])
        r = pl.detect_for_video(im, ms)
        if r.pose_landmarks:
            lm = r.pose_landmarks[0]
            P = lambda i: [lm[i].x * W, lm[i].y * H]      # noqa: E731
            poses.append(dict(ls=P(11), rs=P(12), le=P(13), re=P(14), lw=P(15), rw=P(16)))
        else:
            poses.append(None)
        n += 1
        if n % 300 == 0:
            print(f"  {n} frames", flush=True)
    tl = json.load(open(os.path.join(project, "timeline.json")))
    cuts = tl["picture_cuts"] + tl["reframes"]
    faces = smooth(faces, cuts, ["cx", "cy", "w", "h", "top", "chin", "roll", "yaw", "pitch", "mouth", "open", "eyes", "forehead", "nose"])
    poses = smooth(poses, cuts, ["ls", "rs", "le", "re", "lw", "rw"])
    out = [dict(face=f, hands=hd, pose=p) for f, hd, p in zip(faces, hands, poses)]
    os.makedirs(os.path.join(project, "work", "tracks"), exist_ok=True)
    json.dump(dict(fps=FPS, frames=out), open(os.path.join(project, "work", "tracks", "track.json"), "w"))
    print(f"track: {n} frames, face on {sum(1 for f in faces if f)}, hands on {sum(1 for h in hands if h)} "
          f"-> {os.path.join(project, 'work', 'tracks', 'track.json')}")


if __name__ == "__main__":
    main()
