"""Small read-only server for live operations-console data."""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig, OutlookGraphError
from referral_pipeline.api.intake_inbox import IntakeInboxFeed
from referral_pipeline.live_monitor import LiveInboxMonitor, LiveInboxMonitorConfig
from referral_pipeline.monitoring.store import create_workflow_store


class IntakeApiServer(ThreadingHTTPServer):
    feed: IntakeInboxFeed
    monitor: LiveInboxMonitor
    default_limit: int

    def server_close(self) -> None:
        self.monitor.stop(wait=False)
        super().server_close()


class IntakeApiHandler(BaseHTTPRequestHandler):
    server: IntakeApiServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path == "/api/intake/monitor":
            self._send_json(HTTPStatus.OK, self.server.monitor.status())
            return
        if parsed.path.startswith("/api/intake/inbox/pdf/"):
            referral_id = parsed.path.rsplit("/", 1)[-1]
            try:
                filename, content = self.server.feed.read_pdf(referral_id)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "pdf_not_found"})
                return
            except OutlookGraphError as error:
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "error": "The PDF could not be downloaded from the testing infobox.",
                        "error_code": f"graph_{error.status_code or 'unavailable'}",
                    },
                )
                return
            self._send_pdf(filename, content)
            return
        if parsed.path.startswith("/api/intake/referrals/") and parsed.path.endswith("/timeline"):
            referral_id = parsed.path.split("/")[-2]
            try:
                self._send_json(HTTPStatus.OK, self.server.feed.read_timeline(referral_id))
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "referral_timeline_not_found"})
            return
        if parsed.path == "/api/intake/referrals":
            query = parse_qs(parsed.query)
            limit = _parse_limit(query.get("limit", [str(self.server.default_limit)])[0])
            self._send_json(HTTPStatus.OK, self.server.feed.list_cases(limit=limit))
            return
        if parsed.path != "/api/intake/inbox":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            query = parse_qs(parsed.query)
            limit = _parse_limit(query.get("limit", [str(self.server.default_limit)])[0])
            force = query.get("refresh", ["0"])[0].casefold() in {"1", "true", "yes"}
            self._send_json(HTTPStatus.OK, self.server.feed.read(limit=limit, force=force))
        except OutlookGraphError as error:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "connected": False,
                    "source": "testing-infobox",
                    "error": "Microsoft Graph could not read the testing infobox.",
                    "error_code": f"graph_{error.status_code or 'unavailable'}",
                    "referrals": [],
                },
            )
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/intake/monitor/start", "/api/intake/monitor/stop"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._is_local_control_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "local_control_only"})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": "application_json_required"},
            )
            return
        if parsed.path.endswith("/start"):
            payload = self.server.monitor.start()
        else:
            payload = self.server.monitor.stop(wait=False)
        self._send_json(HTTPStatus.OK, payload)

    def _is_local_control_request(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlparse(origin).hostname in {"127.0.0.1", "localhost", "::1"}

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[intake-api] {self.address_string()} - {format % args}")

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_pdf(self, filename: str, content: bytes) -> None:
        safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


def create_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    max_messages: int = 1,
    cache_ttl_seconds: int = 30,
    workflow_database_backend: str | None = None,
    workflow_sqlite_path: str | Path | None = None,
    feed: IntakeInboxFeed | None = None,
    monitor: LiveInboxMonitor | None = None,
    data_root: str | Path = Path("tmp") / "intake-service",
    poll_interval_seconds: int = 60,
    retry_interval_seconds: int = 60,
    approval_interval_seconds: int = 30,
    max_retry_jobs: int = 10,
    max_approval_messages: int = 100,
    partner_acknowledgement: bool = False,
    stage_one_drk_check: bool = False,
    review_recipient: str | None = None,
) -> IntakeApiServer:
    load_dotenv()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "The testing-infobox API is local-only until frontend authentication is implemented."
        )
    effective_data_root = Path(data_root)
    effective_backend = (
        workflow_database_backend or os.getenv("WORKFLOW_DATABASE_BACKEND") or "sqlite"
    ).strip().casefold()
    effective_sqlite_path = None
    if effective_backend == "sqlite":
        effective_sqlite_path = Path(
            workflow_sqlite_path
            or os.getenv("WORKFLOW_SQLITE_PATH")
            or effective_data_root / "workflow-monitor.sqlite"
        )
    server = IntakeApiServer((host, port), IntakeApiHandler)
    server.default_limit = min(max(max_messages, 1), 25)
    server.monitor = monitor or LiveInboxMonitor(
        LiveInboxMonitorConfig(
            data_root=effective_data_root,
            poll_interval_seconds=poll_interval_seconds,
            retry_interval_seconds=retry_interval_seconds,
            approval_interval_seconds=approval_interval_seconds,
            max_messages=server.default_limit,
            max_retry_jobs=max_retry_jobs,
            max_approval_messages=max_approval_messages,
            partner_acknowledgement=partner_acknowledgement,
            stage_one_drk_check=stage_one_drk_check,
            workflow_database_backend=effective_backend,
            workflow_sqlite_path=effective_sqlite_path,
            review_recipient=review_recipient or os.getenv("REVIEW_RECIPIENT_EMAIL"),
        )
    )
    server.feed = feed or IntakeInboxFeed(
        lambda: OutlookGraphClient(OutlookGraphConfig.from_environment()),
        cache_ttl_seconds=cache_ttl_seconds,
        workflow_store=create_workflow_store(
            backend=effective_backend,
            sqlite_path=effective_sqlite_path,
        ),
    )
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve local Referral Intake data and testing monitor controls."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--max-messages", type=int, default=1)
    parser.add_argument("--cache-ttl-seconds", type=int, default=30)
    parser.add_argument("--workflow-database-backend", choices=("sqlite", "supabase"))
    parser.add_argument("--workflow-sqlite-path", type=Path)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(os.getenv("INTAKE_DATA_ROOT", "tmp/intake-service")),
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=int(os.getenv("INTAKE_POLL_INTERVAL_SECONDS", "60")),
    )
    parser.add_argument(
        "--retry-interval-seconds",
        type=int,
        default=int(os.getenv("INTAKE_RETRY_INTERVAL_SECONDS", "60")),
    )
    parser.add_argument(
        "--approval-interval-seconds",
        type=int,
        default=int(os.getenv("INTAKE_APPROVAL_INTERVAL_SECONDS", "30")),
    )
    parser.add_argument("--max-retry-jobs", type=int, default=10)
    parser.add_argument("--max-approval-messages", type=int, default=100)
    parser.add_argument("--review-recipient", default=os.getenv("REVIEW_RECIPIENT_EMAIL"))
    parser.add_argument(
        "--partner-acknowledgement",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_PARTNER_ACKNOWLEDGEMENT_ENABLED"),
    )
    parser.add_argument(
        "--stage-one-drk-check",
        action=argparse.BooleanOptionalAction,
        default=_env_flag("INTAKE_STAGE_ONE_DRK_CHECK_ENABLED"),
    )
    parser.add_argument(
        "--start-monitor",
        action="store_true",
        help="Start live polling immediately; otherwise use the Stage 1 UI control.",
    )
    args = parser.parse_args(argv)
    server = create_server(
        host=args.host,
        port=args.port,
        max_messages=args.max_messages,
        cache_ttl_seconds=args.cache_ttl_seconds,
        workflow_database_backend=args.workflow_database_backend,
        workflow_sqlite_path=args.workflow_sqlite_path,
        data_root=args.data_root,
        poll_interval_seconds=args.poll_interval_seconds,
        retry_interval_seconds=args.retry_interval_seconds,
        approval_interval_seconds=args.approval_interval_seconds,
        max_retry_jobs=args.max_retry_jobs,
        max_approval_messages=args.max_approval_messages,
        partner_acknowledgement=args.partner_acknowledgement,
        stage_one_drk_check=args.stage_one_drk_check,
        review_recipient=args.review_recipient,
    )
    if args.start_monitor:
        server.monitor.start()
    print(f"[intake-api] Listening on http://{args.host}:{server.server_port}")
    print(
        "[intake-api] GET /api/intake/inbox  GET /api/intake/monitor  "
        "POST /api/intake/monitor/start|stop  GET /health"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[intake-api] Stopped")
    finally:
        server.server_close()
    return 0


def _parse_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise ValueError("limit must be an integer") from error
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    return limit


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
