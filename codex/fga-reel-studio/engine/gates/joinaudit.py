"""Every join of a reel-kit project: is the cut inside the voice? 5 ms energy at the out and in points (dB
re loud speech), plus a greedy wav2vec2 read of the last and first 0.7 s of the two pieces, to spot half words and
repeats.
Run: "$PY" joinaudit.py <project>
"""
import json, os, subprocess, sys, numpy as np, torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
P = os.path.expanduser(sys.argv[1])
TL = json.load(open(os.path.join(P, "timeline.json")))
src = [l for l in open(os.path.join(P, "edit.py")) if l.startswith("SRC")][0].split("=", 1)[1].strip().strip('"\'')
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-af", "highpass=f=80", "-f", "f32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(pcm, np.float32).copy()
hop = 80; n = len(x) // hop
e = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
db = 20 * np.log10(e / np.percentile(e, 99))
name = "facebook/wav2vec2-base-960h"
proc, model = Wav2Vec2Processor.from_pretrained(name), Wav2Vec2ForCTC.from_pretrained(name).eval()
inv = {v: k for k, v in proc.tokenizer.get_vocab().items()}
def read(a, b):
    seg = x[int(a * 16000):int(b * 16000)]
    if len(seg) < 1600: return ""
    with torch.inference_mode():
        ids = model(proc(seg, sampling_rate=16000, return_tensors="pt").input_values).logits[0].argmax(-1).numpy()
    out, prev = "", None
    for i in ids:
        if i != prev:
            ch = inv[int(i)]
            out += " " if ch == "|" else ("" if ch == "<pad>" else ch)
        prev = i
    return " ".join(out.split()).lower()
def peak(a, b):
    return float(db[int(a * 200):max(int(a * 200) + 1, int(b * 200))].max())
K = TL["keep"]
for k in range(len(K) - 1):
    o, i = K[k]["src_out"], K[k + 1]["src_in"]
    eo = peak(o - 0.035, o)            # inside the 30 ms fade-out
    ei = peak(i, i + 0.025)            # inside the 20 ms fade-in
    flag = ("OUT-IN-VOICE " if eo > -30 else "") + ("IN-IN-VOICE " if ei > -30 else "")
    print(f"join {k:2d} out {K[k + 1]['out']:6.2f}  src {o:7.3f}|{i:7.3f}  end {eo:4.0f} dB  start {ei:4.0f} dB  {flag}")
    print(f"      ...{read(max(K[k]['src_in'], o - 0.8), o)!r}  |  {read(i, min(K[k + 1]['src_out'], i + 0.8))!r}...")
