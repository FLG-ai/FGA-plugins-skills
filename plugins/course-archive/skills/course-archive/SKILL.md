---
name: course-archive
description: 'Archives any course or member community you pay for (Skool, Circle, Thinkific, Squarespace, Kajabi, Teachable, custom) into local files: every lesson''s text, video, transcript and downloads, a plain-English recap of every lesson and of the whole course (Word or Notion), and one Word index that links everything. Use on: pull a course, archive a classroom, save this challenge, or a pasted course URL. Not for your own files.'
user-invocable: true
---

# Course archive

One job, any platform: get every lesson the user's account can already open onto their computer
as markdown, so they keep it if access ends. Personal member copy only, never
redistribute.

## Step 0: check the tools and ask where to save

Run this first, every time, before touching the course:

```bash
bash ~/.claude/skills/course-archive/scripts/check_tools.sh
```

Never assume this machine already has what the skill needs. The check covers everything the archive, the Word index and the
recaps need, and it's the only place setup gets asked for. If Google Drive
shows `--`, tell them the index and recap links will open the files in the
course folder rather than Drive, which works fine as long as they keep the
folder together.

If anything shows MISS, show the person the list it prints (what each tool is
for, and the exact install command) and ask them to run those commands in
Terminal, or offer to run them yourself once they say yes. Never install
without a yes. Core tools missing (python3, yt-dlp, Chrome) means stop and wait
until they are in. ffmpeg, faster-whisper and pymupdf only matter for videos,
transcripts and image reuse, so the text pull can go ahead without them, with
a note on what gets skipped. Re-run the check after they install.

Then ask two things, in the same message if tools are fine.

**Where recaps should live.** Word (the default) gives one .docx per lesson
recap plus a course recap .docx in the course folder. Notion gives one page per
recap under a parent page they pick, with the course recap as the top page.
Word is the default. If someone picks Notion, check the Notion connector is
connected before the pull starts. If it isn't, tell them how to add it (on
claude.ai: Settings, Connectors, Notion. In Claude Code: the Notion MCP server
with `claude mcp add`), and offer Word in the meantime. Never ask them for a
Notion token.

**Where the archive should be saved.** Suggest a `Courses` folder in their Documents or Google
Drive and use whatever path they give. Everywhere below that says COURSES
means the folder they chose.

## Step 1: identify the platform and get their session

Look at the URL. `skool.com` is Skool, `*.circle.so` is Circle, anything else
check the table below, then the page source.

Use their **regular Chrome** session. The in-app browser pane is a separate,
logged-out browser, so do not ask them to sign in there. If they are not signed in
on Chrome, ask them to sign in there and say "in". Never type their password.

```bash
python3 ~/.claude/skills/course-archive/scripts/cookies.py <domain fragment> <scratchpad>/cookies.txt
```

Python requests need a browser User-Agent or Cloudflare returns 403.

## Step 2: list what they can open, and tell them the count before pulling

**Lesson 1 first, always** . A course that's already fully
posted gets pulled, numbered and indexed in course order: lesson 1, then 2, 3
and on, within every module. Number files from the course's own order, never
from the platform's newest-first feed. Only a live feed (community posts, a
challenge still dripping) lists newest first, and the index gets
`--newest-first` for those.

Only pull what their account already opens. Locked, undripped or trial-gated
lessons get listed as skipped in INDEX.md, never forced. Read lock state from the
platform's data, never from page text.

## Step 3: pull with the platform's adapter

