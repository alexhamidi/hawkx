#!/usr/bin/env python3
"""
X data agent — local streaming server.

GET http://localhost:<PORT>/<data request>  →  streams agent output as plain text.

Usage:
    python twitter/agent/server.py
    curl http://localhost:8766/get most recent post from elonmusk
    curl http://localhost:8766/show me bookmarks
"""

import asyncio
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

# ── Paths ─────────────────────────────────────────────────────────────────────

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
TWITTER_DIR = os.path.dirname(AGENT_DIR)
PROJECT_ROOT = os.path.dirname(TWITTER_DIR)

sys.path.insert(0, AGENT_DIR)
from proxy import start as start_proxy

# ── Config ────────────────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", 8766))


def _load_env() -> dict:
    for path in [
        os.path.join(TWITTER_DIR, ".env"),
        os.path.join(PROJECT_ROOT, "llms_prompt", ".env"),
    ]:
        if os.path.exists(path):
            env: dict = {}
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip()
            return env
    return {}


_env = _load_env()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or _env.get("OPENROUTER_API_KEY", "")

# ── Proxy (started once, shared across requests) ───────────────────────────────

_proxy_url: str | None = None


def _get_proxy() -> str:
    global _proxy_url
    if _proxy_url is None:
        _proxy_url = start_proxy(OPENROUTER_API_KEY)
    return _proxy_url


# ── System prompt ─────────────────────────────────────────────────────────────

with open(os.path.join(TWITTER_DIR, "package", "llms.txt")) as f:
    SDK_DOCS = f.read()

SYSTEM_PROMPT = f"""You are an X (Twitter) data agent. You fulfill data requests by writing \
and running Python code using the twitter SDK via the Bash tool.

{SDK_DOCS}

--- Importing the SDK ---
Always start your Python scripts with:
```python
import sys
sys.path.insert(0, {repr(PROJECT_ROOT)})
from twitter.package import get_post, get_post_simple, get_user_tweets, get_user_id, get_bookmarks
```

--- Extracting tweet text from timeline entries ---
```python
for entry in entries:
    tweet = entry.get("content", {{}}).get("itemContent", {{}}) \\
                 .get("tweet_results", {{}}).get("result", {{}})\
    text = tweet.get("legacy", {{}}).get("full_text")
    if text:
        print(text)
```

Rules:
- Use Bash to write and run inline Python. Never just describe what you would do.
- Filter cursor entries: skip any where entryId starts with "cursor-".
- Print results clearly — one tweet per block.
- After retrieving data, give a short plain-English summary.
"""

# ── Agent runner ──────────────────────────────────────────────────────────────


async def _run_agent(request: str, write: callable) -> None:
    from claude_code_sdk import ClaudeCodeOptions, query
    from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock

    options = ClaudeCodeOptions(
        model="claude-haiku-4-5-20251001",
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read"],
        permission_mode="bypassPermissions",
        cwd=PROJECT_ROOT,
        env={
            "ANTHROPIC_BASE_URL": _get_proxy(),
            "ANTHROPIC_API_KEY": "proxy",
            "PYTHONPATH": PROJECT_ROOT,
            "CLAUDECODE": "",
        },
        max_turns=10,
    )

    async for message in query(prompt=request, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    write(block.text.encode() + b"\n")
        elif isinstance(message, ResultMessage):
            write(f"\n[done — {message.num_turns} turn(s)]\n".encode())


# ── HTTP handler ──────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = unquote(self.path.lstrip("/"))

        if not request:
            self._send_plain(
                b"Usage: /<data request>\n"
                b"Example: /get most recent post from elonmusk\n"
            )
            return

        if not OPENROUTER_API_KEY:
            self._send_plain(b"Error: OPENROUTER_API_KEY not set.\n")
            return

        # Start streaming — no Content-Length so data flows immediately
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

        def write(data: bytes) -> None:
            try:
                self.wfile.write(data)
                self.wfile.flush()
            except BrokenPipeError:
                pass

        try:
            asyncio.run(_run_agent(request, write))
        except Exception as e:
            try:
                write(f"\nError: {e}\n".encode())
            except BrokenPipeError:
                pass

    def _send_plain(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}", flush=True)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not set. Add it to twitter/.env")
        sys.exit(1)

    _get_proxy()  # start proxy once at boot

    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"X data agent server → http://localhost:{PORT}/")
    print(f"Try: curl http://localhost:{PORT}/get most recent post from elonmusk")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
