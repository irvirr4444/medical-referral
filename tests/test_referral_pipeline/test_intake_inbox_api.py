from __future__ import annotations

import http.client
import json
import threading
from http import HTTPStatus
from unittest.mock import Mock

from Outlook.mail import InboundPdfMetadata
from referral_pipeline.api.intake_inbox import IntakeInboxFeed
from referral_pipeline.api.intake_inbox import _step_projection
from referral_pipeline.api.server import IntakeApiHandler, _parse_limit, create_server
from referral_pipeline.monitoring.models import WorkflowCase, WorkflowEvent
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.stage_one.identity import source_ref
from referral_pipeline.workflow.service import WorkflowExecutionService
from datetime import datetime, timezone


class _GraphClient:
    def __init__(self) -> None:
        self.calls = 0

    def list_inbox_pdf_metadata(self, *, max_messages: int):
        self.calls += 1
        assert max_messages == 10
        return [
            InboundPdfMetadata(
                message_id="message-1",
                attachment_id="attachment-1",
                filename="referral.pdf",
                received_at="2026-08-12T08:30:00Z",
                subject="New referral",
                sender="sender@example.test",
            )
        ]

    def download_pdf_attachment(self, metadata: InboundPdfMetadata):
        from Outlook.mail import InboundPdfAttachment

        return InboundPdfAttachment(
            source="outlook-graph",
            message_id=metadata.message_id,
            attachment_id=metadata.attachment_id,
            filename=metadata.filename,
            content=b"%PDF-1.4\ntest",
        )


def test_inbox_feed_projects_metadata_without_pdf_content() -> None:
    client = _GraphClient()
    feed = IntakeInboxFeed(lambda: client, cache_ttl_seconds=30, clock=lambda: 10.0)

    first = feed.read(limit=10)
    second = feed.read(limit=10)

    assert client.calls == 1
    assert first["connected"] is True
    assert first["source"] == "testing-infobox"
    assert first["referrals"] == second["referrals"]
    assert first["referrals"][0] == {
        "id": "21f6fcf107129b8e",
        "filename": "referral.pdf",
        "subject": "New referral",
        "sender": "sender@example.test",
        "received_at": "2026-08-12T08:30:00Z",
        "source": "testing-infobox",
        "status": "pending_extraction",
        "case_id": None,
        "steps": {},
        "persistence": "none",
    }
    assert "content" not in first["referrals"][0]

    filename, content = feed.read_pdf(first["referrals"][0]["id"])
    assert filename == "referral.pdf"
    assert content.startswith(b"%PDF-")


def test_cached_mailbox_metadata_refreshes_workflow_projection(tmp_path) -> None:
    client = _GraphClient()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    feed = IntakeInboxFeed(
        lambda: client,
        cache_ttl_seconds=30,
        clock=lambda: 10.0,
        workflow_store=store,
    )
    first = feed.read(limit=10)
    referral_id = first["referrals"][0]["id"]
    now = datetime.now(timezone.utc)
    store.upsert_workflow_case(
        WorkflowCase(
            case_id="case-test",
            source_ref=referral_id,
            source="outlook-graph",
            current_stage=1,
            status="processing",
            created_at=now,
            updated_at=now,
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="monday-check-test",
            event_type="monday_duplicate_checked",
            entity_id="case-test",
            source="monday",
            occurred_at=now,
            details={"status": "no_candidates_found", "write_performed": False},
        )
    )
    second = feed.read(limit=10)

    assert client.calls == 1
    step = second["referrals"][0]["steps"]["check-monday"]
    assert step["summary"] == "No matching Monday.com patient found"
    assert step["details"]["status"] == "No matching patient found"
    assert step["details"]["status_code"] == "no_candidates_found"


def test_partner_contact_projection_hides_graph_message_id() -> None:
    now = datetime.now(timezone.utc)
    steps = _step_projection(
        [
            WorkflowEvent(
                event_key="contact-test",
                event_type="partner_contact_confirmed",
                entity_id="case-test",
                source="outlook",
                occurred_at=now,
                details={
                    "confirmed_by": "intake@example.test",
                    "confirmation_message_id": "graph-message-id",
                    "contact_outcome": "reached",
                },
            )
        ]
    )

    step = steps["confirm-referral-contacted"]
    assert step["summary"] == "Referral partner reached"
    assert step["details"] == {
        "confirmed_by": "intake@example.test",
        "contact_outcome": "Reached",
    }