| Platform | How | Notes |
|---|---|---|
| Circle | `scripts/circle/pull.py [--no-media] <host> cookies.txt "<out dir>" <space slug or id> ...` | `internal_api/spaces` lists spaces. `post_type: course` uses `courses/<space>/sections/.../lessons/...`, `basic` spaces are one post each at `spaces/<id>/posts`, and a drip-fed challenge is usually a run of basic spaces, one per lesson. Videos are either Wistia or Circle's own uploads. A Circle upload is an attachment on the body with `video_variants.hls`, `metadata.duration` and, best of all, **`webvtt_file_url`, Circle's own transcript, free and no login**. Originals are huge (a 28 minute .mov is 2GB), so pass `--no-media` to link them instead of downloading and let the VTT carry the words. Downloads PDFs and workbooks to `_attachments/`. A lesson's video is on `featured_media` (not `featured_media_embed`), with `video_variants.hls` and a `duration` like `"11:12"`. Pass `slug::regex` to keep only the posts or lessons whose title matches. |
| Skool | `scripts/skool/harvest.js.txt` in a logged-in Chrome tab, then `scripts/skool/build.py` | Next.js data route. Lock state from `allCourses[].metadata.hasAccess`. See `references/skool.md`. |
| Thinkific | yt-dlp cookies + `/api/course_player/v2/` | No adapter yet: find its JSON API as described under **New platform?** below, starting with `/api/course_player/v2/` and yt-dlp with browser cookies. |
| stan.store | `scripts/stan/pull.py <course uuid> <store_slug> cookies.txt "<out dir>"` | Nuxt app, API at `api.stanwith.me/api/v1/courses/<uuid>`, auth is `Bearer <auth_token cookie from stan.store>` (the cookie outlives the emailed magic-link token by 30 days). One call returns modules, lessons, HTML bodies, direct `.mp4` URLs and PDF assets. No captions, so transcribe locally. |
| Squarespace / Vercel sites | `?format=json` per page | No adapter yet: add `?format=json` to each page URL and read the page JSON. |
| Notion public site (`*.notion.site`) | `scripts/notion_site/pull.py <public url> "<out dir>"` | No login and no integration token: a notion.site serves the same private `/api/v3` endpoints the app uses. `loadCachedPageChunkV2` gives the page tree, `queryCollection` gives each database's rows, every row is itself a page fetched the same way, and `getSignedFileUrls` turns an `attachment:<id>:<name>` ref into a downloadable url (one `permissionRecord` per block). Writes one markdown file per database (properties as a table, then each row's own notes) and per sub-page. |
| HighLevel client portal (FG Funnels / Funnel Gorgeous `my.funnelgorgeous.com`, any `*/courses/products/<uuid>` portal) | `scripts/highlevel/api.py` + `build.py <categories.json> "<out>" <host> <product id> [section order regexes]`, then `attachments.py`, `embeds.py "<out>" https://<host>/`, `transcripts.py` | Auth is the `catv2` cookie on the portal domain: base64 JSON whose `.token` is sent as `authorization: Bearer <token>`, read in-script and never printed. One call, `services.leadconnectorhq.com/clientportal-middleware/memberships/locations/<loc>/user-purchase/categories?product_id=<id>&source=courses`, returns every section, lesson HTML body, video URL and caption path; lock state is `availability` per category and `lockedByPost/lockedByCategory` per post. Videos are plain files on public CDNs (filesafe.space, storage.googleapis.com, `cdn.courses.apisystem.tech` for paths starting `/memberships/`), no login, needs a browser User-Agent. Section `sequenceNo` values collide, so pass the order as regexes. Bodies embed Vimeo tutorials (yt-dlp with the portal as `--referer`, en auto-captions) and `.mp4` video tags. **The `.srt` captions are Zoom captions cut to the first line of each cue**, so run `transcripts.py --redo-captions` once videos are down. **Each lesson's Files (slides, chat logs, full transcript PDFs) are NOT in the categories JSON.** Collect them by walking every lesson in their Chrome tab with the Vue router (`document.querySelector('#app').__vue_app__.config.globalProperties.$router.push(...)`), going back to the product page between lessons and only accepting a file list once it has been stable for about 1.5s (otherwise the previous lesson's files carry over), and read `img.post-material-icon` + sibling `<a>`. Use MessageChannel timers, not setTimeout, because Chrome throttles a background tab to one tick a minute. The hrefs are plain `cdn.courses.apisystem.tech` files, no login. Then `transcript_pdfs.py` turns them into `_transcripts/` and they replace captions and Whisper. Do this BEFORE any Whisper run. Don't probe other private endpoints with the token (the safety check blocks it) and don't pull the token through the browser tool. |
| AI Employee Bootcamp hub (`aiemployeebootcamp.co`, TUB / Callan Faulkner) | `scripts/aieb/pull.py cookies.txt "<out dir>"` | `/api/resources` lists every item with `is_unlocked`/`is_released`, and session transcript and class-notes PDFs appear as signed Supabase urls titled `[session:N]` once posted (usually within 24 hours). Replays are unlisted YouTube iframes on `/hub/sessions`, not in the API, so take the id from Chrome and download with `uvx --python 3.12 --from "yt-dlp[default]" yt-dlp --js-runtimes node` (the Python 3.9 yt-dlp fails on YouTube). Bonuses: Quantum Leap Pack at `/downloads/`, and the Social Growth Kit is a TUB page whose skill zips come through `tubconnect.com/api/images/notion/<block id>`. Details in the script docstring. |
| tubconnect.com | `/api/public/posts` + `/api/public/pages/<id>` | No login needed. Details in `references/archive-recipes.md`. |

**Skills and workbooks are often not attachments.** A creator will host the actual file on Google Drive or Notion and just link it from the lesson text. Always sweep the written bodies for `drive.google.com/uc?export=download&id=` and `file/d/<id>` links and pull those too, taking the real filename from the response's `content-disposition`, then point the markdown at the local copy. Half Day Thursdays' 65 skills all arrived this way and none of them were attachments. Do not size-gate the download: a one-file skill zip can be 350 bytes.

