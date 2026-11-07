# Skool adapter

Skool serves its classroom through a Next.js data route that answers to the
logged-in browser session, so the whole course comes down in one pass.

Group slug comes from `skool.com/<group>/classroom`. This adapter runs inside a
logged-in Chrome tab (claude-in-chrome tools), not from cookies.

1. Navigate to `https://www.skool.com/<group>/classroom`.
2. Check lock state (never from page text, the "End trial to Unlock" labels come
   out of `get_page_text` shifted one row):
   ```js
   JSON.stringify(window.__NEXT_DATA__.props.pageProps.allCourses.map(c => ({
     title: c.metadata.title, access: c.metadata.hasAccess ?? null, locked: c.metadata.lockFreeTrial ?? null
   })), null, 1)
   ```
3. Paste `scripts/skool/harvest.js.txt` via `javascript_tool`. It returns at once and
   runs in the background (a full course passes the 45s CDP timeout). Poll:
   ```js
   JSON.stringify({done: window.__skool.done, at: window.__skool.progress, result: window.__skool.result, error: window.__skool.error})
   ```
   It downloads `skool-<group>.json` to `~/Downloads`. Leave the 250ms delay alone.
4. `python3 scripts/skool/build.py ~/Downloads/skool-<group>.json "<out dir>"`, then
   move the JSON in beside it as `_raw-skool-export.json`.

Known behaviour: section headers return HTTP 400 (no payload, the build turns
them into INDEX headings). `resources` is usually the string `"[]"`. A bare
course URL 307s to its first lesson and harvest.js.txt follows it. If `buildId`
changes mid-pull, reload and rerun.

Note: the harvester ships as `harvest.js.txt`, a plain text copy of the script, because email services refuse to deliver a zip that contains a .js file. Paste its contents into the javascript tool exactly as you would the .js version.
