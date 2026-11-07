#!/usr/bin/env python3
"""Export your logged-in Chrome cookies for one site to a Netscape cookies.txt.

Usage: cookies.py <domain fragment> <out.txt>     e.g. cookies.py circle.so circle.txt
Works for any platform, no Chrome extension needed. You must be signed in on
regular Chrome (not the in-app browser pane, which is a separate session).
"""
import http.cookiejar, sys, warnings
warnings.filterwarnings("ignore")
import yt_dlp.cookies as c

frag, out = sys.argv[1:3]
mj = http.cookiejar.MozillaCookieJar(out)
for ck in c.extract_cookies_from_browser("chrome"):
    if frag in ck.domain:
        mj.set_cookie(ck)
mj.save(ignore_discard=True, ignore_expires=True)
print(len(mj), "cookies:", sorted({ck.domain for ck in mj}))
