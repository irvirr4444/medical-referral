from __future__ import annotations

import http.client
import json
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest.mock import Mock

from referral_pipeline.api.server import create_server
from referral_pipeline.monitoring.models import (
    WorkflowCase,
    WorkflowEvent,
    WorkflowException,
    WorkflowWorkItem,
)
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.workflow.attention import workflow_attention
from referral_pipeline.workflow.attention_policy import DEFAULT_WARNING_SECONDS
from referral_pipeline.workflow.deadlines import with_case_deadline, with_work_item_deadline
from referral_pipeline.workflow.service import WorkflowExecutionService


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
MANAGERS = [{"name": "Case Manager One", "email": "one@example.test"}]


def _case(**overrides: object) -> WorkflowCase:
    payload = {
        "case_id": "case-1",
        "source_ref": "message:attachment",
        "source": "outlook-graph",
        "patient_label": "Demo Patient",
        "current_stage": 1,
        "status": "processing",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return WorkflowCase(**payload)  # type: ignore[arg-type]


def _work_item(**overrides: object) -> WorkflowWorkItem:
    payload = {
        "work_item_id": "work-1",
        "case_id": "case-1",
        "stage": 2,
        "step_id": "assign-case-manager",
        "owner_role": "case_manager",
        "status": "waiting",
        "created_at": NOW,
        "updated_at": NOW,
    }
    payload.update(overrides)
    return WorkflowWorkItem(**payload)  # type: ignore[arg-type]


def test_deadline_assignment_sets_and_preserves_case_attention() -> None:
    first = with_case_deadline(_case(), now=NOW)
    assert first.attention_due_at == NOW + timedelta(minutes=15)
    later = with_case_deadline(
        first.model_copy(update={"updated_at": NOW + timedelta(minutes=3)}),
        previous=first,
        now=NOW + timedelta(minutes=3),
    )
    assert later.attention_due_at == first.attention_due_at
    advanced = with_case_deadline(
        first.model_copy(update={"status": "awaiting_partner_contact"}),
        previous=first,
        now=NOW + timedelta(minutes=3),
    )
    assert advanced.attention_due_at == NOW + timedelta(minutes=3) + timedelta(hours=1)


def test_replacement_work_item_gets_a_fresh_deadline() -> None:
    original = with_work_item_deadline(_work_item(), now=NOW)
    replacement = with_work_item_deadline(
        _work_item(work_item_id="work-2"),
        previous=original,
        now=NOW + timedelta(minutes=10),
    )
    assert original.due_at == NOW + timedelta(minutes=30)
    assert replacement.due_at == NOW + timedelta(minutes=40)


def test_completed_work_item_clears_deadline() -> None:
    waiting = with_work_item_deadline(_work_item(), now=NOW)
    completed = with_work_item_deadline(
        waiting.model_copy(update={"status": "completed", "completed_at": NOW}),
        previous=waiting,
        now=NOW,
    )
    assert completed.due_at is None


def test_due_soon_and_overdue_boundaries(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    warning_due = NOW + timedelta(seconds=DEFAULT_WARNING_SECONDS)
    just_outside = NOW + timedelta(seconds=DEFAULT_WARNING_SECONDS + 1)
    store.upsert_workflow_case(
        _case(case_id="soon", source_ref="soon", attention_due_at=warning_due)
    )
    store.upsert_workflow_case(
        _case(case_id="normal", source_ref="normal", attention_due_at=just_outside)
    )
    store.upsert_workflow_case(
        _case(case_id="late", source_ref="late", attention_due_at=NOW)
    )
    payload = workflow_attention(store, now=NOW)
    by_id = {item["signal_id"]: item for item in payload["items"]}
    assert by_id["workflow_case:soon"]["severity"] == "due_soon"
    assert by_id["workflow_case:normal"]["severity"] == "normal"
    assert by_id["workflow_case:late"]["severity"] == "overdue"
    assert by_id["workflow_case:late"]["overdue_seconds"] == 0


def test_completed_records_and_resolved_exceptions_are_excluded(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(
        _case(status="completed", completed_at=NOW, attention_due_at=NOW)
    )
    store.upsert_work_item(
        _work_item(status="completed", completed_at=NOW, due_at=NOW)
    )
    store.upsert_exception(
        WorkflowException(
            exception_key="resolved-1",
            exception_type="stale_schedule",
            entity_id="case-1",
            status="resolved",
            first_seen_at=NOW,
            last_seen_at=NOW,
            resolved_at=NOW,
        )
    )
    payload = workflow_attention(store, now=NOW)
    assert payload["items"] == []
    assert payload["summary"] == {
        "overdue": 0,
        "due_soon": 0,
        "blocked": 0,
        "by_stage": {},
    }


def test_open_exception_projects_as_blocked(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(_case(attention_due_at=NOW + timedelta(hours=2)))
    store.upsert_exception(
        WorkflowException(
            exception_key="open-1",
            exception_type="missing_visit",
            entity_id="case-1",
            status="open",
            first_seen_at=NOW,
            last_seen_at=NOW,
        )
    )
    payload = workflow_attention(store, now=NOW)
    blocked = [item for item in payload["items"] if item["source"] == "exception"]
    assert len(blocked) == 1
    assert blocked[0]["severity"] == "blocked"
    assert blocked[0]["patient_label"] == "Demo Patient"
    assert "details" not in blocked[0]


def test_scheduling_exception_is_placed_on_stage_five_not_case_stage(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(_case(current_stage=3, status="handoff_in_progress"))
    store.upsert_exception(
        WorkflowException(
            exception_key="scheduling:case-1:2026-08-17",
            exception_type="scheduling_exception",
            entity_id="case-1",
            status="open",
            first_seen_at=NOW,
            last_seen_at=NOW,
        )
    )
    payload = workflow_attention(store, now=NOW)
    exceptions = [item for item in payload["items"] if item["source"] == "exception"]
    assert len(exceptions) == 1
    assert exceptions[0]["stage"] == 5
    assert exceptions[0]["step_id"] == "check-scheduling-status"

    filtered = workflow_attention(store, now=NOW, stage=5)
    assert len(filtered["items"]) == 1
    filtered_out = workflow_attention(store, now=NOW, stage=3)
    assert filtered_out["items"] == []


def test_stage_aggregation_and_stable_sorting(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(
        _case(case_id="case-a", source_ref="a", attention_due_at=NOW - timedelta(minutes=5))
    )
    store.upsert_workflow_case(
        _case(
            case_id="case-b",
            source_ref="b",
            status="needs_attention",
            attention_due_at=NOW + timedelta(hours=1),
        )
    )
    store.upsert_work_item(
        _work_item(
            work_item_id="work-blocked",
            case_id="case-b",
            status="blocked",
            due_at=NOW + timedelta(hours=1),
        )
    )
    store.upsert_work_item(
        _work_item(
            work_item_id="work-soon",
            case_id="case-a",
            due_at=NOW + timedelta(minutes=5),
        )
    )
    payload = workflow_attention(store, now=NOW)
    severities = [item["severity"] for item in payload["items"]]
    assert severities[0] == "blocked"
    assert "overdue" in severities
    assert payload["summary"]["by_stage"]["2"]["blocked"] == 1
    assert payload["summary"]["by_stage"]["1"]["overdue"] == 1
    ranked = sorted(
        payload["items"],
        key=lambda item: (
            {"blocked": 0, "overdue": 1, "due_soon": 2, "normal": 3}[item["severity"]],
            item["due_at"] or "9999",
            item["signal_id"],
        ),
    )
    assert [item["signal_id"] for item in payload["items"]] == [
        item["signal_id"] for item in ranked
    ]


def test_assignment_service_sets_work_item_due_at(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(_case(status="completed", completed_at=NOW))
    store.record_event(
        WorkflowEvent(
            event_key="contact-confirmed",
            event_type="partner_contact_confirmed",
            entity_id="case-1",
            source="outlook",
            occurred_at=NOW,
            details={"contact_outcome": "reached"},
        )
    )
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.reconcile_stage_one_completions()
    item = store.list_work_items(case_id="case-1")[0]
    assert item.due_at is not None
    service.confirm_assignment("case-1", case_manager_email="one@example.test", decided_by="op")
    completed = store.work_item(item.work_item_id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.due_at is None


def test_attention_endpoint_is_read_only(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(_case(attention_due_at=NOW - timedelta(minutes=1)))
    upserts: list[str] = []
    original_case = store.upsert_workflow_case
    original_item = store.upsert_work_item

    def track_case(case: WorkflowCase) -> WorkflowCase:
        upserts.append("case")
        return original_case(case)

    def track_item(item: WorkflowWorkItem) -> WorkflowWorkItem:
        upserts.append("item")
        return original_item(item)

    store.upsert_workflow_case = track_case  # type: ignore[method-assign]
    store.upsert_work_item = track_item  # type: ignore[method-assign]
    server = create_server(
        host="127.0.0.1",
        port=0,
        workflow_execution=WorkflowExecutionService(store, case_managers=MANAGERS),
        feed=Mock(),
        monitor=Mock(),
        handoff_mailbox_factory=lambda: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        conn.request("GET", "/api/workflow/attention")
        response = conn.getresponse()
        body = json.loads(response.read())
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
    assert response.status == HTTPStatus.OK
    assert upserts == []
    assert body["items"]
    assert body["summary"]["overdue"] >= 1