**Dropbox Transfer links** (`dropbox.com/t/...` or `/transfer/...`) have no usable public API and guessing endpoints is a waste of time. Open the link in the in-app browser, decline cookies, click **Download**, then click **"Or continue with download only"** to get past the login wall, and read `read_network_requests` for the `POST /2/file_transfers/files/download_logged_out` response: it hands back a direct `dl.dropboxusercontent.com` url that curl takes with no cookies. A password goes in the field first (creators publish it in the post). Never sign in to get a file.

**New platform?** Most course sites load lessons from a JSON API. Find it: try
`/internal_api/`, `/api/`, `?format=json`, `window.__NEXT_DATA__`, or watch the
network requests while a lesson loads. Write the adapter to
`scripts/<platform>/pull.py`, reusing `block()` from `scripts/skool/build.py` if
the bodies are TipTap/ProseMirror JSON, and **add a row to this table** so the
next run is one command.

## Step 4: output

`<save folder from Step 0>/<Creator or Community> - <Course>/`: one numbered
markdown file per lesson (title, section, source link, video link, attachments,
body), `_attachments/` for PDFs and workbooks, `_videos/` for the replays,
`INDEX.md` at the root.

**Download the videos** (keep them, rather than linking back to the platform).
Take 720p straight from the source, no re-encode: sharp enough to read slides,
about 5GB for 14 hours. Wistia: `yt-dlp -f "hd_mp4-720p/md_mp4-540p/best"` on
`https://fast.wistia.net/embed/iframe/<id>`, name each file after its lesson
markdown file. Download in lesson order, lesson 1 first, so a stopped run leaves
the start of the course complete. A second worker can take the second half of
the list (from the midpoint, still in ascending order) to halve the time. Then
check every file is 1280x720 with ffmpeg. YouTube and Loom stay as links.

**Add transcripts**: `python3 scripts/transcripts.py "<course dir>"`
writes each video's transcript to `_transcripts/` and links it from the notes file.
It reads the manifest: a Circle upload's `webvtt_file_url` first, then Wistia's
free captions in `fast.wistia.net/embed/medias/<id>.json`. Both need no login,
and neither needs the video downloaded. When a community has captions switched off, it
falls back to local `faster-whisper`, installed with pip --user: extract 16kHz mono audio
with ffmpeg from the **HLS** variant, never the original, and run model `small.en` int8 on
CPU. Circle's originals are 4K .mov files running to 2GB each and the HLS stream is a
fraction of that. Reckon on a couple of minutes per 17 minutes of video, so run it in the
background. Report any video that had no captions, and mark those transcripts as
auto-transcribed.

**Notes PDFs are Notion copies, never the platform's PDF export.** This is the rule for all course materials. Any lesson or page that lives in
Notion (all of TUB Connect, and any Notion-hosted notes) gets its PDF from
`python3 scripts/notion_pdf.py <tubconnect id or slug> "<out>.pdf"`: cover, icon,
callouts, tables and images as on the page, every toggle opened out, and every
prompt wrapped in full. Add `--images-from <older archived pdf>` when the page's
image links have expired. For non-Notion platforms, print the lesson page itself
with every toggle and accordion open, the same way. The Notes.md sidecar is still
written beside it. A superseded platform export goes to that folder's
`_superseded/`, never the bin.


## Step 5: prompts stay whole and copyable

A prompt is the part of a class people reuse, and it is the part that gets
clipped. Platform PDF exports cut long prompts, and a prompt pasted out of a PDF
arrives with broken line breaks.

```bash
python3 ~/.claude/skills/course-archive/scripts/prompts_export.py "<course dir>" --check-pdfs
```

It writes two files at the course root. `PROMPTS.md` holds every prompt as a
fenced block, grouped by lesson, in full. `PROMPTS.html` holds the same prompts
as cards with a Copy button each, and the page pastes into Google Docs or Notion
as rich text with the monospace blocks intact, for easy copy and paste.

`--check-pdfs` compares each lesson's PDF text layer against its markdown and
names any prompt whose ending is missing from the PDF. Anything it flags gets
re-rendered with `notion_pdf.py` before the course is called done. The markdown
notes are the source of truth for prompt text, always, and they are never
truncated to fit a page.

The Word index (Step 8) links both files in its Course extras row.

## Step 6: skills come out as .skill packets

claude.ai, Claude in Chrome and Cowork all take a skill as one zipped folder
with SKILL.md at its root, so a loose folder or a bare SKILL.md cannot be
uploaded. So finished skills ship as a single `.skill` file, and course skills are no different.