def test_recovered_case_supersedes_historical_failure_in_operational_feed() -> None:
    started = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    failed = datetime(2026, 8, 14, 9, 2, tzinfo=timezone.utc)
    events = [
        WorkflowEvent(
            event_key="extracted",
            event_type="extraction_completed",
            entity_id="case-test",
            source="extractor",
            occurred_at=started,
            details={"fields": {"patient_name": "Synthetic Patient"}},
        ),
        WorkflowEvent(
            event_key="failed",
            event_type="stage_one_failed",
            entity_id="case-test",
            source="pipeline",
            occurred_at=failed,
            details={"error_code": "SupabaseReviewStoreError"},
        ),
    ]

    retrying = _step_projection(events, case_status="processing")
    recovered = _step_projection(events, case_status="awaiting_partner_contact")

    assert retrying["extract-and-verify"]["status"] == "current"
    assert retrying["extract-and-verify"]["summary"] == "Retrying referral processing"
    assert recovered["extract-and-verify"]["status"] == "done"
    assert recovered["extract-and-verify"]["summary"] == "Referral details extracted"


def test_later_extraction_revision_supersedes_stale_failure() -> None:
    started = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    failed = datetime(2026, 8, 14, 9, 2, tzinfo=timezone.utc)
    recovered = datetime(2026, 8, 14, 9, 4, tzinfo=timezone.utc)
    events = [
        WorkflowEvent(
            event_key="extracted-rev1",
            event_type="extraction_completed",
            entity_id="case-test",
            source="extractor",
            occurred_at=started,
            details={"revision": 1, "fields": {"patient_name": "Synthetic Patient"}},
        ),
        WorkflowEvent(
            event_key="failed-rev1",
            event_type="stage_one_failed",
            entity_id="case-test",
            source="pipeline",
            occurred_at=failed,
            details={"revision": 1, "error_code": "OutlookGraphError"},
        ),
        WorkflowEvent(
            event_key="extracted-rev2",
            event_type="extraction_completed",
            entity_id="case-test",
            source="extractor",
            occurred_at=recovered,
            details={"revision": 2, "fields": {"patient_name": "Synthetic Patient"}},
        ),
    ]
    steps = _step_projection(events, case_status="awaiting_partner_contact")
    assert steps["extract-and-verify"]["status"] == "done"
    assert steps["extract-and-verify"]["details"]["revision"] == 2


def test_case_advanced_to_stage_two_supersedes_stage_one_failure(tmp_path) -> None:
    client = _GraphClient()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    feed = IntakeInboxFeed(lambda: client, workflow_store=store)
    referral_id = source_ref("message-1", "attachment-1")
    now = datetime.now(timezone.utc)
    store.upsert_workflow_case(
        WorkflowCase(
            case_id="case-advanced",
            source_ref=referral_id,
            source="outlook-graph",
            patient_label="Synthetic Patient",
            current_stage=2,
            status="awaiting_assignment",
            created_at=now,
            updated_at=now,
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="extracted-advanced",
            event_type="extraction_completed",
            entity_id="case-advanced",
            source="extractor",
            occurred_at=now,
            details={"fields": {"patient_name": "Synthetic Patient"}},
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="failed-advanced",
            event_type="stage_one_failed",
            entity_id="case-advanced",
            source="pipeline",
            occurred_at=now,
            details={"error_code": "SupabaseReviewStoreError"},
        )
    )

    referral = feed.read(limit=10)["referrals"][0]

    assert referral["status"] == "completed"
    assert referral["steps"]["extract-and-verify"]["status"] == "done"
    assert referral["steps"]["extract-and-verify"]["summary"] == "Referral details extracted"


