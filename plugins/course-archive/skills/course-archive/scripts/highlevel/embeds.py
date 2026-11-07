"""Download videos embedded in HighLevel lesson bodies (Vimeo iframes, filesafe.space
<video> tags) and turn their captions into transcripts.

Usage: embeds.py "<course dir>" <portal origin, e.g. https://my.funnelgorgeous.com/>
Vimeo embeds need the portal as Referer. Takes 720p (no re-encode) and the
en-x-autogen VTT. Direct .mp4 embeds get curl, then local Whisper if no captions.
Rewrites each "▶ Embedded video: <url>" line in the lesson file to point at the
local copy and transcript. Safe to re-run.
"""
import glob, json, os, re, subprocess, sys

d, ref = sys.argv[1], sys.argv[2]
# --no-whisper: skip local transcription when the lesson already has transcript PDFs
no_whisper = '--no-whisper' in sys.argv
m = json.load(open(os.path.join(d, '_manifest.json')))
V, T = os.path.join(d, '_videos'), os.path.join(d, '_transcripts')
os.makedirs(V, exist_ok=True); os.makedirs(T, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def prose(lines):
    t = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    return re.sub(r'(?<=[.!?]) (?=[A-Z])', '\n\n', t)


def vtt_text(path):
    out = []
    for l in open(path, encoding='utf-8', errors='replace'):
        l = re.sub(r'<[^>]+>', '', l.strip())
        if not l or '-->' in l or l.isdigit() or l.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')):
            continue
        if not out or out[-1] != l:
            out.append(l)
    return prose(out)


def whisper(path):
    import shutil, tempfile
    from faster_whisper import WhisperModel
    global _wm
    if '_wm' not in globals():
        _wm = WhisperModel('small.en', device='cpu', compute_type='int8')
    tmp = tempfile.mkdtemp(); wav = os.path.join(tmp, 'a.wav')
    try:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
        segs, _ = _wm.transcribe(wav, beam_size=1, vad_filter=True)
        return prose([s.text.strip() for s in segs])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


for x in m:
    embeds = [e for e in x.get('embeds', []) if 'vimeo.com' in e or re.search(r'\.(mp4|mov|m4v)(\?|$)', e)]
    if not embeds:
        continue
    lesson = os.path.join(d, x['stem'] + '.md')
    s = open(lesson).read()
    for i, url in enumerate(embeds, 1):
        name = f"{x['stem']} - video {i}" if len(embeds) > 1 else f"{x['stem']} - video"
        mp4, tr = os.path.join(V, name + '.mp4'), os.path.join(T, name + '.md')
        note = 'From the platform captions.'
        if not os.path.exists(mp4):
            if 'vimeo.com' in url:
                subprocess.run([sys.executable, '-m', 'yt_dlp', '-q', '--no-warnings', '--socket-timeout', '30', '--retries', '5', '--fragment-retries', '10', '--referer', ref,
                                '-f', 'bv*[height<=720]+ba/b[height<=720]/b', '--merge-output-format', 'mp4',
                                '--write-subs', '--write-auto-subs', '--sub-langs', 'en.*', '--sub-format', 'vtt',
                                '-o', os.path.join(V, name + '.%(ext)s'), url])
            else:
                subprocess.run(['curl', '-sSL', '--fail', '-A', 'Mozilla/5.0', '-o', mp4 + '.part', url])
                if os.path.exists(mp4 + '.part'):
                    os.replace(mp4 + '.part', mp4)
        if not os.path.exists(tr) and os.path.exists(mp4):
            vtts = glob.glob(os.path.join(V, glob.escape(name) + '*.vtt'))
            if vtts:
                text = vtt_text(vtts[0])
                for v in vtts:
                    os.remove(v)
            elif no_whisper:
                text = None
            else:
                text = whisper(mp4); note = 'Auto-transcribed locally with Whisper (no captions on the platform).'
            if text is not None:
              open(tr, 'w').write(f"# {x['title']}, {'video ' + str(i) if len(embeds) > 1 else 'video'} (transcript)\n\n"
                                f"Section: {x['section']}\n{note}\n\n{text}\n")
        ok = os.path.exists(mp4)
        print('ok ' if ok else 'MISS', name, flush=True)
        if ok:
            trl = f'transcript: [_transcripts/{name}.md](<_transcripts/{name}.md>) ' if os.path.exists(tr) else ''
            s = s.replace(f'▶ Embedded video: {url}',
                          f'▶ Video: [_videos/{name}.mp4](<_videos/{name}.mp4>), {trl}(original: {url.split("?")[0]})')
    open(lesson, 'w').write(s)
