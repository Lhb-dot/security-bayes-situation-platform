"""Small local OpenAI-compatible mock for integration testing.

Usage:
    python scripts/mock_openai_server.py --port 8765

The endpoint accepts both ``/v1/chat/completions`` and
``/chat/completions``.  It intentionally never logs request headers or body so
that it is safe to use with representative test fixtures.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockOpenAIHandler(BaseHTTPRequestHandler):
    server_version = "LocalOpenAICompatibleMock/1.0"

    def log_message(self, _format: str, *_args) -> None:
        # Do not print request URLs, headers, prompts, or sample data.
        return

    def _json_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path not in {"/v1/chat/completions", "/chat/completions"}:
            self._send_json(404, {"error": {"message": "not found", "type": "not_found"}})
            return

        payload = self._json_body()
        mode = getattr(self.server, "response_mode", "success")
        if mode == "rate_limited":
            self._send_json(429, {"error": {"message": "rate limited", "type": "rate_limit"}})
            return
        if mode == "authentication_failed":
            self._send_json(401, {"error": {"message": "authentication failed", "type": "authentication_error"}})
            return
        if mode == "model_not_found":
            self._send_json(404, {"error": {"message": "model not found", "type": "invalid_request_error"}})
            return

        content = "### 研判结论\nMock 服务已生成解释。"
        if mode == "empty":
            content = ""
        if payload.get("stream"):
            self._send_stream(content)
            return
        self._send_json(200, {
            "id": "mock-completion",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        })

    def _send_stream(self, content: str) -> None:
        chunks = [content[index:index + 12] for index in range(0, len(content), 12)]
        body = "".join(
            "data: " + json.dumps({"choices": [{"delta": {"content": chunk}}]}, ensure_ascii=False) + "\n\n"
            for chunk in chunks
        ) + "data: [DONE]\n\n"
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def serve(host: str = "127.0.0.1", port: int = 8765, mode: str = "success") -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MockOpenAIHandler)
    server.response_mode = mode
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Local OpenAI-compatible mock server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--mode",
        choices=("success", "empty", "rate_limited", "authentication_failed", "model_not_found"),
        default="success",
    )
    args = parser.parse_args()
    server = serve(args.host, args.port, args.mode)
    print(f"Mock OpenAI-compatible server listening on {args.host}:{args.port} ({args.mode})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
