from __future__ import annotations

from datetime import datetime, timedelta, timezone

from referral_pipeline.email_alerts import (
    case_role_emails,
    dispatch_pending_email_alerts,
    queue_email_alert,
    queue_workflow_email_alerts,
)
from referral_pipeline.monitoring.config import load_monitoring_config
from referral_pipeline.monitoring.models import OperationalSnapshot, WorkflowCase
from referral_pipeline.monitoring.service import WorkflowMonitoringService
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


NOW = datetime(2026, 8, 25, 20, 0, tzinfo=timezone.utc)


def test_alert_outbox_deduplicates_and_dispatches_to_test_sink(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    arguments = {
        "store": store,
        "action_id": "cm-assigned",
        "patient_id": "case-1",
        "patient_name": "Test Patient",
        "now": NOW,
        "case_emails": {"assigned_cm": ("cm@example.test",)},
    }

    assert queue_email_alert(**arguments) is True
    assert queue_email_alert(**arguments) is False

    delivered = []
    report = dispatch_pending_email_alerts(
        store=store,
        environ={"GMAIL_ALERT_DEFAULT_TO": "sink@example.test"},
        send_alert=lambda alert, to, cc: delivered.append((alert, to, cc)),
    )

    assert report["sent"] == 1
    assert report["failed"] == []
    assert delivered[0][1:] == (("sink@example.test",), ())
    assert store.pending_email_alerts() == []


def test_missing_live_recipient_stays_failed_and_retryable(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    queue_email_alert(
        store=store,
        action_id="eod-follow-up-cm",
        patient_id="case-1",
        patient_name="Test Patient",
        now=NOW,
    )

    report = dispatch_pending_email_alerts(
        store=store,
        environ={},
        send_alert=lambda *_args: None,
    )

    assert report["sent"] == 0
    assert len(report["failed"]) == 1
    pending = store.pending_email_alerts()
    assert pending[0].status == "failed"
    assert pending[0].attempts == 1
    assert "assigned_cm" in (pending[0].last_error or "")


def test_monday_case_manager_name_resolves_through_roster(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    snapshot = _snapshot(case_manager="Cole Winfield")

    assert case_role_emails(store, snapshot.entity_id, snapshot=snapshot) == {
        "assigned_cm": ("cwinfield@westcoastwound.com",)
    }


def test_invalid_role_routing_fails_durably_without_sending(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    queue_email_alert(
        store=store,
        action_id="confirm-intake-review",
        patient_id="case-1",
        patient_name="Test Patient",
        now=NOW,
    )
    delivered = []

    report = dispatch_pending_email_alerts(
        store=store,
        environ={"GMAIL_ALERT_ROLE_EMAILS": "not-json"},
        send_alert=lambda *args: delivered.append(args),
    )

    assert report["sent"] == 0
    assert len(report["failed"]) == 1
    assert delivered == []
    assert store.pending_email_alerts()[0].status == "failed"


def test_overdue_stage_one_alert_uses_persisted_deadline(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_workflow_case(
        WorkflowCase(
            case_id="case-1",
            source_ref="message:attachment",
            source="outlook-graph",
            patient_label="Test Patient",
            current_stage=1,
            status="processing",
            created_at=NOW - timedelta(hours=1),
            updated_at=NOW - timedelta(hours=1),
            attention_due_at=NOW - timedelta(minutes=15),
        )
    )

    first = queue_workflow_email_alerts(store=store, now=NOW)
    second = queue_workflow_email_alerts(store=store, now=NOW)

    assert first == {"eligible": 1, "queued": 1}
    assert second == {"eligible": 1, "queued": 0}
    assert store.pending_email_alerts()[0].action_id == "confirm-intake-review"


def test_monitor_queues_not_seen_progression(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())
    previous = _snapshot(visit_status="ACT Ready", visit_event_id="visit-0")
    current = _snapshot(visit_status="ATTEMPTED TO SEE THE PATIENT BUT NOT SEEN", visit_event_id="visit-1")

    service.process([previous], now=NOW)
    report = service.process([current], now=NOW + timedelta(minutes=1))

    assert report["email_alerts_queued"] == 1
    assert [alert.action_id for alert in store.pending_email_alerts()] == ["not-seen-week-1"]


def test_monitor_promotes_scheduling_follow_up_to_escalation(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())
    snapshot = _snapshot(
        sent_to_case_manager="Yes",
        due_date="2026-08-24",
        scheduled_status="Not Scheduled",
        scheduling_complete="No",
    )
    after_cutoff = datetime(2026, 8, 26, 2, 0, tzinfo=timezone.utc)

    service.process([snapshot], now=after_cutoff)
    service.process([snapshot], now=after_cutoff + timedelta(days=1))

    assert [alert.action_id for alert in store.pending_email_alerts()] == [
        "eod-follow-up-cm",
        "eod-escalate",
    ]


def test_monitor_queues_provider_referral_on_recorded_send(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    service = WorkflowMonitoringService(store=store, config=load_monitoring_config())
    previous = _snapshot(referral_sent_to_provider="No")
    current = _snapshot(referral_sent_to_provider="Sent")

    service.process([previous], now=NOW)
    report = service.process([current], now=NOW + timedelta(minutes=1))

    assert report["email_alerts_queued"] == 1
    assert store.pending_email_alerts()[0].action_id == "send-referral-provider"


def _snapshot(**updates) -> OperationalSnapshot:
    values = {
        "source": "monday",
        "external_id": "item-1",
        "observed_at": NOW,
        "patient_label": "Test Patient",
        "monday_item_id": "item-1",
        "group": "Active",
        "sent_to_case_manager": "No",
        "visit_status": "ACT Ready",
    }
    values.update(updates)
    return OperationalSnapshot(**values)