def test_inbox_api_limit_is_bounded() -> None:
    assert _parse_limit("1") == 1
    assert _parse_limit("25") == 25

    for invalid in ("0", "26", "many"):
        try:
            _parse_limit(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid limit to fail: {invalid}")


def test_api_response_ignores_client_disconnect() -> None:
    handler = object.__new__(IntakeApiHandler)
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler.wfile = Mock()
    handler.wfile.write.side_effect = ConnectionAbortedError(10053, "client disconnected")
    handler.close_connection = False

    handler._send_json(HTTPStatus.OK, {"status": "ok"})

    assert handler.close_connection is True


def test_pdf_response_ignores_client_disconnect() -> None:
    handler = object.__new__(IntakeApiHandler)
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    handler.wfile = Mock()
    handler.wfile.write.side_effect = BrokenPipeError("client disconnected")
    handler.close_connection = False

    handler._send_pdf("referral.pdf", b"%PDF-1.4")

    assert handler.close_connection is True


def test_inbox_api_cannot_bind_publicly_without_authentication() -> None:
    try:
        create_server(host="0.0.0.0", port=0, feed=IntakeInboxFeed(lambda: _GraphClient()))
    except ValueError as error:
        assert "local-only" in str(error)
    else:
        raise AssertionError("Expected public binding to be rejected")


def test_inbox_api_exposes_local_monitor_controls() -> None:
    class FakeMonitor:
        def __init__(self) -> None:
            self.state = "stopped"

        def status(self):
            return {"available": True, "state": self.state, "enabled": self.state == "monitoring"}

        def start(self):
            self.state = "monitoring"
            return self.status()

        def stop(self, *, wait: bool = False):
            assert wait is False
            self.state = "stopped"
            return self.status()

    monitor = FakeMonitor()
    server = create_server(
        host="127.0.0.1",
        port=0,
        feed=IntakeInboxFeed(lambda: _GraphClient()),
        monitor=monitor,  # type: ignore[arg-type]
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/api/intake/monitor")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "stopped"

        connection.request(
            "POST",
            "/api/intake/monitor/start",
            body="{}",
            headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "monitoring"

        connection.request(
            "POST",
            "/api/intake/monitor/stop",
            body="{}",
            headers={"Content-Type": "application/json", "Origin": "https://not-local.example"},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_workflow_api_persists_assignment_and_prepares_handoff(tmp_path) -> None:
    class FakeMonitor:
        def status(self):
            return {"available": True, "state": "stopped", "enabled": False}

        def start(self):
            return self.status()

        def stop(self, *, wait: bool = False):
            return self.status()

    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    now = datetime.now(timezone.utc)
    case = WorkflowCase(
        case_id="case-api",
        source_ref="message:attachment",
        source="outlook-graph",
        patient_label="Synthetic Patient",
        current_stage=1,
        status="completed",
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    store.upsert_workflow_case(case)
    store.record_event(
        WorkflowEvent(
            event_key="contact-api",
            event_type="partner_contact_confirmed",
            entity_id=case.case_id,
            source="outlook",
            occurred_at=now,
            details={"contact_outcome": "reached"},
        )
    )
    store.record_event(
        WorkflowEvent(
            event_key="received-api",
            event_type="referral_received",
            entity_id=case.case_id,
            source="outlook",
            occurred_at=now,
            details={"message_id": "source-message-api"},
        )
    )
    sent: list[dict[str, object]] = []

    class Mailbox:
        def send_reply(self, **kwargs):
            sent.append(kwargs)

    execution = WorkflowExecutionService(
        store,
        case_managers=[{"name": "Case Manager", "email": "manager@example.test"}],
    )
    server = create_server(
        host="127.0.0.1",
        port=0,
        feed=IntakeInboxFeed(lambda: _GraphClient()),
        monitor=FakeMonitor(),  # type: ignore[arg-type]
        workflow_execution=execution,
        handoff_mailbox_factory=lambda: Mailbox(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/api/workflow/assignments")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["items"][0]["status"] == "waiting"

        connection.request(
            "POST",
            f"/api/workflow/assignments/{case.case_id}/confirm",
            body=json.dumps({"case_manager_email": "manager@example.test"}),
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173",
            },
        )
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["status"] == "completed"

        connection.request("GET", "/api/workflow/handoffs")
        response = connection.getresponse()
        handoff = json.loads(response.read())["items"][0]
        assert len(handoff["operations"]) == 3
        assert {item["status"] for item in handoff["operations"]} == {"ready"}

        connection.request(
            "POST",
            f"/api/workflow/handoffs/{case.case_id}/preview",
            body=json.dumps({"operation_type": "create-monday-record"}),
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173",
            },
        )
        preview = json.loads(connection.getresponse().read())
        assert preview["mode"] == "preview"
        assert preview["consumed"] is False
        assert preview["status"] == "ready"

        connection.request(
            "POST",
            f"/api/workflow/handoffs/{case.case_id}/execute",
            body=json.dumps({"operation_type": "create-monday-record", "confirm": True}),
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173",
            },
        )
        denied = connection.getresponse()
        assert denied.status == 409
        assert "confirm_monday_write" in json.loads(denied.read())["error"]

        monday = next(
            item
            for item in store.list_external_operations(case.case_id)
            if item.operation_type == "create-monday-record"
        )
        assert monday.status == "ready"
        assert monday.attempts == 0

        connection.request(
            "POST",
            f"/api/workflow/handoffs/{case.case_id}/execute",
            body=json.dumps(
                {"operation_type": "notify-assigned-case-manager", "confirm": True}
            ),
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:5173",
            },
        )
        notified = connection.getresponse()
        assert notified.status == 200
        assert json.loads(notified.read())["status"] == "succeeded"
        assert sent[0]["source_message_id"] == "source-message-api"
        assert sent[0]["recipient"] == "manager@example.test"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
