#!/usr/bin/env python3
"""
X data agent — powered by the Claude Code SDK.

Turns natural language data requests into twitter SDK calls, executes them,
and returns the result. Uses arcee-ai/trinity-large-preview:free via OpenRouter,
routed through a local proxy so the Claude Code CLI accepts the model.

Usage:
    python twitter/agent/agent.py "get all posts from elonmusk"
    python twitter/agent/agent.py "show me my bookmarks"
    python twitter/agent/agent.py "get the replies to tweet 2025486153969983826"
"""

import asyncio
import os
import sys

from claude_code_sdk import ClaudeCodeOptions, query
from claude_code_sdk.types import AssistantMessage, ResultMessage, TextBlock

from proxy import start as start_proxy

# ── Paths ─────────────────────────────────────────────────────────────────────

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
TWITTER_DIR = os.path.dirname(AGENT_DIR)
PROJECT_ROOT = os.path.dirname(TWITTER_DIR)

# ── Config ────────────────────────────────────────────────────────────────────

def _load_env() -> dict:
    for path in [
        os.path.join(TWITTER_DIR, ".env"),
        os.path.join(PROJECT_ROOT, "llms_prompt", ".env"),
    ]:
        if os.path.exists(path):
            env = {}
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

# The CLI only accepts Claude model names. The proxy replaces this with
# arcee-ai/trinity-large-preview:free before forwarding to OpenRouter.
CLI_MODEL = "claude-haiku-4-5-20251001"

# ── SDK docs ──────────────────────────────────────────────────────────────────

with open(os.path.join(TWITTER_DIR, "package", "llms.txt")) as f:
    SDK_DOCS = f.read()

# ── System prompt ─────────────────────────────────────────────────────────────

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
                 .get("tweet_results", {{}}).get("result", {{}})
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

# ── Agent ─────────────────────────────────────────────────────────────────────

async def run(request: str) -> None:
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not set. Add it to twitter/.env")
        sys.exit(1)

    proxy_url = start_proxy(OPENROUTER_API_KEY)

    options = ClaudeCodeOptions(
        model=CLI_MODEL,
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Bash", "Read"],
        permission_mode="bypassPermissions",
        cwd=PROJECT_ROOT,
        env={
            "ANTHROPIC_BASE_URL": proxy_url,
            "ANTHROPIC_API_KEY": "proxy",  # proxy handles the real key
            "PYTHONPATH": PROJECT_ROOT,
            "CLAUDECODE": "",
        },
        max_turns=10,
    )

    async for message in query(prompt=request, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[done — {message.num_turns} turn(s)]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(" ".join(sys.argv[1:])))
