"""Minimal public HTTP service for Monday webhook deliveries.

This is intentionally separate from the local operator/UI API. A public
webhook process should expose only health and the authenticated Monday route;
it should not make the local control endpoints internet-facing.
"""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from referral_pipeline.integrations.monday.webhook_auth import (
    WebhookAuthError,
    verify_webhook_token,
)
from referral_pipeline.integrations.monday.webhook_processor import process_webhook_payload
from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.store import create_workflow_store


class MondayWebhookServer(ThreadingHTTPServer):
    daemon_threads = True


class MondayWebhookHandler(BaseHTTPRequestHandler):
    server: MondayWebhookServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlparse(self.path).path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "service": "monday-webhook"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlparse(self.path).path != "/api/monday/webhook":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        query = parse_qs(urlparse(self.path).query)
        try:
            verify_webhook_token(
                query.get("token", [None])[0],
                header_token=self.headers.get("X-Monday-Webhook-Token"),
                expected=os.getenv("MONDAY_WEBHOOK_TOKEN"),
            )
            payload = self._read_json()
            result = process_webhook_payload(
                payload,
                store=self.server.store,  # type: ignore[attr-defined]
                config=load_monitoring_config(),
                expected_board_id=os.getenv("MONDAY_WEBHOOK_BOARD_ID"),
            )
        except WebhookAuthError as error:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": str(error)})
            return
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        except Exception as error:  # noqa: BLE001 - return a retryable 5xx to Monday
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "webhook_processing_failed"})
            self.log_error("webhook processing failed: %s", error)
            return
        self._send_json(HTTPStatus.OK, result)

    def log_message(self, _format: str, *_args: object) -> None:
        # Keep request logs free of URLs, query tokens, and request bodies.
        # BaseHTTPRequestHandler treats its first argument as a %-format
        # string, so pass a real placeholder rather than an empty argument
        # tuple. This method is called for both successful and error replies.
        super().log_message("%s", "monday webhook request")

    def _read_json(self) -> dict[str, object]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            raise ValueError("application_json_required")
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 16_384:
            raise ValueError("request_body_size_invalid")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid_json") from error
        if not isinstance(payload, dict):
            raise ValueError("json_object_required")
        return payload

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_webhook_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    database_backend: str | None = None,
    sqlite_path: str | Path | None = None,
) -> MondayWebhookServer:
    load_dotenv()
    backend = database_backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite"
    data_root = Path(os.getenv("INTAKE_DATA_ROOT") or "tmp/intake-service")
    store = create_workflow_store(
        backend=backend,
        sqlite_path=sqlite_path or os.getenv("WORKFLOW_SQLITE_PATH") or data_root / "workflow-monitor.sqlite",
    )
    server = MondayWebhookServer((host, port), MondayWebhookHandler)
    server.store = store  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the authenticated Monday webhook endpoint.")
    parser.add_argument("--host", default=os.getenv("WEBHOOK_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    parser.add_argument("--database-backend", default=None)
    parser.add_argument("--sqlite-path", type=Path, default=None)
    args = parser.parse_args(argv)
    server = create_webhook_server(
        host=args.host,
        port=args.port,
        database_backend=args.database_backend,
        sqlite_path=args.sqlite_path,
    )
    print(f"[monday-webhook] listening on {args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
