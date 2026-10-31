#!/usr/bin/env python3
"""A tiny web UI + proxy for DeepTutor voice chat.

Usage:
    cd voice_chat_ui
    python3 run.py

Environment variables:
    DEEPTUTOR_URL   Backend base URL (default: http://localhost:8001)
    VOICE_UI_PORT   Port for this UI server (default: 8080)
    DEEPTUTOR_TOKEN Optional Bearer token forwarded to the backend.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_URL = os.environ.get("DEEPTUTOR_URL", "http://localhost:8001").rstrip("/")
UI_PORT = int(os.environ.get("VOICE_UI_PORT", "8080"))


class VoiceUIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/_info":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = json.dumps({"backend_url": BACKEND_URL, "ui_port": UI_PORT})
            self.wfile.write(payload.encode("utf-8"))
            return
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/voice/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        target = f"{BACKEND_URL}/api/voice/chat?output=audio"
        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/octet-stream"),
            "Content-Length": str(len(body)),
            "Accept": "*/*",
        }
        token = os.environ.get("DEEPTUTOR_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(target, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                for h in ("Content-Type", "X-Session-Id", "X-Turn-Id", "X-Transcript", "X-Reply"):
                    v = resp.headers.get(h)
                    if v:
                        self.send_header(h, v)
                self.end_headers()
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(exc.read())


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", UI_PORT), VoiceUIHandler)
    print(f"Voice UI:   http://localhost:{UI_PORT}")
    print(f"Backend:    {BACKEND_URL}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
