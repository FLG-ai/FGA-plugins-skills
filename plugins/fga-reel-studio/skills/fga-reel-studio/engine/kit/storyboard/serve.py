#!/usr/bin/env python3
"""Local review: serves <project>/storyboard/ (or any folder, like the style board) on this computer and saves notes.

For hosts without Claude artifacts (Codex, any terminal agent), or when the creator prefers to review locally.
Open the printed address, leave a note on any beat, press "Looks good: render it" when done. Every note lands in
<project>/storyboard/notes.json as {"beat": "p06" | "all", "text": ..., "at": ISO time}; the agent reads that file.
Run: python3 storyboard/serve.py <project or folder> [--port 8765]    (standard library only; Ctrl+C to stop)
"""
import datetime
import http.server
import json
import os
import sys
import threading


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = os.path.abspath(os.path.expanduser(sys.argv[1]))
    sb = os.path.join(root, "storyboard") if os.path.isdir(os.path.join(root, "storyboard")) else root
    if not os.path.exists(os.path.join(sb, "index.html")):
        sys.exit(f"nothing to review yet: {sb}/index.html doesn't exist (build the storyboard or the style board first)")
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    notes_path = os.path.join(sb, "notes.json")
    lock = threading.Lock()

    def read_notes():
        try:
            return json.load(open(notes_path))
        except (OSError, ValueError):
            return []

    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                          ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
                          ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}

        def __init__(self, *a, **kw):
            super().__init__(*a, directory=sb, **kw)

        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0].endswith("/api/notes"):
                return self._json(200, read_notes())
            return super().do_GET()

        def do_POST(self):
            if not self.path.split("?")[0].endswith("/api/notes"):
                return self._json(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                note = json.loads(self.rfile.read(min(n, 16384)))
                beat, text = str(note["beat"])[:16], str(note["text"]).strip()[:4000]
            except (ValueError, KeyError):
                return self._json(400, {"error": "send {beat, text}"})
            if not text:
                return self._json(400, {"error": "empty note"})
            with lock:
                notes = read_notes()
                notes.append({"beat": beat, "text": text, "at": datetime.datetime.now().isoformat(timespec="seconds")})
                json.dump(notes, open(notes_path, "w"), indent=1)
            print(f"note on {beat}: {text}", flush=True)
            return self._json(200, {"ok": True})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Storyboard: http://127.0.0.1:{port}/   (notes -> {notes_path})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
