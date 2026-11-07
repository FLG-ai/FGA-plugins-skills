"""faster-whisper small.en word timestamps and confidence for the given ranges of a clip (no prompt). A quick second
opinion on a word the first transcript got wrong.
Run: "$PY" fw.py <clip> <from-to> [<from-to> ...]
"""
import subprocess, sys, numpy as np
from faster_whisper import WhisperModel
src = sys.argv[1]
m = WhisperModel("small.en", device="cpu", compute_type="int8")
for rng in sys.argv[2:]:
    a, b = map(float, rng.split("-"))
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-to", str(b), "-i", src, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    segs, _ = m.transcribe(np.frombuffer(pcm, np.float32), language="en", word_timestamps=True, beam_size=5, vad_filter=False, condition_on_previous_text=False)
    print(f"== src {a}-{b}")
    for s in segs:
        for w in s.words or []:
            print(f"  {a + w.start:7.3f} {a + w.end:7.3f}  {w.word.strip()}  p={w.probability:.2f}")
