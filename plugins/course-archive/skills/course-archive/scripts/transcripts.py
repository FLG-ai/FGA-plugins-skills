#!/usr/bin/env python3
"""Write each video's transcript to _transcripts/<lesson> - Transcript.md.

Usage: transcripts.py "<course dir>"
Reads _manifest.json. Wistia: the public media JSON carries the full caption
text (media.captions[].text), no login needed. Skips files that already have
a transcript. Links it from the notes file and records it in _manifest.json
so doc_tables.py gives the Doc a Transcript column. Other hosts are reported.
"""
import json, os, re, shutil, subprocess, sys, tempfile, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"


def vtt_text(url):
    """WebVTT -> prose. Drops cue numbers, timings and repeated rolling lines."""
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120).read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if (not line or line.startswith(("WEBVTT", "NOTE", "STYLE", "Kind:", "Language:"))
                or "-->" in line or line.isdigit()):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if not out or line != out[-1]:
            out.append(line)
    text = " ".join(out)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[.!?]) (?=[A-Z])", "\n\n", text)


_model = None


def whisper(hls, label):
    """No captions on this community: take audio from the HLS variant (small, transcoded)
    rather than the multi-GB original, and transcribe locally with faster-whisper."""
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel("small.en", device="cpu", compute_type="int8")
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "a.wav")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", hls,
                            "-vn", "-ac", "1", "-ar", "16000", wav], capture_output=True, text=True)
        if r.returncode or not os.path.exists(wav):
            print("ffmpeg failed:", label, r.stderr.strip()[:200]); return ""
        segs, _ = _model.transcribe(wav, beam_size=1, vad_filter=True)
        out = " ".join(x.text.strip() for x in segs)
        return re.sub(r"(?<=[.!?]) (?=[A-Z])", "\n\n", re.sub(r"\s+", " ", out)).strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


d = sys.argv[1]
m = json.load(open(os.path.join(d, "_manifest.json")))
done = none = 0
for x in m:
    p = os.path.join(d, x["md"])
    s = open(p).read()
    if x.get("transcript") or not x["videos"]:
        continue
    parts = []
    for mv in x.get("media") or []:
        t = ""
        if mv.get("vtt"):
            try:
                t = vtt_text(mv["vtt"])
            except Exception as e:
                print("vtt failed:", mv["name"], e)
        if not t and mv.get("hls"):
            print("transcribing locally:", x["md"])
            t = whisper(mv["hls"], x["md"])
        if t:
            parts.append(t)
            x["auto"] = not mv.get("vtt")
    for v in ([] if parts else x["videos"]):
        w = re.search(r"wistia\.net/embed/iframe/([a-z0-9]{10})", v)
        if not w:
            print("no transcript source for", v); continue
        j = json.load(urllib.request.urlopen(f"https://fast.wistia.net/embed/medias/{w.group(1)}.json", timeout=60))
        caps = j["media"].get("captions") or []
        cap = next((c for c in caps if c.get("language") == "eng"), caps[0] if caps else None)
        if cap and cap.get("text"):
            parts.append(cap["text"].strip())
    if parts:
        os.makedirs(os.path.join(d, "_transcripts"), exist_ok=True)
        tn = x["md"][:-3] + " - Transcript.md"
        open(os.path.join(d, "_transcripts", tn), "w").write(
            f"# {x['title']}: transcript\n\nNotes: [{x['md']}](<../{x['md']}>)\n"
            + ("\n_Auto-transcribed locally (faster-whisper small.en), the community has captions off._\n" if x.get("auto") else "")
            + "\n---\n\n" + "\n\n---\n\n".join(parts) + "\n")
        open(p, "w").write(s.rstrip() + f"\n\n---\n\n**Transcript:** [{tn}](<_transcripts/{tn}>)\n")
        x["transcript"] = tn; done += 1
    else:
        none += 1; print("no captions:", x["md"])
json.dump(m, open(os.path.join(d, "_manifest.json"), "w"), indent=1, ensure_ascii=False)
print(f"{done} transcripts added, {none} videos without captions")
