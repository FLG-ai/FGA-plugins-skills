"""Turn the Zoom/tutorial transcript PDFs a HighLevel course posts as lesson Files
into _transcripts/<name>.md. These beat captions and Whisper: speaker-labelled,
complete. Overwrites any caption or Whisper transcript for the same lesson video.

Usage: transcript_pdfs.py "<course dir>"
Matches "<NN> ...Transcript*.pdf" (and "...Trannscript", "...Transcrpt") in
_attachments/ to lesson NN. For a lesson with one video, the transcript replaces
_transcripts/<stem>.md. Extra transcripts (tutorials inside a lesson) are saved
as _transcripts/<NN> <pdf title>.md and linked from the lesson file.
"""
import glob, json, os, re, sys
import fitz

d = sys.argv[1]
m = json.load(open(os.path.join(d, '_manifest.json')))
by_n = {x['stem'].split(' ', 1)[0]: x for x in m}


def text_of(pdf):
    raw = '\n'.join(p.get_text() for p in fitz.open(pdf))
    lines = [l.strip() for l in raw.splitlines()]
    lines = [l for l in lines if l and '-->' not in l and not l.isdigit() and l != 'WEBVTT']
    turns, spk = [], re.compile(r'^([A-Z][^:]{1,45}):\s*(.*)')
    labelled = sum(1 for l in lines if spk.match(l)) > len(lines) * 0.2
    if not labelled:
        t = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
        return re.sub(r'(?<=[.!?]) (?=[A-Z])', '\n\n', t)
    for l in lines:
        mm = spk.match(l)
        if mm:
            who = re.sub(r'\s*\(.*?\)', '', mm.group(1)).strip()
            if turns and turns[-1][0] == who:
                turns[-1][1].append(mm.group(2))
            else:
                turns.append([who, [mm.group(2)]])
        elif turns:
            turns[-1][1].append(l)
    return '\n\n'.join(f'**{w}:** ' + re.sub(r'\s+', ' ', ' '.join(t)).strip() for w, t in turns)


pdfs = sorted(glob.glob(os.path.join(d, '_attachments', '[0-9][0-9] *Tran*scr*.pdf')))
groups = {}
for p in pdfs:
    groups.setdefault(os.path.basename(p).split(' ', 1)[0], []).append(p)

for n, files in groups.items():
    x = by_n.get(n)
    if not x:
        continue
    lesson = os.path.join(d, x['stem'] + '.md')
    s = open(lesson).read()
    single = x['video'] and len(files) == 1
    extra = []
    for p in files:
        title = re.sub(r'_?Tran+s?cr?i?pt\.pdf$', '', os.path.basename(p).split(' ', 1)[1]).strip(' _')
        name = x['stem'] if single else f"{n} {title}"
        out = os.path.join(d, '_transcripts', name + '.md')
        body = text_of(p)
        open(out, 'w').write(f"# {x['title'] if single else title} (transcript)\n\nSection: {x['section']}\n"
                             f"From the transcript PDF posted with the lesson: _attachments/{os.path.basename(p)}\n\n{body}\n")
        if single:
            for y in m:
                if y['stem'] == x['stem']:
                    y['transcript'] = f"_transcripts/{name}.md"; y['auto'] = False
        else:
            extra.append(name)
        print('ok', name, len(body.split()), 'words')
    if extra and '## Transcripts' not in s:
        s = s.rstrip() + '\n\n## Transcripts\n\n' + '\n'.join(f'- [{e}](<_transcripts/{e}.md>)' for e in extra) + '\n'
        open(lesson, 'w').write(s)
json.dump(m, open(os.path.join(d, '_manifest.json'), 'w'), indent=1)
