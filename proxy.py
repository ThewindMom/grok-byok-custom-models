#!/usr/bin/env python3
"""Local OpenAI-compatible proxy for Grok CLI custom BYOK models.

Rewrites Grok's built-in model id to your configured upstream model, removes
fields some OpenAI-compatible providers reject, and preserves SSE streaming for
Grok's interactive TUI.
"""

import json
import os
import socketserver
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TARGET = os.environ.get("GROK_BYOK_BASE_URL", "https://api.fireworks.ai/inference/v1").rstrip("/")
MODEL = os.environ.get("GROK_BYOK_MODEL", "accounts/fireworks/routers/kimi-k2p6-turbo")
SOURCE_MODEL = os.environ.get("GROK_BYOK_SOURCE_MODEL", "grok-build")
LOG = os.environ.get("GROK_BYOK_PROXY_LOG", "0") not in ("", "0", "false", "False")


def scrub_schema(obj):
    """Remove null values recursively; many providers reject nulls in schemas."""
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if value is None:
                del obj[key]
            elif isinstance(value, list) and None in value:
                obj[key] = [item for item in value if item is not None]
                scrub_schema(obj[key])
            else:
                scrub_schema(value)
    elif isinstance(obj, list):
        for item in obj:
            scrub_schema(item)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    allow_reuse_address = True

    def log_message(self, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def forward(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        wants_stream = False

        if body:
            try:
                payload = json.loads(body)
                if isinstance(payload, dict):
                    wants_stream = bool(payload.get("stream"))
                    if payload.get("model") == SOURCE_MODEL:
                        payload["model"] = MODEL
                    for message in payload.get("messages", []):
                        message.pop("model_id", None)
                    if "tools" in payload:
                        scrub_schema(payload["tools"])
                body = json.dumps(payload).encode()
            except Exception as exc:
                if LOG:
                    print(f"rewrite failed: {exc}", file=sys.stderr, flush=True)

        request = Request(f"{TARGET}{self.path}", data=body if body else None, method=method)
        request.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

        for header, value in self.headers.items():
            if header.lower() not in ("host", "content-length", "transfer-encoding", "user-agent", "accept-encoding"):
                request.add_header(header, value)

        try:
            with urlopen(request, timeout=120) as response:
                is_sse = "text/event-stream" in (response.headers.get("Content-Type") or "")
                if wants_stream or is_sse:
                    self.send_response(response.status)
                    self.copy_headers(response.headers, include_content_length=False)
                    self.end_headers()
                    self.stream_response(response)
                else:
                    response_body = response.read()
                    self.send_response(response.status)
                    self.copy_headers(response.headers, include_content_length=False)
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                    self.wfile.flush()
        except HTTPError as exc:
            error_body = exc.read()
            self.send_response(exc.code)
            self.copy_headers(exc.headers, include_content_length=False)
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)

    def copy_headers(self, headers, include_content_length):
        blocked = {"transfer-encoding", "connection", "keep-alive"}
        if not include_content_length:
            blocked.add("content-length")
        for header, value in headers.items():
            if header.lower() not in blocked:
                self.send_header(header, value)
        self.send_header("Connection", "close")

    def stream_response(self, response):
        total = 0
        for chunk in response:
            if not chunk:
                continue
            total += len(chunk)
            try:
                self.wfile.write(chunk)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break
        if LOG:
            print(f"[{time.time()}] streamed {total} bytes", file=sys.stderr, flush=True)

    do_POST = lambda self: self.forward("POST")
    do_GET = lambda self: self.forward("GET")
    do_PUT = lambda self: self.forward("PUT")
    do_DELETE = lambda self: self.forward("DELETE")
    do_PATCH = lambda self: self.forward("PATCH")
    do_HEAD = lambda self: self.forward("HEAD")


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("GROK_BYOK_PORT", "8795"))
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as server:
        print(f"[grok-byok] http://127.0.0.1:{port} -> {TARGET} ({MODEL})", file=sys.stderr, flush=True)
        server.serve_forever()
