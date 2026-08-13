from __future__ import annotations

from datetime import datetime, timezone

import pytest

from referral_pipeline.monitoring.models import WorkflowCase, WorkflowEvent
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore
from referral_pipeline.workflow.service import WorkflowExecutionError, WorkflowExecutionService


NOW = datetime(2026, 8, 13, tzinfo=timezone.utc)
MANAGERS = [
    {"name": "Case Manager One", "email": "one@example.test"},
    {"name": "Case Manager Two", "email": "two@example.test"},
]


def _completed_stage_one(store: SQLiteWorkflowStore, *, outcome: str = "reached") -> WorkflowCase:
    case = WorkflowCase(
        case_id="case-synthetic",
        source_ref="message:attachment",
        source="outlook-graph",
        patient_label="Synthetic Patient",
        current_stage=1,
        status="completed",
        created_at=NOW,
        updated_at=NOW,
        completed_at=NOW,
    )
    store.upsert_workflow_case(case)
    store.record_event(
        WorkflowEvent(
            event_key="contact-confirmed",
            event_type="partner_contact_confirmed",
            entity_id=case.case_id,
            source="outlook",
            occurred_at=NOW,
            details={"contact_outcome": outcome},
        )
    )
    return case


def test_reconcile_creates_human_assignment_without_fake_recommendation(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)

    assert service.reconcile_stage_one_completions() == 1
    assert service.reconcile_stage_one_completions() == 0

    payload = service.assignments()
    item = payload["items"][0]
    assert item["patient_label"] == "Synthetic Patient"
    assert item["status"] == "waiting"
    assert item["recommended_assignee"] is None
    assert payload["recommendation_available"] is False


def test_confirm_assignment_is_idempotent_and_prepares_handoff(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store)
    service = WorkflowExecutionService(store, case_managers=MANAGERS)
    service.reconcile_stage_one_completions()

    first = service.confirm_assignment(
        case.case_id,
        case_manager_email="one@example.test",
        decided_by="demo-operator",
    )
    second = service.confirm_assignment(
        case.case_id,
        case_manager_email="one@example.test",
        decided_by="demo-operator",
    )

    assert first["status"] == second["status"] == "completed"
    assert first["assigned_case_manager"]["name"] == "Case Manager One"
    assert len(store.list_decisions(case.case_id)) == 1
    assert {operation.operation_type for operation in store.list_external_operations(case.case_id)} == {
        "notify-assigned-case-manager",
        "create-monday-record",
        "prefill-drk-chart",
    }
    updated = store.workflow_case(case.case_id)
    assert updated is not None
    assert updated.current_stage == 3
    assert updated.status == "awaiting_handoff"
    assert updated.completed_at is None

    with pytest.raises(WorkflowExecutionError, match="another case manager"):
        service.confirm_assignment(
            case.case_id,
            case_manager_email="two@example.test",
            decided_by="demo-operator",
        )


def test_unreached_partner_stays_with_intake_team(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    case = _completed_stage_one(store, outcome="not_reached")
    service = WorkflowExecutionService(store, case_managers=MANAGERS)

    service.reconcile_stage_one_completions()
    item = service.assignments()["items"][0]

    assert item["owner_role"] == "intake_team"
    assert item["status"] == "blocked"
    assert item["assigned_to"] == "WCW Intake Team"
    with pytest.raises(WorkflowExecutionError, match="intake-team follow-up"):
        service.confirm_assignment(
            case.case_id,
            case_manager_email="one@example.test",
            decided_by="demo-operator",
        )
