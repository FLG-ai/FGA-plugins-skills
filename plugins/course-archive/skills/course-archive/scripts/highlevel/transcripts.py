"""Transcripts for a HighLevel course built by build.py.

Usage: transcripts.py "<course dir>" [--only-captions]
Captions first: the lesson's .srt on cdn.courses.apisystem.tech (public, no login;
the metaData key can say "ar" while the file is English, check the "-en-" in the name).
Otherwise local faster-whisper small.en int8 on the downloaded _videos/<stem>.mp4,
or the public video URL if the download is not there yet. Skips done transcripts.
"""
import json, os, re, shutil, subprocess, sys, tempfile, urllib.request

d = sys.argv[1]
only_caps = '--only-captions' in sys.argv
rev = '--reverse' in sys.argv  # run a second worker from the other end
# HighLevel .srt files are often Zoom captions cut to the first line of each cue.
# --redo-captions re-transcribes those lessons with Whisper from the downloaded video.
redo = '--redo-captions' in sys.argv
m = json.load(open(os.path.join(d, '_manifest.json')))
os.makedirs(os.path.join(d, '_transcripts'), exist_ok=True)


def prose(lines):
    t = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    return re.sub(r'(?<=[.!?]) (?=[A-Z])', '\n\n', t)


def srt(url):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh) Chrome/140.0'}), timeout=120).read().decode('utf-8', 'replace')
    out = [l.strip() for l in raw.splitlines()
           if l.strip() and '-->' not in l and not l.strip().isdigit()]
    return prose(out)


_model = None


def whisper(src):
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel('small.en', device='cpu', compute_type='int8')
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, 'a.wav')
    try:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
        segs, _ = _model.transcribe(wav, beam_size=1, vad_filter=True)
        return prose([s.text.strip() for s in segs])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


for x in (m[::-1] if rev else m):
    if not x['video']:
        continue
    out = os.path.join(d, '_transcripts', x['stem'] + '.md')
    if os.path.exists(out + '.lock'):
        continue
    if os.path.exists(out) and not (redo and 'From the platform captions.' in open(out).read()):
        continue
    auto = redo or not x['subtitles']
    if auto and only_caps:
        continue
    if not auto:
        text = srt(next(iter(x['subtitles'].values())))
    else:
        local = os.path.join(d, '_videos', x['stem'] + '.mp4')
        src = local if os.path.exists(local) else x['video']
        print('transcribing locally:', x['stem'], flush=True)
        open(out + '.lock', 'w').close()
        try:
            text = whisper(src)
        finally:
            os.remove(out + '.lock')
    note = 'Auto-transcribed locally with Whisper (no captions on the platform).' if auto else 'From the platform captions.'
    open(out, 'w').write(f"# {x['title']} (transcript)\n\nSection: {x['section']}\n{note}\n\n{text}\n")
    cur = json.load(open(os.path.join(d, '_manifest.json')))
    for y in cur:
        if y['stem'] == x['stem']:
            y['transcript'] = f"_transcripts/{x['stem']}.md"; y['auto'] = auto
    json.dump(cur, open(os.path.join(d, '_manifest.json'), 'w'), indent=1)
    print('done', x['stem'], len(text.split()), 'words', flush=True)
