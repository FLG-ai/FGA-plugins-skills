#!/usr/bin/env python3
"""Words: per-range word timings with faster-whisper (word timestamps), mapped onto the output timeline.

Each kept range is transcribed on its own so word times stay honest across the cuts. edit.PROMPT should name the
people, products and numbers in the script; edit.FIXES maps known mishearings to the real word.
Writes <project>/words.json: [{text, start, end, src}] (start/end on the output timeline, src = source time).
Run: PY pipeline/words.py <project>
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_edit, project_arg  # noqa: E402
from cut import plan  # noqa: E402


def main():
    project = project_arg()
    E = load_edit(project)
    from faster_whisper import WhisperModel
    segs, _ = plan(E)
    work = os.path.join(project, "work", "whisper")
    os.makedirs(work, exist_ok=True)
    cache_path = os.path.join(work, "fw_ranges.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    model, words = None, []
    for g in segs:
        key = f"{g['s']}-{g['e']}"
        if key not in cache:
            if model is None:
                print("transcribing with Whisper medium (the very first run downloads it, about 1.5 GB) ...", flush=True)
                model = WhisperModel("medium", compute_type="int8")
            wav = os.path.join(work, "range.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{g['s']:.3f}", "-to", f"{g['e']:.3f}", "-i", E.SRC,
                            "-ar", "16000", "-ac", "1", wav], check=True)
            sr, pcm = wavfile.read(wav)                   # samples, not a path: av 19 broke faster-whisper's decoder
            out, _ = model.transcribe(pcm.astype(np.float32) / 32768.0, language="en", word_timestamps=True, vad_filter=False,
                                      initial_prompt=E.PROMPT or None, condition_on_previous_text=False)
            ws = []
            for s in out:
                for w in s.words:
                    t = w.word.strip()
                    if ws and t[:1] in "-." and len(t) > 1 and t[1:2].isdigit():      # "1" + ".6%" -> "1.6%"
                        ws[-1][2] += t
                        ws[-1][1] = round(w.end, 3)
                        continue
                    ws.append([round(w.start, 3), round(w.end, 3), t])
            cache[key] = ws
            json.dump(cache, open(cache_path, "w"), indent=1)
        for a, b, t in cache[key]:
            words.append({"text": E.FIXES.get(t, t), "start": round(a + g["out"], 3),
                          "end": round(min(b, g["e"] - g["s"]) + g["out"], 3), "src": round(a + g["s"], 3)})
    json.dump(words, open(os.path.join(project, "words.json"), "w"), indent=1)
    print(" ".join(f"{w['text']}@{w['start']:.2f}" for w in words))


if __name__ == "__main__":
    main()
