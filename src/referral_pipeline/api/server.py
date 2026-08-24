"""Small read-only server for live operations-console data."""

from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from Outlook.graph import OutlookGraphClient, OutlookGraphConfig, OutlookGraphError
from Outlook.review_mail import OutlookReviewMailbox
from referral_pipeline.api.intake_inbox import IntakeInboxFeed
from referral_pipeline.live_monitor import LiveInboxMonitor, LiveInboxMonitorConfig
from referral_pipeline.monitoring.store import create_live_workflow_store
from referral_pipeline.workflow import WorkflowExecutionService
from referral_pipeline.workflow.execution_cache import WorkflowExecutionCache
from referral_pipeline.workflow.handoff import HandoffExecutionError
from referral_pipeline.workflow.service import WorkflowExecutionError


class IntakeApiServer(ThreadingHTTPServer):
    feed: IntakeInboxFeed
    monitor: LiveInboxMonitor
    default_limit: int
    workflow_execution: WorkflowExecutionService
    workflow_cache: WorkflowExecutionCache
    handoff_mailbox_factory: Callable[[], Any]

    def server_close(self) -> None:
        self.monitor.stop(wait=False)
        self.feed.stop_heartbeat()
        self.workflow_cache.stop_heartbeat()
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
        if parsed.path == "/api/workflow/assignments":
            query = parse_qs(parsed.query)
            limit = _parse_workflow_limit(query.get("limit", ["100"])[0])
            self._send_json(HTTPStatus.OK, self.server.workflow_cache.assignments(limit=limit))
            return
        if parsed.path == "/api/workflow/attention":
            query = parse_qs(parsed.query)
            try:
                limit = _parse_workflow_limit(query.get("limit", ["200"])[0])
                stage = _parse_workflow_stage(query.get("stage", [None])[0])
            except ValueError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return
            from referral_pipeline.workflow.attention import workflow_attention

            self._send_json(
                HTTPStatus.OK,
                workflow_attention(
                    self.server.workflow_execution.store,
                    stage=stage,
                    limit=limit,
                ),
            )
            return
        if parsed.path == "/api/workflow/handoffs":
            query = parse_qs(parsed.query)
            limit = _parse_workflow_limit(query.get("limit", ["100"])[0])
            self._send_json(HTTPStatus.OK, self.server.workflow_cache.handoffs(limit=limit))
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
        except TimeoutError as error:
            self._send_json(
                HTTPStatus.GATEWAY_TIMEOUT,
                {
                    "connected": False,
                    "source": "testing-infobox",
                    "error": str(error),
                    "error_code": "inbox_refresh_timeout",
                    "referrals": [],
                },
            )
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        if parsed.path == "/api/monday/webhook":
            self._handle_monday_webhook(parsed)
            return
        monitor_control = parsed.path in {
            "/api/intake/monitor/start",
            "/api/intake/monitor/stop",
        }
        assignment_confirm = (
            parsed.path.startswith("/api/workflow/assignments/")
            and parsed.path.endswith("/confirm")
        )
        handoff_preview = (
            parsed.path.startswith("/api/workflow/handoffs/")
            and parsed.path.endswith("/preview")
        )
        handoff_execute = (
            parsed.path.startswith("/api/workflow/handoffs/")
            and parsed.path.endswith("/execute")
        )
        if not monitor_control and not assignment_confirm and not handoff_preview and not handoff_execute:
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
        if monitor_control:
            if parsed.path.endswith("/start"):
                payload = self.server.monitor.start()
                if payload.get("enabled"):
                    self.server.feed.start_heartbeat()
                    self.server.workflow_cache.start_heartbeat()
            else:
                payload = self.server.monitor.stop(wait=False)
                self.server.feed.stop_heartbeat()
                self.server.workflow_cache.stop_heartbeat()
            self._send_json(HTTPStatus.OK, payload)
            return

        case_id = parsed.path.split("/")[-2]
        try:
            body = self._read_json_object()
            if handoff_preview or handoff_execute:
                operation_type = str(body.get("operation_type") or "")
                if not operation_type:
                    raise ValueError("operation_type is required")
                if handoff_preview:
                    payload = self.server.workflow_execution.preview_handoff_operation(
                        case_id,
                        operation_type,
                    )
                else:
                    if body.get("confirm") is not True:
                        raise ValueError("handoff execute requires confirm=true")
                    confirm_monday_write = bool(body.get("confirm_monday_write"))
                    if operation_type == "create-monday-record" and not confirm_monday_write:
                        raise ValueError("create-monday-record requires confirm_monday_write=true")
                    mailbox = None
                    if operation_type == "notify-assigned-case-manager":
                        try:
                            mailbox = self.server.handoff_mailbox_factory()
                        except Exception as error:
                            raise HandoffExecutionError(
                                f"case-manager notification mailbox is unavailable: {error}"
                            ) from error
                    payload = self.server.workflow_execution.execute_handoff_operation(
                        case_id,
                        operation_type,
                        execute=True,
                        confirm_monday_write=confirm_monday_write,
                        mailbox=mailbox,
                        operator_retry=bool(body.get("operator_retry")),
                    )
            else:
                payload = self.server.workflow_execution.confirm_assignment(
                    case_id,
                    case_manager_email=str(body.get("case_manager_email") or ""),
                    decided_by=str(body.get("decided_by") or "demo-operator"),
                )
        except (ValueError, WorkflowExecutionError, HandoffExecutionError) as error:
            self._send_json(HTTPStatus.CONFLICT, {"error": str(error)})
            return
        if not handoff_preview:
            # A real write (assignment confirm, or a real handoff execute)
            # just happened -- pull it into the cache now rather than
            # leaving the UI looking at pre-write state until the next
            # heartbeat tick.
            self.server.workflow_cache.refresh_now()
        self._send_json(HTTPStatus.OK, payload)

    def _handle_monday_webhook(self, parsed: Any) -> None:
        # Not gated by _is_local_control_request: Monday calls this from its
        # own servers, so a same-origin check would either block it outright
        # or (worse) pass trivially since server-to-server calls send no
        # Origin header at all. The shared-secret token is the real guard.
        from referral_pipeline.monitoring.config import load_monitoring_config
        from referral_pipeline.monitoring.webhook import (
            WebhookAuthError,
            handle_webhook_payload,
            verify_webhook_token,
        )

        query = parse_qs(parsed.query)
        token = query.get("token", [None])[0]
        try:
            verify_webhook_token(
                token,
                header_token=self.headers.get("X-Monday-Webhook-Token"),
                expected=os.environ.get("MONDAY_WEBHOOK_TOKEN"),
            )
        except WebhookAuthError as error:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": str(error)})
            return
        try:
            body = self._read_json_object()
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        result = handle_webhook_payload(
            body,
            store=self.server.workflow_execution.store,
            config=load_monitoring_config(),
            expected_board_id=os.environ.get("MONDAY_WEBHOOK_BOARD_ID"),
        )
        if result.get("processed"):
            self.server.workflow_cache.refresh_now()
        self._send_json(HTTPStatus.OK, result)

    def _is_local_control_request(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlparse(origin).hostname in {"127.0.0.1", "localhost", "::1"}

    def _read_json_object(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length > 16_384:
            raise ValueError("request body is too large")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[intake-api] {self.address_string()} - {format % args}")

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_body(
            status,
            body,
            content_type="application/json; charset=utf-8",
        )

    def _send_pdf(self, filename: str, content: bytes) -> None:
        safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
        self._send_body(
            HTTPStatus.OK,
            content,
            content_type="application/pdf",
            content_disposition=f'inline; filename="{safe_name}"',
        )

    def _send_body(
        self,
        status: HTTPStatus,
        body: bytes,
        *,
        content_type: str,
        content_disposition: str | None = None,
    ) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if content_disposition:
                self.send_header("Content-Disposition", content_disposition)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # Browser polling aborts superseded requests; this is not an API failure.
            self.close_connection = True


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
    workflow_execution: WorkflowExecutionService | None = None,
    handoff_mailbox_factory: Callable[[], Any] | None = None,
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
    # Supabase runs still need a durable local fallback for non-allowlisted PDFs.
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
    workflow_store = create_live_workflow_store(
        sqlite_path=effective_sqlite_path,
        backend=effective_backend,
    )
    server.workflow_execution = workflow_execution or WorkflowExecutionService(workflow_store)
    server.workflow_cache = WorkflowExecutionCache(server.workflow_execution)
    server.handoff_mailbox_factory = handoff_mailbox_factory or (
        lambda: OutlookReviewMailbox(
            OutlookGraphClient(OutlookGraphConfig.from_environment())
        )
    )
    server.feed = feed or IntakeInboxFeed(
        lambda: OutlookGraphClient(OutlookGraphConfig.from_environment()),
        cache_ttl_seconds=cache_ttl_seconds,
        workflow_store=workflow_store,
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
        if server.monitor.start().get("enabled"):
            server.feed.start_heartbeat()
            server.workflow_cache.start_heartbeat()
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


def _parse_workflow_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise ValueError("limit must be an integer") from error
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    return limit


def _parse_workflow_stage(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        stage = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("stage must be an integer") from error
    if not 1 <= stage <= 7:
        raise ValueError("stage must be between 1 and 7")
    return stage


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