```bash
python3 ~/.claude/skills/course-archive/scripts/pack_skills.py "<course dir>"
```

It packs every folder that holds a SKILL.md into `_skills/<name>.skill`, renames
any zip that is already shaped like a skill, and leaves the originals in place.

It deliberately does not turn prompts, templates or worksheets into skills. A
prompt is not a skill, and inventing a SKILL.md for someone else's prompt puts
words in their mouth. Those stay in PROMPTS.md and PROMPTS.html. If the user wants
one of them turned into a real skill, that is a separate job with skill-creator.

The Word index (Step 8) lists every packet in its Course extras row, so they can
see what is upload-ready without opening the folder.

## Step 7: recaps, so nobody has to rewatch

Every lesson gets a recap, and the course gets one recap that pulls them all
together: everything said in the video, summarised on one
sheet, with the skills to use, how to use them and why, written plainly and
practically rather than technically. Templates and writing rules are in
`references/recap-template.md`. Read it before writing.

1. **Lesson recaps.** One `_recaps/<lesson stem> - Recap.md` per lesson, written
   from its transcript, notes and attachments, lesson 1 first. Read each skill's
   SKILL.md before describing it. For a course over about 8 lessons, hand
   batches of 5 lessons to parallel subagents with the template, then read every
   recap back yourself for accuracy and plain language.
2. **Course recap.** `COURSE RECAP.md` at the course root, built only from the
   lesson recaps: the big ideas, the method lesson by lesson, every skill and
   tool in one table, and the first three things to do.
3. **Check them** with the user's own writing rules (or a humanizer skill if they have one) (no em
   dashes, no semicolons, no banned words) before saving.
4. **Make them easy to open.** The markdown is only the source copy. For Word
   (the default) run
   `python3 ~/.claude/skills/course-archive/scripts/recap_docx.py "<course dir>"`,
   which writes a .docx beside every recap and `COURSE RECAP.docx` at the root,
   with headings, bullets, tables and Drive links. Re-run it once Drive has
   synced, until it reports no unlinked files. For Notion, create the course
   recap page under the parent they chose and one child page per lesson recap
   through the Notion connector, then save the page urls to
   `_recaps/notion.json` as `{"<recap file name>.md": url, "COURSE RECAP": url}`.
   The Word index links those pages instead of the Word copies.

On a re-run for a live course, write recaps only for the new lessons and then
refresh the course recap.

## Step 8: the Word index, the one sheet they open (every course gets one)

Every archived course ends with `<Course>, course index.docx` in the course
folder . It replaces the old Google Doc index: one Word doc
listing every module and lesson, lesson 1 first, with every file a click away,
so it's the only sheet they need to look at.

A "Start here" link to `COURSE RECAP.md` at the top, then one table per
section with these columns:

| Column | What goes in it |
|---|---|
| **#** | The lesson number in course order |
| **Lesson** | The module or lesson name |
| **Recap** | The lesson recap from Step 7 (its Word copy, or its Notion page) |
| **Video** | The copy saved in their Drive (or the course folder). A public YouTube or Loom link as-is. `no video` when there's none |
| **Transcript** | The transcript markdown and PDF |
| **Notes** | The notes from the module page, its Notion-style PDF, class notes |
| **Bonuses** | Everything else for that lesson: skills, workbooks, slides, prompt packs, downloads |

A last **Course extras** row carries the course-wide files: every `_skills/*.skill`
packet and `PROMPTS.html` / `PROMPTS.md`.

Rules that do not bend: links point at the Drive copy, never back at the
platform, and never at tubconnect. YouTube and Loom are the only outside links.
An empty cell says `none` (or `not written yet` for a missing recap), never blank.

```bash
python3 ~/.claude/skills/course-archive/scripts/course_index.py "<course dir>" <scratchpad>/doc.json --docx --md --title "<Course>"
```

Add `--newest-first` only for a live feed. It works with or without
`_manifest.json` and reads Drive IDs from the Drive for Desktop xattr, so no
Drive listing or connector is needed. `--md` also writes `COURSE INDEX.md` as
the offline copy. Run it last, after the videos and recaps have synced to Drive,
because anything Drive hasn't uploaded yet shows as `pending sync` (the JSON
lists those under `pending`, and missing recaps under `no_recap`). Re-run it
until both lists are empty, then hand them the .docx.

A Google Doc version is optional now: build one only when the user asks for it.

## Reporting back

Lead with the Word index (sent with SendUserFile) and the course recap, since
those are what they'll open. Then lesson count, folder path, attachment count,
what was skipped and why, and any other spaces in the same community they might
want next. Offer the re-run when a
trial converts or more lessons drip.
