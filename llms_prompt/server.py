#!/usr/bin/env python3
"""
Lightweight local server.
GET localhost:<PORT>/<stuff>  →  streams arcee-ai/trinity-large-preview:free's opinion
                                 on <stuff> as plain text, token by token.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

import requests

PORT = int(os.getenv("PORT", 8765))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "arcee-ai/trinity-large-preview:free"
FLUSH_INTERVAL = 0.05  # seconds between flushes (50 ms)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        stuff = unquote(self.path.lstrip("/"))

        if not stuff:
            self._send_plain(b"Usage: /<stuff>")
            return

        if not OPENROUTER_API_KEY:
            self._send_plain(b"Error: OPENROUTER_API_KEY not set.")
            return

        # Send headers without Content-Length so we can stream
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "stream": True,
                    "messages": [
                        {"role": "user", "content": stuff}
                    ],
                },
                stream=True,
                timeout=60,
            )
            resp.raise_for_status()

            buf = b""
            last_flush = time.monotonic()

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                # SSE lines look like:  data: {...}  or  data: [DONE]
                if not raw_line.startswith(b"data: "):
                    continue
                payload = raw_line[6:]
                if payload == b"[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0]["delta"].get("content") or ""
                    if delta:
                        buf += delta.encode()
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

                # Flush every FLUSH_INTERVAL seconds
                now = time.monotonic()
                if buf and (now - last_flush) >= FLUSH_INTERVAL:
                    self.wfile.write(buf)
                    self.wfile.flush()
                    buf = b""
                    last_flush = now

            # Flush any remaining bytes
            if buf:
                self.wfile.write(buf)
                self.wfile.flush()

        except Exception as e:
            try:
                self.wfile.write(f"\n\nError: {e}".encode())
                self.wfile.flush()
            except BrokenPipeError:
                pass

    def _send_plain(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")


if __name__ == "__main__":
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY is not set.")
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
