"""5 ms energy of a clip in dB re loud speech, for the given ranges. Use it to see whether a cut point sits in the
room tone or inside a word.
Run: python3 env.py <clip> <from-to> [<from-to> ...]
"""
import subprocess, sys, numpy as np
src = sys.argv[1]
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", "-af", "highpass=f=80", "-f", "f32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(pcm, np.float32)
hop = 80  # 5 ms
n = len(x) // hop
e = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
ref = np.percentile(e, 99)
db = 20 * np.log10(e / ref)
for rng in sys.argv[2:]:
    a, b = map(float, rng.split("-"))
    i0, i1 = int(a * 200), int(b * 200)
    print(f"== {a}-{b}  (5 ms steps, dB re loud speech)")
    for i in range(i0, i1, 10):
        print(f"  {i / 200:6.3f} " + " ".join(f"{d:4.0f}" for d in db[i:min(i + 10, i1)]))
