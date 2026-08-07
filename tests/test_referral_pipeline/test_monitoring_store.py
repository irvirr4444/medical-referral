from __future__ import annotations

from datetime import datetime, timezone

from referral_pipeline.monitoring.models import (
    NotificationRecord,
    OperationalSnapshot,
    WorkflowEvent,
    WorkflowException,
    PatientLink,
)
from referral_pipeline.monitoring.sqlite_store import SQLiteWorkflowStore


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def test_sqlite_store_is_idempotent_for_snapshots_events_and_notifications(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    snapshot = OperationalSnapshot(
        source="monday",
        external_id="1",
        observed_at=NOW,
        monday_item_id="1",
        patient_label="Synthetic Patient",
    )
    event = WorkflowEvent(
        event_key="event-1",
        event_type="visit_seen",
        entity_id="monday:1",
        source="monday",
        occurred_at=NOW,
    )
    exception = WorkflowException(
        exception_key="exception-1",
        exception_type="scheduling_exception",
        entity_id="monday:1",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    notification = NotificationRecord(
        notification_key="notification-1",
        exception_key="exception-1",
        recipient="reviewer@example.com",
        subject="Review",
        body="Synthetic exception",
        created_at=NOW,
    )

    assert store.save_snapshot(snapshot) is True
    assert store.save_snapshot(snapshot) is False
    assert store.record_event(event) is True
    assert store.record_event(event) is False
    assert store.upsert_exception(exception) is True
    assert store.upsert_exception(exception) is False
    assert store.enqueue_notification(notification) is True
    assert store.enqueue_notification(notification) is False
    assert len(store.pending_notifications()) == 1

    store.mark_notifications_sent(["notification-1"])
    assert store.pending_notifications() == []
    assert store.status_summary()["snapshots"] == 1
    assert store.status_summary()["unhealthy_components"] == 0


def test_resolving_exception_allows_a_deliberate_reopen(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    exception = WorkflowException(
        exception_key="exception-1",
        exception_type="scheduling_exception",
        entity_id="monday:1",
        first_seen_at=NOW,
        last_seen_at=NOW,
    )
    assert store.upsert_exception(exception) is True
    assert store.resolve_exceptions(
        entity_id="monday:1",
        exception_type="scheduling_exception",
        resolved_at=NOW.isoformat(),
    ) == 1
    assert store.upsert_exception(exception) is True


def test_store_lists_patient_links_and_round_trip_cursor(tmp_path) -> None:
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    store.upsert_patient_link(
        PatientLink(
            entity_id="ref-1",
            monday_item_id="monday-1",
            drk_patient_id="123",
            patient_label="Synthetic Patient",
            updated_at=NOW,
        )
    )
    store.record_cursor("drk_live_rotation", "123")

    assert store.list_patient_links()[0].drk_patient_id == "123"
    assert store.read_cursor("drk_live_rotation") == "123"
