"""
Local proxy: converts Anthropic API requests → OpenAI format and routes to OpenRouter.

The Claude Code CLI speaks Anthropic protocol (/v1/messages, SSE streaming).
OpenRouter speaks OpenAI protocol (/v1/chat/completions).
This proxy converts in both directions, including streaming SSE.
"""

import json
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

TARGET_MODEL = "arcee-ai/trinity-large-preview:free"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ── Format converters ─────────────────────────────────────────────────────────

def _to_openai(body: dict) -> dict:
    """Anthropic Messages request → OpenAI Chat Completions request."""
    messages = []

    sys = body.get("system")
    if sys:
        if isinstance(sys, list):
            sys = "\n".join(b.get("text", "") for b in sys if b.get("type") == "text")
        messages.append({"role": "system", "content": sys})

    for msg in body.get("messages", []):
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue

        # content is a list of blocks
        texts, tool_calls, tool_results = [], [], []
        for blk in content:
            t = blk.get("type")
            if t == "text":
                texts.append(blk.get("text", ""))
            elif t == "tool_use":
                tool_calls.append({
                    "id": blk.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "type": "function",
                    "function": {
                        "name": blk.get("name", ""),
                        "arguments": json.dumps(blk.get("input", {})),
                    },
                })
            elif t == "tool_result":
                rc = blk.get("content", "")
                if isinstance(rc, list):
                    rc = "\n".join(b.get("text", "") for b in rc)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": blk.get("tool_use_id", ""),
                    "content": str(rc),
                })

        if role == "assistant":
            out: dict = {"role": "assistant", "content": "\n".join(texts) or None}
            if tool_calls:
                out["tool_calls"] = tool_calls
            messages.append(out)
        elif role == "user":
            if tool_results:
                messages.extend(tool_results)
            if texts:
                messages.append({"role": "user", "content": "\n".join(texts)})
        else:
            messages.append({"role": role, "content": "\n".join(texts)})

    oai: dict = {
        "model": TARGET_MODEL,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 4096),
        "stream": body.get("stream", False),
    }
    if "temperature" in body:
        oai["temperature"] = body["temperature"]
    if "tools" in body:
        oai["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in body["tools"]
        ]
        oai["tool_choice"] = "auto"

    return oai


