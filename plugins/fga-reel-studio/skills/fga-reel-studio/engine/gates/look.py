"""For each range: greedy CTC words with times, and a 10 ms energy strip with a time ruler (digits = -dB/10).
Use it to hear where a word really starts and ends before moving a cut.
Run: "$PY" look.py <source clip> <from-to> [<from-to> ...]
"""
import subprocess, sys, numpy as np, torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
src = sys.argv[1]
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-af", "highpass=f=80", "-f", "f32le", "-"], capture_output=True, check=True).stdout
X = np.frombuffer(pcm, np.float32).copy()
hop = 160; n = len(X) // hop
e = np.sqrt(np.mean(X[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
DB = 20 * np.log10(e / np.percentile(e, 99))
name = "facebook/wav2vec2-base-960h"
proc, model = Wav2Vec2Processor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval()
inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
for rng in sys.argv[2:]:
    a, b = map(float, rng.split("-"))
    a0 = max(0.0, a - 1); seg = X[int(a0 * 16000):int((b + 1) * 16000)]
    with torch.inference_mode():
        ids = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values).logits[0].argmax(-1).numpy()
    fr = len(seg) / 16000 / len(ids)
    ws, cur, t0, last, prev = [], "", 0, 0, None
    for t, i in enumerate(ids):
        ch = inv[int(i)]
        if i != prev and ch != "<pad>":
            if ch == "|":
                if cur: ws.append((cur, a0 + t0 * fr, a0 + (last + 1) * fr))
                cur = ""
            else:
                if not cur: t0 = t
                cur += ch
        if ch not in ("<pad>", "|"): last = t
        prev = i
    if cur: ws.append((cur, a0 + t0 * fr, a0 + (last + 1) * fr))
    print(f"== {a}-{b}: " + "  ".join(f"{w}[{s:.2f}-{e2:.2f}]" for w, s, e2 in ws if e2 > a - 0.2 and s < b + 0.2))
    i0, i1 = int(a * 100), int(b * 100)
    strip = "".join(str(min(9, int(-DB[i] // 6))) for i in range(i0, i1))   # 0 = loud ... 6 = -36 dB ... 9 quiet
    for r in range(0, len(strip), 50):
        print(f"   {a + r / 100:6.2f} {strip[r:r + 50]}")
