#!/usr/bin/env python3
"""Transcribes the work folder's audio.wav with word timings, on this Mac, then writes the word files.
Usage: python3 transcribe.py <work folder> [--lang en]
Writes transcript.json (raw), words.json (the file the other skills read), sentences.txt and lines.txt (for reading)."""
import json, sys
from pathlib import Path

a = sys.argv[1:]
if not a: sys.exit(__doc__)
d = Path(a[0]).expanduser().resolve()
lang = a[a.index('--lang') + 1] if '--lang' in a else 'en'
from faster_whisper import WhisperModel
model = WhisperModel('small.en' if lang == 'en' else 'small', compute_type='int8')
# hand the model the audio itself (16 kHz mono floats). Giving it a file path makes faster-whisper open it with the av library, and
# the newest av versions break that call ("open() got an unexpected keyword argument 'metadata_errors'")
import shutil, subprocess
import numpy as np
FF = next(p for p in [shutil.which('ffmpeg'), '/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', str(Path.home() / '.local/bin/ffmpeg')] if p and Path(p).exists())
pcm = subprocess.run([FF, '-v', 'error', '-i', str(d / 'audio.wav'), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True, check=True).stdout
segs, _ = model.transcribe(np.frombuffer(pcm, np.float32), word_timestamps=True, vad_filter=False, language=lang)
raw = [{'start': s.start, 'end': s.end, 'text': s.text, 'words': [{'w': w.word.strip(), 's': w.start, 'e': w.end} for w in s.words]} for s in segs]
(d / 'transcript.json').write_text(json.dumps(raw))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordfiles import write_readables
words = []
for s in raw:
    first = len(words)
    for w in s['words']:
        t = w['w']
        if not t: continue
        # the model splits some tokens: "20" + ",000", "well" + "-known", "p" + ".m.". Join them back.
        if len(words) > first and (t.startswith('-') or t.startswith(',0') or t.startswith("'") or t.startswith('.')):
            words[-1]['t'] += t; words[-1]['e'] = round(w['e'], 3); continue
        words.append({'t': t, 's': round(w['s'], 3), 'e': round(w['e'], 3)})
for i, w in enumerate(words): w['i'] = i
(d / 'words.json').write_text(json.dumps(words, indent=0))
write_readables(d, words)
print(json.dumps({'words': len(words)}))
