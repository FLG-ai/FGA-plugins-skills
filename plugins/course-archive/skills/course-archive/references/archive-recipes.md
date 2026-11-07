# Platform recipes

Hard-won access facts for pulling courses. Each one was proved on a real pull.

## TUB Connect / UCL

`tubconnect.com/api/public/posts` serves the whole catalogue with no login, no cookie and no browser extension. Page records and the PDF, md and txt downloads come from `/api/public/pages/<slug-or-id>`, and `videoEmbedUrl` on the page record gives the Loom link directly. `isLocked: true` is cosmetic, the download still works.

Gate on `indexedAt`, falling back to `lastSynced` then `createdAt`, over a 45-day window. A 16 Sep Strategy Lab carried a `createdAt` 52 days old and was invisible to a `createdAt` check. The archive is the dedupe.

## Circle

`webvtt_file_url` on a video attachment is Circle's own transcript, free and login-free, so a Circle course never needs the video downloaded to get the words. When captions are off (Eliot Prince's Half Day Thursdays), transcribe locally from the HLS variant instead.

A creator's skill files are often Google Drive links inside the lesson body, not Circle attachments, so always sweep the bodies for `drive.google.com` downloads. Half Day Thursdays is hosted at `community.halfdaythursdays.com`, and `half-day-thursdays.circle.so` 401s.

## Public Notion sites

A public `*.notion.site` needs no login and no integration token. Its `/api/v3` endpoints serve the whole tree, database rows and signed attachment urls. Adapter at `scripts/notion_site/pull.py`.

## Dropbox Transfer

No usable API. Open the link in the in-app browser, click Download then "Or continue with download only" to skip the login wall, and read the `/2/file_transfers/files/download_logged_out` response for a direct `dl.dropboxusercontent.com` url that curl can take.

## stan.store

Nuxt plus `api.stanwith.me`, Bearer `auth_token` cookie (the 30-day one, not the 24-hour emailed token). Adapter in this skill.

## Course PDFs

Every course material PDF is rendered from the page's Notion blocks by `scripts/notion_pdf.py`: cover, callouts, tables, images, every toggle open, prompts in full. A platform's own PDF export is never filed, because those clip prompts. Superseded exports go to `_superseded/`.
