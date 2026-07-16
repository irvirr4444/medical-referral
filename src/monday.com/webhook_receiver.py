from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


_LOCK = threading.Lock()
_EVENTS: list[dict[str, Any]] = []


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "MondayWebhookReceiver/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[webhook] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {"raw": raw.decode("utf-8", errors="replace")}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"ok": True})
            return
        if path == "/events":
            with _LOCK:
                events = list(_EVENTS)
            self._send_json(200, {"count": len(events), "events": events})
            return
        if path == "/clear":
            with _LOCK:
                _EVENTS.clear()
            self._send_json(200, {"cleared": True})
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/webhook", "/"}:
            self._send_json(404, {"error": "not_found"})
            return

        body = self._read_json()
        record = {
            "path": path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
        }
        with _LOCK:
            _EVENTS.append(record)

        # Monday webhook verification handshake.
        if isinstance(body, dict) and "challenge" in body:
            self._send_json(200, {"challenge": body["challenge"]})
            return

        self._send_json(200, {"ok": True})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Local Monday.com webhook receiver for API tests.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    print("Routes: POST /webhook  GET /events  GET /clear  GET /health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
