"""Local read-only HTTP API for live Monday + DRK patient lookup."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from patient_profile.lookup import PatientLookupResult, lookup_patient

lookup_patient_fn = lookup_patient


def handle_get(path: str, query: dict[str, str]) -> tuple[int, dict[str, Any]]:
    if path == "/health":
        return 200, {"ok": True}
    prefix = "/api/patient/"
    if not path.startswith(prefix) or path.rstrip("/") == "/api/patient":
        return 404, {"error": "not_found"}
    slug = unquote(path[len(prefix) :].split("/", 1)[0])
    if not slug or "/" in slug:
        return 404, {"error": "not_found"}
    source = query.get("source", "all")
    if source not in {"all", "monday", "drk"}:
        return 400, {"error": "invalid_source"}
    result = lookup_patient_fn(slug, source=source)  # type: ignore[arg-type]
    if isinstance(result, PatientLookupResult):
        return result.status, result.body
    return 500, {"error": "invalid_lookup_result"}


class PatientProfileHandler(BaseHTTPRequestHandler):
    server_version = "PatientProfileAPI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[patient-profile] {self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items() if values}
        status, body = handle_get(parsed.path, query)
        self._send_json(status, body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Monday + DRK patient profile API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), PatientProfileHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    print("Routes: GET /api/patient/:slug  GET /health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