def _to_anthropic(oai: dict, msg_id: str) -> dict:
    """OpenAI Chat Completions response → Anthropic Messages response."""
    choice = oai["choices"][0]
    msg = choice["message"]
    finish = choice.get("finish_reason", "stop")

    content = []
    if msg.get("content"):
        content.append({"type": "text", "text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        try:
            inp = json.loads(tc["function"]["arguments"])
        except Exception:
            inp = {}
        content.append({
            "type": "tool_use",
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": inp,
        })

    stop_reason = "tool_use" if finish == "tool_calls" else "end_turn"
    usage = oai.get("usage", {})
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": TARGET_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ── Streaming converter ───────────────────────────────────────────────────────

class _StreamConverter:
    """Converts an OpenAI SSE stream to Anthropic SSE format."""

    def __init__(self, msg_id: str, input_tokens: int = 0):
        self.msg_id = msg_id
        self.input_tokens = input_tokens
        self._text_idx: int | None = None
        self._tool_blocks: dict[int, dict] = {}  # oai_index → {block_idx, id, name}
        self._next_idx = 0
        self._output_tokens = 0
        self._stop_reason = "end_turn"

    @staticmethod
    def _sse(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    def start(self) -> bytes:
        return (
            self._sse("message_start", {
                "type": "message_start",
                "message": {
                    "id": self.msg_id, "type": "message", "role": "assistant",
                    "content": [], "model": TARGET_MODEL,
                    "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": self.input_tokens, "output_tokens": 0},
                },
            })
            + self._sse("ping", {"type": "ping"})
        )

    def process(self, chunk: dict) -> bytes:
        out = b""
        choices = chunk.get("choices") or []
        if not choices:
            return out

        choice = choices[0]
        delta = choice.get("delta") or {}
        finish = choice.get("finish_reason")

        # Text delta
        text = delta.get("content") or ""
        if text:
            if self._text_idx is None:
                self._text_idx = self._next_idx
                self._next_idx += 1
                out += self._sse("content_block_start", {
                    "type": "content_block_start",
                    "index": self._text_idx,
                    "content_block": {"type": "text", "text": ""},
                })
            out += self._sse("content_block_delta", {
                "type": "content_block_delta",
                "index": self._text_idx,
                "delta": {"type": "text_delta", "text": text},
            })

        # Tool call deltas
        for tc in delta.get("tool_calls") or []:
            oi = tc.get("index", 0)
            if oi not in self._tool_blocks:
                # Close text block first if open
                if self._text_idx is not None:
                    out += self._sse("content_block_stop", {
                        "type": "content_block_stop", "index": self._text_idx,
                    })
                    self._text_idx = None
                bidx = self._next_idx
                self._next_idx += 1
                self._tool_blocks[oi] = {"block_idx": bidx, "id": tc.get("id", ""), "name": ""}
                out += self._sse("content_block_start", {
                    "type": "content_block_start",
                    "index": bidx,
                    "content_block": {
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:8]}"),
                        "name": tc.get("function", {}).get("name") or "",
                        "input": {},
                    },
                })
                self._stop_reason = "tool_use"

            blk = self._tool_blocks[oi]
            fn = tc.get("function") or {}
            if fn.get("name"):
                blk["name"] = fn["name"]
            args_delta = fn.get("arguments") or ""
            if args_delta:
                out += self._sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": blk["block_idx"],
                    "delta": {"type": "input_json_delta", "partial_json": args_delta},
                })

        if finish in ("tool_calls",):
            self._stop_reason = "tool_use"

        usage = chunk.get("usage") or {}
        if usage.get("completion_tokens"):
            self._output_tokens = usage["completion_tokens"]

        return out

    def finish(self) -> bytes:
        out = b""
        if self._text_idx is not None:
            out += self._sse("content_block_stop", {
                "type": "content_block_stop", "index": self._text_idx,
            })
        for blk in self._tool_blocks.values():
            out += self._sse("content_block_stop", {
                "type": "content_block_stop", "index": blk["block_idx"],
            })
        out += self._sse("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": self._stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": self._output_tokens},
        })
        out += self._sse("message_stop", {"type": "message_stop"})
        return out


# ── HTTP handler ──────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    api_key: str = ""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        streaming = body.get("stream", False)

        oai_body = _to_openai(body)
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        resp = requests.post(
            OPENROUTER_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/anthropics/claude-code",
                "X-Title": "claude-code-twitter-agent",
            },
            json=oai_body,
            stream=streaming,
            timeout=120,
        )

        if not streaming:
            data = resp.json()
            if "error" in data:
                err_bytes = json.dumps({
                    "type": "error",
                    "error": {"type": "api_error", "message": str(data["error"])},
                }).encode()
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
                return

            out_bytes = json.dumps(_to_anthropic(data, msg_id)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out_bytes)))
            self.end_headers()
            self.wfile.write(out_bytes)
            return

        # Streaming
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        conv = _StreamConverter(msg_id)
        self.wfile.write(conv.start())
        self.wfile.flush()

        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode() if isinstance(raw, bytes) else raw
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            out = conv.process(chunk)
            if out:
                self.wfile.write(out)
                self.wfile.flush()

        self.wfile.write(conv.finish())
        self.wfile.flush()

    def do_GET(self):
        # Models endpoint — return a fake entry so the CLI model check passes
        models = {"data": [{"id": "claude-haiku-4-5-20251001", "object": "model"}]}
        body = json.dumps(models).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

def start(api_key: str) -> str:
    """Start the proxy in a daemon thread. Returns the base URL."""
    port = _free_port()
    _Handler.api_key = api_key
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"
